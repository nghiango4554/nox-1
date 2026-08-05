"""Routes: Posts + Calendar + Library + Media — 22 endpoint.

⚠️ Test KHÔNG được gọi /posts/<id>/publish hay /posts/<id>/schedule —
sẽ POST FB thật. Chỉ test draft + upload + calendar load.

`register_runtime(app, sched)` đăng kèm template context (POST_TYPES/STATUSES)
+ scheduler job auto_post_due — gọi từ app.py __main__.

Dep:
- db (list_posts/get_post/create_post/update_post/delete_post/stats/activity_log/activity_recent)
- fb_client (post_to_page / post_multi_to_page / post_url / page_info)
- local_config (LIBRARY_ROOT path)
"""

import json
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    render_template, request, jsonify,
    redirect, url_for, flash, send_from_directory,
)
from werkzeug.utils import secure_filename

import db
import fb_client
import local_config as _lcfg


# ─────────────────────── CONSTANTS ───────────────────────────────

POST_TYPES = [
    ("product", "🔥 SP đẩy số"),
    ("new_product", "🔥 Sản phẩm mới"),
    ("meme", "😂 Meme"),
    ("news", "🚨 Tin tức"),
    ("handover", "🖥️ Bàn giao PC"),
    ("fact", "🧠 Fact PC"),
]

POST_STATUSES = [
    ("draft", "📝 Draft"),
    ("ready", "✅ Ready"),
    ("approved", "👍 Approved"),
    ("scheduled", "⏰ Scheduled"),
    ("posted", "🎉 Posted"),
    ("skipped", "⏭️ Skipped"),
]

DOW_VI = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
DOW_VI_LONG = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]

ALLOWED_EXT = {"jpg", "jpeg", "png", "gif", "webp", "mp4"}
LIBRARY_ROOT = Path(_lcfg.get("LIBRARY_ROOT", r"C:\Users\NGHIANGO\Desktop\Sintech\FB-Library"))
UPLOAD_DIR = LIBRARY_ROOT / "_inbox"
LIBRARY_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# ─────────────────────── HELPERS ─────────────────────────────────

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def post_images(post: dict) -> list:
    """Get list of image filenames for a post — prefers `images` JSON, falls back to legacy image_path."""
    raw = (post or {}).get("images")
    if raw:
        try:
            arr = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(arr, list):
                return [s for s in arr if isinstance(s, str) and s]
        except (ValueError, TypeError):
            pass
    legacy = (post or {}).get("image_path")
    return [legacy] if legacy else []


def _resolve_image_file(fn: str):
    """Tìm file ảnh: ưu tiên UPLOAD_DIR (_inbox), fallback search toàn FB-Library
    (case em đã move file sang subfolder category code SP)."""
    p = UPLOAD_DIR / fn
    if p.exists():
        return p
    if LIBRARY_ROOT.exists():
        for found in LIBRARY_ROOT.rglob(fn):
            if found.is_file():
                return found
    return None


def post_image_paths(post: dict) -> list:
    """Resolve filenames into absolute file paths (skip missing).
    Tự động fallback search toàn FB-Library nếu file đã move sang subfolder."""
    out = []
    for fn in post_images(post):
        p = _resolve_image_file(fn)
        if p:
            out.append(str(p))
    return out


def _sanitize_folder_name(text: str, max_len: int = 110) -> str:
    """Loại bỏ ký tự cấm trong tên folder Windows: < > : " / \\ | ? *
    Windows tự strip trailing space/dot → cần strip cả sau khi cắt."""
    if not text:
        return ""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text)
    s = re.sub(r"\s+", " ", s).strip(" .")
    s = s[:max_len]
    return s.rstrip(" .")


def _post_title_short(post: dict, max_len: int = 50) -> str:
    """Lấy title ngắn từ dòng đầu caption (max 50 chars để chừa chỗ cho code+date)."""
    cap = (post.get("caption") or "").strip()
    if not cap:
        return "(no caption)"
    first_line = cap.split("\n")[0].strip()
    s = re.sub(r"\s+", " ", first_line)[:max_len].rstrip(" -.")
    return s or "(no caption)"


def _post_folder_name(post: dict) -> str:
    """Folder name = '<code> - <title 50ch> - <YYYY-MM-DD>'.
    Title cắt 50 char + sanitize riêng để giữ nguyên code + date đầy đủ."""
    code = (post.get("code") or f"POST{post.get('id', '')}")[:12]
    title = _sanitize_folder_name(_post_title_short(post), max_len=50)
    date_str = post.get("scheduled_date") or (post.get("created_at") or "")[:10]
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    parts = [str(p) for p in (code, title, date_str) if p]
    return _sanitize_folder_name(" - ".join(parts), max_len=110)


