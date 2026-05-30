"""Sintech Marketing Hub — web app quản lý lịch đăng Facebook Page.

Run: python app.py  →  http://127.0.0.1:5055
"""

import os
import re
import json
import secrets
import threading
import queue as _queue_mod
import uuid
from datetime import datetime, timedelta, date
from pathlib import Path

import requests

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    send_from_directory,
    flash,
    make_response,
    session,
    Response,
    stream_with_context,
)
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler

import db
import fb_client
import seo as seo_mod
import haravan_sync as hv_sync
import notifier
import competitors as competitors_mod
import product_parser as pp
import product_writer as pw
import codex_provider as cp
import haravan_client as hv_client
import job_sync
import alt_manager
import cwv as cwv_mod

ROOT = Path(__file__).parent
ALLOWED_EXT = {"jpg", "jpeg", "png", "gif", "webp", "mp4"}
LIBRARY_ROOT = Path(r"C:\Users\NGHIANGO\Desktop\Sintech\FB-Library")
# Ảnh upload trực tiếp từ Hub → vào _inbox dưới FB-Library (gộp 2 chỗ thành 1).
# Em có thể move file sang subfolder code SP (vd "FB0003 - Laptop X/") sau khi
# categorize — filename không đổi nên bài cũ vẫn đọc được nếu app fallback search.
UPLOAD_DIR = LIBRARY_ROOT / "_inbox"
LIBRARY_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Constants
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
    # Fallback: search recursive trong LIBRARY_ROOT
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
                    import shutil
                    shutil.move(str(src), str(dst))


# ─────────────────────────── ROUTES ───────────────────────────


DOW_VI = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
DOW_VI_LONG = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]


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


@app.route("/")
def dashboard():
    s = db.stats()
    today = date.today()

    week_param = request.args.get("week")
    month_param = request.args.get("month")
    year_param = request.args.get("year")

    monday = None
    if month_param and year_param:
        try:
            target = date(int(year_param), int(month_param), 1)
            days_to_mon = (7 - target.weekday()) % 7
            monday = target + timedelta(days=days_to_mon)
        except (ValueError, TypeError):
            monday = None
    if monday is None and week_param:
        try:
            wd = date.fromisoformat(week_param)
            monday = wd - timedelta(days=wd.weekday())
        except ValueError:
            monday = None
    if monday is None:
        monday = today - timedelta(days=today.weekday())

    sunday = monday + timedelta(days=6)
    prev_week = (monday - timedelta(days=7)).isoformat()
    next_week = (monday + timedelta(days=7)).isoformat()
    this_week = (today - timedelta(days=today.weekday())).isoformat()

    upcoming = []
    for i in range(7):
        d = monday + timedelta(days=i)
        posts = db.list_posts(date=d.isoformat())
        meta = _day_meta(d, today)
        meta["posts"] = posts
        upcoming.append(meta)

    display_month = monday.month
    display_year = monday.year
    year_options = list(range(today.year - 1, today.year + 4))

    try:
        page = fb_client.page_info()
    except Exception as e:
        page = {"error": str(e)}
    recent_activity = db.activity_recent(limit=12)
    return render_template(
        "dashboard.html",
        stats=s,
        health=_dashboard_health(),
        worklog_tasks=_worklog_tasks(),
        upcoming=upcoming,
        page=page,
        types=POST_TYPES,
        statuses=POST_STATUSES,
        today=today.isoformat(),
        week_start=monday.isoformat(),
        week_end=sunday.isoformat(),
        week_start_disp=f"{monday.day:02d}/{monday.month:02d}",
        recent_activity=recent_activity,
        week_end_disp=f"{sunday.day:02d}/{sunday.month:02d}",
        prev_week=prev_week,
        next_week=next_week,
        this_week=this_week,
        display_month=display_month,
        display_year=display_year,
        year_options=year_options,
        is_current_week=(monday.isoformat() == this_week),
    )


@app.route("/posts")
def posts_page():
    today = date.today()
    f_status = request.args.get("status") or None
    f_type = request.args.get("type") or None

    week_param = request.args.get("week")
    month_param = request.args.get("month")
    year_param = request.args.get("year")

    monday = None
    if month_param and year_param:
        try:
            target = date(int(year_param), int(month_param), 1)
            days_to_mon = (7 - target.weekday()) % 7
            monday = target + timedelta(days=days_to_mon)
        except (ValueError, TypeError):
            monday = None
    if monday is None and week_param:
        try:
            wd = date.fromisoformat(week_param)
            monday = wd - timedelta(days=wd.weekday())
        except ValueError:
            monday = None
    if monday is None:
        monday = today - timedelta(days=today.weekday())

    sunday = monday + timedelta(days=6)
    prev_week = (monday - timedelta(days=7)).isoformat()
    next_week = (monday + timedelta(days=7)).isoformat()
    this_week = (today - timedelta(days=today.weekday())).isoformat()

    posts = db.list_posts(
        date_from=monday.isoformat(),
        date_to=sunday.isoformat(),
        status=f_status,
        ptype=f_type,
    )

    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        meta = _day_meta(d, today)
        meta["posts"] = [p for p in posts if p.get("scheduled_date") == d.isoformat()]
        days.append(meta)

    year_options = list(range(today.year - 1, today.year + 4))

    return render_template(
        "posts.html",
        posts=posts,
        days=days,
        types=POST_TYPES,
        statuses=POST_STATUSES,
        f_status=f_status,
        f_type=f_type,
        week_start=monday.isoformat(),
        week_end=sunday.isoformat(),
        week_start_disp=f"{monday.day:02d}/{monday.month:02d}",
        week_end_disp=f"{sunday.day:02d}/{sunday.month:02d}",
        prev_week=prev_week,
        next_week=next_week,
        this_week=this_week,
        display_month=monday.month,
        display_year=monday.year,
        year_options=year_options,
        is_current_week=(monday.isoformat() == this_week),
    )


@app.route("/calendar")
def calendar_page():
    today = date.today()
    days = []
    for i in range(14):
        d = today + timedelta(days=i)
        posts = db.list_posts(date=d.isoformat())
        meta = _day_meta(d, today)
        meta["posts"] = posts
        days.append(meta)
    return render_template(
        "calendar.html", days=days, types=POST_TYPES, statuses=POST_STATUSES
    )


@app.route("/posts/new", methods=["GET", "POST"])
def post_new():
    if request.method == "POST":
        files = request.files.getlist("images") or []
        if not files:
            single = request.files.get("image")
            if single:
                files = [single]
        # Phase 1: upload tạm vào _inbox (chưa biết post.id để tạo folder)
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
        # Phase 2: post đã có id+code, move ảnh từ _inbox sang folder bài
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
        post=None,
        types=POST_TYPES,
        statuses=POST_STATUSES,
    )


@app.route("/posts/<int:post_id>")
def post_detail(post_id):
    p = db.get_post(post_id)
    if not p:
        return "Not found", 404
    p["image_list"] = post_images(p)
    p["image_warnings"] = _detect_image_mismatches(p["code"], p["image_list"])
    return render_template(
        "post_form.html",
        post=p,
        types=POST_TYPES,
        statuses=POST_STATUSES,
    )


_FB_CODE_RE = __import__("re").compile(r"fb\d{4}", __import__("re").IGNORECASE)


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


@app.route("/posts/<int:post_id>/update", methods=["POST"])
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


@app.route("/api/post/<int:post_id>/images/reorder", methods=["POST"])
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


@app.route("/api/post/<int:post_id>/images/remove", methods=["POST"])
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


@app.route("/posts/<int:post_id>/delete", methods=["POST"])
def post_delete(post_id):
    db.delete_post(post_id)
    flash("Đã xóa bài", "warning")
    return redirect(url_for("posts_page"))


@app.route("/api/posts/bulk", methods=["POST"])
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


@app.route("/api/post/<int:post_id>/reschedule", methods=["POST"])
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


@app.route("/posts/<int:post_id>/status/<new_status>", methods=["POST"])
def post_change_status(post_id, new_status):
    valid = {s[0] for s in POST_STATUSES}
    if new_status not in valid:
        return jsonify({"error": "invalid status"}), 400
    db.update_post(post_id, {"status": new_status})
    return jsonify({"ok": True, "status": new_status})


# ─────────────────────────── FB POSTING ───────────────────────────


@app.route("/posts/<int:post_id>/publish", methods=["POST"])
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
    return jsonify(
        {
            "ok": True,
            "fb_post_id": fb_id,
            "url": fb_client.post_url(fb_id) if fb_id else None,
        }
    )


@app.route("/posts/<int:post_id>/schedule", methods=["POST"])
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


# ─────────────────────────── WIDGET CHAT ───────────────────────────


@app.route("/api/widget-chat", methods=["POST"])
def api_widget_chat():
    data = request.get_json(force=True) or {}
    msg = (data.get("message") or "").strip()
    if not msg:
        return jsonify({"reply": "Vợ yêu nói gì với anh nè 💕"})
    # MVP: echo + light routing. Có thể nâng cấp gọi LLM sau.
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


# ─────────────────────────── COMMAND CENTER ───────────────────────────


@app.route("/api/command/<name>", methods=["POST"])
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


# ─────────────────────────── MEDIA ───────────────────────────


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    """Serve ảnh: ưu tiên _inbox, fallback search toàn FB-Library
    (case em đã move file sang subfolder category SP)."""
    p = _resolve_image_file(filename)
    if p and p.is_file():
        return send_from_directory(p.parent, p.name)
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/local-images/<handle>/<filename>")
def serve_local_image(handle, filename):
    """Serve ảnh content_jobs đã resize local (pattern lazy upload 2026-05-12).

    Path: marketing_hub/data/images/<handle>/<filename>
    """
    from pathlib import Path
    import re as _re
    safe_handle = _re.sub(r"[^a-z0-9_-]", "_", (handle or "").lower())[:80]
    folder = Path(__file__).parent / "data" / "images" / safe_handle
    if not folder.exists():
        return ("Image folder not found", 404)
    return send_from_directory(folder, filename)


# ─────────────────────────── IMAGE LIBRARY ───────────────────────────


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


@app.route("/api/library/categories")
def api_library_categories():
    if not LIBRARY_ROOT.exists():
        return jsonify({"error": f"library root not found: {LIBRARY_ROOT}"}), 404
    cats = []
    for entry in sorted(LIBRARY_ROOT.iterdir()):
        if not entry.is_dir():
            continue
        # Skip folder internal (prefix _) như _inbox
        if entry.name.startswith("_"):
            continue
        count = sum(
            1 for f in entry.iterdir()
            if f.is_file() and f.suffix.lower() in LIBRARY_IMG_EXT
        )
        if count > 0:
            cats.append({"name": entry.name, "count": count})
    return jsonify({"categories": cats, "total": len(cats)})


@app.route("/api/library/images")
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


@app.route("/library/file/<category>/<path:filename>")
def library_file(category, filename):
    target = _safe_lib_path(category, filename)
    if not target or not target.is_file():
        return "Not found", 404
    return send_from_directory(target.parent, target.name)


@app.route("/api/library/use", methods=["POST"])
def api_library_use():
    """Copy library image(s) into uploads/ and append to post.images list.

    Body: {category, filename | filenames[], post_id}
    """
    import shutil
    data = request.get_json(force=True) or {}
    cat = (data.get("category") or "").strip()
    post_id = data.get("post_id")
    fnames = data.get("filenames")
    if not fnames:
        single = (data.get("filename") or "").strip()
        fnames = [single] if single else []
    if not fnames:
        return jsonify({"error": "no filename(s)"}), 400

    # Copy thẳng vào folder bài (nếu có post_id), không thì _inbox
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


# ─────────────────────────── SEO ───────────────────────────


SEO_SNAPSHOT_DIR = ROOT / "data" / "seo_snapshots"