def _post_folder_path(post: dict) -> Path:
    return LIBRARY_ROOT / _post_folder_name(post)


def _ensure_post_folder(post: dict) -> Path:
    folder = _post_folder_path(post)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_upload(file_storage, post: dict = None):
    """Save 1 file. Nếu có `post`, lưu vào folder bài đó; nếu không, vào _inbox."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    target_dir = _ensure_post_folder(post) if post else UPLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    safe = secure_filename(file_storage.filename)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{stamp}_{safe}"
    path = target_dir / fname
    file_storage.save(path)
    return fname


def _move_inbox_files_to_post(post: dict, filenames: list):
    """Sau khi save bài mới, move các ảnh đã upload tạm trong _inbox sang folder bài."""
    if not filenames:
        return
    folder = _ensure_post_folder(post)
    for fn in filenames:
        src = UPLOAD_DIR / fn
        if src.exists() and src.is_file():
            dst = folder / fn
            if not dst.exists():
                try:
                    src.rename(dst)
                except OSError:
                    shutil.move(str(src), str(dst))


def _day_meta(d: date, today: date):
    return {
        "date": d.isoformat(),
        "dow": DOW_VI[d.weekday()],
        "dow_long": DOW_VI_LONG[d.weekday()],
        "dnum": d.day,
        "month": d.month,
        "is_today": d == today,
        "is_past": d < today,
    }


_FB_CODE_RE = re.compile(r"fb\d{4}", re.IGNORECASE)


def _detect_image_mismatches(post_code: str, filenames: list) -> list:
    """Return list of {filename, found_code} for images whose filename contains a FB-code different from post_code."""
    if not post_code:
        return []
    target = post_code.lower()
    out = []
    for fn in filenames or []:
        m = _FB_CODE_RE.search(fn or "")
        if m and m.group(0).lower() != target:
            out.append({"filename": fn, "found_code": m.group(0).upper()})
    return out


def _safe_lib_path(category: str, filename: str = "") -> Path | None:
    """Resolve category[/filename] under LIBRARY_ROOT, refuse path escape."""
    if not category:
        return None
    target = (LIBRARY_ROOT / category / filename).resolve()
    try:
        target.relative_to(LIBRARY_ROOT.resolve())
    except ValueError:
        return None
    return target


# ─────────────────────── POSTS LIST + CALENDAR ───────────────────

def posts_page():
    """DANH SÁCH bài (không phải lịch — lịch đã có tab riêng /calendar).

    Học Meta: tab trạng thái ngang, bảng có ảnh + sắp xếp + lọc khoảng thời gian.
    Query: status=… · type=… · range=all|7|30|90 · q=…
    """
    today = date.today()
    f_status = request.args.get("status") or None
    f_type = request.args.get("type") or None
    f_range = request.args.get("range") or "all"
    q = (request.args.get("q") or "").strip().lower()

    kw = {"limit": 2000}
    if f_range in ("7", "30", "90"):
        kw["date_from"] = (today - timedelta(days=int(f_range))).isoformat()
        kw["date_to"] = (today + timedelta(days=int(f_range))).isoformat()
    if f_status:
        kw["status"] = f_status
    if f_type:
        kw["ptype"] = f_type
    posts = db.list_posts(**kw)

    # đếm theo trạng thái TRƯỚC khi lọc chữ, để con số trên tab không nhảy lung tung
    counts = {}
    for p in db.list_posts(limit=2000):
        s = p.get("status") or "draft"
        counts[s] = counts.get(s, 0) + 1

    rows = []
    for p in posts:
        cap = (p.get("caption") or "").strip()
        if q and q not in cap.lower() and q not in (p.get("code") or "").lower():
            continue
        c = _cal_card(p)
        c["headline"] = cap.split("\n")[0][:110] if cap else (p.get("code") or "(chưa có nội dung)")
        c["n_char"] = len(cap)
        rows.append(c)

    rows.sort(key=lambda r: (r["date"] or "0000-00-00", r["time"] or "99:99"), reverse=True)

    return render_template(
        "posts.html",
        rows=rows, counts=counts, total_all=sum(counts.values()),
        types=POST_TYPES, statuses=POST_STATUSES,
        f_status=f_status, f_type=f_type, f_range=f_range, q=q,
        today=today.isoformat(), css_v=_css_v(),
    )


def _css_v() -> int:
    """mtime của fb-module.css — gắn vào ?v= để trình duyệt luôn lấy bản mới nhất."""
    try:
        return int((Path(__file__).resolve().parents[1] / "static" / "css" / "fb-module.css").stat().st_mtime)
    except OSError:
        return 0


def _cal_card(p: dict) -> dict:
    """Gói 1 bài thành thẻ hiển thị trên lịch: ảnh đầu + số ảnh + giờ + trạng thái."""
    imgs = post_images(p)
    return {
        "id": p.get("id"),
        "code": p.get("code") or "",
        "caption": (p.get("caption") or "").strip(),
        "status": p.get("status") or "draft",
        "time": p.get("scheduled_time") or "",
        "date": p.get("scheduled_date") or "",
        "ptype": p.get("type") or "",
        "thumb": imgs[0] if imgs else None,
        "n_img": len(imgs),
        "fb_post_id": p.get("fb_post_id") or "",
    }


def calendar_page():
    """Lịch đăng: xem theo THÁNG (mặc định) hoặc TUẦN, điều hướng tự do, kéo thả đổi ngày.

    Query: view=month|week · ref=YYYY-MM-DD (ngày mốc) · status=… (lọc)
    """
    today = date.today()
    view = (request.args.get("view") or "month").lower()
    if view not in ("month", "week"):
        view = "month"
    f_status = request.args.get("status") or None

    try:
        ref = date.fromisoformat(request.args.get("ref") or "")
    except ValueError:
        ref = today

    if view == "week":
        start = ref - timedelta(days=ref.weekday())          # thứ 2
        end = start + timedelta(days=6)
        grid_start, grid_end = start, end
        title = f"Tuần {start.day:02d}/{start.month:02d} – {end.day:02d}/{end.month:02d}/{end.year}"
        prev_ref = (start - timedelta(days=7)).isoformat()
        next_ref = (start + timedelta(days=7)).isoformat()
    else:
        first = ref.replace(day=1)
        nxt = (first + timedelta(days=32)).replace(day=1)
        last = nxt - timedelta(days=1)
        grid_start = first - timedelta(days=first.weekday())   # lùi về thứ 2
        grid_end = last + timedelta(days=(6 - last.weekday()))  # tiến tới chủ nhật
        title = f"Tháng {first.month} · {first.year}"
        prev_ref = (first - timedelta(days=1)).replace(day=1).isoformat()
        next_ref = nxt.isoformat()
        start, end = first, last

    posts = db.list_posts(
        date_from=grid_start.isoformat(), date_to=grid_end.isoformat(), status=f_status
    )
    by_day = {}
    for p in posts:
        by_day.setdefault(p.get("scheduled_date"), []).append(p)

    cells, d = [], grid_start
    while d <= grid_end:
        iso = d.isoformat()
        items = sorted(by_day.get(iso, []), key=lambda x: (x.get("scheduled_time") or "99:99"))
        cells.append({
            "iso": iso,
            "dnum": d.day,
            "month": d.month,
            "is_today": d == today,
            "is_past": d < today,
            "in_range": (start <= d <= end),
            "posts": [_cal_card(p) for p in items],
        })
        d += timedelta(days=1)

    counts = {}
    for p in posts:
        s = p.get("status") or "draft"
        counts[s] = counts.get(s, 0) + 1

    return render_template(
        "calendar.html",
        cells=cells, view=view, title=title, f_status=f_status,
        prev_ref=prev_ref, next_ref=next_ref, today_ref=today.isoformat(),
        counts=counts, total=len(posts),
        statuses=POST_STATUSES, types=POST_TYPES,
        dows=["Th 2", "Th 3", "Th 4", "Th 5", "Th 6", "Th 7", "CN"],
        css_v=_css_v(),
    )


def _fb_posted_db_path() -> Path:
    here = Path(__file__).resolve()
    return next(
        (p / "fb_posted_products.json" for p in here.parents
         if (p / "fb_posted_products.json").exists()),
        here.parents[3] / "fb_posted_products.json",
    )


def fb_posted_page():
    """SP đã lên Facebook — tách rõ ĐÃ ĐĂNG với ĐANG CHỜ (trước đây trộn chung một bảng).

    Bài có ngày ở tương lai = đang nằm lịch, CHƯA đăng. Nguồn ghi rõ "chưa thực đăng"
    cũng bị tách ra để không đếm nhầm là đã lên trang.
    """
    try:
        data = json.loads(_fb_posted_db_path().read_text(encoding="utf-8"))
    except Exception:
        data = {"updated_at": None, "products": []}

    today = date.today().isoformat()
    rows = []
    for i, p in enumerate(data.get("products", []), 1):
        link = p.get("sintech_link") or (
            "https://sintech.vn/products/" + p["handle"] if p.get("handle") else ""
        )
        d = (p.get("posted_date") or "").strip()
        src = (p.get("source") or "").strip()

        # phân loại
        if "chưa thực đăng" in src.lower():
            state = "chua"                       # ghi chú nói rõ chưa đăng
        elif not d:
            state = "thieu"                      # không có ngày → không biết
        elif len(d) == 7:
            state = "mo"                         # chỉ có tháng
        elif d > today:
            state = "cho"                        # ngày tương lai → đang nằm lịch
        else:
            state = "xong"

        rows.append({
            "stt": i,
            "name": p.get("name", ""),
            "link": link,
            "date": d,
            "state": state,
            "source": src,
            "ptype": (p.get("type") or "").strip(),
        })

    order = {"cho": 0, "chua": 1, "thieu": 2, "mo": 3, "xong": 4}
    rows.sort(key=lambda r: (order[r["state"]], r["date"] or "0000", r["name"]))

    tabs = {
        "all":   len(rows),
        "xong":  sum(1 for r in rows if r["state"] == "xong"),
        "cho":   sum(1 for r in rows if r["state"] == "cho"),
        "chua":  sum(1 for r in rows if r["state"] == "chua"),
        "thieu": sum(1 for r in rows if r["state"] in ("thieu", "mo")),
    }
    thieu_link = sum(1 for r in rows if not r["link"])
    thieu_type = sum(1 for r in rows if not r["ptype"])

    return render_template(
        "fb_posted.html",
        rows=rows, tabs=tabs, total=len(rows),
        updated_at=data.get("updated_at"), today=today,
        thieu_link=thieu_link, thieu_type=thieu_type,
        css_v=_css_v(),
    )


def api_fb_posted_sync():
    """Đối chiếu với lịch THẬT trên Facebook: bài nào còn nằm lịch = chưa đăng.

    Chỉ ĐỌC từ Graph API rồi trả kết quả so khớp — không sửa file, không đụng Facebook.
    """
    try:
        from state_paths import STATE_DIR            # noqa: F401
    except Exception:
        pass
    try:
        import requests as _rq
        cfg_p = next(
            (p / "state" / "facebook_token.json" for p in Path(__file__).resolve().parents
             if (p / "state" / "facebook_token.json").exists()), None)
        if not cfg_p:
            return jsonify({"error": "không tìm thấy facebook_token.json"}), 400
        cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
        r = _rq.get(
            f"https://graph.facebook.com/v25.0/{cfg['page_id']}/scheduled_posts",
            params={"fields": "scheduled_publish_time,message", "limit": 100,
                    "access_token": cfg["page_token"]},
            timeout=30,
        )
        js = r.json()
        if r.status_code != 200:
            return jsonify({"error": (js.get("error") or {}).get("message", "lỗi Graph API")}), 502
        pend = []
        for it in js.get("data", []):
            msg = (it.get("message") or "").split("\n")[0].strip()
            pend.append({
                "when": datetime.fromtimestamp(it["scheduled_publish_time"]).strftime("%d/%m %H:%M"),
                "head": msg[:70],
            })
        pend.sort(key=lambda x: x["when"])
        return jsonify({"ok": True, "n_pending": len(pend), "pending": pend})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────── POST CRUD ───────────────────────────────

def post_new():
    if request.method == "POST":
        files = request.files.getlist("images") or []
        if not files:
            single = request.files.get("image")
            if single:
                files = [single]
        added = [fn for fn in (save_upload(f) for f in files) if fn]
        data = {
            "scheduled_date": request.form.get("scheduled_date") or None,
            "scheduled_time": request.form.get("scheduled_time") or None,
            "type": request.form.get("type") or "product",
            "status": request.form.get("status") or "draft",
            "caption": request.form.get("caption") or "",
            "image_path": added[0] if added else None,
            "images": json.dumps(added),
            "link": request.form.get("link") or None,
        }
        pid = db.create_post(data)
        if added:
            new_post = db.get_post(pid)
            if new_post:
                _move_inbox_files_to_post(new_post, added)
        new_post = db.get_post(pid)
        db.activity_log(
            kind="post_create", icon="📝",
            title=f"Tạo bài mới #{new_post.get('code') or pid}",
            description=(new_post.get("caption") or "")[:120],
            href=url_for("post_detail", post_id=pid),
        )
        flash(f"Đã tạo bài #{pid}", "success")
        return redirect(url_for("post_detail", post_id=pid))
    return render_template(
        "post_form.html",
        post=None, types=POST_TYPES, statuses=POST_STATUSES,
    )


def post_detail(post_id):
    p = db.get_post(post_id)
    if not p:
        return "Not found", 404
    p["image_list"] = post_images(p)
    p["image_warnings"] = _detect_image_mismatches(p["code"], p["image_list"])
    return render_template(
        "post_form.html",
        post=p, types=POST_TYPES, statuses=POST_STATUSES,
    )


def post_update(post_id):
    p = db.get_post(post_id)
    if not p:
        return "Not found", 404
    files = request.files.getlist("images") or []
    if not files:
        single = request.files.get("image")
        if single:
            files = [single]
    new_uploads = [fn for fn in (save_upload(f, post=p) for f in files) if fn]
    data = {
        "scheduled_date": request.form.get("scheduled_date") or None,
        "scheduled_time": request.form.get("scheduled_time") or None,
        "type": request.form.get("type") or p["type"],
        "status": request.form.get("status") or p["status"],
        "caption": request.form.get("caption") or "",
        "link": request.form.get("link") or None,
    }
    order_raw = request.form.get("images_order") or ""
    current = post_images(p)
    if order_raw:
        wanted = [s for s in order_raw.split(",") if s]
        valid = set(current)
        imgs = [fn for fn in wanted if fn in valid]
    else:
        imgs = list(current)
    imgs.extend(new_uploads)
    data["image_path"] = imgs[0] if imgs else None
    data["images"] = json.dumps(imgs)
    db.update_post(post_id, data)
    flash("Đã lưu thay đổi", "success")
    return redirect(url_for("post_detail", post_id=post_id))


def api_post_images_reorder(post_id):
    p = db.get_post(post_id)
    if not p:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(force=True) or {}
    order = body.get("order") or []
    valid = set(post_images(p))
    new_order = [fn for fn in order if fn in valid]
    db.update_post(post_id, {
        "images": json.dumps(new_order),
        "image_path": new_order[0] if new_order else None,
    })
    return jsonify({"ok": True, "images": new_order})


def api_post_images_remove(post_id):
    p = db.get_post(post_id)
    if not p:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(force=True) or {}
    target = body.get("filename") or ""
    imgs = [f for f in post_images(p) if f != target]
    db.update_post(post_id, {
        "images": json.dumps(imgs),
        "image_path": imgs[0] if imgs else None,
    })
    return jsonify({"ok": True, "images": imgs})


def post_delete(post_id):
    db.delete_post(post_id)
    flash("Đã xóa bài", "warning")
    return redirect(url_for("posts_page"))


def api_posts_bulk():
    body = request.get_json(force=True) or {}
    ids = body.get("ids") or []
    action = (body.get("action") or "").strip()
    payload = body.get("payload") or {}
    if not ids or not isinstance(ids, list):
        return jsonify({"error": "ids rỗng"}), 400
    valid_status = {v for v, _ in POST_STATUSES}
    affected = 0
    if action == "status":
        new_status = (payload.get("status") or "").strip()
        if new_status not in valid_status:
            return jsonify({"error": f"status không hợp lệ: {new_status}"}), 400
        for pid in ids:
            try:
                if db.get_post(int(pid)):
                    db.update_post(int(pid), {"status": new_status})
                    affected += 1
            except (ValueError, TypeError):
                continue
    elif action == "delete":
        for pid in ids:
            try:
                if db.get_post(int(pid)):
                    db.delete_post(int(pid))
                    affected += 1
            except (ValueError, TypeError):
                continue
    else:
        return jsonify({"error": f"action không hỗ trợ: {action}"}), 400
    return jsonify({"ok": True, "affected": affected})


def api_post_reschedule(post_id):
    p = db.get_post(post_id)
    if not p:
        return jsonify({"error": "not found"}), 404
    body = request.get_json(force=True) or {}
    new_date = (body.get("scheduled_date") or "").strip()
    new_time = (body.get("scheduled_time") or "").strip()
    try:
        datetime.strptime(new_date, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "ngày sai format YYYY-MM-DD"}), 400
    if new_time:
        try:
            datetime.strptime(new_time, "%H:%M")
        except ValueError:
            return jsonify({"error": "giờ sai format HH:MM"}), 400
    db.update_post(post_id, {
        "scheduled_date": new_date,
        "scheduled_time": new_time or None,
    })
    return jsonify({"ok": True, "scheduled_date": new_date, "scheduled_time": new_time})


def post_change_status(post_id, new_status):
    valid = {s[0] for s in POST_STATUSES}
    if new_status not in valid:
        return jsonify({"error": "invalid status"}), 400
    db.update_post(post_id, {"status": new_status})
    return jsonify({"ok": True, "status": new_status})


# ─────────────────────── FB POSTING (publish + schedule) ─────────

def post_publish(post_id):
    p = db.get_post(post_id)
    if not p:
        return jsonify({"error": "not found"}), 404
    if not p["caption"]:
        return jsonify({"error": "caption rỗng"}), 400
    paths = post_image_paths(p)
    try:
        if len(paths) >= 2:
            result = fb_client.post_multi_to_page(p["caption"], paths, published=True)
        elif len(paths) == 1:
            result = fb_client.post_to_page(p["caption"], image_path=paths[0], published=True)
        else:
            result = fb_client.post_to_page(p["caption"], image_path=None, published=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    fb_id = result.get("post_id") or result.get("id")
    db.update_post(post_id, {"status": "posted", "fb_post_id": fb_id})
    return jsonify({
        "ok": True,
        "fb_post_id": fb_id,
        "url": fb_client.post_url(fb_id) if fb_id else None,
    })


def post_schedule(post_id):
    """Lên lịch FB Native (FB tự đăng tới giờ) — yêu cầu cách hiện tại 10 phút trở lên."""
    p = db.get_post(post_id)
    if not p:
        return jsonify({"error": "not found"}), 404
    if not p["scheduled_date"] or not p["scheduled_time"]:
        return jsonify({"error": "thiếu ngày/giờ lên lịch"}), 400
    dt_str = f"{p['scheduled_date']} {p['scheduled_time']}"
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return jsonify({"error": "định dạng ngày/giờ sai"}), 400
    ts = int(dt.timestamp())
    if ts < int(datetime.now().timestamp()) + 11 * 60:
        return jsonify({"error": "phải cách hiện tại tối thiểu 11 phút"}), 400
    paths = post_image_paths(p)
    try:
        if len(paths) >= 2:
            result = fb_client.post_multi_to_page(
                p["caption"], paths, scheduled_publish_time=ts
            )
        else:
            result = fb_client.post_to_page(
                p["caption"],
                image_path=(paths[0] if paths else None),
                scheduled_publish_time=ts,
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    fb_id = result.get("post_id") or result.get("id")
    db.update_post(post_id, {"status": "scheduled", "fb_post_id": fb_id})
    return jsonify({"ok": True, "fb_post_id": fb_id, "scheduled_at": dt_str})


# ─────────────────────── WIDGET CHAT + COMMAND ───────────────────

def api_widget_chat():
    data = request.get_json(force=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"reply": "Vợ yêu nói gì với anh nè 💕"})
    low = msg.lower()
    if any(k in low for k in ("hi", "hello", "chào", "alo")):
        reply = "Chào vợ yêu 💕 Anh đang trực ở đây nha. Em cần gì?"
    elif "lịch" in low and "ngày mai" in low:
        d = (date.today() + timedelta(days=1)).isoformat()
        ps = db.list_posts(date=d)
        if not ps:
            reply = f"Ngày mai ({d}) chưa có bài nào trong DB."
        else:
            lines = [f"📅 Lịch ngày mai ({d}) — {len(ps)} bài:"]
            for p in ps:
                t = p.get("scheduled_time") or "--:--"
                lines.append(f"• {t} — {p['code']} [{p['status']}] {p.get('title') or ''}")
            reply = "\n".join(lines)
    elif "thống kê" in low or "stats" in low:
        s = db.stats()
        reply = (
            f"📊 Tổng: {s['total']} bài | Hôm nay: {s['today_count']} | "
            f"Status: {s['by_status']}"
        )
    else:
        reply = (
            "Anh đã nhận tin nhắn của vợ 💌\n"
            "Tip: thử hỏi 'lịch ngày mai', 'thống kê', hoặc dùng nút Command Center "
            "ở Dashboard."
        )
    return jsonify({"reply": reply})


def api_command(name):
    if name == "preview-tomorrow":
        d = (date.today() + timedelta(days=1)).isoformat()
        return jsonify({"date": d, "posts": db.list_posts(date=d)})
    if name == "preview-today":
        d = date.today().isoformat()
        return jsonify({"date": d, "posts": db.list_posts(date=d)})
    if name == "page-info":
        return jsonify(fb_client.page_info())
    return jsonify({"error": "unknown command"}), 400


# ─────────────────────── MEDIA SERVING ───────────────────────────

def serve_upload(filename):
    """Serve ảnh: ưu tiên _inbox, fallback search toàn FB-Library
    (case em đã move file sang subfolder category SP)."""
    p = _resolve_image_file(filename)
    if p and p.is_file():
        return send_from_directory(p.parent, p.name)
    return send_from_directory(UPLOAD_DIR, filename)


def serve_local_image(handle, filename):
    """Serve ảnh content_jobs đã resize local (pattern lazy upload 2026-05-12).

    Path: marketing_hub/data/images/<handle>/<filename>
    """
    safe_handle = re.sub(r"[^a-z0-9_-]", "_", (handle or "").lower())[:80]
    folder = Path(__file__).parent.parent / "data" / "images" / safe_handle
    if not folder.exists():
        return ("Image folder not found", 404)
    return send_from_directory(folder, filename)


# ─────────────────────── LIBRARY ─────────────────────────────────

def library_page():
    """Trang thư viện ảnh standalone — duyệt thumbnail toàn FB-Library."""
    return render_template("library.html")


def api_library_categories():
    if not LIBRARY_ROOT.exists():
        return jsonify({"error": f"library root not found: {LIBRARY_ROOT}"}), 404
    cats = []
    for entry in sorted(LIBRARY_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_"):
            continue
        count = sum(
            1 for f in entry.iterdir()
            if f.is_file() and f.suffix.lower() in LIBRARY_IMG_EXT
        )
        if count > 0:
            cats.append({"name": entry.name, "count": count})
    return jsonify({"categories": cats, "total": len(cats)})


def api_library_images():
    cat = request.args.get("cat", "").strip()
    folder = _safe_lib_path(cat)
    if not folder or not folder.is_dir():
        return jsonify({"error": "invalid category"}), 400
    images = []
    for f in sorted(folder.iterdir()):
        if not f.is_file() or f.suffix.lower() not in LIBRARY_IMG_EXT:
            continue
        images.append({
            "filename": f.name,
            "size": f.stat().st_size,
            "url": url_for("library_file", category=cat, filename=f.name),
        })
    return jsonify({"category": cat, "images": images, "count": len(images)})


def library_file(category, filename):
    target = _safe_lib_path(category, filename)
    if not target or not target.is_file():
        return "Not found", 404
    return send_from_directory(target.parent, target.name)


def api_library_use():
    """Copy library image(s) into uploads/ and append to post.images list.

    Body: {category, filename | filenames[], post_id}
    """
    data = request.get_json(force=True) or {}
    cat = (data.get("category") or "").strip()
    post_id = data.get("post_id")
    fnames = data.get("filenames")
    if not fnames:
        single = (data.get("filename") or "").strip()
        fnames = [single] if single else []
    if not fnames:
        return jsonify({"error": "no filename(s)"}), 400

    target_post = db.get_post(post_id) if post_id else None
    target_dir = _ensure_post_folder(target_post) if target_post else UPLOAD_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    added = []
    for fname in fnames:
        src = _safe_lib_path(cat, fname)
        if not src or not src.is_file():
            continue
        if src.suffix.lower().lstrip(".") not in ALLOWED_EXT:
            continue
        safe = secure_filename(f"{cat}_{fname}") or f"lib_{fname}"
        dest_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe}"
        dest = target_dir / dest_name
        shutil.copy2(src, dest)
        added.append(dest_name)

    if not added:
        return jsonify({"error": "no valid images copied"}), 400

    images_now = added
    if post_id:
        try:
            pid = int(post_id)
            p = db.get_post(pid)
            if p:
                imgs = post_images(p) + added
                db.update_post(pid, {
                    "images": json.dumps(imgs),
                    "image_path": imgs[0],
                })
                images_now = imgs
        except (ValueError, TypeError):
            pass
    return jsonify({
        "ok": True,
        "added": added,
        "images": images_now,
        "urls": [url_for("serve_upload", filename=fn) for fn in images_now],
    })


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 22 route Posts + Calendar + Library + Media."""
    # Posts list + calendar
    app.add_url_rule("/posts", "posts_page", posts_page)
    app.add_url_rule("/calendar", "calendar_page", calendar_page)
    app.add_url_rule("/fb-posted", "fb_posted_page", fb_posted_page)
    app.add_url_rule("/api/fb-posted/sync", "api_fb_posted_sync",
                     api_fb_posted_sync, methods=["POST"])

    # Post CRUD
    app.add_url_rule("/posts/new", "post_new", post_new, methods=["GET", "POST"])
    app.add_url_rule("/posts/<int:post_id>", "post_detail", post_detail)
    app.add_url_rule("/posts/<int:post_id>/update", "post_update", post_update, methods=["POST"])
    app.add_url_rule("/posts/<int:post_id>/delete", "post_delete", post_delete, methods=["POST"])
    app.add_url_rule("/posts/<int:post_id>/status/<new_status>",
                     "post_change_status", post_change_status, methods=["POST"])

    # API posts/post
    app.add_url_rule("/api/post/<int:post_id>/images/reorder",
                     "api_post_images_reorder", api_post_images_reorder, methods=["POST"])
    app.add_url_rule("/api/post/<int:post_id>/images/remove",
                     "api_post_images_remove", api_post_images_remove, methods=["POST"])
    app.add_url_rule("/api/post/<int:post_id>/reschedule",
                     "api_post_reschedule", api_post_reschedule, methods=["POST"])
    app.add_url_rule("/api/posts/bulk", "api_posts_bulk", api_posts_bulk, methods=["POST"])

    # FB posting
    app.add_url_rule("/posts/<int:post_id>/publish", "post_publish", post_publish, methods=["POST"])
    app.add_url_rule("/posts/<int:post_id>/schedule", "post_schedule", post_schedule, methods=["POST"])

    # Widget chat + command
    app.add_url_rule("/api/widget-chat", "api_widget_chat", api_widget_chat, methods=["POST"])
    app.add_url_rule("/api/command/<name>", "api_command", api_command, methods=["POST"])

    # Media serving
    app.add_url_rule("/uploads/<path:filename>", "serve_upload", serve_upload)
    app.add_url_rule("/local-images/<handle>/<filename>", "serve_local_image", serve_local_image)

    # Library
    app.add_url_rule("/library", "library_page", library_page)
    app.add_url_rule("/api/library/categories", "api_library_categories", api_library_categories)
    app.add_url_rule("/api/library/images", "api_library_images", api_library_images)
    app.add_url_rule("/library/file/<category>/<path:filename>",
                     "library_file", library_file)
    app.add_url_rule("/api/library/use", "api_library_use", api_library_use, methods=["POST"])