def _open_snapshot(path):
    import gzip
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def _list_seo_snapshots() -> list:
    SEO_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    paths = list(SEO_SNAPSHOT_DIR.glob("*.json")) + list(SEO_SNAPSHOT_DIR.glob("*.json.gz"))
    for p in sorted(paths, key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with _open_snapshot(p) as f:
                data = json.load(f)
            counts = data.get("counts") or {}
            out.append({
                "filename": p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "exported_at": data.get("exported_at") or "",
                "label": data.get("label") or "",
                "pages": counts.get("pages", 0),
                "links": counts.get("links", 0),
                "runs": counts.get("runs", 0),
            })
        except (ValueError, OSError):
            continue
    return out


@app.route("/seo")
def seo_dashboard():
    stats = db.seo_stats()
    latest_run = db.seo_latest_run()
    state = seo_mod.state_snapshot()
    snapshots = _list_seo_snapshots()
    top_issues = db.seo_top_issues(limit=10)
    # bổ sung label cho top_issues
    for it in top_issues:
        icon, label, _fix = seo_mod.ISSUE_LABELS.get(it["code"], ("⚪", it["code"], ""))
        it["icon"] = icon
        it["label"] = label

    f_type = request.args.get("type") or None
    f_band = request.args.get("band") or None
    f_issue = request.args.get("issue") or None
    f_search = (request.args.get("q") or "").strip() or None
    f_sort = request.args.get("sort") or "score_asc"
    try:
        page_num = max(1, int(request.args.get("page") or 1))
    except (TypeError, ValueError):
        page_num = 1
    per_page = 50

    band_map = {"good": (80, None), "ok": (60, 79), "bad": (None, 59)}
    min_score, max_score = band_map.get(f_band, (None, None))

    list_kwargs = dict(
        url_type=f_type, min_score=min_score, max_score=max_score,
        issue_code=f_issue, search=f_search, sort=f_sort,
    )
    total_filtered = db.seo_count_pages(**list_kwargs)
    pages_list = db.seo_list_pages(**list_kwargs, limit=per_page, offset=(page_num - 1) * per_page)
    total_pages = max(1, (total_filtered + per_page - 1) // per_page)

    return render_template(
        "seo.html",
        stats=stats,
        latest_run=latest_run,
        state=state,
        link_state=seo_mod.link_check_state(),
        pages=pages_list,
        top_issues=top_issues,
        snapshots=snapshots,
        filters={
            "type": f_type, "band": f_band, "issue": f_issue,
            "q": f_search or "", "sort": f_sort,
        },
        page_num=page_num,
        total_pages=total_pages,
        total_filtered=total_filtered,
    )


@app.route("/seo/url/<int:page_id>")
def seo_url_detail(page_id):
    page = db.seo_get_page(page_id)
    if not page:
        flash("Không tìm thấy URL.", "error")
        return redirect(url_for("seo_dashboard"))
    raw_issues = []
    if page.get("issues"):
        try:
            raw_issues = json.loads(page["issues"])
        except (ValueError, TypeError):
            raw_issues = []
    issues = [seo_mod.enrich_issue(it) for it in raw_issues]
    return render_template("seo_detail.html", p=page, issues=issues)


@app.route("/seo/duplicates")
def seo_duplicates():
    field = request.args.get("field", "title")
    if field not in ("title", "meta_desc", "h1"):
        field = "title"
    dup_groups = db.seo_find_duplicates(field)
    counts = {
        "title": len(db.seo_find_duplicates("title")),
        "meta_desc": len(db.seo_find_duplicates("meta_desc")),
        "h1": len(db.seo_find_duplicates("h1")),
    }
    return render_template("seo_duplicates.html", field=field, groups=dup_groups, counts=counts)


@app.route("/seo/inlinks")
def seo_inlinks_page():
    view = request.args.get("view", "top")  # top | orphans
    url_type = request.args.get("type") or None
    summary = db.seo_inlinks_summary()
    if view == "orphans":
        items = db.seo_orphan_pages(url_type=url_type, limit=500)
    else:
        items = db.seo_top_inlinks(limit=100)
    return render_template(
        "seo_inlinks.html",
        summary=summary, items=items, view=view, url_type=url_type,
    )


@app.route("/seo/indexability")
def seo_indexability_page():
    reason = request.args.get("reason")
    stats = db.seo_indexability_stats()
    pages = db.seo_list_non_indexable(reason=reason, limit=500)
    return render_template(
        "seo_indexability.html",
        stats=stats, pages=pages, active_reason=reason,
    )


@app.route("/seo/broken-links")
def seo_broken_links_page():
    summary = db.seo_broken_link_summary()
    state = seo_mod.link_check_state()
    breakdown = db.seo_broken_breakdown()

    kind = request.args.get("kind") or None
    if kind not in ("4xx", "5xx", "timeout"):
        kind = None
    try:
        status_code = int(request.args["status"]) if request.args.get("status") else None
    except (TypeError, ValueError):
        status_code = None
    error_kind = request.args.get("error_kind") or None
    internal_arg = request.args.get("internal")
    is_internal = None
    if internal_arg == "1":
        is_internal = True
    elif internal_arg == "0":
        is_internal = False
    search = (request.args.get("q") or "").strip() or None
    sort = request.args.get("sort") or "refs_desc"
    if sort not in ("refs_desc", "refs_asc", "url", "status"):
        sort = "refs_desc"
    try:
        page_num = max(1, int(request.args.get("page") or 1))
    except (TypeError, ValueError):
        page_num = 1
    per_page = 100

    filters = dict(kind=kind, status_code=status_code, error_kind=error_kind,
                   is_internal=is_internal, search=search)
    total_filtered = db.seo_count_broken_filtered(**filters)
    total_pages = max(1, (total_filtered + per_page - 1) // per_page)
    broken = db.seo_broken_links_filtered(
        **filters, sort=sort,
        limit=per_page, offset=(page_num - 1) * per_page,
    )

    return render_template(
        "seo_broken_links.html",
        summary=summary, state=state, broken=broken,
        breakdown=breakdown,
        error_labels=seo_mod.LINK_ERROR_LABELS,
        filters={
            "kind": kind, "status_code": status_code, "error_kind": error_kind,
            "internal": internal_arg, "q": search or "", "sort": sort,
        },
        page_num=page_num, total_pages=total_pages, total_filtered=total_filtered,
        per_page=per_page,
    )


@app.route("/seo/check-links", methods=["POST"])
def seo_check_links():
    started = seo_mod.start_link_check_async()
    if started:
        flash("Đã bắt đầu check link gãy. Quá trình này có thể mất vài phút.", "success")
    else:
        flash("Đang check link — chờ xong rồi check tiếp.", "error")
    return redirect(url_for("seo_broken_links_page"))


@app.route("/seo/recheck-broken", methods=["POST"])
def seo_recheck_broken():
    """Re-check ĐÚNG các link đang broken (4xx/5xx/timeout) — không quét toàn bộ
    pool external chưa check. Tiện cho việc phân loại error_kind chi tiết."""
    # Lấy danh sách target broken TRƯỚC khi reset (sau reset sẽ NULL → query không match)
    targets = db.seo_get_broken_target_urls()
    if not targets:
        flash("Không có link broken nào để re-check.", "error")
        return redirect(url_for("seo_broken_links_page"))
    n = db.seo_reset_broken_links_for_recheck()
    started = seo_mod.start_link_check_async(only_targets=targets)
    if started:
        flash(f"Đã reset {n} link và bắt đầu re-check ĐÚNG {len(targets)} target broken.", "success")
    else:
        flash(f"Đã reset {n} link nhưng đang có run khác — chờ xong rồi bấm lại.", "warning")
    return redirect(url_for("seo_broken_links_page"))


@app.route("/api/seo/link-check-status")
def seo_link_check_status():
    return jsonify({
        "state": seo_mod.link_check_state(),
        "summary": db.seo_broken_link_summary(),
    })


@app.route("/seo/rules")
def seo_rules_page():
    """UI quản lý SEO rules: enable/disable, edit threshold/score/label/message."""
    cfg = seo_mod.load_rules_config()
    return render_template("seo_rules.html", config=cfg)


@app.route("/seo/rules/save", methods=["POST"])
def seo_rules_save():
    """Lưu config rules từ form. Field name format: rule_<code>_<field>."""
    cfg = seo_mod.load_rules_config(force=True)
    # Update thresholds (good/ok)
    try:
        cfg["thresholds"]["good"] = int(request.form.get("threshold_good") or 65)
        cfg["thresholds"]["ok"] = int(request.form.get("threshold_ok") or 50)
    except ValueError:
        pass

    # Update từng rule
    for rule in cfg.get("rules", []):
        code = rule.get("code")
        if not code:
            continue
        # Enabled checkbox
        rule["enabled"] = bool(request.form.get(f"rule_{code}_enabled"))
        # Name
        name = (request.form.get(f"rule_{code}_name") or "").strip()
        if name:
            rule["name"] = name
        # Level
        lvl = request.form.get(f"rule_{code}_level")
        if lvl in ("error", "warn", "info"):
            rule["level"] = lvl
        # Score
        try:
            score_str = request.form.get(f"rule_{code}_score")
            if score_str is not None and score_str != "":
                rule["score"] = int(score_str)
        except ValueError:
            pass
        # Threshold
        thr_str = request.form.get(f"rule_{code}_threshold")
        if thr_str is not None and thr_str != "":
            try:
                rule["threshold"] = int(thr_str)
            except ValueError:
                try:
                    rule["threshold"] = float(thr_str)
                except ValueError:
                    rule["threshold"] = thr_str
        # Message
        msg = request.form.get(f"rule_{code}_msg")
        if msg is not None:
            rule["msg"] = msg

    # Save atomically
    import datetime as _dt
    cfg["last_edited"] = _dt.datetime.now().isoformat(timespec="seconds")
    seo_mod.save_rules_config(cfg)
    flash(f"✅ Đã lưu {len(cfg.get('rules', []))} rules. Crawl sau sẽ apply ngay.", "success")
    return redirect(url_for("seo_rules_page"))


@app.route("/seo/export/<kind>")
def seo_export(kind):
    """kind = pages | issues | summary"""
    import csv
    import io
    from flask import Response

    if kind == "summary":
        summary = {
            "stats": db.seo_stats(),
            "indexability": db.seo_indexability_stats(),
            "inlinks": db.seo_inlinks_summary(),
            "duplicates": {
                "title": len(db.seo_find_duplicates("title")),
                "meta_desc": len(db.seo_find_duplicates("meta_desc")),
                "h1": len(db.seo_find_duplicates("h1")),
            },
            "broken_links": db.seo_broken_link_summary(),
            "top_issues": db.seo_top_issues(limit=20),
            "exported_at": datetime.now().isoformat(timespec="seconds"),
        }
        return Response(
            json.dumps(summary, ensure_ascii=False, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=seo-summary.json"},
        )

    buf = io.StringIO()
    writer = csv.writer(buf)

    if kind == "pages":
        writer.writerow([
            "url", "url_type", "status_code", "indexable", "indexability_reason",
            "title", "title_len", "meta_desc", "meta_desc_len",
            "h1", "h1_count", "word_count", "score",
            "internal_links", "external_links", "images_total", "images_no_alt",
            "has_canonical", "canonical_url", "has_og", "has_schema",
            "load_ms", "page_size_bytes", "last_crawled",
        ])
        pages_all = db.seo_list_pages(limit=10000, sort="score_asc")
        for p in pages_all:
            writer.writerow([
                p.get("url"), p.get("url_type"), p.get("status_code"),
                p.get("indexable"), p.get("indexability_reason"),
                p.get("title"), p.get("title_len"),
                p.get("meta_desc"), p.get("meta_desc_len"),
                p.get("h1"), p.get("h1_count"), p.get("word_count"), p.get("score"),
                p.get("internal_links"), p.get("external_links"),
                p.get("images_total"), p.get("images_no_alt"),
                p.get("has_canonical"), p.get("canonical_url"),
                p.get("has_og"), p.get("has_schema"),
                p.get("load_ms"), p.get("page_size_bytes"), p.get("last_crawled"),
            ])
        return Response(
            "﻿" + buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=seo-pages.csv"},
        )

    if kind == "issues":
        writer.writerow(["url", "url_type", "score", "issue_code", "level", "message", "fix"])
        pages_all = db.seo_list_pages(limit=10000, sort="score_asc")
        for p in pages_all:
            try:
                issue_arr = json.loads(p.get("issues") or "[]")
            except (ValueError, TypeError):
                issue_arr = []
            for it in issue_arr:
                _icon, label, fix = seo_mod.ISSUE_LABELS.get(it.get("code", ""), ("", it.get("code", ""), ""))
                writer.writerow([
                    p.get("url"), p.get("url_type"), p.get("score"),
                    it.get("code"), it.get("level"),
                    f"{label} — {it.get('msg', '')}", fix,
                ])
        return Response(
            "﻿" + buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=seo-issues.csv"},
        )

    flash("Loại export không hợp lệ. Chọn: pages / issues / summary.", "error")
    return redirect(url_for("seo_dashboard"))


@app.route("/seo/snapshot/save", methods=["POST"])
def seo_snapshot_save():
    import gzip
    SEO_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    label_raw = (request.form.get("label") or "").strip()
    label_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", label_raw)[:40] if label_raw else ""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"seo_{stamp}{('_' + label_slug) if label_slug else ''}.json.gz"
    snapshot = db.seo_export_snapshot()
    snapshot["label"] = label_raw
    path = SEO_SNAPSHOT_DIR / fname
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False)
    counts = snapshot["counts"]
    size_mb = round(path.stat().st_size / 1024 / 1024, 1)
    flash(
        f"💾 Đã save snapshot: {fname} ({size_mb} MB) — {counts['pages']} URL, {counts['links']} link, {counts['runs']} run.",
        "success",
    )
    return redirect(url_for("seo_dashboard"))


@app.route("/seo/snapshot/load/<filename>", methods=["POST"])
def seo_snapshot_load(filename):
    safe = secure_filename(filename)
    path = SEO_SNAPSHOT_DIR / safe
    if not path.exists() or not (safe.endswith(".json") or safe.endswith(".json.gz")):
        flash("Không tìm thấy snapshot.", "error")
        return redirect(url_for("seo_dashboard"))
    try:
        with _open_snapshot(path) as f:
            data = json.load(f)
        db.seo_import_snapshot(data)
        counts = data.get("counts") or {}
        flash(
            f"📂 Đã load snapshot {safe} — {counts.get('pages', 0)} URL, {counts.get('links', 0)} link.",
            "success",
        )
    except (ValueError, OSError) as e:
        flash(f"Lỗi load snapshot: {e}", "error")
    return redirect(url_for("seo_dashboard"))


@app.route("/seo/snapshot/delete/<filename>", methods=["POST"])
def seo_snapshot_delete(filename):
    safe = secure_filename(filename)
    path = SEO_SNAPSHOT_DIR / safe
    if path.exists() and (safe.endswith(".json") or safe.endswith(".json.gz")):
        path.unlink()
        flash(f"🗑️ Đã xoá snapshot {safe}.", "success")
    else:
        flash("Không tìm thấy snapshot.", "error")
    return redirect(url_for("seo_dashboard"))


@app.route("/seo/clear", methods=["POST"])
def seo_clear():
    if request.form.get("confirm") != "yes":
        flash("Cần xác nhận xoá. Click lại nút Clear.", "error")
        return redirect(url_for("seo_dashboard"))
    db.seo_clear_all()
    flash("⚠️ Đã clear toàn bộ data crawl SEO.", "success")
    return redirect(url_for("seo_dashboard"))


@app.route("/seo/url/<int:page_id>/recrawl", methods=["POST"])
def seo_url_recrawl(page_id):
    page = db.seo_get_page(page_id)
    if not page:
        flash("Không tìm thấy URL.", "error")
        return redirect(url_for("seo_dashboard"))
    result = seo_mod.crawl_one(page["url"])
    result["last_run_id"] = page.get("last_run_id")
    links = result.pop("_links", [])
    db.seo_upsert_page(result)
    if links:
        db.seo_replace_links(result["url"], links)
    flash(f"Đã crawl lại — điểm: {result.get('score', 0)}.", "success")
    return redirect(url_for("seo_url_detail", page_id=page_id))


@app.route("/seo/seed", methods=["POST"])
def seo_seed():
    try:
        urls = seo_mod.fetch_sitemap_urls()
    except Exception as e:
        flash(f"Lỗi fetch sitemap: {e.__class__.__name__}: {e}", "error")
        return redirect(url_for("seo_dashboard"))
    pairs = [(u, seo_mod.classify_url(u)) for u in urls]
    res = db.seo_seed_urls(pairs)
    flash(
        f"Đã quét sitemap: {len(urls)} URL — thêm mới {res['added']}, đã có sẵn {res['existing']}.",
        "success",
    )
    return redirect(url_for("seo_dashboard"))


@app.route("/api/seo/status")
def seo_status():
    return jsonify({
        "state": seo_mod.state_snapshot(),
        "link_state": seo_mod.link_check_state(),
        "stats": db.seo_stats(),
        "broken_summary": db.seo_broken_link_summary(),
    })


# ─────────────────────── JOB CENTER (gộp mọi job nền 1 chỗ) ───────────────────────
@app.route("/jobs")
def jobs_center_page():
    return render_template("jobs_center.html")


def _collect_jobs():
    """Thu thập trạng thái mọi job nền → list chuẩn hoá (dùng cho /api/jobs + job_monitor)."""
    def J(key, name, icon, page, running, total, done, extra, message,
          started_at, finished_at, current, stop):
        return {"key": key, "name": name, "icon": icon, "page": page,
                "running": bool(running), "total": int(total or 0), "done": int(done or 0),
                "extra": extra or "", "message": message or "",
                "started_at": started_at, "finished_at": finished_at,
                "current": current or "", "stop": stop}

    jobs = []
    try:
        s = seo_mod.state_snapshot()
        run = s.get("status") in ("fetching_sitemap", "crawling", "stopping")
        jobs.append(J("crawl", "SEO Crawl", "🕷️", "/seo", run, s.get("total"), s.get("done"),
                      f"✅ {s.get('success',0)} · ❌ {s.get('failed',0)} · {s.get('status','')}",
                      s.get("message"), s.get("started_at"), None, "",
                      "/seo/stop-crawl" if run else None))
    except Exception:
        pass
    try:
        s = seo_mod.link_check_state()
        jobs.append(J("links", "Kiểm tra link gãy", "🔗", "/seo/broken-links", s.get("running"),
                      s.get("total"), s.get("checked"), f"🔴 gãy: {s.get('broken',0)}",
                      "", None, None, "", None))
    except Exception:
        pass
    try:
        s = seo_mod.title_meta_fix_state()
        jobs.append(J("title_meta", "Auto-fix Title/Meta", "📝", "/seo/title-meta", s.get("running"),
                      s.get("total"), s.get("checked"),
                      f"✅ {s.get('success',0)} · ❌ {s.get('failed',0)} · ⏭️ {s.get('skipped',0)}",
                      s.get("message"), s.get("started_at"), s.get("finished_at"),
                      s.get("current_url", ""),
                      "/seo/title-meta/fix-all/stop" if s.get("running") else None))
    except Exception:
        pass
    try:
        s = seo_mod.desc_h1_state()
        jobs.append(J("h1_scan", "Quét H1 trong mô tả", "🔎", "/seo/h1-in-desc", s.get("running"),
                      s.get("total"), s.get("checked"), f"⚠️ vi phạm: {s.get('violations',0)}",
                      s.get("message"), s.get("started_at"), None, "", None))
    except Exception:
        pass
    try:
        s = seo_mod.h1_fix_all_state()
        jobs.append(J("h1_fix", "Auto-fix H1", "🔧", "/seo/h1-in-desc", s.get("running"),
                      s.get("total"), s.get("checked"),
                      f"✅ {s.get('success',0)} · ◐ {s.get('partial',0)} · ❌ {s.get('failed',0)}",
                      s.get("message"), s.get("started_at"), s.get("finished_at"),
                      s.get("current_url", ""),
                      "/seo/h1-in-desc/fix-all/stop" if s.get("running") else None))
    except Exception:
        pass
    try:
        s = seo_mod.empty_desc_state()
        jobs.append(J("empty_desc", "Quét SP thiếu mô tả", "📭", "/seo/empty-desc", s.get("running"),
                      s.get("total"), s.get("checked"),
                      f"rỗng {s.get('empty',0)} · ngắn {s.get('short',0)} · đủ {s.get('ok',0)}",
                      s.get("message"), s.get("started_at"), None, "", None))
    except Exception:
        pass
    try:
        s = content_writer.queue_state()
        pend = s.get("pending_in_db", 0) or 0
        done = s.get("completed", 0) or 0
        jobs.append(J("content_queue", "Hàng đợi gen Content SP", "🏭", "/content-jobs", s.get("running"),
                      done + (s.get("failed", 0) or 0) + pend, done,
                      f"❌ {s.get('failed',0)} · ⏳ chờ: {pend}",
                      s.get("last_message"), s.get("started_at"), None,
                      s.get("current_job_url", ""),
                      "/content-jobs/queue/stop" if s.get("running") else None))
    except Exception:
        pass
    try:
        s = dict(_GEN_BG)
        jobs.append(J("collection_gen", "Gen Content Collection", "📂", "/collection-content", s.get("running"),
                      s.get("total"), s.get("done"),
                      f"✅ {s.get('ok',0)} · ❌ {s.get('fail',0)}",
                      "", s.get("started_at"), s.get("finished_at"),
                      s.get("current_name") or "",
                      "/collection-content/gen-stop" if s.get("running") else None))
    except Exception:
        pass
    try:
        s = competitors_mod.state_snapshot()
        jobs.append(J("competitors", "Crawl đối thủ", "🥷", "/competitors", s.get("running"),
                      s.get("total"), s.get("fetched"), s.get("competitor") or "",
                      s.get("message"), s.get("started_at"), None, "", None))
    except Exception:
        pass

    return jobs


@app.route("/api/jobs")
def api_jobs():
    import job_monitor
    jobs = job_monitor.enrich(_collect_jobs())
    merged = job_monitor.merge_with_snapshot(jobs)
    snap = job_monitor.read_snapshot()
    return jsonify({
        "jobs": merged,
        "running_count": sum(1 for j in merged if j.get("running")),
        "snapshot_saved_at": (snap or {}).get("saved_at"),
    })


@app.route("/seo/recompute-dup", methods=["POST"])
def seo_recompute_dup():
    """Detect dup title/meta cross-site, trừ điểm + cập nhật issues vào seo_pages."""
    try:
        stats = seo_mod.recompute_dup_flags()
        return jsonify({"ok": True, **stats})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


# ─────────────────────────── GLOBAL SEARCH ───────────────────────────


@app.route("/api/search")
def api_global_search():
    """Fuzzy search trên posts + Haravan products + SEO pages + competitors."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    limit_each = 5
    like = f"%{q}%"
    results = []
    conn = db.get_conn()

    # Posts
    rows = conn.execute(
        "SELECT id, code, caption, scheduled_date FROM posts "
        "WHERE code LIKE ? OR caption LIKE ? ORDER BY id DESC LIMIT ?",
        (like, like, limit_each),
    ).fetchall()
    for r in rows:
        results.append({
            "kind": "post", "icon": "📝",
            "title": (r["code"] or f"Post #{r['id']}"),
            "snippet": (r["caption"] or "")[:80],
            "href": url_for("post_detail", post_id=r["id"]),
            "tag": r["scheduled_date"] or "",
        })

    # Haravan products
    rows = conn.execute(
        "SELECT haravan_id, title, handle, vendor, audit_score FROM haravan_products "
        "WHERE title LIKE ? OR handle LIKE ? OR vendor LIKE ? "
        "ORDER BY audit_score ASC LIMIT ?",
        (like, like, like, limit_each),
    ).fetchall()
    for r in rows:
        results.append({
            "kind": "haravan", "icon": "🛒",
            "title": r["title"] or "(no title)",
            "snippet": f"{r['vendor'] or ''} · /{r['handle']}",
            "href": url_for("haravan_product_detail", haravan_id=r["haravan_id"]),
            "tag": f"score {r['audit_score']}" if r["audit_score"] is not None else "",
        })

    # SEO pages (chỉ match URL/title nhanh)
    rows = conn.execute(
        "SELECT id, url, title, url_type, score FROM seo_pages "
        "WHERE title LIKE ? OR url LIKE ? "
        "ORDER BY score ASC LIMIT ?",
        (like, like, limit_each),
    ).fetchall()
    for r in rows:
        results.append({
            "kind": "seo", "icon": "🔍",
            "title": r["title"] or r["url"],
            "snippet": r["url"],
            "href": url_for("seo_url_detail", page_id=r["id"]),
            "tag": f"{r['url_type'] or ''} · {r['score']}đ" if r["score"] is not None else (r["url_type"] or ""),
        })

    # Competitors
    rows = conn.execute(
        "SELECT id, competitor, url, title FROM competitor_urls "
        "WHERE title LIKE ? OR url LIKE ? LIMIT ?",
        (like, like, limit_each),
    ).fetchall()
    for r in rows:
        results.append({
            "kind": "competitor", "icon": "🥷",
            "title": r["title"] or "(no title)",
            "snippet": r["url"],
            "href": r["url"],
            "tag": r["competitor"],
        })

    conn.close()
    return jsonify({"results": results, "total": len(results)})


# ─────────────────────────── COMPETITORS ───────────────────────────


@app.route("/competitors")
def competitors_page():
    stats = db.competitor_stats()
    state = competitors_mod.state_snapshot()
    topic_gap = db.competitor_topic_gap(min_competitor_count=3)

    # Cross-reference với Sintech (seo_pages) để tính gap thật
    sintech_topic_count = {}
    sintech_blogs = db.seo_list_pages(url_type="blog", limit=1000, sort="url")
    for b in sintech_blogs:
        topic = classify_blog_topic(b.get("title") or "")
        sintech_topic_count[topic] = sintech_topic_count.get(topic, 0) + 1

    for it in topic_gap:
        it["sintech_count"] = sintech_topic_count.get(it["topic"], 0)
        it["gap"] = it["competitor_count"] - it["sintech_count"]
        label, color = BLOG_TOPIC_LABELS.get(it["topic"], (it["topic"], "rgba(120,120,140,0.15)"))
        it["label"] = label
        it["color"] = color

    # Filter & paginate URL list
    f_competitor = request.args.get("competitor") or None
    f_topic = request.args.get("topic") or None
    f_search = (request.args.get("q") or "").strip() or None
    f_sort = request.args.get("sort") or "recent"
    try:
        page_num = max(1, int(request.args.get("page") or 1))
    except (TypeError, ValueError):
        page_num = 1
    per_page = 50

    filters = dict(competitor=f_competitor, topic=f_topic, search=f_search)
    total = db.competitor_count(**filters)
    total_pages = max(1, (total + per_page - 1) // per_page)
    items = db.competitor_list(
        **filters, sort=f_sort,
        limit=per_page, offset=(page_num - 1) * per_page,
    )

    return render_template(
        "competitors.html",
        stats=stats, state=state,
        topic_gap=topic_gap,
        items=items,
        competitors_meta=competitors_mod.COMPETITORS,
        topic_labels=BLOG_TOPIC_LABELS,
        filters={"competitor": f_competitor, "topic": f_topic,
                 "q": f_search or "", "sort": f_sort},
        page_num=page_num, total_pages=total_pages, total=total,
        per_page=per_page,
    )


@app.route("/competitors/crawl", methods=["POST"])
def competitors_crawl():
    started = competitors_mod.start_crawl_all_async()
    if started:
        flash("Đã bắt đầu crawl 4 đối thủ. Có thể mất 1-3 phút.", "success")
    else:
        flash("Đang crawl — chờ xong rồi crawl tiếp.", "error")
    return redirect(url_for("competitors_page"))


@app.route("/api/competitors/status")
def api_competitors_status():
    return jsonify({
        "state": competitors_mod.state_snapshot(),
        "stats": db.competitor_stats(),
    })


# ─────────────────────────── SEO HISTORY ───────────────────────────


@app.route("/seo/history")
def seo_history_page():
    history = db.seo_history_list(limit=200)
    chart_data = db.seo_history_chart_data(limit=52)
    return render_template(
        "seo_history.html",
        history=history,
        chart_data=chart_data,
    )


@app.route("/seo/history/capture", methods=["POST"])
def seo_history_capture():
    note = (request.form.get("note") or "").strip()
    rid = db.seo_capture_history(note=note)
    db.activity_log(
        kind="seo_snapshot", icon="📸",
        title=f"Chụp snapshot SEO #{rid}",
        description=f"Note: {note or 'manual'}",
        href=url_for("seo_history_page"),
    )
    flash(f"📸 Đã chụp snapshot lịch sử #{rid}", "success")
    return redirect(url_for("seo_history_page"))


# ─────────────────────────── H1 TRONG MÔ TẢ ───────────────────────────


@app.route("/seo/h1-in-desc")
def seo_h1_in_desc_page():
    url_type = request.args.get("type") or None
    show_all = request.args.get("all") == "1"
    items = db.seo_h1_in_desc_list(
        url_type=url_type,
        only_violations=not show_all,
        limit=2000,
    )
    summary = db.seo_h1_in_desc_summary()
    state = seo_mod.desc_h1_state()
    for it in items:
        try:
            it["desc_h1_list"] = json.loads(it["desc_h1_text"]) if it.get("desc_h1_text") else []
        except Exception:
            it["desc_h1_list"] = []
    return render_template(
        "seo_h1_in_desc.html",
        items=items, summary=summary, state=state,
        url_type=url_type, show_all=show_all,
    )


@app.route("/seo/h1-in-desc/scan", methods=["POST"])
def seo_h1_in_desc_scan():
    types_raw = request.form.getlist("types")
    valid = {"product", "collection", "blog", "page"}
    url_types = [t for t in types_raw if t in valid] or None
    try:
        limit = int(request.form.get("limit") or 0) or None
    except ValueError:
        limit = None
    started = seo_mod.start_desc_h1_scan_async(url_types=url_types, limit=limit)
    if started:
        scope = ", ".join(url_types) if url_types else "tất cả loại"
        flash(f"🔎 Đã bắt đầu quét H1 trong mô tả ({scope}). Tự refresh để xem tiến độ.", "success")
    else:
        flash("⏳ Đang có lượt quét chạy — chờ xong mới chạy lượt mới.", "info")
    return redirect(url_for("seo_h1_in_desc_page"))


@app.route("/api/seo/h1-in-desc/status")
def seo_h1_in_desc_status():
    return jsonify({
        "state": seo_mod.desc_h1_state(),
        "summary": db.seo_h1_in_desc_summary(),
    })


@app.route("/seo/h1-in-desc/fix", methods=["POST"])
def seo_h1_in_desc_fix():
    payload = request.get_json(silent=True) or request.form
    url = (payload.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Thiếu url"}), 400
    try:
        result = seo_mod.fix_h1_in_desc_for_url(url)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/seo/h1-in-desc/fix-all/start", methods=["POST"])
def seo_h1_fix_all_start():
    payload = request.get_json(silent=True) or request.form
    url_type = (payload.get("type") or "").strip() or None
    if url_type and url_type not in ("product", "collection", "blog", "page"):
        url_type = None
    started = seo_mod.start_h1_fix_all_async(url_type=url_type)
    if started:
        return jsonify({"ok": True, "message": "Đã start job fix-all."})
    return jsonify({"ok": False, "error": "Job đang chạy rồi — đợi xong hoặc bấm dừng."}), 409


@app.route("/seo/h1-in-desc/fix-all/stop", methods=["POST"])
def seo_h1_fix_all_stop():
    stopped = seo_mod.stop_h1_fix_all()
    if stopped:
        return jsonify({"ok": True, "message": "Đã gửi yêu cầu dừng."})
    return jsonify({"ok": False, "error": "Không có job đang chạy."}), 400


@app.route("/api/seo/h1-in-desc/fix-all/status")
def seo_h1_fix_all_status():
    return jsonify(seo_mod.h1_fix_all_state())


# ─────────────────────────── TITLE / META HUB ───────────────────────────


@app.route("/seo/title-meta")
def seo_title_meta_page():
    url_type = request.args.get("type") or None
    issue_filter = request.args.get("issue") or None
    sort = request.args.get("sort") or "score_asc"
    sync_filter = request.args.get("sync") or None
    if url_type and url_type not in ("product", "collection", "blog", "page"):
        url_type = None
    if issue_filter and issue_filter not in seo_mod.ALL_TITLE_META_CODES:
        issue_filter = None
    if sort not in ("score_asc", "n_issues_desc", "url"):
        sort = "score_asc"
    if sync_filter not in ("synced", "unsynced"):
        sync_filter = None
    items = seo_mod.list_title_meta_pages(
        url_type=url_type, issue_filter=issue_filter, sort=sort, limit=2000,
        sync_filter=sync_filter,
    )
    summary = seo_mod.title_meta_summary()
    fix_state = seo_mod.title_meta_fix_state()
    return render_template(
        "seo_title_meta.html",
        items=items, summary=summary, fix_state=fix_state,
        url_type=url_type, issue_filter=issue_filter, sort=sort,
        sync_filter=sync_filter,
        issue_labels=seo_mod.TITLE_META_LABELS,
    )


@app.route("/seo/title-meta/fix", methods=["POST"])
def seo_title_meta_fix():
    payload = request.get_json(silent=True) or request.form
    url = (payload.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Thiếu url"}), 400
    force_title = (payload.get("title") or "").strip() or None
    force_meta = (payload.get("meta") or "").strip() or None
    try:
        result = seo_mod.fix_title_meta_for_url(url,
            force_title=force_title, force_meta=force_meta)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify(result), 200 if result.get("ok") else 400


@app.route("/seo/title-meta/regen", methods=["POST"])
def seo_title_meta_regen():
    """Đẩy 1 SP vào hàng chờ gen+sync lại — chạy ngầm, frontend poll realtime."""
    payload = request.get_json(silent=True) or request.form
    url = (payload.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Thiếu url"}), 400
    try:
        result = seo_mod.enqueue_title_meta_regen(url)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify(result), 200 if result.get("ok") else 409


@app.route("/seo/title-meta/fix-all/start", methods=["POST"])
def seo_title_meta_fix_all_start():
    payload = request.get_json(silent=True) or request.form
    url_type = (payload.get("type") or "").strip() or None
    issue_filter = (payload.get("issue") or "").strip() or None
    sync_filter = (payload.get("sync") or "").strip() or None
    if url_type and url_type not in ("product", "collection", "blog", "page"):
        url_type = None
    if issue_filter and issue_filter not in seo_mod.ALL_TITLE_META_CODES:
        issue_filter = None
    if sync_filter not in ("synced", "unsynced"):
        sync_filter = None
    started = seo_mod.start_title_meta_fix_all_async(
        url_type=url_type, issue_filter=issue_filter, sync_filter=sync_filter)
    if started:
        return jsonify({"ok": True, "message": "Đã start job."})
    return jsonify({"ok": False, "error": "Job đang chạy rồi."}), 409


# ─────────────────────────── ALT MANAGER (P1: audit only) ───────────────────────────


@app.route("/alt-manager")
def alt_manager_page():
    """P2 — trang list SP với ALT coverage badge, KPI + filter + paginate."""
    page = max(1, int(request.args.get("page", 1) or 1))
    only_missing = request.args.get("missing", "1") != "0"
    filter_type = (request.args.get("type") or "").strip() or None
    filter_vendor = (request.args.get("vendor") or "").strip() or None
    search = (request.args.get("q") or "").strip() or None
    sort = request.args.get("sort", "missing_desc")
    if sort not in ("missing_desc", "total_desc", "handle_asc"):
        sort = "missing_desc"

    summary = alt_manager.summarize_alt_coverage()
    page_data = alt_manager.list_products_paginated(
        page=page, page_size=100,
        only_missing=only_missing,
        filter_type=filter_type, filter_vendor=filter_vendor,
        search=search, sort=sort,
    )
    options = alt_manager.list_filter_options()
    return render_template(
        "alt_manager.html",
        summary=summary, page_data=page_data, options=options,
        only_missing=only_missing,
        filter_type=filter_type, filter_vendor=filter_vendor,
        search=search, sort=sort,
    )


@app.route("/alt-manager/<int:product_id>")
def alt_manager_product_page(product_id):
    """P3 — editor inline ALT text cho 1 SP."""
    from content_writer import _gen_alt_for_position  # noqa: F401 — confirm importable
    product = alt_manager.get_product_for_editor(product_id)
    if not product:
        return "Không tìm thấy SP", 404
    return render_template("alt_manager_product.html", product=product)


@app.route("/api/alt-manager/<int:product_id>/gen-alt", methods=["POST"])
def alt_manager_gen_alt(product_id):
    """P3 — AI gen ALT text cho 1 image."""
    from content_writer import _gen_alt_for_position
    data = request.get_json(force=True) or {}
    position = int(data.get("position", 1))
    total = int(data.get("total", 1))
    product = alt_manager.get_product_for_editor(product_id)
    if not product:
        return jsonify({"error": "SP not found"}), 404
    name_clean = (product.get("title") or product.get("handle") or "").strip()
    alt = _gen_alt_for_position(name_clean, position, total)
    return jsonify({"alt": alt})


@app.route("/api/alt-manager/<int:product_id>/save", methods=["POST"])
def alt_manager_save_alts(product_id):
    """P3 — bulk save ALT: PUT Haravan API + update local DB."""
    data = request.get_json(force=True) or {}
    updates = data.get("updates", [])  # [{image_id, alt}, ...]
    if not updates:
        return jsonify({"ok": True, "saved": 0, "errors": []})
    errors = []
    saved = 0
    for item in updates:
        image_id = item.get("image_id")
        new_alt = (item.get("alt") or "").strip()
        if not image_id:
            continue
        result = hv_client.put_image_alt(product_id, image_id, new_alt)
        if result.get("ok"):
            alt_manager.update_image_alt_local(product_id, image_id, new_alt)
            saved += 1
        else:
            errors.append({"image_id": image_id, "error": result.get("error", "unknown")})
    return jsonify({"ok": len(errors) == 0, "saved": saved, "errors": errors})


@app.route("/api/alt-manager/summary")
def alt_manager_summary():
    """P1 — coverage stats toàn shop, parse JSON images đã có trong DB."""
    return jsonify(alt_manager.summarize_alt_coverage())


@app.route("/api/alt-manager/worst")
def alt_manager_worst():
    """P1 — top SP có nhiều ảnh thiếu/yếu ALT nhất."""
    limit = max(1, min(int(request.args.get("limit", 50)), 500))
    only_missing = request.args.get("all", "").lower() not in ("1", "true", "yes")
    return jsonify({
        "items": alt_manager.worst_products(limit=limit, only_with_missing=only_missing),
        "limit": limit,
    })


@app.route("/api/alt-manager/<int:product_id>/desc-images")
def alt_manager_desc_images(product_id):
    """P5 — fetch body_html LIVE từ Haravan, parse img tags."""
    try:
        imgs, _ = alt_manager.get_product_desc_images(product_id)
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500
    product = alt_manager.get_product_for_editor(product_id)
    return jsonify({"images": imgs, "title": (product or {}).get("title", "")})


@app.route("/api/alt-manager/<int:product_id>/gen-alt-desc", methods=["POST"])
def alt_manager_gen_alt_desc(product_id):
    """P5 — gen ALT cho 1 ảnh mô tả."""
    data = request.get_json(force=True) or {}
    idx = int(data.get("index", 0))
    product = alt_manager.get_product_for_editor(product_id)
    if not product:
        return jsonify({"error": "SP not found"}), 404
    name = (product.get("title") or product.get("handle") or "").strip()
    alt = alt_manager.gen_alt_for_desc_image(name, idx)
    return jsonify({"alt": alt})


@app.route("/api/alt-manager/<int:product_id>/save-desc", methods=["POST"])
def alt_manager_save_desc(product_id):
    """P5 — fetch live body_html → inject ALT → PUT lên Haravan."""
    data = request.get_json(force=True) or {}
    updates = data.get("updates", [])
    if not updates:
        return jsonify({"ok": True, "saved": 0})
    try:
        _, live_html = alt_manager.get_product_desc_images(product_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Fetch Haravan thất bại: {e}"}), 500
    if not live_html:
        return jsonify({"ok": False, "error": "body_html trống"}), 400
    new_html = alt_manager.save_desc_image_alts(product_id, updates, live_html)
    try:
        hv_client.update_product(product_id, {"body_html": new_html})
        return jsonify({"ok": True, "saved": len(updates)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 500


@app.route("/api/alt-manager/bulk-gen/start", methods=["POST"])
def alt_manager_bulk_gen_start():
    """P4 — khởi chạy bulk gen ALT background job."""
    ok = alt_manager.start_bulk_gen_async()
    if not ok:
        return jsonify({"ok": False, "error": "Job đang chạy rồi"}), 409
    return jsonify({"ok": True, "message": "Đã bắt đầu bulk gen"})


@app.route("/api/alt-manager/bulk-gen/start-desc", methods=["POST"])
def alt_manager_bulk_gen_start_desc():
    """Bulk gen chỉ ảnh mô tả (body_html) — API image ALT không hỗ trợ."""
    ok = alt_manager.start_bulk_gen_async(desc_only=True)
    if not ok:
        return jsonify({"ok": False, "error": "Job đang chạy rồi"}), 409
    return jsonify({"ok": True})


@app.route("/api/alt-manager/bulk-gen/stop", methods=["POST"])
def alt_manager_bulk_gen_stop():
    """P4 — gửi tín hiệu dừng bulk gen job."""
    stopped = alt_manager.stop_bulk_gen()
    return jsonify({"ok": stopped, "message": "Đang dừng..." if stopped else "Job không chạy"})


@app.route("/api/alt-manager/bulk-gen/status")
def alt_manager_bulk_gen_status():
    """P4 — polling endpoint trả trạng thái bulk gen job."""
    return jsonify(alt_manager.bulk_gen_job_state())


@app.route("/api/alt-manager/<int:product_id>/gen-save-all", methods=["POST"])
def alt_manager_gen_save_all(product_id):
    """Gen + save ALT cho tất cả ảnh (product + desc) của 1 SP."""
    try:
        result = alt_manager.gen_and_save_all_alts(product_id)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500
    return jsonify(result)


@app.route("/seo/title-meta/fix-all/stop", methods=["POST"])
def seo_title_meta_fix_all_stop():
    stopped = seo_mod.stop_title_meta_fix()
    if stopped:
        return jsonify({"ok": True, "message": "Đã gửi yêu cầu dừng."})
    return jsonify({"ok": False, "error": "Không có job đang chạy."}), 400


@app.route("/api/seo/title-meta/fix-all/status")
def seo_title_meta_fix_all_status():
    return jsonify(seo_mod.title_meta_fix_state())


@app.route("/api/seo/title-meta/gen-map")
def seo_title_meta_gen_map():
    """Set URL đã gen (đã có đề xuất F/G trong Sheet) — cho cột Trạng thái + skip gen lại."""
    try:
        import sheet_writer
        done = sorted(sheet_writer.list_urls_with_proposal())
        return jsonify({"ok": True, "done": done, "count": len(done)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200], "done": []})


# ─────────────────────────── GSC INSIGHTS ───────────────────────────


@app.route("/seo/gsc")
def seo_gsc_page():
    cache = seo_mod.gsc_load_cache()
    if not cache:
        return render_template("seo_gsc.html", cache=None, tasks=[], summary=None)
    tasks = seo_mod.gsc_build_tasks(cache)
    return render_template(
        "seo_gsc.html",
        cache=cache, tasks=tasks,
        summary=cache.get("summary", {}),
        fetched_at=cache.get("fetched_at"),
        performance=cache.get("performance", {}),
        coverage=cache.get("coverage", {}),
    )


@app.route("/seo/gsc/task/<task_id>")
def seo_gsc_task_page(task_id):
    task = seo_mod.gsc_get_task(task_id)
    if not task:
        flash("Task không tồn tại trong cache.", "error")
        return redirect(url_for("seo_gsc_page"))
    return render_template("seo_gsc_task.html", task=task)


@app.route("/seo/gsc/refresh", methods=["POST"])
def seo_gsc_refresh():
    """Re-fetch data từ 2 Google Sheet GSC export."""
    import subprocess
    script = Path(app.root_path) / "_fetch_gsc_cache.py"
    try:
        r = subprocess.run(
            ["python", str(script)],
            capture_output=True, text=True, timeout=120, encoding="utf-8",
        )
        if r.returncode == 0:
            flash("✅ Refresh cache GSC xong.", "success")
        else:
            flash(f"❌ Refresh fail: {r.stderr[:300]}", "error")
    except Exception as e:
        flash(f"❌ Refresh error: {e}", "error")
    return redirect(url_for("seo_gsc_page"))


# ─────────────────────── CORE WEB VITALS (PSI) ────────────────────────


@app.route("/seo/cwv")
def seo_cwv_page():
    strategy = request.args.get("strategy", "mobile")
    sort = request.args.get("sort", "performance_score")
    order = request.args.get("order", "asc")
    page_num = max(1, int(request.args.get("page", 1)))
    per_page = 50
    offset = (page_num - 1) * per_page

    total = db.cwv_count(strategy)
    rows = db.cwv_list(strategy=strategy, limit=per_page, offset=offset, sort=sort, order=order)
    stats = db.cwv_stats(strategy)
    state = cwv_mod.state_snapshot()
    total_pages = max(1, (total + per_page - 1) // per_page)
    progress = db.cwv_progress(strategy)

    return render_template(
        "seo_cwv.html",
        rows=rows, stats=stats, state=state,
        strategy=strategy, sort=sort, order=order,
        page_num=page_num, total_pages=total_pages, total=total,
        psi_key=_load_psi_key(),
        progress=progress,
    )


@app.route("/seo/cwv/diff")
def seo_cwv_diff_page():
    diff_path = Path(__file__).parent / "data" / "cwv_weekly_diff.json"
    diff = None
    error = None
    if diff_path.exists():
        try:
            diff = json.loads(diff_path.read_text(encoding="utf-8"))
        except Exception as e:
            error = f"Không đọc được {diff_path.name}: {e}"
    else:
        error = (
            "Chưa có file `data/cwv_weekly_diff.json`. "
            "Cần snapshot ≥2 tuần (`_scripts/weekly_cwv_snapshot.py`) rồi chạy "
            "`_scripts/weekly_cwv_diff.py` để generate."
        )
    return render_template("seo_cwv_diff.html", diff=diff, error=error)


@app.route("/api/seo/cwv/status")
def api_cwv_status():
    return jsonify(cwv_mod.state_snapshot())


@app.route("/api/seo/cwv/progress")
def api_cwv_progress():
    strategy = request.args.get("strategy", "mobile")
    return jsonify({"progress": db.cwv_progress(strategy)})


def _load_psi_key() -> str:
    try:
        cfg = json.loads((ROOT.parent / "state" / "psi_config.json").read_text())
        return cfg.get("psi_api_key", "")
    except Exception:
        return ""


@app.route("/api/seo/cwv/scan/start", methods=["POST"])
def api_cwv_scan_start():
    body = request.get_json(silent=True) or {}
    strategy = body.get("strategy", "mobile")
    api_key = body.get("api_key", "").strip() or _load_psi_key()
    mode = body.get("mode", "top")       # "top" | "custom"
    url_type = body.get("url_type", "product")
    limit = min(int(body.get("limit", 30)), 200)

    skip_scanned = bool(body.get("skip_scanned", False))
    if mode == "custom":
        urls = [u.strip() for u in body.get("urls", []) if u.strip()]
    else:
        urls = cwv_mod.get_top_urls(limit=limit, url_type=url_type, skip_scanned=skip_scanned, strategy=strategy)

    if not urls:
        return jsonify({"ok": False, "error": "Không có URL nào để scan"})

    ok = cwv_mod.start_scan_async(urls, api_key=api_key, strategy=strategy)
    return jsonify({"ok": ok, "total": len(urls),
                    "message": "Đã bắt đầu scan" if ok else "Đang có scan chạy rồi"})


@app.route("/api/seo/cwv/scan/start-all", methods=["POST"])
def api_cwv_scan_start_all():
    """Quét All Batch — chain 8 phase: mobile×(product→collection→blog→page) → desktop×(...)."""
    body = request.get_json(silent=True) or {}
    api_key = body.get("api_key", "").strip() or _load_psi_key()
    ok = cwv_mod.start_chain_async(api_key=api_key)
    return jsonify({"ok": ok, "message": "Đã bắt đầu Quét All Batch" if ok else "Đang có scan chạy rồi"})


@app.route("/api/seo/cwv/scan/stop", methods=["POST"])
def api_cwv_scan_stop():
    cwv_mod.stop_scan()
    return jsonify({"ok": True})


@app.route("/api/seo/cwv/clear", methods=["POST"])
def api_cwv_clear():
    strategy = (request.get_json(silent=True) or {}).get("strategy")
    db.cwv_clear(strategy)
    return jsonify({"ok": True})


# ─── CWV Sync từ GitHub Actions ─────────────────────────────────────────
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/nghiango4554/nox-1/master"
GITHUB_API_BASE = "https://api.github.com/repos/nghiango4554/nox-1"


@app.route("/api/seo/cwv/sync-github", methods=["POST"])
def api_cwv_sync_github():
    """Pull JSON kết quả CWV scan mới nhất từ GitHub Actions → upsert vào seo_cwv local.

    Đọc data/cwv_results/_latest.json → fetch từng file con → upsert.
    """
    try:
        # 1. Lấy pointer latest
        r = requests.get(f"{GITHUB_RAW_BASE}/data/cwv_results/_latest.json", timeout=15)
        if r.status_code != 200:
            return jsonify({"ok": False, "error": f"_latest.json HTTP {r.status_code}"}), 502
        latest = r.json()
        latest_date = latest.get("latest_date")
        files = latest.get("files") or []
        if not latest_date or not files:
            return jsonify({"ok": False, "error": "latest pointer thiếu date/files"}), 502

        # 2. Fetch + upsert
        total_upserted = 0
        total_failed = 0
        per_file = []
        for fname in files:
            url = f"{GITHUB_RAW_BASE}/data/cwv_results/{latest_date}/{fname}"
            try:
                fr = requests.get(url, timeout=30)
                if fr.status_code != 200:
                    per_file.append({"file": fname, "ok": False, "error": f"HTTP {fr.status_code}"})
                    total_failed += 1
                    continue
                payload = fr.json()
                results = payload.get("results") or []
                upserted = 0
                for res in results:
                    if res.get("ok"):
                        db.cwv_upsert(res)
                        upserted += 1
                per_file.append({"file": fname, "ok": True, "upserted": upserted, "total": len(results)})
                total_upserted += upserted
            except Exception as e:
                per_file.append({"file": fname, "ok": False, "error": str(e)[:200]})
                total_failed += 1

        # 3. Lưu state sync gần nhất (file)
        try:
            sync_state_path = Path(__file__).parent / "data" / "cwv_last_sync.json"
            sync_state_path.parent.mkdir(parents=True, exist_ok=True)
            sync_state_path.write_text(json.dumps({
                "synced_at": datetime.now().isoformat(timespec="seconds"),
                "from_date": latest_date,
                "upserted": total_upserted,
                "failed_files": total_failed,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "latest_date": latest_date,
            "files_processed": len(files),
            "upserted": total_upserted,
            "failed_files": total_failed,
            "detail": per_file,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 500


@app.route("/api/seo/cwv/sync-status")
def api_cwv_sync_status():
    """Trạng thái sync GitHub gần nhất + có scan mới hơn local không."""
    info = {"last_sync": None, "remote_latest": None, "has_new": False}
    try:
        sync_state_path = Path(__file__).parent / "data" / "cwv_last_sync.json"
        if sync_state_path.exists():
            info["last_sync"] = json.loads(sync_state_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        r = requests.get(f"{GITHUB_RAW_BASE}/data/cwv_results/_latest.json", timeout=10)
        if r.status_code == 200:
            remote = r.json()
            info["remote_latest"] = remote
            local_date = (info["last_sync"] or {}).get("from_date") if info["last_sync"] else None
            if remote.get("latest_date") and remote["latest_date"] != local_date:
                info["has_new"] = True
    except Exception as e:
        info["remote_error"] = str(e)[:200]
    return jsonify(info)


# ─────────────────────────── SP THIẾU MÔ TẢ ───────────────────────────


@app.route("/seo/empty-desc")
def seo_empty_desc_page():
    try:
        threshold = int(request.args.get("threshold") or seo_mod.EMPTY_DESC_THRESHOLD)
    except ValueError:
        threshold = seo_mod.EMPTY_DESC_THRESHOLD
    threshold = max(0, min(threshold, 1000))
    show_all = request.args.get("all") == "1"
    items = db.seo_empty_desc_list(
        url_type="product",
        threshold=threshold,
        only_empty=not show_all,
        limit=2000,
    )
    summary = db.seo_empty_desc_summary(threshold=threshold)
    state = seo_mod.empty_desc_state()
    return render_template(
        "seo_empty_desc.html",
        items=items, summary=summary, state=state,
        threshold=threshold, show_all=show_all,
    )


@app.route("/seo/empty-desc/scan", methods=["POST"])
def seo_empty_desc_scan():
    try:
        threshold = int(request.form.get("threshold") or seo_mod.EMPTY_DESC_THRESHOLD)
    except ValueError:
        threshold = seo_mod.EMPTY_DESC_THRESHOLD
    threshold = max(0, min(threshold, 1000))
    try:
        limit = int(request.form.get("limit") or 0) or None
    except ValueError:
        limit = None
    started = seo_mod.start_empty_desc_scan_async(threshold=threshold, limit=limit)
    if started:
        flash(f"📭 Đã bắt đầu quét SP thiếu mô tả (ngưỡng {threshold} từ).", "success")
    else:
        flash("⏳ Đang có lượt quét chạy — chờ xong mới chạy lượt mới.", "info")
    return redirect(url_for("seo_empty_desc_page", threshold=threshold))


@app.route("/api/seo/empty-desc/status")
def seo_empty_desc_status():
    return jsonify({
        "state": seo_mod.empty_desc_state(),
        "summary": db.seo_empty_desc_summary(),
    })


# ─────────────────────────── HARAVAN PRODUCT EDIT INLINE ───────────────────────────


# Whitelist các field cho phép edit qua API (tránh inject)
HV_EDITABLE_FIELDS = {"title", "vendor", "product_type", "tags",
                       "metafields_global_title_tag", "metafields_global_description_tag"}

# Map field UI → field API Haravan + DB local
HV_FIELD_API_MAP = {
    "title": "title",
    "vendor": "vendor",
    "product_type": "product_type",
    "tags": "tags",
    "meta_title": "metafields_global_title_tag",
    "meta_description": "metafields_global_description_tag",
}
HV_FIELD_DB_MAP = {
    "title": "title",
    "vendor": "vendor",
    "product_type": "product_type",
    "tags": "tags",
    "meta_title": "meta_title",
    "meta_description": "meta_description",
}


@app.route("/api/haravan/products/<int:haravan_id>/edit", methods=["POST"])
def api_haravan_product_edit(haravan_id):
    """Inline edit 1 field SP Haravan: push API + update DB local."""
    import haravan_client as hv
    data = request.get_json(force=True) or {}
    field = (data.get("field") or "").strip()
    value = data.get("value")
    if field not in HV_FIELD_API_MAP:
        return jsonify({"error": f"field không hợp lệ: {field}"}), 400
    api_field = HV_FIELD_API_MAP[field]
    db_field = HV_FIELD_DB_MAP[field]

    try:
        # SEO flat field: PUT qua /products/{id}.json — theme đọc field flat (KHÔNG đọc
        # từ /products/{id}/metafields.json dù endpoint đó cũng nhận data). Verified 15/5.
        hv.update_product(haravan_id, {api_field: value})
    except Exception as e:
        return jsonify({"error": f"Haravan API error: {e.__class__.__name__}: {str(e)[:200]}"}), 502

    # Update DB local
    conn = db.get_conn()
    conn.execute(
        f"UPDATE haravan_products SET {db_field}=?, last_synced=? WHERE haravan_id=?",
        (value, datetime.now().isoformat(timespec="seconds"), haravan_id),
    )
    conn.commit()
    conn.close()

    db.activity_log(
        kind="hv_edit", icon="✏️",
        title=f"Sửa SP Haravan: {field}",
        description=f"Value: {(value or '')[:80]}",
        href=url_for("haravan_product_detail", haravan_id=haravan_id),
    )
    return jsonify({"ok": True, "field": field, "value": value})


# ─────────────────────────── HARAVAN BLOG AI REWRITE ───────────────────────────


@app.route("/haravan/blogs/<int:page_id>/ai-rewrite", methods=["GET"])
def haravan_blog_ai_rewrite(page_id):
    """Pre-fill form AI writer với info bài blog cũ → AI viết bản mới."""
    p = db.seo_get_page(page_id)
    if not p or p.get("url_type") != "blog":
        flash("Không tìm thấy bài blog.", "error")
        return redirect(url_for("haravan_blogs"))

    # Pre-fill blog writer form: dùng title cũ làm "product_name"
    title = p.get("title") or "(không title)"
    specs = (
        f"URL gốc: {p.get('url')}\n"
        f"Title hiện tại: {title}\n"
        f"Meta description hiện tại: {p.get('meta_desc') or '(thiếu)'}\n"
        f"H1 hiện tại: {p.get('h1') or '(thiếu)'}\n"
        f"Word count hiện tại: {p.get('word_count') or 0}\n"
        f"Điểm SEO hiện tại: {p.get('score') or '?'}/100\n"
        f"\nViết lại bài này theo rule v2 — giữ nguyên CHỦ ĐỀ + THÔNG TIN CHÍNH "
        f"nhưng cải thiện cấu trúc, độ dài, meta, FAQ. Không đổi keyword chính."
    )
    return render_template(
        "blog_writer.html",
        product_types=PRODUCT_TYPES_FOR_BLOG,
        product_info={
            "product_name": title,
            "product_type": "Khác",
            "vendor": "",
            "specs": specs,
            "usp": f"Viết lại blog cũ điểm {p.get('score') or '?'}/100 — cải thiện SEO",
        },
        rewrite_source={"id": page_id, "url": p.get("url"), "old_score": p.get("score")},
    )


# ─────────────────────────── LIBRARY STANDALONE PAGE ───────────────────────────


@app.route("/library")
def library_page():
    """Trang thư viện ảnh standalone — duyệt thumbnail toàn FB-Library."""
    return render_template("library.html")


# ─────────────────────────── AI BLOG WRITER (kept for haravan_blog_ai_rewrite) ───────────────────────────


PRODUCT_TYPES_FOR_BLOG = [
    "CPU", "VGA / Card đồ họa", "RAM", "MAINBOARD", "SSD", "HDD",
    "NGUỒN / Power Supply", "VỎ CASE", "TẢN NHIỆT", "MÀN HÌNH",
    "BÀN PHÍM", "CHUỘT", "TAI NGHE", "LAPTOP", "PC",
    "GHẾ GAMING", "BÀN GAMING", "MICRO", "WEBCAM", "Khác",
]


# Trang `/blog-writer` cũ (form 1-shot, không lưu DB) đã bị xoá.
# Workflow viết SP mới chuyển sang `/content-jobs` — có quản lý trạng thái + sync Haravan.
# Template blog_writer.html vẫn dùng cho `/haravan/blogs/<id>/ai-rewrite` (rewrite blog cũ).


@app.route("/blog-writer")
def blog_writer_redirect():
    return redirect(url_for("content_jobs_list_page"))


# ─────────────────────────── CONTENT JOBS — quản lý bài viết AI cho SP ───────────────────────────


import content_writer
import internal_links


# ─────────────────────────── COLLECTION CONTENT ───────────────────────────


def _collection_jobs_list(status: str = None):
    conn = db.get_conn()
    sql = "SELECT * FROM collection_jobs"
    args = []
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY id ASC"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _collection_jobs_get(job_id: int):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM collection_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _collection_jobs_update(job_id: int, **fields):
    if not fields: return
    # Auto-compute quality score nếu có update title/meta/body
    if any(k in fields for k in ("edited_title", "edited_meta", "edited_body_html")):
        # Fetch row hiện tại để có data chưa update
        row = _collection_jobs_get(job_id) or {}
        title = fields.get("edited_title", row.get("edited_title")) or ""
        meta = fields.get("edited_meta", row.get("edited_meta")) or ""
        body = fields.get("edited_body_html", row.get("edited_body_html")) or ""
        if title or meta or body:
            try:
                import seo_quality
                rate = seo_quality.rate_content(title, meta, body, url_type="collection")
                fields["quality_score"] = rate["score"]
                fields["readability_score"] = int(rate["readability"].get("score", 0))
                fields["quality_breakdown"] = json.dumps({
                    "breakdown": {k: {kk: vv for kk, vv in v.items() if kk in ("score", "max")}
                                   for k, v in rate["breakdown"].items()},
                    "issues_high": rate["issues_high"],
                    "issues_med": rate["issues_med"],
                    "issues_low": rate["issues_low"],
                    "tier": rate["tier"],
                }, ensure_ascii=False)
            except Exception as e:
                print(f"[quality_score] err: {e}")
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    keys = list(fields.keys())
    sets = ", ".join(f"{k}=?" for k in keys)
    conn = db.get_conn()
    conn.execute(f"UPDATE collection_jobs SET {sets} WHERE id=?",
                 [*[fields[k] for k in keys], job_id])
    conn.commit()
    conn.close()


def _build_tier_groups(all_jobs):
    """Group jobs by tier1 → tier2, maintaining nav order from taxonomy JSON."""
    import json as _json
    tax_path = os.path.join(os.path.dirname(__file__), "data", "collection_taxonomy.json")
    try:
        with open(tax_path, encoding="utf-8") as f:
            tax_data = _json.load(f)
        t1_order = list(tax_data["taxonomy"].keys())
    except Exception:
        t1_order = []

    # Build tier1 → tier2 → jobs mapping
    t1_map = {}  # t1_handle → {name, t2_map}
    for j in all_jobs:
        t1h = j.get("tier1_handle") or "uncategorized"
        t1n = j.get("tier1_name") or "Chưa phân loại"
        t2h = j.get("tier2_handle") or t1h
        t2n = j.get("tier2_name") or t1n
        if t1h not in t1_map:
            t1_map[t1h] = {"name": t1n, "handle": t1h, "t2_map": {}}
        t2_map = t1_map[t1h]["t2_map"]
        if t2h not in t2_map:
            t2_map[t2h] = {"name": t2n, "handle": t2h, "jobs": []}
        t2_map[t2h]["jobs"].append(j)

    # Sort tier1 by nav order, then alphabetical for unknowns
    def t1_sort_key(h):
        try: return t1_order.index(h)
        except ValueError: return 9999

    # Build final list with stats
    tier_groups = []
    for t1h in sorted(t1_map.keys(), key=t1_sort_key):
        t1v = t1_map[t1h]
        t2_groups = []
        for t2h, t2v in t1v["t2_map"].items():
            t2_stats = {}
            for s in ("pending", "draft", "synced", "failed", "existing", "drafting"):
                t2_stats[s] = sum(1 for j in t2v["jobs"] if j["status"] == s)
            t2_stats["total"] = len(t2v["jobs"])
            t2_stats["done"] = t2_stats["synced"] + t2_stats["existing"]
            t2_stats["active"] = t2_stats["draft"] + t2_stats["pending"] + t2_stats["failed"]
            t2_groups.append({**t2v, "stats": t2_stats})

        t1_stats = {}
        all_t1_jobs = [j for g in t2_groups for j in g["jobs"]]
        for s in ("pending", "draft", "synced", "failed", "existing", "drafting"):
            t1_stats[s] = sum(1 for j in all_t1_jobs if j["status"] == s)
        t1_stats["total"] = len(all_t1_jobs)
        t1_stats["done"] = t1_stats["synced"] + t1_stats["existing"]
        t1_stats["pct"] = round(t1_stats["done"] / t1_stats["total"] * 100) if t1_stats["total"] else 0

        tier_groups.append({
            "name": t1v["name"], "handle": t1h,
            "tier2_groups": t2_groups,
            "stats": t1_stats,
        })
    return tier_groups


@app.route("/collection-content")
def collection_content_page():
    status_filter = request.args.get("status") or None
    view = request.args.get("view") or ("tier" if not status_filter else "flat")
    jobs = _collection_jobs_list(status=status_filter)
    conn = db.get_conn()
    stats = {}
    for s in ("pending", "draft", "synced", "failed", "existing"):
        stats[s] = conn.execute("SELECT COUNT(*) FROM collection_jobs WHERE status=?", (s,)).fetchone()[0]
    stats["total"] = conn.execute("SELECT COUNT(*) FROM collection_jobs").fetchone()[0]
    conn.close()
    tier_groups = _build_tier_groups(jobs) if view == "tier" else []
    return render_template("collection_content.html", jobs=jobs, stats=stats,
                           active_status=status_filter, view=view, tier_groups=tier_groups)


@app.route("/collection-content/<int:job_id>")
def collection_content_detail_page(job_id):
    job = _collection_jobs_get(job_id)
    if not job:
        flash("Job không tồn tại.", "error")
        return redirect(url_for("collection_content_page"))
    return render_template("collection_content_detail.html", job=job)


# ─────────────────────────── CANVA OAUTH + STATUS ───────────────────────────

@app.route("/canva")
def canva_status_page():
    import canva_client
    connected = canva_client.is_connected()
    profile = None
    templates = []
    err = None
    if connected:
        try:
            profile = canva_client.get_user_profile().get("profile", {})
            templates = canva_client.list_brand_templates(limit=50)
        except Exception as e:
            err = str(e)[:300]
    return render_template("canva.html",
                           connected=connected,
                           profile=profile,
                           templates=templates,
                           err=err)


@app.route("/canva/connect")
def canva_connect():
    import canva_client
    state = secrets.token_urlsafe(24)
    auth_url, verifier = canva_client.build_auth_url(state)
    session["canva_oauth_state"] = state
    session["canva_code_verifier"] = verifier
    return redirect(auth_url)


@app.route("/canva/callback")
def canva_callback():
    import canva_client
    code = request.args.get("code")
    state = request.args.get("state")
    err = request.args.get("error")
    if err:
        flash(f"Canva OAuth lỗi: {err} ({request.args.get('error_description','')})", "error")
        return redirect(url_for("canva_status_page"))
    if not code or state != session.get("canva_oauth_state"):
        flash("Canva OAuth state không khớp (CSRF guard). Bấm Connect lại.", "error")
        return redirect(url_for("canva_status_page"))
    verifier = session.pop("canva_code_verifier", None)
    session.pop("canva_oauth_state", None)
    if not verifier:
        flash("Mất code_verifier (session expired). Connect lại.", "error")
        return redirect(url_for("canva_status_page"))
    try:
        canva_client.exchange_code(code, verifier)
        flash("✅ Kết nối Canva thành công!", "success")
    except Exception as e:
        flash(f"❌ Exchange token lỗi: {str(e)[:300]}", "error")
    return redirect(url_for("canva_status_page"))


@app.route("/canva/disconnect", methods=["POST"])
def canva_disconnect():
    import canva_client
    canva_client.clear_tokens()
    flash("Đã ngắt kết nối Canva.", "success")
    return redirect(url_for("canva_status_page"))


# ─────────────────────────── BACKGROUND GEN COLLECTION ───────────────────────────
import threading as _threading
import time as _time_bg

_GEN_BG = {
    "running": False, "stopped": False, "kind": None,
    "queue": [], "total": 0,
    "current_id": None, "current_name": None, "job_started_at": None,
    "started_at": None, "finished_at": None,
    "ok": 0, "fail": 0, "done": 0,
    "completed_durations": [], "errors": [],
}
_GEN_BG_LOCK = _threading.Lock()


def _gen_bg_worker_collection_loop():
    """Background worker — consume hàng đợi ĐỘNG: pop job từ _GEN_BG['queue'] cho tới khi cạn.

    Cho phép enqueue thêm job trong lúc đang chạy (gen lẻ / gen lại / bulk đều nối đuôi vào đây).
    """
    import collection_content_writer as ccw
    while True:
        with _GEN_BG_LOCK:
            if _GEN_BG["stopped"]:
                _GEN_BG["queue"] = []
                _GEN_BG["running"] = False
                _GEN_BG["finished_at"] = datetime.now().isoformat(timespec="seconds")
                _GEN_BG["current_id"] = None
                _GEN_BG["current_name"] = None
                _GEN_BG["job_started_at"] = None
                break
            if not _GEN_BG["queue"]:
                _GEN_BG["running"] = False
                _GEN_BG["finished_at"] = datetime.now().isoformat(timespec="seconds")
                _GEN_BG["current_id"] = None
                _GEN_BG["current_name"] = None
                _GEN_BG["job_started_at"] = None
                break
            jid = _GEN_BG["queue"][0]  # peek — giữ trong queue để UI vẫn thấy đang xử lý
            job = _collection_jobs_get(jid)
            if not job:
                _GEN_BG["fail"] += 1
                _GEN_BG["done"] += 1
                _GEN_BG["errors"].append(f"#{jid}: Job not found")
                _GEN_BG["queue"] = [x for x in _GEN_BG["queue"] if x != jid]
                continue
            _GEN_BG["current_id"] = jid
            _GEN_BG["current_name"] = job.get("collection_title") or job.get("handle") or f"#{jid}"
            _GEN_BG["job_started_at"] = datetime.now().isoformat(timespec="seconds")

        t0 = _time_bg.time()
        _collection_jobs_update(jid, status="drafting", error=None)
        try:
            ctx = ccw.fetch_collection_context(job["collection_url"])
            if not ctx.get("ok"):
                _collection_jobs_update(jid, status="failed", error=f"Fetch ctx: {ctx.get('error')}")
                with _GEN_BG_LOCK:
                    _GEN_BG["fail"] += 1
                    _GEN_BG["errors"].append(f"#{jid}: fetch ctx: {str(ctx.get('error',''))[:80]}")
            else:
                gen = ccw.gen_collection_content(
                    job["collection_url"],
                    job["collection_title"] or ctx.get("h1", ""),
                    page_title=ctx.get("page_title", ""),
                    admin_desc=ctx.get("admin_desc", ""),
                    sp_names=ctx.get("sp_names", []),
                    haravan_id=job.get("haravan_id"),
                )
                if not gen.get("ok"):
                    _collection_jobs_update(jid, status="failed", error=gen.get("error"))
                    with _GEN_BG_LOCK:
                        _GEN_BG["fail"] += 1
                        _GEN_BG["errors"].append(f"#{jid}: {str(gen.get('error',''))[:80]}")
                else:
                    _collection_jobs_update(
                        jid,
                        edited_title=gen["title"], edited_meta=gen["meta"],
                        edited_body_html=gen["body_html"],
                        status="draft",
                        ai_generated_at=datetime.now().isoformat(timespec="seconds"),
                        error=None,
                    )
                    with _GEN_BG_LOCK:
                        _GEN_BG["ok"] += 1
        except Exception as e:
            _collection_jobs_update(jid, status="failed", error=str(e)[:300])
            with _GEN_BG_LOCK:
                _GEN_BG["fail"] += 1
                _GEN_BG["errors"].append(f"#{jid}: {str(e)[:80]}")
        with _GEN_BG_LOCK:
            _GEN_BG["done"] += 1
            _GEN_BG["completed_durations"].append(round(_time_bg.time() - t0, 1))
            _GEN_BG["queue"] = [x for x in _GEN_BG["queue"] if x != jid]
            _GEN_BG["current_id"] = None
            _GEN_BG["current_name"] = None
            _GEN_BG["job_started_at"] = None
            if len(_GEN_BG["errors"]) > 20:
                _GEN_BG["errors"] = _GEN_BG["errors"][-20:]
        _time_bg.sleep(1)


def _enqueue_collection_gen(ids):
    """Thêm job_ids vào hàng đợi gen nền; khởi động worker nếu đang idle.

    Idle → reset counters + start worker. Đang chạy → chỉ nối đuôi (dedup current + queue).
    Trả snapshot _GEN_BG.
    """
    try:
        ids = [int(x) for x in ids]
    except Exception:
        ids = []
    start_worker = False
    with _GEN_BG_LOCK:
        if not _GEN_BG.get("running"):
            _GEN_BG.update({
                "running": True, "stopped": False, "kind": "collection",
                "queue": [], "total": 0,
                "current_id": None, "current_name": None, "job_started_at": None,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "finished_at": None,
                "ok": 0, "fail": 0, "done": 0,
                "completed_durations": [], "errors": [],
            })
            start_worker = True
        for jid in ids:
            if jid == _GEN_BG.get("current_id") or jid in _GEN_BG["queue"]:
                continue
            _GEN_BG["queue"].append(jid)
            _GEN_BG["total"] += 1
        snapshot = dict(_GEN_BG)
    if start_worker:
        t = _threading.Thread(target=_gen_bg_worker_collection_loop, daemon=True)
        t.start()
    return snapshot


@app.route("/collection-content/gen-bg", methods=["POST"])
def collection_content_gen_bg():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids") or []
    try:
        ids = [int(x) for x in ids]
    except Exception:
        return jsonify({"ok": False, "error": "ids phải là list int"}), 400
    if not ids:
        return jsonify({"ok": False, "error": "Thiếu list ids"}), 400
    state = _enqueue_collection_gen(ids)
    return jsonify({"ok": True, "state": state})


@app.route("/collection-content/gen-status")
def collection_content_gen_status():
    return jsonify(dict(_GEN_BG))


@app.route("/collection-content/gen-stop", methods=["POST"])
def collection_content_gen_stop():
    with _GEN_BG_LOCK:
        _GEN_BG["stopped"] = True
    return jsonify({"ok": True, "state": dict(_GEN_BG)})


@app.route("/collection-content/<int:job_id>/gen", methods=["POST"])
def collection_content_gen(job_id):
    """Gen lẻ / gen lại 1 collection — KHÔNG chạy đồng bộ nữa mà ĐẨY VÀO HÀNG ĐỢI nền.

    Bấm nhiều bài liên tiếp → nối đuôi nhau, worker xử lý tuần tự. Client poll /gen-status.
    """
    job = _collection_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    state = _enqueue_collection_gen([job_id])
    queue = state.get("queue", [])
    if state.get("current_id") == job_id:
        position = 0  # đang gen ngay
    elif job_id in queue:
        position = queue.index(job_id) + 1
    else:
        position = 0
    return jsonify({
        "ok": True, "queued": True,
        "position": position,
        "queue_len": len(queue),
        "running": state.get("running", False),
        "state": state,
    })


@app.route("/collection-content/<int:job_id>/gen-title-meta", methods=["POST"])
def collection_content_gen_title_meta(job_id):
    """Gen LẠI title HOẶC meta HOẶC cả 2 — payload {field: 'title'|'meta'|'both'}."""
    job = _collection_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    payload = request.get_json(silent=True) or {}
    field = payload.get("field", "both")
    if field not in ("title", "meta", "both"):
        field = "both"
    import collection_content_writer as ccw
    try:
        ctx = ccw.fetch_collection_context(job["collection_url"])
        gen = ccw.gen_title_meta_only(
            job["collection_url"],
            job["collection_title"] or (ctx.get("h1") if ctx.get("ok") else ""),
            page_title=ctx.get("page_title", "") if ctx.get("ok") else "",
            admin_desc=ctx.get("admin_desc", "") if ctx.get("ok") else "",
            sp_names=ctx.get("sp_names", []) if ctx.get("ok") else [],
            existing_title=job.get("edited_title") or "",
            existing_meta=job.get("edited_meta") or "",
            field=field,
        )
        if not gen.get("ok"):
            return jsonify(gen), 500
        update_kwargs = {"ai_generated_at": datetime.now().isoformat(timespec="seconds")}
        if "title" in gen:
            update_kwargs["edited_title"] = gen["title"]
        if "meta" in gen:
            update_kwargs["edited_meta"] = gen["meta"]
        _collection_jobs_update(job_id, **update_kwargs)
        return jsonify({"ok": True, **gen})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _save_seo_job_edits(update_fn, job_id):
    """Lưu edit title/meta/body từ form detail (CHUNG cho collection + blog).

    update_fn tự lo recompute quality/readability khi có edited_* (xem _*_jobs_update).
    """
    payload = request.get_json(silent=True) or request.form
    update_fn(job_id,
              edited_title=(payload.get("title") or "").strip(),
              edited_meta=(payload.get("meta") or "").strip(),
              edited_body_html=(payload.get("body") or "").strip())
    return jsonify({"ok": True})


@app.route("/collection-content/<int:job_id>/save", methods=["POST"])
def collection_content_save(job_id):
    return _save_seo_job_edits(_collection_jobs_update, job_id)


@app.route("/collection-content/<int:job_id>/sync", methods=["POST"])
def collection_content_sync(job_id):
    job = _collection_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    if not job.get("haravan_id"):
        return jsonify({"ok": False, "error": "Thiếu haravan_id (collection chưa tồn tại trên Haravan)"}), 400
    if not job.get("edited_title") or not job.get("edited_body_html"):
        return jsonify({"ok": False, "error": "Chưa có title/body — gen AI trước"}), 400
    import collection_content_writer as ccw
    res = ccw.sync_collection_to_haravan(
        int(job["haravan_id"]),
        job["edited_title"],
        job.get("edited_meta") or "",
        job["edited_body_html"],
    )
    # apply_sync_result reset 'failed' khi fail (kể cả khi trước đó là 'synced')
    if job_sync.apply_sync_result(_collection_jobs_update, job_id, res):
        return jsonify({"ok": True})
    return jsonify(res), 500


@app.route("/collection-content/sync-all", methods=["POST"])
def collection_content_sync_all():
    jobs = _collection_jobs_list(status="draft")
    ok = fail = 0
    errors = []
    import collection_content_writer as ccw
    import time
    for job in jobs:
        if not job.get("haravan_id") or not job.get("edited_title") or not job.get("edited_body_html"):
            fail += 1; errors.append(f"#{job['id']}: thiếu data")
            continue
        try:
            res = ccw.sync_collection_to_haravan(
                int(job["haravan_id"]),
                job["edited_title"], job.get("edited_meta") or "",
                job["edited_body_html"],
            )
            if job_sync.apply_sync_result(_collection_jobs_update, job["id"], res):
                ok += 1
            else:
                fail += 1; errors.append(f"#{job['id']}: {res.get('error', '')[:80]}")
        except Exception as e:
            fail += 1; errors.append(f"#{job['id']}: {str(e)[:80]}")
        time.sleep(0.8)
    flash(f"🚀 Sync xong: {ok} OK, {fail} fail." + (f" Sample lỗi: {errors[0]}" if errors else ""),
          "success" if ok else "error")
    return redirect(url_for("collection_content_page"))


# ─────────────────────────── BLOG CONTENT (bài viết huong-dan/news) ───────────────────────────

# SSE batch-gen streams: stream_id → {queue, stop_flag}
_batch_streams: dict = {}


def _blog_jobs_list(status: str = None, source: str = None, blog: str = None):
    conn = db.get_conn()
    sql = "SELECT * FROM blog_jobs WHERE 1=1"
    args = []
    if status == "not_gen":          # chưa gen = pending + failed
        sql += " AND status IN ('pending','failed')"
    elif status == "generated":      # đã gen = draft + synced
        sql += " AND status IN ('draft','synced')"
    elif status:
        sql += " AND status = ?"
        args.append(status)
    if source:
        sql += " AND source = ?"
        args.append(source)
    if blog:
        sql += " AND target_blog = ?"
        args.append(blog)
    sql += " ORDER BY CASE WHEN pillar LIKE '%Autodesk%' THEN 0 ELSE 1 END ASC, COALESCE(pillar,'zzz') ASC, click DESC, id ASC"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _blog_jobs_get(job_id: int):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM blog_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _blog_jobs_update(job_id: int, **fields):
    if not fields: return
    if any(k in fields for k in ("edited_title", "edited_meta", "edited_body_html")):
        row = _blog_jobs_get(job_id) or {}
        title = fields.get("edited_title", row.get("edited_title")) or ""
        meta = fields.get("edited_meta", row.get("edited_meta")) or ""
        body = fields.get("edited_body_html", row.get("edited_body_html")) or ""
        if title or meta or body:
            try:
                import seo_quality
                rate = seo_quality.rate_content(title, meta, body, url_type="blog")
                fields["quality_score"] = rate["score"]
                fields["readability_score"] = int(rate["readability"].get("score", 0))
                fields["quality_breakdown"] = json.dumps({
                    "breakdown": {k: {kk: vv for kk, vv in v.items() if kk in ("score", "max")}
                                   for k, v in rate["breakdown"].items()},
                    "issues_high": rate["issues_high"],
                    "issues_med": rate["issues_med"],
                    "issues_low": rate["issues_low"],
                    "tier": rate["tier"],
                }, ensure_ascii=False)
                # Word count
                import re as _re_wc
                text_only = _re_wc.sub(r"<[^>]+>", " ", body)
                fields["word_count"] = len([w for w in text_only.split() if w])
            except Exception as e:
                print(f"[blog quality_score] err: {e}")
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    keys = list(fields.keys())
    sets = ", ".join(f"{k}=?" for k in keys)
    conn = db.get_conn()
    conn.execute(f"UPDATE blog_jobs SET {sets} WHERE id=?",
                 [*[fields[k] for k in keys], job_id])
    conn.commit()
    conn.close()


@app.route("/blog-content")
def blog_content_page():
    status_filter = request.args.get("status") or None
    source_filter = request.args.get("source") or None
    blog_filter = request.args.get("blog") or None
    jobs = _blog_jobs_list(status=status_filter, source=source_filter, blog=blog_filter)
    import image_gather
    for j in jobs:  # badge ảnh: số đã gom · số đã chọn
        items = image_gather.load_meta(j["id"]).get("items", [])
        j["img_count"] = len(items)
        j["img_selected"] = sum(1 for it in items if it.get("selected"))
    conn = db.get_conn()
    stats = {}
    for s in ("pending", "draft", "synced", "failed"):
        stats[s] = conn.execute("SELECT COUNT(*) FROM blog_jobs WHERE status=?", (s,)).fetchone()[0]
    stats["total"] = conn.execute("SELECT COUNT(*) FROM blog_jobs").fetchone()[0]
    blog_counts = {r[0]: r[1] for r in conn.execute(
        "SELECT target_blog, COUNT(*) FROM blog_jobs GROUP BY target_blog").fetchall()}
    conn.close()
    return render_template("blog_content.html", jobs=jobs, stats=stats,
                           active_status=status_filter, active_blog=blog_filter,
                           blog_counts=blog_counts, shop="sintech.myharavan.com")


@app.route("/blog-content/<int:job_id>")
def blog_content_detail_page(job_id):
    job = _blog_jobs_get(job_id)
    if not job:
        flash("Bài không tồn tại.", "error")
        return redirect(url_for("blog_content_page"))
    import image_gather
    meta = image_gather.load_meta(job_id)
    images = meta.get("items", []) if meta else []
    for it in images:
        it["thumb_url"] = url_for("blog_content_image", job_id=job_id, filename=it["file"])
    return render_template("blog_content_detail.html", job=job, images=images)


def _run_blog_gen(job_id, gather_images=True):
    """Gen 1 bài blog. ai_pillar → brief-mode (viết mới); seo_seed → scrape-mode (cào URL cũ).
    Sau khi gen xong tự gom ảnh ứng viên (T2). Trả dict gen ({ok,...} hoặc {ok:False,error})."""
    job = _blog_jobs_get(job_id)
    if not job:
        return {"ok": False, "error": "Job không tồn tại"}
    import blog_content_writer as bcw
    _blog_jobs_update(job_id, status="drafting", error=None)
    try:
        if job.get("source") == "ai_pillar":
            gen = bcw.gen_blog_content_from_brief(job)
        else:
            ctx = bcw.fetch_blog_context(job["blog_url"])
            if not ctx.get("ok"):
                _blog_jobs_update(job_id, status="failed", error=f"Fetch ctx: {ctx.get('error')}")
                return {"ok": False, "error": ctx.get("error")}
            gen = bcw.gen_blog_content(
                job["blog_url"], job["article_title"] or ctx.get("h1", ""),
                page_title=ctx.get("page_title", ""), existing_meta=ctx.get("existing_meta", ""),
                body_snippet=ctx.get("body_snippet", ""))
        if not gen.get("ok"):
            _blog_jobs_update(job_id, status="failed", error=gen.get("error"))
            return gen
        body_html = gen["body_html"]
        if gather_images:
            try:
                import image_gather
                q = gen["title"] or job.get("article_title") or ""
                # ai_pillar: handle là slug (không phải SP) → để rỗng, match theo keyword
                handles = [job["handle"]] if (job.get("source") != "ai_pillar" and job.get("handle")) else []
                res_img = image_gather.gather(job_id, q, product_handles=handles, max_n=10)
                # AI tự chọn 2-3 ảnh (ưu tiên ảnh SP Sintech) + tự chèn vào bài → em chỉ vào duyệt
                picked = image_gather.auto_pick(res_img.get("items", []), n=3)
                if picked:
                    body_html, used = image_gather.insert_into_body(gen["body_html"], picked)
                    image_gather.mark_selected(job_id, [u["idx"] for u in used])
            except Exception as e:
                print(f"[blog gen auto-image] #{job_id}: {e}")
        _blog_jobs_update(
            job_id, edited_title=gen["title"], edited_meta=gen["meta"],
            edited_body_html=body_html, status="draft",
            ai_generated_at=datetime.now().isoformat(timespec="seconds"), error=None)
        gen["body_html"] = body_html
        return {"ok": True, **gen}
    except Exception as e:
        _blog_jobs_update(job_id, status="failed", error=str(e)[:300])
        return {"ok": False, "error": str(e)}


@app.route("/blog-content/<int:job_id>/gen", methods=["POST"])
def blog_content_gen(job_id):
    if not _blog_jobs_get(job_id):
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    res = _run_blog_gen(job_id)
    return jsonify(res) if res.get("ok") else (jsonify(res), 500)


def _run_blog_gen_full(job_id: int) -> dict:
    """2-pass gen full: outline → content → auto-image. Dùng chung cho route lẻ + batch."""
    job = _blog_jobs_get(job_id)
    if not job:
        return {"ok": False, "error": "Job không tồn tại"}
    import blog_content_writer as bcw
    _blog_jobs_update(job_id, status="drafting", error=None)
    try:
        outline_res = bcw.gen_outline(
            article_title=job.get("article_title") or job.get("handle") or "",
            keyword=job.get("keyword") or "",
            intent=job.get("intent") or "",
            unique_angle=job.get("unique_angle") or "",
        )
        if not outline_res.get("ok"):
            _blog_jobs_update(job_id, status="failed", error=f"Outline: {outline_res.get('error')}")
            return {"ok": False, "error": outline_res.get("error")}
        outline_text = outline_res["outline_text"]
        _blog_jobs_update(job_id, outline=outline_text)

        gen = bcw.gen_blog_with_outline(job, outline_text)
        if not gen.get("ok"):
            _blog_jobs_update(job_id, status="failed", error=gen.get("error"))
            return {"ok": False, "error": gen.get("error")}

        body_html = gen["body_html"]
        try:
            import image_gather
            q = gen["title"] or job.get("article_title") or ""
            handles = [job["handle"]] if (job.get("source") != "ai_pillar" and job.get("handle")) else []
            res_img = image_gather.gather(job_id, q, product_handles=handles, max_n=10)
            picked = image_gather.auto_pick(res_img.get("items", []), n=3)
            if picked:
                body_html, used = image_gather.insert_into_body(gen["body_html"], picked)
                image_gather.mark_selected(job_id, [u["idx"] for u in used])
        except Exception as e:
            print(f"[gen-full auto-image] #{job_id}: {e}")

        _blog_jobs_update(
            job_id, edited_title=gen["title"], edited_meta=gen["meta"],
            edited_body_html=body_html, status="draft",
            ai_generated_at=datetime.now().isoformat(timespec="seconds"), error=None)

        return {"ok": True, "title": gen["title"], "meta_len": len(gen["meta"]),
                "h2_count": len(outline_res.get("outline_json") or [])}
    except Exception as e:
        _blog_jobs_update(job_id, status="failed", error=str(e)[:300])
        return {"ok": False, "error": str(e)}


@app.route("/blog-content/<int:job_id>/gen-full", methods=["POST"])
def blog_content_gen_full(job_id):
    if not _blog_jobs_get(job_id):
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    res = _run_blog_gen_full(job_id)
    return jsonify(res) if res.get("ok") else (jsonify(res), 500)


@app.route("/blog-content/batch-gen", methods=["POST"])
def blog_content_batch_gen():
    """Khởi động batch gen liên tục. Trả stream_id để client lắng nghe SSE."""
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "full")
    status_filter = data.get("status", "not_gen")
    jobs = _blog_jobs_list(status=status_filter)
    if not jobs:
        return jsonify({"ok": False, "error": "Không có bài nào trong filter này."})
    job_ids = [j["id"] for j in jobs]
    titles = {j["id"]: (j.get("article_title") or j.get("handle") or f"#{j['id']}")[:60] for j in jobs}

    stream_id = uuid.uuid4().hex[:10]
    # Dùng append-only list thay Queue → client reconnect bất kỳ lúc nào vẫn nhận đủ events
    entry = {"events": [], "stop": {"stop": False}, "done": False}
    _batch_streams[stream_id] = entry

    def push(msg):
        entry["events"].append(msg)

    def runner():
        import time as _t
        total = len(job_ids)
        done = 0
        for idx, jid in enumerate(job_ids):
            if entry["stop"]["stop"]:
                push({"type": "stopped", "done": done, "total": total})
                break
            title = titles.get(jid, f"#{jid}")
            push({"type": "start", "id": jid, "title": title, "idx": idx + 1, "total": total})
            try:
                res = _run_blog_gen_full(jid) if mode == "full" else _run_blog_gen(jid)
                if res.get("ok"):
                    done += 1
                    push({"type": "done", "id": jid, "title": title, "idx": idx + 1, "total": total})
                else:
                    push({"type": "error", "id": jid, "title": title,
                          "error": (res.get("error") or "?")[:120], "idx": idx + 1, "total": total})
            except Exception as e:
                push({"type": "error", "id": jid, "title": title,
                      "error": str(e)[:120], "idx": idx + 1, "total": total})
        else:
            push({"type": "finish", "done": done, "total": total})
        entry["done"] = True
        # Giữ entry 30 phút để client kịp reconnect xem lại kết quả
        _t.sleep(1800)
        _batch_streams.pop(stream_id, None)

    threading.Thread(target=runner, daemon=True).start()
    return jsonify({"ok": True, "stream_id": stream_id, "total": len(job_ids)})


@app.route("/blog-content/batch-gen/stop/<stream_id>", methods=["POST"])
def blog_content_batch_gen_stop(stream_id):
    entry = _batch_streams.get(stream_id)
    if entry:
        entry["stop"]["stop"] = True
    return jsonify({"ok": True})


@app.route("/blog-content/batch-gen/status/<stream_id>")
def blog_content_batch_gen_status(stream_id):
    """Client hỏi stream còn active không (dùng khi reconnect)."""
    entry = _batch_streams.get(stream_id)
    if not entry:
        return jsonify({"active": False})
    return jsonify({"active": True, "done": entry["done"], "total_events": len(entry["events"])})


@app.route("/blog-content/batch-gen/stream/<stream_id>")
def blog_content_batch_gen_stream(stream_id):
    """SSE stream — client có thể reconnect bất kỳ lúc nào, nhận lại toàn bộ events từ offset."""
    entry = _batch_streams.get(stream_id)
    if not entry:
        return jsonify({"error": "Stream không tồn tại hoặc đã hết."}), 404
    # Client truyền ?from=N để nhận events từ index N (skip events đã nhận trước đó)
    start_idx = max(0, request.args.get("from", 0, type=int))

    import time as _t

    @stream_with_context
    def generate():
        yield "retry: 3000\n\n"
        idx = start_idx
        while True:
            events = entry["events"]
            # Flush tất cả events từ idx trở đi
            while idx < len(events):
                yield f"data: {json.dumps(events[idx], ensure_ascii=False)}\n\n"
                idx += 1
            # Nếu đã xong thì kết thúc stream
            if entry["done"]:
                break
            # Chưa xong → wait polling
            _t.sleep(0.4)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/blog-content/<int:job_id>/gen-title", methods=["POST"])
def blog_content_gen_title(job_id):
    """Gen lại title 45-61c từ title/keyword hiện tại của job."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    current_title = job.get("edited_title") or job.get("article_title") or job.get("handle") or ""
    keyword = job.get("keyword") or ""
    body_snippet = ""
    if job.get("edited_body_html"):
        import re as _re
        body_snippet = _re.sub(r"<[^>]+>", " ", job["edited_body_html"])[:800]
    try:
        import ai_provider
        sys_p = "Bạn là SEO copywriter cho Sintech.vn (shop PC/laptop/gaming gear). Viết title SEO tiếng Việt."
        usr_p = (f"Tiêu đề hiện tại: {current_title}\nKeyword: {keyword or '(suy ra từ tiêu đề)'}\n"
                 f"Snippet nội dung: {body_snippet or '(chưa có)'}\n\n"
                 f"Viết lại title 45-61 ký tự, bám keyword, KHÔNG chứa 'Sintech', tự nhiên buyer-facing. "
                 f"Chỉ trả text thuần, không dấu ngoặc kép.")
        raw = ai_provider.call_ai(sys_p, usr_p, timeout=60).strip()
        raw = raw.strip('"\'')
        if not (20 <= len(raw) <= 80):
            return jsonify({"ok": False, "error": f"AI trả title bất thường ({len(raw)}c): {raw[:80]}"})
        return jsonify({"ok": True, "title": raw, "len": len(raw)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/blog-content/<int:job_id>/gen-meta", methods=["POST"])
def blog_content_gen_meta(job_id):
    """Gen lại meta description 140-160c từ title + body hiện tại."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    title = job.get("edited_title") or job.get("article_title") or ""
    body_snippet = ""
    if job.get("edited_body_html"):
        import re as _re
        body_snippet = _re.sub(r"<[^>]+>", " ", job["edited_body_html"])[:1200]
    try:
        import ai_provider
        sys_p = "Bạn là SEO copywriter cho Sintech.vn (shop PC/laptop/gaming gear). Viết meta description chuẩn SEO tiếng Việt."
        usr_p = (f"Title bài: {title}\nNội dung (snippet): {body_snippet or '(chưa có)'}\n\n"
                 f"Viết meta description 140-160 ký tự: tóm tắt giá trị bài, có keyword, kết thúc bằng CTA HOA "
                 f"(XEM NGAY / KHÁM PHÁ NGAY / TÌM HIỂU NGAY / THAM KHẢO NGAY). "
                 f"Chỉ trả text thuần, không dấu ngoặc kép.")
        raw = ai_provider.call_ai(sys_p, usr_p, timeout=60).strip()
        raw = raw.strip('"\'')
        if not (100 <= len(raw) <= 200):
            return jsonify({"ok": False, "error": f"AI trả meta bất thường ({len(raw)}c): {raw[:100]}"})
        return jsonify({"ok": True, "meta": raw, "len": len(raw)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/blog-content/<int:job_id>/save", methods=["POST"])
def blog_content_save(job_id):
    return _save_seo_job_edits(_blog_jobs_update, job_id)


# blog_id Sintech theo loại bài (Open API haravan_blog). huong-dan=Hướng dẫn · news=Tin tức.
BLOG_ID_BY_TARGET = {"huong-dan": 1000960873, "news": 1000906526}


def _push_blog_to_haravan(job, publish=True):
    """Đẩy 1 bài blog lên Haravan qua Open API (haravan_blog.py — KHÔNG dùng admin metafields).
    Chưa có haravan_article_id → tạo bài MỚI (hidden = not publish). Đã có → update (giữ trạng thái).
    Trả {ok, article_id, blog_id, created} hoặc {ok:False, error}."""
    import haravan_blog
    import blog_content_writer as bcw
    title = (job.get("edited_title") or "").strip()
    body = job.get("edited_body_html") or ""
    if not title or not body:
        return {"ok": False, "error": "Chưa có title/body — gen AI trước."}
    body_html = bcw.compress_html(bcw.sanitize_pasted_html(body))
    blog_id = job.get("haravan_blog_id") or BLOG_ID_BY_TARGET.get(
        (job.get("target_blog") or "news").strip(), 1000906526)
    meta = (job.get("edited_meta") or "").strip()
    fields = {
        "title": title,
        "author": "Trọng Nghĩa",
        "body_html": body_html,
        "summary_html": meta,  # trích dẫn / excerpt
        "page_title": title,
        "meta_description": meta,
    }
    if job.get("handle"):
        fields["handle"] = job["handle"]
    if job.get("keyword"):
        fields["tags"] = job["keyword"]
    try:  # ảnh đại diện: ưu tiên hero AI (is_hero), sau đó ảnh chọn đầu tiên (URL CDN công khai)
        import image_gather
        _items = image_gather.load_meta(job["id"]).get("items", [])
        _hero = next((it for it in _items if it.get("is_hero") and it.get("origin_url")), None)
        _sel = [it for it in _items if it.get("selected") and it.get("origin_url")]
        _chosen = _hero or (_sel[0] if _sel else None)
        if _chosen:
            fields["image"] = {"src": _chosen["origin_url"]}
    except Exception:
        pass
    try:
        import haravan_client as _hc
        aid = job.get("haravan_article_id")
        if aid:
            haravan_blog.update_article(int(blog_id), int(aid), fields)
            try:
                _hc.upsert_seo_metafields("articles", int(aid), title=title, description=meta)
            except Exception:
                pass
            return {"ok": True, "article_id": int(aid), "blog_id": int(blog_id), "created": False}
        art = haravan_blog.create_article(int(blog_id), fields, hidden=not publish)
        new_aid = art.get("id")
        if new_aid:
            try:
                _hc.upsert_seo_metafields("articles", int(new_aid), title=title, description=meta)
            except Exception:
                pass
        return {"ok": True, "article_id": new_aid, "blog_id": int(blog_id), "created": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _apply_blog_push(job_id, res):
    """Map kết quả push → cập nhật blog_jobs (synced + lưu article_id/blog_id nếu vừa tạo)."""
    if not res.get("ok"):
        _blog_jobs_update(job_id, status="failed", error=(res.get("error") or "")[:500])
        return False
    upd = {"status": "synced", "synced_at": datetime.now().isoformat(timespec="seconds"), "error": None}
    if res.get("created"):
        upd["haravan_article_id"] = res.get("article_id")
        upd["haravan_blog_id"] = res.get("blog_id")
    _blog_jobs_update(job_id, **upd)
    return True


@app.route("/blog-content/<int:job_id>/sync", methods=["POST"])
def blog_content_sync(job_id):
    """Vợ đã duyệt tay → sync thẳng lên Haravan, PUBLISH hiện (Google index được)."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    res = _push_blog_to_haravan(job, publish=True)
    if _apply_blog_push(job_id, res):
        return jsonify({"ok": True, "article_id": res.get("article_id"),
                        "created": res.get("created"), "published": True})
    return jsonify(res), 500


@app.route("/blog-content/sync-all", methods=["POST"])
def blog_content_sync_all():
    jobs = _blog_jobs_list(status="draft")
    ok = fail = 0
    errors = []
    import time as _t
    for job in jobs:
        res = _push_blog_to_haravan(job, publish=True)
        if _apply_blog_push(job["id"], res):
            ok += 1
        else:
            fail += 1; errors.append(f"#{job['id']}: {res.get('error', '')[:80]}")
        _t.sleep(0.8)
    flash(f"🚀 Sync xong: {ok} OK, {fail} fail." + (f" Sample lỗi: {errors[0]}" if errors else ""),
          "success" if ok else "error")
    return redirect(url_for("blog_content_page"))


# ─────────────────────────── BLOG IMAGES (T1/T3) ───────────────────────────


def _blog_image_dir(job_id):
    return Path(__file__).parent / "data" / "blog_images" / str(job_id)


@app.route("/blog-content/<int:job_id>/gather-images", methods=["POST"])
def blog_content_gather_images(job_id):
    """Gom ảnh ứng viên về local cho job (T1). Query mặc định = title/article_title,
    product_handles mặc định = [job.handle]. Trả meta items kèm thumb_url."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    import image_gather
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or job.get("edited_title") or job.get("article_title") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "Thiếu query (chưa có title) — gen AI hoặc nhập title trước."}), 400
    handles = data.get("product_handles")
    if handles is None:
        handles = [job["handle"]] if job.get("handle") else []
    try:
        max_n = max(1, min(int(data.get("max_n") or 10), 20))
    except (TypeError, ValueError):
        max_n = 10
    try:
        res = image_gather.gather(job_id, query, product_handles=handles, max_n=max_n)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 500
    for it in res.get("items", []):
        it["thumb_url"] = url_for("blog_content_image", job_id=job_id, filename=it["file"])
    return jsonify(res)


@app.route("/blog-content/<int:job_id>/image/<path:filename>")
def blog_content_image(job_id, filename):
    """Serve ảnh ứng viên local: data/blog_images/<job_id>/<filename>."""
    folder = _blog_image_dir(job_id)
    safe = secure_filename(filename)
    if not folder.exists() or not (folder / safe).is_file():
        return "Not found", 404
    return send_from_directory(folder, safe)


@app.route("/blog-content/<int:job_id>/images/select", methods=["POST"])
def blog_content_images_select(job_id):
    """Đánh dấu ảnh đã chọn (selected=true) trong meta.json."""
    import image_gather
    meta = image_gather.load_meta(job_id)
    if not meta:
        return jsonify({"ok": False, "error": "Chưa gom ảnh cho job này."}), 400
    data = request.get_json(silent=True) or {}
    try:
        selected = {int(i) for i in (data.get("selected") or [])}
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "selected phải là list số idx."}), 400
    for it in meta.get("items", []):
        it["selected"] = it["idx"] in selected
    (_blog_image_dir(job_id) / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"ok": True, "selected": sorted(selected)})


@app.route("/blog-content/<int:job_id>/image-upload", methods=["POST"])
def blog_content_image_upload(job_id):
    """Tải 1 ảnh AI (gen ngoài bằng ChatGPT/Canva) từ máy → auto-scale 1200px →
    host lên Haravan asset_storage (URL CDN public) → trả src để chèn vào bài.
    target=hero: đồng thời ghim làm ảnh đại diện (is_hero). target=body: chỉ trả src."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Chưa chọn file ảnh."}), 400
    target = (request.form.get("target") or "body").strip()
    alt = (request.form.get("alt") or job.get("edited_title") or "").strip()[:180]
    try:
        raw = f.read()
        if not raw:
            return jsonify({"ok": False, "error": "File ảnh rỗng."}), 400
        import image_processor
        scaled = image_processor.process_blog_image(raw, max_w=1200)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Xử lý ảnh lỗi: {str(e)[:200]}"}), 400
    try:
        import cloudinary_upload
        fname = secure_filename(f.filename) or "ai_image.jpg"
        if not fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            fname += ".jpg"
        src = cloudinary_upload.upload(scaled, filename=fname)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Host ảnh lên Cloudinary lỗi: {str(e)[:240]}"}), 500
    is_hero = target == "hero"
    if is_hero:
        try:
            import image_gather
            image_gather.set_ai_hero(job_id, src, alt=alt)
        except Exception as e:
            print(f"[image-upload hero meta] #{job_id}: {e}")
    return jsonify({"ok": True, "src": src, "alt": alt, "target": target,
                    "is_hero": is_hero, "bytes": len(scaled)})


@app.route("/blog-content/<int:job_id>/image-url", methods=["POST"])
def blog_content_image_url(job_id):
    """Gắn ảnh từ 1 URL công khai có sẵn (vd Haravan Files: cdn.hstatic.net/files/...)
    vào bài — KHÔNG upload, KHÔNG scale (ảnh đã host sẵn). target=hero ghim featured."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    target = (data.get("target") or "body").strip()
    alt = (data.get("alt") or job.get("edited_title") or "").strip()[:180]
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "URL phải bắt đầu bằng http(s)://"}), 400
    is_hero = target == "hero"
    if is_hero:
        try:
            import image_gather
            image_gather.set_ai_hero(job_id, url, alt=alt)
        except Exception as e:
            print(f"[image-url hero meta] #{job_id}: {e}")
    return jsonify({"ok": True, "src": url, "alt": alt, "target": target, "is_hero": is_hero})


# ─────────────────────────── BLOG PILLARS (T4) ───────────────────────────

_PILLAR_BG = {
    "running": False, "stopped": False, "phase": None, "msg": "",
    "n_pillars": 0, "pillar_idx": 0, "pillar_total": 0, "pillar_title": "",
    "jobs_created": 0, "n_clusters": 0,
    "started_at": None, "finished_at": None, "error": None, "result": None,
}
_PILLAR_BG_LOCK = _threading.Lock()


def _pillar_progress(d):
    with _PILLAR_BG_LOCK:
        _PILLAR_BG.update(d)


def _pillar_bg_worker(n_pillars, clusters_per_pillar):
    """Chỉ gen Pillar + Cluster (đề xuất chủ đề) → seed blog_jobs status='pending'.
    KHÔNG gen nội dung — viết bài là bước riêng ở /blog-content."""
    import blog_pillar_writer as bpw
    try:
        res = bpw.generate_plan(n_pillars, clusters_per_pillar, progress=_pillar_progress)
        with _PILLAR_BG_LOCK:
            _PILLAR_BG["result"] = res
            _PILLAR_BG["jobs_created"] = res["jobs_created"]
            _PILLAR_BG["n_clusters"] = res["n_clusters"]
            _PILLAR_BG["n_pillars"] = res["n_pillars"]
    except Exception as e:
        with _PILLAR_BG_LOCK:
            _PILLAR_BG["error"] = str(e)[:300]
    finally:
        with _PILLAR_BG_LOCK:
            _PILLAR_BG["running"] = False
            _PILLAR_BG["phase"] = "done"
            _PILLAR_BG["finished_at"] = datetime.now().isoformat(timespec="seconds")


@app.route("/blog-pillars")
def blog_pillars_page():
    conn = db.get_conn()
    pillars = [dict(r) for r in conn.execute(
        "SELECT * FROM blog_pillars ORDER BY id DESC").fetchall()]
    for p in pillars:
        rows = conn.execute(
            "SELECT id, article_title, content_layer, article_type, priority, status, is_external "
            "FROM blog_jobs WHERE pillar_id=? ORDER BY id", (p["id"],)).fetchall()
        p["clusters"] = [dict(r) for r in rows]
    total_jobs = conn.execute(
        "SELECT COUNT(*) FROM blog_jobs WHERE source='ai_pillar'").fetchone()[0]
    conn.close()
    return render_template("blog_pillars.html", pillars=pillars, total_jobs=total_jobs)


@app.route("/blog-pillars/generate", methods=["POST"])
def blog_pillars_generate():
    with _PILLAR_BG_LOCK:
        if _PILLAR_BG["running"]:
            return jsonify({"ok": False, "error": "Đang chạy rồi — đợi lượt này xong."}), 409
        data = request.get_json(silent=True) or {}
        try:
            n_pillars = max(1, min(int(data.get("n_pillars") or 12), 20))
            cpp = max(1, min(int(data.get("clusters_per_pillar") or 10), 15))
        except (TypeError, ValueError):
            n_pillars, cpp = 12, 10
        _PILLAR_BG.update({
            "running": True, "stopped": False, "phase": "starting", "msg": "Khởi động...",
            "n_pillars": 0, "pillar_idx": 0, "pillar_total": n_pillars, "pillar_title": "",
            "jobs_created": 0, "n_clusters": 0,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None, "error": None, "result": None,
        })
    t = _threading.Thread(target=_pillar_bg_worker, args=(n_pillars, cpp), daemon=True)
    t.start()
    return jsonify({"ok": True, "msg": f"Bắt đầu gen {n_pillars} pillar × ~{cpp} cluster (chạy nền)."})


@app.route("/blog-pillars/stop", methods=["POST"])
def blog_pillars_stop():
    with _PILLAR_BG_LOCK:
        _PILLAR_BG["stopped"] = True
    return jsonify({"ok": True, "msg": "Đã yêu cầu dừng — sẽ dừng sau bài đang gen."})


@app.route("/blog-pillars/status")
def blog_pillars_status():
    with _PILLAR_BG_LOCK:
        return jsonify(dict(_PILLAR_BG))


# ─────────────────────────── CONTENT JOBS (SP) ───────────────────────────


@app.route("/content-jobs")
def content_jobs_list_page():
    status = request.args.get("status") or None
    cate = request.args.get("cate") or None
    valid_statuses = ("pending", "drafting", "text_done", "draft", "approved", "synced", "failed")
    if status and status not in valid_statuses:
        status = None
    jobs = db.content_jobs_list(status=status, cate=cate, limit=500)
    stats = db.content_jobs_stats()
    categories = db.content_jobs_categories()
    # parse JSON fields nhẹ cho list view
    for j in jobs:
        try:
            j["internal_links_list"] = json.loads(j["internal_links_json"]) if j.get("internal_links_json") else []
        except Exception:
            j["internal_links_list"] = []
    resp = make_response(render_template(
        "content_jobs_list.html",
        jobs=jobs, stats=stats, active_status=status,
        categories=categories, active_cate=cate,
    ))
    # Force no-cache để browser luôn fetch HTML mới (JS inline)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/content-jobs/push-from-empty-desc", methods=["POST"])
def content_jobs_push_from_empty_desc():
    """Đẩy SP thiếu mô tả/ngắn từ /seo/empty-desc vào content_jobs."""
    try:
        threshold = int(request.form.get("threshold") or seo_mod.EMPTY_DESC_THRESHOLD)
    except ValueError:
        threshold = seo_mod.EMPTY_DESC_THRESHOLD
    items = db.seo_empty_desc_list(
        url_type="product", threshold=threshold,
        only_empty=True, limit=2000,
    )
    # Skip mọi job đã có content AI để tránh overwrite (giữ draft/synced của vợ)
    SKIP_STATUSES_PUSH = ("drafting", "text_done", "draft", "approved", "synced")
    pushed = 0
    skipped = 0
    for it in items:
        existing = db.content_job_get_by_url(it["url"])
        if existing and existing["status"] in SKIP_STATUSES_PUSH:
            skipped += 1
            continue
        wc = it.get("desc_word_count") or 0
        reason = "empty_desc" if wc == 0 else "short_desc"
        db.content_job_upsert(
            it["url"],
            product_title=it.get("title"),
            current_word_count=wc,
            reason=reason,
            status="pending" if not existing else existing["status"],
        )
        pushed += 1
    flash(
        f"📤 Đã đẩy {pushed} SP vào hàng đợi viết AI "
        f"({skipped} SP đã có content AI — bỏ qua, không overwrite).",
        "success",
    )
    return redirect(url_for("content_jobs_list_page"))


@app.route("/content-jobs/push-one", methods=["POST"])
def content_jobs_push_one():
    """Đẩy 1 URL cụ thể vào jobs (dùng từ tab /seo/empty-desc cho từng SP)."""
    url = (request.form.get("url") or "").strip()
    reason = (request.form.get("reason") or "manual").strip()
    if not url:
        flash("Thiếu URL", "error")
        return redirect(request.referrer or url_for("content_jobs_list_page"))
    existing = db.content_job_get_by_url(url)
    if existing:
        flash(f"⏳ SP đã có trong hàng đợi (status: {existing['status']}). Mở để xem.", "info")
        return redirect(url_for("content_jobs_detail_page", job_id=existing["id"]))
    job_id = db.content_job_upsert(url, reason=reason, status="pending")
    flash("✅ Đã đẩy SP vào hàng đợi viết AI.", "success")
    return redirect(url_for("content_jobs_detail_page", job_id=job_id))


@app.route("/content-jobs/<int:job_id>")
def content_jobs_detail_page(job_id):
    job = db.content_job_get(job_id)
    if not job:
        flash("Không tìm thấy job.", "error")
        return redirect(url_for("content_jobs_list_page"))
    # parse JSON fields
    for k in ("ai_titles_json", "ai_metas_json", "ai_outline",
               "internal_links_json", "ai_stats_json"):
        try:
            job[k.replace("_json", "_list" if "links" in k or "titles" in k or "metas" in k else "_data")] = (
                json.loads(job[k]) if job.get(k) else []
            )
        except Exception:
            pass
    titles = []
    metas = []
    try:
        titles = json.loads(job["ai_titles_json"]) if job.get("ai_titles_json") else []
    except Exception:
        pass
    try:
        metas = json.loads(job["ai_metas_json"]) if job.get("ai_metas_json") else []
    except Exception:
        pass
    try:
        internal_link_list = json.loads(job["internal_links_json"]) if job.get("internal_links_json") else []
    except Exception:
        internal_link_list = []
    try:
        outline = json.loads(job["ai_outline"]) if job.get("ai_outline") else []
    except Exception:
        outline = []
    try:
        ai_stats = json.loads(job["ai_stats_json"]) if job.get("ai_stats_json") else {}
    except Exception:
        ai_stats = {}
    return render_template(
        "content_jobs_detail.html",
        job=job,
        titles=titles, metas=metas,
        internal_link_list=internal_link_list,
        outline=outline,
        ai_stats=ai_stats,
    )


@app.route("/content-jobs/<int:job_id>/generate", methods=["POST"])
def content_jobs_generate(job_id):
    """Đẩy 1 job vào queue → worker tự gen ngầm (return ngay, không đợi)."""
    job = db.content_job_get(job_id)
    if not job:
        flash("Job không tồn tại.", "error")
        return redirect(url_for("content_jobs_list_page"))
    # Check provider
    import ai_writer
    import codex_provider
    has_provider = (
        codex_provider.is_codex_available()
        or ai_writer._load_openai_key()
        or ai_writer._load_anthropic_key()
    )
    if not has_provider:
        flash("⚠️ Chưa có AI provider. Cài Codex CLI (`npm install -g @openai/codex`).", "error")
        return redirect(url_for("content_jobs_detail_page", job_id=job_id))
    # Reset về pending nếu đang failed/draft → worker pickup
    if job["status"] in ("failed", "draft", "drafting"):
        db.content_job_update(job_id, status="pending", error=None)
    started = content_writer.start_worker_async()
    msg = f"📥 Đã đẩy job #{job_id} vào queue."
    msg += " Worker đã start." if started else " Worker đang chạy sẽ pickup."
    msg += " Em làm việc khác đi, anh báo khi xong."
    flash(msg, "success")
    return redirect(url_for("content_jobs_detail_page", job_id=job_id))


@app.route("/content-jobs/queue/start-all", methods=["POST"])
def content_jobs_queue_start_all():
    """Reset tất cả job draft/failed về pending + start worker (gen tất cả pending)."""
    started = content_writer.start_worker_async()
    if started:
        flash("🚀 Worker đã start — sẽ gen lần lượt tất cả job pending. Em làm việc khác, anh báo tiến độ.", "success")
    else:
        flash("⏳ Worker đang chạy sẵn — không cần start lại.", "info")
    return redirect(url_for("content_jobs_list_page"))


@app.route("/content-jobs/queue/stop", methods=["POST"])
def content_jobs_queue_stop():
    stopped = content_writer.stop_worker()
    if stopped:
        flash("🛑 Đã gửi signal dừng — worker sẽ stop sau khi xong job hiện tại.", "info")
    else:
        flash("Worker không đang chạy.", "info")
    return redirect(url_for("content_jobs_list_page"))


@app.route("/api/content-jobs/queue-status")
def content_jobs_queue_status_api():
    return jsonify(content_writer.queue_state())


@app.route("/content-jobs/<int:job_id>/save", methods=["POST"])
def content_jobs_save(job_id):
    """Save edits từ form detail (title chosen + meta chosen + body edited + sync flags)."""
    job = db.content_job_get(job_id)
    if not job:
        flash("Job không tồn tại.", "error")
        return redirect(url_for("content_jobs_list_page"))
    try:
        sel_title_idx = int(request.form.get("selected_title_idx") or 0)
    except ValueError:
        sel_title_idx = 0
    try:
        sel_meta_idx = int(request.form.get("selected_meta_idx") or 0)
    except ValueError:
        sel_meta_idx = 0
    edited_title = (request.form.get("edited_title") or "").strip()
    edited_meta = (request.form.get("edited_meta") or "").strip()
    edited_body_html = request.form.get("edited_body_html") or ""
    is_money = 1 if request.form.get("is_money_product") else 0
    # Default sync ALL 3 field (body + meta_title + meta_desc) — em không cần tick nữa
    db.content_job_update(
        job_id,
        selected_title_idx=sel_title_idx,
        selected_meta_idx=sel_meta_idx,
        edited_title=edited_title,
        edited_meta=edited_meta,
        edited_body_html=edited_body_html,
        is_money_product=is_money,
        sync_body=1,
        sync_meta_title=1,
        sync_meta_desc=1,
    )
    flash("💾 Đã lưu chỉnh sửa.", "success")
    return redirect(url_for("content_jobs_detail_page", job_id=job_id))


@app.route("/content-jobs/<int:job_id>/toggle-money", methods=["POST"])
def content_jobs_toggle_money(job_id):
    """Toggle is_money_product flag — endpoint riêng cho nút nhanh trên list."""
    job = db.content_job_get(job_id)
    if not job:
        return {"ok": False, "error": "not found"}, 404
    new_val = 0 if job.get("is_money_product") else 1
    db.content_job_update(job_id, is_money_product=new_val)
    return {"ok": True, "is_money_product": new_val}


@app.route("/content-jobs/<int:job_id>/approve", methods=["POST"])
def content_jobs_approve(job_id):
    """Đổi status job sang 'approved' — sẵn sàng sync."""
    job = db.content_job_get(job_id)
    if not job:
        flash("Job không tồn tại.", "error")
        return redirect(url_for("content_jobs_list_page"))
    if job["status"] != "draft":
        flash(f"Chỉ duyệt được job ở trạng thái 'draft' (hiện: {job['status']}).", "info")
        return redirect(url_for("content_jobs_detail_page", job_id=job_id))
    if not (job.get("edited_body_html") or "").strip():
        flash("⚠️ Body trống — không duyệt được.", "error")
        return redirect(url_for("content_jobs_detail_page", job_id=job_id))
    db.content_job_update(
        job_id,
        status="approved",
        approved_at=datetime.now().isoformat(timespec="seconds"),
    )
    flash("✅ Đã duyệt — chờ Sync ngoài bảng list.", "success")
    return redirect(url_for("content_jobs_list_page"))


@app.route("/content-jobs/<int:job_id>/unapprove", methods=["POST"])
def content_jobs_unapprove(job_id):
    db.content_job_update(job_id, status="draft", approved_at=None)
    flash("↩️ Đã chuyển về draft để chỉnh tiếp.", "info")
    return redirect(url_for("content_jobs_detail_page", job_id=job_id))


@app.route("/content-jobs/<int:job_id>/delete", methods=["POST"])
def content_jobs_delete(job_id):
    db.content_job_delete(job_id)
    flash("🗑️ Đã xoá job.", "info")
    return redirect(url_for("content_jobs_list_page"))


@app.route("/content-jobs/sync", methods=["POST"])
def content_jobs_sync():
    """Bulk sync các job 'approved' lên Haravan (update body_html + optional meta)."""
    import haravan_client
    job_ids_raw = request.form.getlist("job_ids")
    if not job_ids_raw:
        flash("⚠️ Chưa chọn job nào để sync.", "error")
        return redirect(url_for("content_jobs_list_page"))
    job_ids = []
    for s in job_ids_raw:
        try:
            job_ids.append(int(s))
        except ValueError:
            continue
    ok, fail = 0, 0
    errors = []
    for jid in job_ids:
        job = db.content_job_get(jid)
        if not job or job["status"] != "approved":
            continue
        if not job.get("haravan_id"):
            db.content_job_update(jid, status="failed", error="Thiếu haravan_id — không sync được.")
            fail += 1
            errors.append(f"#{jid}: thiếu haravan_id")
            continue
        payload = {}
        if job.get("sync_body"):
            # Lazy upload: scan body_html find /local-images/... → upload Haravan + replace URL
            try:
                from content_writer import upload_local_images_in_body_to_haravan
                body_with_cdn = upload_local_images_in_body_to_haravan(job.get("edited_body_html") or "")
                payload["body_html"] = body_with_cdn
                # Lưu body có CDN URL về DB để lần sau không upload lại
                if body_with_cdn != (job.get("edited_body_html") or ""):
                    db.content_job_update(jid, edited_body_html=body_with_cdn)
            except Exception as e:
                db.content_job_update(jid, status="failed", error=f"Upload local images fail: {str(e)[:200]}")
                fail += 1
                errors.append(f"#{jid}: upload img fail")
                continue
        # Theme đọc SEO title/meta từ flat field `metafields_global_*` (verified 15/5)
        sync_title = job.get("sync_meta_title")
        sync_desc = job.get("sync_meta_desc")
        if not payload and not sync_title and not sync_desc:
            db.content_job_update(jid, status="failed", error="Không tick field nào để sync.")
            fail += 1
            errors.append(f"#{jid}: chưa tick field nào")
            continue
        if sync_title:
            payload[job_sync.SEO_TITLE_FIELD] = (job.get("edited_title") or "").strip()
        if sync_desc:
            payload[job_sync.SEO_DESC_FIELD] = (job.get("edited_meta") or "").strip()
        try:
            haravan_client.update_product(int(job["haravan_id"]), payload)
            db.content_job_update(
                jid, status="synced",
                synced_at=datetime.now().isoformat(timespec="seconds"),
                error=None,
            )
            ok += 1
        except Exception as e:
            db.content_job_update(jid, status="failed", error=f"Sync: {e.__class__.__name__}: {str(e)[:200]}")
            fail += 1
            errors.append(f"#{jid}: {e.__class__.__name__}")
    if ok:
        db.activity_log(
            kind="content_jobs_sync", icon="🚀",
            title=f"Sync {ok} bài lên Haravan",
            description=f"Lỗi: {fail}",
            href=url_for("content_jobs_list_page"),
        )
    flash(f"🚀 Sync xong: {ok} OK, {fail} lỗi." + (f" Lỗi: {', '.join(errors[:5])}" if errors else ""),
          "success" if ok else "error")
    return redirect(url_for("content_jobs_list_page", status="synced" if ok else None))


@app.route("/api/content-jobs/stats")
def content_jobs_stats_api():
    return jsonify(db.content_jobs_stats())


# ─────────────────────────── HARAVAN BLOGS ───────────────────────────

# Phân loại blog theo từ khóa trong title (auto-detect)
# Order matters: rule cụ thể trước, generic sau (vd "pirate" check trước "tutorial")
BLOG_TOPICS = [
    ("pirate",   "⚠️ Crack / Pirate",    "rgba(239,68,68,0.15)",  ["full 100", "full crack", "active key", "kích hoạt key", "key bản quyền"]),
    ("service",  "🛠️ Dịch vụ Sintech",   "rgba(34,197,94,0.15)",  ["sửa chữa", "sua chua", "dịch vụ", "tphcm", "quận"]),
    ("review",   "📖 Review",            "rgba(168,85,247,0.15)", ["review", "đánh giá", "danh gia"]),
    ("compare",  "🆚 So sánh",           "rgba(236,72,153,0.15)", ["so sánh", "so sanh", " vs ", "vs."]),
    ("build_pc", "🧰 Build PC",          "rgba(245,158,11,0.15)", ["build pc", "cấu hình pc", "cau hinh pc", "build cấu hình"]),
    ("top",      "🏆 Top / List",        "rgba(251,146,60,0.15)", ["top ", "best ", "những "]),
    ("promo",    "💰 Khuyến mãi",        "rgba(34,197,94,0.15)",  ["khuyến mãi", "khuyen mai", "sale", "giảm giá", "ưu đãi"]),
    ("gaming",   "🎮 Gaming",            "rgba(99,102,241,0.15)", ["tựa game", "tua game", "fps", "moba", "esport", "gaming "]),
    ("tutorial", "📝 Hướng dẫn",         "rgba(59,130,246,0.15)", ["hướng dẫn", "huong dan", "cách ", "tutorial", "tips", "thủ thuật"]),
    ("news",     "📰 Tin tức",           "rgba(14,165,233,0.15)", ["tin tức", "tin tuc", "news", "ra mắt", "ra mat", "công bố"]),
    ("explain",  "💡 Giải thích",        "rgba(20,184,166,0.15)", [" là gì", "la gi", "có nên", "co nen", "khác gì", "khac gi"]),
]
BLOG_TOPIC_LABELS = {code: (label, color) for code, label, color, _ in BLOG_TOPICS}
BLOG_TOPIC_LABELS["other"] = ("❓ Khác", "rgba(120,120,140,0.15)")


def classify_blog_topic(title: str) -> str:
    """Detect chủ đề blog theo keyword trong title."""
    t = (title or "").lower()
    for code, _label, _color, keywords in BLOG_TOPICS:
        if any(kw in t for kw in keywords):
            return code
    return "other"


@app.route("/haravan/blogs")
def haravan_blogs():
    """Quản lý blog/news của sintech.vn — data từ seo_pages (đã crawl).

    Khi nào Haravan API blogs/articles fix lỗi 502, có thể swap source sang sync trực tiếp.
    """
    # Lấy tất cả blog từ DB (max 500, hiện 286 → đủ chỗ)
    all_blogs = db.seo_list_pages(url_type="blog", limit=500, sort="url")

    # Classify topic + add helper fields
    for b in all_blogs:
        b["topic"] = classify_blog_topic(b.get("title") or "")
        try:
            b["issue_count"] = len(json.loads(b.get("issues") or "[]"))
        except (ValueError, TypeError):
            b["issue_count"] = 0

    # Topic counts (trên TOÀN BỘ — không filter)
    topic_counts = {}
    for b in all_blogs:
        topic_counts[b["topic"]] = topic_counts.get(b["topic"], 0) + 1
    topic_breakdown = []
    for code, label, color, _kw in BLOG_TOPICS:
        topic_breakdown.append({
            "code": code, "label": label, "color": color,
            "count": topic_counts.get(code, 0),
        })
    if topic_counts.get("other", 0):
        topic_breakdown.append({
            "code": "other", "label": "❓ Khác",
            "color": "rgba(120,120,140,0.15)",
            "count": topic_counts["other"],
        })

    # Filter
    f_topic = request.args.get("topic") or None
    f_band = request.args.get("band") or None
    f_search = (request.args.get("q") or "").strip().lower() or None
    f_sort = request.args.get("sort") or "score_asc"

    filtered = list(all_blogs)
    if f_topic:
        filtered = [b for b in filtered if b["topic"] == f_topic]
    if f_band == "good":
        filtered = [b for b in filtered if (b.get("score") or 0) >= 80]
    elif f_band == "ok":
        filtered = [b for b in filtered if 60 <= (b.get("score") or 0) < 80]
    elif f_band == "bad":
        filtered = [b for b in filtered if (b.get("score") or 0) < 60]
    if f_search:
        filtered = [b for b in filtered if f_search in (b.get("title") or "").lower()
                    or f_search in (b.get("url") or "").lower()]

    sort_keys = {
        "score_asc":  lambda b: (b.get("score") or 0, -(b.get("id") or 0)),
        "score_desc": lambda b: (-(b.get("score") or 0), -(b.get("id") or 0)),
        "title":      lambda b: (b.get("title") or "").lower(),
        "wc_desc":    lambda b: -(b.get("word_count") or 0),
        "wc_asc":     lambda b: (b.get("word_count") or 0),
        "issues_desc": lambda b: -b["issue_count"],
        "recent":     lambda b: -(b.get("id") or 0),
    }
    filtered.sort(key=sort_keys.get(f_sort, sort_keys["score_asc"]))

    # Stats trên TOÀN BỘ blogs
    scores = [b.get("score") for b in all_blogs if b.get("score") is not None]
    stats = {
        "total": len(all_blogs),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "good": sum(1 for s in scores if s >= 80),
        "ok":   sum(1 for s in scores if 60 <= s < 80),
        "bad":  sum(1 for s in scores if s < 60),
    }

    try:
        page_num = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page_num = 1
    per_page = 50
    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page_items = filtered[(page_num - 1) * per_page : page_num * per_page]

    return render_template(
        "haravan_blogs.html",
        blogs=page_items, stats=stats,
        topic_breakdown=topic_breakdown,
        topic_labels=BLOG_TOPIC_LABELS,
        filters={"topic": f_topic, "band": f_band, "q": f_search or "", "sort": f_sort},
        page_num=page_num, total_pages=total_pages, total=total, per_page=per_page,
    )


# ─────────────────────────── HARAVAN ───────────────────────────


@app.route("/haravan")
def haravan_dashboard():
    stats = db.hv_stats()
    state = hv_sync.sync_state()
    latest = db.hv_latest_sync()
    top_issues = db.hv_top_issues(limit=10)
    enriched_top = []
    for it in top_issues:
        icon, label, _fix = hv_sync.HV_ISSUE_LABELS.get(it["code"], ("⚪", it["code"], ""))
        enriched_top.append({**it, "icon": icon, "label": label})
    return render_template(
        "haravan.html",
        stats=stats, state=state, latest=latest, top_issues=enriched_top,
    )


@app.route("/haravan/sync", methods=["POST"])
def haravan_sync_start():
    try:
        limit_pages = int(request.form.get("limit_pages") or 0) or None
    except (TypeError, ValueError):
        limit_pages = None
    started = hv_sync.start_sync_async(limit_pages=limit_pages)
    if started:
        flash(f"Đã bắt đầu sync Haravan {'(' + str(limit_pages) + ' page test)' if limit_pages else '(toàn bộ)'}.", "success")
    else:
        flash("Đang sync — chờ xong rồi sync tiếp.", "error")
    return redirect(url_for("haravan_dashboard"))


@app.route("/api/haravan/sync-incremental/start", methods=["POST"])
def haravan_sync_incremental_start():
    """Incremental sync — chỉ pull SP thay đổi/mới kể từ last_synced."""
    ok = hv_sync.start_sync_incremental_async()
    if ok:
        return jsonify({"ok": True, "message": "Incremental sync đã bắt đầu"})
    return jsonify({"ok": False, "message": "Đang sync — chờ xong"}), 409


@app.route("/api/haravan/sync/status")
def haravan_sync_status_api():
    return jsonify(hv_sync.sync_state())


@app.route("/api/haravan/status")
def haravan_status_api():
    return jsonify({
        "state": hv_sync.sync_state(),
        "stats": db.hv_stats(),
    })


@app.route("/haravan/products")
def haravan_products_page():
    filters = {
        "vendor": request.args.get("vendor") or None,
        "product_type": request.args.get("type") or None,
        "status": request.args.get("status") or None,
        "issue_code": request.args.get("issue") or None,
        "search": request.args.get("q") or None,
        "sort": request.args.get("sort") or "score_asc",
    }
    band = request.args.get("band")
    score_filter = {}
    if band == "good":
        score_filter = {"min_score": 80}
    elif band == "ok":
        score_filter = {"min_score": 60, "max_score": 79}
    elif band == "bad":
        score_filter = {"max_score": 59}

    page_num = max(1, int(request.args.get("page", 1)))
    per_page = 50
    total = db.hv_count_products(**filters)
    total_pages = max(1, (total + per_page - 1) // per_page)
    products = db.hv_list_products(
        **filters, limit=per_page, offset=(page_num - 1) * per_page,
    )
    stats = db.hv_stats()
    top_issues = db.hv_top_issues(limit=12)
    enriched_top = []
    for it in top_issues:
        icon, label, _fix = hv_sync.HV_ISSUE_LABELS.get(it["code"], ("⚪", it["code"], ""))
        enriched_top.append({**it, "icon": icon, "label": label})
    return render_template(
        "haravan_products.html",
        products=products, stats=stats, top_issues=enriched_top,
        filters=filters, band=band,
        page_num=page_num, total_pages=total_pages, total=total,
    )


@app.route("/haravan/products/<int:haravan_id>")
def haravan_product_detail(haravan_id):
    p = db.hv_get_product(haravan_id)
    if not p:
        flash("Không tìm thấy sản phẩm trong DB. Sync lại có thể giúp.", "error")
        return redirect(url_for("haravan_products_page"))
    raw_issues = []
    if p.get("audit_issues"):
        try:
            raw_issues = json.loads(p["audit_issues"])
        except (ValueError, TypeError):
            raw_issues = []
    issues = [hv_sync.hv_enrich_issue(it) for it in raw_issues]
    images = []
    if p.get("images"):
        try:
            images = json.loads(p["images"])
        except (ValueError, TypeError):
            images = []
    return render_template(
        "haravan_product_detail.html",
        p=p, issues=issues, images=images,
    )


@app.route("/seo/crawl", methods=["POST"])
def seo_crawl():
    try:
        limit = int(request.form.get("limit") or 0) or None
    except (TypeError, ValueError):
        limit = None
    started = seo_mod.start_crawl_async(limit=limit)
    if started:
        flash(f"Đã bắt đầu crawl {'(' + str(limit) + ' URL test)' if limit else '(toàn bộ sitemap)'}.", "success")
    else:
        flash("Đang có run khác — chờ xong rồi crawl tiếp.", "error")
    return redirect(url_for("seo_dashboard"))


@app.route("/seo/stop-crawl", methods=["POST"])
def seo_stop_crawl():
    """Stop crawl đang chạy (graceful — đợi các request đang fly xong)."""
    stopped = seo_mod.stop_crawl()
    if stopped:
        flash("🛑 Đã gửi signal stop — crawl sẽ dừng sau khi xong các URL đang fetch.", "info")
    else:
        flash("Crawl đang idle — không có gì để stop.", "info")
    return redirect(url_for("seo_dashboard"))


@app.route("/seo/crawl-fresh", methods=["POST"])
def seo_crawl_fresh():
    """Stop crawl đang chạy + xóa toàn bộ data + start crawl mới fresh.
    Hữu ích khi muốn re-crawl từ đầu, không bị data cũ ảnh hưởng."""
    # 1. Stop crawl đang chạy (nếu có) — soft signal
    seo_mod.stop_crawl()
    # 2. Đợi state về idle/done (max 10s)
    import time
    for _ in range(20):
        snap = seo_mod.state_snapshot()
        if snap["status"] not in ("fetching_sitemap", "crawling", "stopping"):
            break
        time.sleep(0.5)
    # 3. Clear toàn bộ DB seo_pages + seo_links
    db.seo_clear_all()
    # 4. Start crawl mới — toàn bộ sitemap, không limit
    started = seo_mod.start_crawl_async(limit=None)
    if started:
        flash("🆕 Đã xóa toàn bộ data cũ + bắt đầu crawl mới fresh. Refresh trang để xem tiến độ realtime.", "success")
    else:
        flash("Vẫn còn run khác chưa stop hết — đợi 30s rồi thử lại.", "error")
    return redirect(url_for("seo_dashboard"))


# ─────────────────────────── BACKGROUND ───────────────────────────


def auto_post_due():
    """Worker chạy mỗi phút — đăng các bài 'approved' tới giờ.

    Lưu ý: có thể dùng FB native scheduling thay (đã có endpoint /schedule),
    đây chỉ là backup local trong trường hợp em muốn quản hoàn toàn từ Hub."""
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


@app.template_filter("from_json")
def jinja_from_json(value):
    if not value:
        return []
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return []


@app.context_processor
def inject_globals():
    return {
        "now": datetime.now(),
        "POST_TYPES": POST_TYPES,
        "POST_STATUSES": POST_STATUSES,
    }


# ──────────────────────────────────────────────────────────────
#  /products/new — Phase 1: form + parser preview (no Haravan POST yet)
# ──────────────────────────────────────────────────────────────

@app.route("/products/new", methods=["GET"])
def products_new_form():
    return render_template("products_new.html")


@app.route("/products/new/preview", methods=["POST"])
def products_new_preview():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    warranty = (body.get("warranty_months") or "").strip()

    parsed = pp.parse(name)

    all_tags = []
    if warranty and warranty.isdigit() and 1 <= int(warranty) <= 120:
        all_tags.append(f"bh_{int(warranty):02d}_tháng")
    all_tags.extend(parsed.get("tags") or [])

    return jsonify({
        **parsed,
        "all_tags": all_tags,
        "warranty_months": warranty,
        "price": body.get("price"),
        "compare_price": body.get("compare_price"),
        "stock": body.get("stock"),
    })


@app.route("/products/new/organize-spec", methods=["POST"])
def products_new_organize_spec():
    """Phase 5 — clean up + structure spec_raw qua Claude.

    Body: {name, spec_raw} → trả {spec_table, key_features, use_cases, compatibility_notes, warnings}.
    """
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    spec_raw = (body.get("spec_raw") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Thiếu tên SP"}), 400
    if not spec_raw:
        return jsonify({"ok": False, "error": "Spec_raw rỗng — paste spec trước"}), 400

    parsed = pp.parse(name)
    if not parsed.get("loai"):
        return jsonify({"ok": False, "error": parsed.get("note") or "Tên SP không hợp lệ"}), 400

    try:
        organized = pw.organize_spec(name=name, parsed=parsed, spec_raw=spec_raw)
        return jsonify({"ok": True, **organized})
    except cp.CodexRateLimitError as e:
        return jsonify({"ok": False, "error": f"Codex quota hết. ({e})"}), 503
    except Exception as e:
        return jsonify({"ok": False, "error": f"Organize fail: {e}"}), 500


@app.route("/products/new/generate", methods=["POST"])
def products_new_generate():
    """Phase 2 — gọi Claude gen body_html + excerpt + SEO title + SEO meta.

    Nếu body chứa `organized_spec` (từ /organize-spec) → AI dùng làm source of truth.
    """
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Thiếu tên SP"}), 400
    parsed = pp.parse(name)
    if not parsed.get("loai"):
        return jsonify({"ok": False, "error": parsed.get("note") or "Tên SP không hợp lệ"}), 400

    organized_spec = body.get("organized_spec")
    if isinstance(organized_spec, dict) and not any(organized_spec.get(k) for k in ("spec_table", "key_features", "use_cases", "compatibility_notes")):
        organized_spec = None  # treat empty dict as None

    try:
        gen = pw.generate(
            name=name,
            parsed=parsed,
            price=(body.get("price") or "").strip(),
            warranty_months=(body.get("warranty_months") or "").strip(),
            organized_spec=organized_spec,
            prev_angle=(body.get("prev_angle") or None),
        )
        return jsonify({"ok": True, **gen})
    except cp.CodexRateLimitError as e:
        return jsonify({"ok": False, "error": f"Codex quota hết — đợi reset rồi thử lại. ({e})"}), 503
    except Exception as e:
        return jsonify({"ok": False, "error": f"Gen fail: {e}"}), 500


@app.route("/products/new/create", methods=["POST"])
def products_new_create():
    """Phase 3 — POST Haravan tạo SP thật. Lift permission gate cho route này."""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Thiếu tên SP"}), 400

    parsed = pp.parse(name)
    if not parsed.get("loai"):
        return jsonify({"ok": False, "error": parsed.get("note") or "Tên SP không hợp lệ"}), 400

    warranty = (body.get("warranty_months") or "").strip()
    price = body.get("price")
    compare_price = body.get("compare_price")
    body_html = (body.get("body_html") or "").strip()
    excerpt = (body.get("excerpt") or "").strip()
    seo_title = (body.get("seo_title") or "").strip()
    seo_meta = (body.get("seo_meta") or "").strip()

    if not body_html:
        return jsonify({"ok": False, "error": "Body HTML rỗng — chạy AI gen trước"}), 400

    # Tags = bh_ tag + parsed tags
    tags_list = []
    if warranty and str(warranty).isdigit() and 1 <= int(warranty) <= 120:
        tags_list.append(f"bh_{int(warranty):02d}_tháng")
    tags_list.extend(parsed.get("tags") or [])

    # Variant: 1 biến thể "Bảo hành NN tháng" — stock + Google visibility TẠM TẮT theo yêu cầu vợ
    variant_title = f"Bảo hành {int(warranty)} tháng" if warranty and str(warranty).isdigit() else "Mặc định"
    variant = {
        "option1": variant_title,
        "requires_shipping": False,  # vợ bỏ tick "cho phép giao hàng"
    }
    if price and str(price).replace(".", "").isdigit():
        variant["price"] = float(price)
    if compare_price and str(compare_price).replace(".", "").isdigit():
        variant["compare_at_price"] = float(compare_price)

    from datetime import timezone
    product_fields = {
        "title": name,
        "body_html": body_html,
        "vendor": parsed.get("hang") or "",
        "product_type": parsed.get("loai") or "",
        "tags": ", ".join(tags_list),
        # published_scope: tắt — vợ tick "Hiển thị Google" tay sau trong admin Haravan
        # published_at: publish SP ngay (không để draft) → SEO metafields hiển thị được
        "published_at": datetime.now(timezone.utc).isoformat(),
        "summary_html": excerpt,
        "options": [{"name": "Kích thước", "values": [variant_title]}],
        "variants": [variant],
    }

    errors = []

    try:
        with hv_client.allow_blocked_operations("ui_form:/products/new"):
            created = hv_client.create_product(product_fields)
        product_id = created.get("id")
        if not product_id:
            return jsonify({"ok": False, "error": "Tạo SP OK nhưng không có id trả về", "raw": created}), 500

        # SEO metafields — errors propagate to response (not silent)
        seo_results = {"title": None, "description": None}
        if seo_title:
            try:
                with hv_client.allow_blocked_operations("ui_form:/products/new"):
                    seo_results["title"] = hv_client.upsert_metafield(
                        "products", product_id, "global", "title_tag", seo_title)
            except Exception as e:
                errors.append(f"upsert SEO title fail: {e}")
        if seo_meta:
            try:
                with hv_client.allow_blocked_operations("ui_form:/products/new"):
                    seo_results["description"] = hv_client.upsert_metafield(
                        "products", product_id, "global", "description_tag", seo_meta)
            except Exception as e:
                errors.append(f"upsert SEO meta fail: {e}")

        # Verify body_html stored correctly
        body_check = {}
        try:
            with hv_client.allow_blocked_operations("ui_form:/products/new"):
                verified = hv_client.get_product(product_id)
            stored_body = verified.get("body_html") or ""
            body_check = {
                "stored_length": len(stored_body),
                "sent_length": len(body_html),
                "has_h2": "<h2" in stored_body,
                "has_h3": "<h3" in stored_body,
                "has_table": "<table" in stored_body,
                "has_ul": "<ul" in stored_body,
                "has_link": "<a " in stored_body,
                "first_200": stored_body[:200],
                "haravan_published_at": verified.get("published_at"),
            }
        except Exception as e:
            errors.append(f"verify body fail: {e}")

        # Verify SEO metafields — trust upsert response, KHÔNG re-GET (Haravan có cache delay
        # ~3min cho list_metafields ngay sau POST → returns empty cho dù upsert đã tạo OK).
        title_resp = seo_results.get("title") or {}
        desc_resp = seo_results.get("description") or {}
        seo_check = {
            "title_tag_present": bool(title_resp.get("id")),
            "title_tag_id": title_resp.get("id"),
            "title_tag_value": (title_resp.get("value") or "")[:100] if title_resp else None,
            "description_tag_present": bool(desc_resp.get("id")),
            "description_tag_id": desc_resp.get("id"),
            "description_tag_value": (desc_resp.get("value") or "")[:160] if desc_resp else None,
            "note": "Verified from upsert response (Haravan list cache ~3min, sẽ hiện trong admin sau vài phút)",
        }

        handle = created.get("handle") or parsed.get("slug") or ""
        return jsonify({
            "ok": True,
            "product_id": product_id,
            "handle": handle,
            "admin_url": f"https://admin.haravan.com/admin/products/{product_id}",
            "live_url": f"https://sintech.vn/products/{handle}" if handle else None,
            "body_check": body_check,
            "seo_check": seo_check,
            "errors": errors,
        })
    except hv_client.HaravanError as e:
        return jsonify({"ok": False, "error": f"Haravan: {e}", "errors": errors}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": f"Unexpected: {e}", "errors": errors}), 500


# ─────────────────────────── DASHBOARD HEALTH (Ops Center — Phase 1) ───────────────────────────
# Lớp data gộp cho dashboard "5 giây biết hệ thống ổn/lỗi". Mọi field CÓ fallback, KHÔNG bịa số.
# Probe chậm (git / bot ping / provider) cache TTL để poll nhẹ.

_HEALTH_CACHE = {}  # key -> (expires_ts, value)


def _health_cached(key, ttl, fn):
    import time as _t
    now = _t.time()
    hit = _HEALTH_CACHE.get(key)
    if hit and hit[0] > now:
        return hit[1]
    try:
        val = fn()
    except Exception as e:
        val = {"error": str(e)[:120]}
    _HEALTH_CACHE[key] = (now + ttl, val)
    return val


def _backup_info(pattern):
    """File backup mới nhất khớp pattern trong data/backups/ (chỉ trả thời gian, KHÔNG đọc nội dung)."""
    import glob
    import os
    bdir = Path(__file__).parent / "data" / "backups"
    files = glob.glob(str(bdir / pattern))
    if not files:
        return {"ok": False}
    newest = max(files, key=os.path.getmtime)
    mt = os.path.getmtime(newest)
    return {
        "ok": True,
        "file": os.path.basename(newest),
        "at": datetime.fromtimestamp(mt).isoformat(timespec="seconds"),
        "age_hours": round((datetime.now().timestamp() - mt) / 3600, 1),
    }


def _git_health():
    import subprocess
    repo = str(Path(__file__).parent)

    def _g(*args):
        return subprocess.run(["git", "-C", repo, *args],
                              capture_output=True, text=True, timeout=8).stdout.strip()

    branch = _g("rev-parse", "--abbrev-ref", "HEAD")
    if not branch:
        return {"available": False}
    dirty = _g("status", "--porcelain")
    uncommitted = len([l for l in dirty.splitlines() if l.strip()])
    ahead = behind = None
    counts = _g("rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    if counts and "\t" in counts:
        b, a = counts.split("\t")[:2]
        try:
            behind, ahead = int(b), int(a)
        except ValueError:
            pass
    return {"available": True, "branch": branch, "uncommitted": uncommitted,
            "ahead": ahead, "behind": behind}


def _bot_health():
    import os
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not tok:
        tf = Path(__file__).parent / ".env" / "telegram_bot_token.txt"
        if tf.exists():
            tok = tf.read_text(encoding="utf-8").strip()
    if not tok:
        return {"status": "no_token"}
    try:
        r = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=5, verify=False)
        j = r.json() if r.text else {}
        if r.status_code == 200 and j.get("ok"):
            return {"status": "ok", "username": j.get("result", {}).get("username")}
        return {"status": "down", "detail": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "down", "detail": str(e)[:80]}


def _provider_health():
    import ai_provider
    av = ai_provider.available_providers()
    return {"primary": av[0] if av else None, "available": av}


def _dashboard_health():
    """Gộp toàn bộ chỉ số sức khỏe (data thật + fallback). Không bao giờ raise."""
    out = {"ts": datetime.now().isoformat(timespec="seconds"), "flask": {"status": "up"}}

    try:
        out["content_jobs"] = db.content_jobs_stats()
    except Exception as e:
        out["content_jobs"] = {"error": str(e)[:100]}
    try:
        s = db.seo_stats()
        out["seo"] = {k: s.get(k) for k in ("total", "avg_score", "good", "ok", "bad", "broken")}
    except Exception as e:
        out["seo"] = {"error": str(e)[:100]}
    try:
        h = db.hv_stats()
        out["haravan"] = {"total": h.get("total"), "avg_score": h.get("avg_score"),
                          "by_status": h.get("by_status")}
    except Exception as e:
        out["haravan"] = {"error": str(e)[:100]}
    try:
        out["fb_posts"] = db.stats()
    except Exception as e:
        out["fb_posts"] = {"error": str(e)[:100]}

    try:  # review queue + pillar progress — chỉ COUNT, nhẹ
        conn = db.get_conn()
        blog_draft = conn.execute("SELECT COUNT(*) FROM blog_jobs WHERE status='draft'").fetchone()[0]
        content_review = conn.execute(
            "SELECT COUNT(*) FROM content_jobs WHERE status IN ('text_done','draft','approved')").fetchone()[0]
        pil_total = conn.execute("SELECT COUNT(*) FROM blog_jobs WHERE source='ai_pillar'").fetchone()[0]
        pil_done = conn.execute(
            "SELECT COUNT(*) FROM blog_jobs WHERE source='ai_pillar' AND status IN ('draft','synced')").fetchone()[0]
        conn.close()
        out["review_queue"] = {"blog_draft": blog_draft, "content_review": content_review,
                               "total": blog_draft + content_review}
        out["pillar"] = {"total": pil_total, "done": pil_done, "pending": pil_total - pil_done}
    except Exception as e:
        out["review_queue"] = {"error": str(e)[:100]}
        out["pillar"] = {"error": str(e)[:100]}

    try:
        s = alt_manager.summarize_alt_coverage()
        out["alt"] = {
            "total_images": s.get("total_images", 0),
            "good": s.get("good", 0),
            "none": s.get("none", 0),
            "weak": s.get("weak", 0),
            "coverage_percent": s.get("coverage_percent", 0.0),
        }
    except Exception as e:
        out["alt"] = {"error": str(e)[:100]}

    try:
        m = db.cwv_stats("mobile")
        d = db.cwv_stats("desktop")
        m_total = db.cwv_count("mobile")
        d_total = db.cwv_count("desktop")
        sync_state = None
        sync_path = Path(__file__).parent / "data" / "cwv_last_sync.json"
        if sync_path.exists():
            try:
                sync_state = json.loads(sync_path.read_text(encoding="utf-8"))
            except Exception:
                sync_state = None
        out["cwv"] = {
            "total": (m_total or 0) + (d_total or 0),
            "mobile_total": m_total or 0,
            "desktop_total": d_total or 0,
            "mobile_bad": (m.get("perf_bad") or 0) if isinstance(m, dict) else 0,
            "desktop_bad": (d.get("perf_bad") or 0) if isinstance(d, dict) else 0,
            "mobile_avg": m.get("avg_perf") if isinstance(m, dict) else None,
            "desktop_avg": d.get("avg_perf") if isinstance(d, dict) else None,
            "last_sync": sync_state,
        }
    except Exception as e:
        out["cwv"] = {"error": str(e)[:100]}

    try:
        diff_path = Path(__file__).parent / "data" / "cwv_weekly_diff.json"
        if diff_path.exists():
            diff_data = json.loads(diff_path.read_text(encoding="utf-8"))
            mob = diff_data.get("strategies", {}).get("mobile", {}) or {}
            out["cwv_diff"] = {
                "generated_at": diff_data.get("generated_at"),
                "current_week": diff_data.get("current_week"),
                "prev_week": diff_data.get("prev_week"),
                "mobile_avg_change": mob.get("avg_change"),
                "mobile_current_avg": mob.get("current_avg_score"),
                "mobile_prev_avg": mob.get("prev_avg_score"),
                "improved_count": mob.get("improved_count"),
                "regressed_count": mob.get("regressed_count"),
            }
        else:
            out["cwv_diff"] = None
    except Exception as e:
        out["cwv_diff"] = {"error": str(e)[:100]}

    out["backups"] = {"db": _backup_info("posts_*.db.zip"), "secrets": _backup_info("secrets_*.zip")}
    out["git"] = _health_cached("git", 30, _git_health)
    out["bot"] = _health_cached("bot", 120, _bot_health)
    out["provider"] = _health_cached("provider", 120, _provider_health)
    return out


def _worklog_tasks(limit=8):
    """Parse NHẸ WORKLOG.md: lấy mục chưa xong '- [ ]' + gắn nhãn active/blocked theo
    heading gần nhất. Fallback {ok:False} nếu không đọc được (không bịa)."""
    import re
    p = Path(__file__).parent.parent / "WORKLOG.md"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {"ok": False, "tasks": []}
    bucket = "active"
    tasks = []
    for ln in lines:
        stripped = ln.lstrip()
        if stripped.startswith("#") or stripped.startswith(">"):
            low = ln.lower()
            if "🟡" in ln or "blocked" in low or "chờ vợ" in low:
                bucket = "blocked"
            elif "🔴" in ln or "active" in low:
                bucket = "active"
            continue
        m = re.match(r"\s*-\s*\[\s\]\s*(.+)", ln)  # chỉ mục CHƯA xong
        if m:
            txt = re.sub(r"[*`\[\]]", "", m.group(1))
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                tasks.append({"text": txt[:150], "bucket": bucket})
            if len(tasks) >= limit:
                break
    return {"ok": True, "tasks": tasks}


@app.route("/api/dashboard/health")
def api_dashboard_health():
    return jsonify(_dashboard_health())


if __name__ == "__main__":
    db.init_db()
    import job_monitor
    job_monitor.start_monitor(_collect_jobs)
    sched = BackgroundScheduler()
    sched.add_job(auto_post_due, "interval", minutes=1, id="auto_post_due")
    sched.add_job(
        lambda: seo_mod.start_crawl_async(),
        "cron", day_of_week="sun", hour=3, minute=0,
        id="seo_weekly_crawl",
    )
    sched.add_job(
        lambda: db.seo_capture_history(note="weekly_auto"),
        "cron", day_of_week="sun", hour=4, minute=0,
        id="seo_weekly_history_capture",
    )
    sched.start()
    try:
        app.run(host="127.0.0.1", port=5055, debug=False, threaded=True)
    finally:
        sched.shutdown(wait=False)