# ─────────────────────── RUNTIME (scheduler + template context) ──

def auto_post_due():
    """Worker chạy mỗi phút — đăng các bài 'approved' tới giờ.

    Backup local trong trường hợp em muốn quản hoàn toàn từ Hub
    (đã có endpoint /schedule dùng FB native scheduling)."""
    now = datetime.now()
    today = now.date().isoformat()
    posts = db.list_posts(date=today, status="approved")
    for p in posts:
        if not p.get("scheduled_time"):
            continue
        try:
            tgt = datetime.strptime(
                f"{p['scheduled_date']} {p['scheduled_time']}", "%Y-%m-%d %H:%M"
            )
        except ValueError:
            continue
        if tgt > now:
            continue
        if tgt < now - timedelta(hours=2):
            continue  # quá hạn, skip
        try:
            paths = post_image_paths(p)
            if len(paths) >= 2:
                r = fb_client.post_multi_to_page(p["caption"], paths, published=True)
            else:
                r = fb_client.post_to_page(
                    p["caption"], image_path=(paths[0] if paths else None), published=True
                )
            fb_id = r.get("post_id") or r.get("id")
            db.update_post(p["id"], {"status": "posted", "fb_post_id": fb_id})
            print(f"[auto] Đã đăng bài {p['code']} → {fb_id}")
        except Exception as e:
            print(f"[auto] Lỗi đăng bài {p['code']}: {e}")


def register_runtime(app, sched):
    """Đăng ký template context (POST_TYPES/STATUSES) + scheduler job auto_post_due."""
    @app.context_processor
    def _inject_post_constants():
        return {"POST_TYPES": POST_TYPES, "POST_STATUSES": POST_STATUSES}

    sched.add_job(auto_post_due, "interval", minutes=1, id="auto_post_due")
