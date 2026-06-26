"""ALT text manager — audit coverage trên toàn shop Haravan.

P1 (28/5/2026): data layer + audit baseline. Dùng JSON `images` đã có trong
`haravan_products` (sync gần nhất 03/5/2026), KHÔNG tạo bảng mới.

Classify ALT theo 3 mức:
  - none: rỗng / None
  - weak: <= 5 từ HOẶC chỉ là số/SKU (vd "1_db8ed8c708...") HOẶC chứa chủ yếu ký tự không phải chữ
  - good: >= 5 từ + có chữ Việt/Eng có nghĩa

Tham chiếu: project_blog_content_tasks.md (rule ALT trong content_writer._gen_alt_for_position).
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime
from typing import Any, Literal

import db


AltStatus = Literal["none", "weak", "good"]

# Pattern fake-ALT thường gặp (file name, hash, SKU dài)
_RE_HASH_LIKE = re.compile(r"^[a-f0-9]{12,}$", re.I)
_RE_FILE_LIKE = re.compile(r"^\d+_[a-f0-9]{12,}", re.I)
_RE_ONLY_NON_LETTER = re.compile(r"^[^a-zA-ZÀ-ỹ]+$")


def classify_alt(alt: str | None) -> AltStatus:
    """Phân loại ALT của 1 image."""
    if alt is None:
        return "none"
    s = alt.strip()
    if not s:
        return "none"
    if _RE_HASH_LIKE.match(s) or _RE_FILE_LIKE.match(s):
        return "weak"
    if _RE_ONLY_NON_LETTER.match(s):
        return "weak"
    words = [w for w in re.split(r"\s+", s) if w]
    # weak chỉ khi vừa ít từ VỪA ngắn — tên SP ngắn (≥20 ký tự hoặc ≥4 từ) vẫn good
    if len(words) < 4 and len(s) < 20:
        return "weak"
    return "good"


def _fmt_alt_synced(iso: str | None) -> str:
    """ISO datetime → 'DD/MM HH:MM' cho cột 'Ngày sync' (rỗng nếu chưa sync)."""
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m %H:%M")
    except Exception:
        return iso[:16]


def _iter_product_images() -> list[dict[str, Any]]:
    """Parse all SP + images cross DB. Trả list dict {product_id, handle, title, type, vendor, images: [...]}."""
    conn = db.get_conn()
    rows = conn.execute("""
        SELECT haravan_id, handle, title, product_type, vendor, status, images, last_synced, body_html, alt_synced_at
        FROM haravan_products
        WHERE images IS NOT NULL AND images != '' AND images != '[]'
    """).fetchall()
    conn.close()

    out = []
    for r in rows:
        try:
            imgs = json.loads(r["images"]) or []
        except Exception:
            imgs = []
        if not imgs:
            continue
        out.append({
            "product_id": r["haravan_id"],
            "handle": r["handle"],
            "title": r["title"],
            "type": r["product_type"],
            "vendor": r["vendor"],
            "status": r["status"],
            "last_synced": r["last_synced"],
            "alt_synced_at": r["alt_synced_at"],
            "images": imgs,
            "body_html": r["body_html"] or "",
        })
    return out


def _count_desc_images(body_html: str | None) -> tuple[int, int]:
    """Count img tags + số ảnh thiếu ALT good từ body_html DB snapshot. Trả (total, missing)."""
    if not body_html:
        return 0, 0
    total = 0
    missing = 0
    for m in _RE_IMG_TAG.finditer(body_html):
        tag = m.group(0)
        alt_m = re.search(r"""alt\s*=\s*["']([^"']*)["']""", tag, re.IGNORECASE)
        alt = alt_m.group(1) if alt_m else None
        if classify_alt(alt) != "good":
            missing += 1
        total += 1
    return total, missing


def summarize_alt_coverage() -> dict[str, Any]:
    """Aggregate coverage stats cho toàn shop.

    Output:
      {
        total_products: 2123,
        products_with_images: 2100,
        total_images: 7859,
        none: 7859, weak: 0, good: 0,
        coverage_percent: 0.0,
        by_type: {product: {...}, blog: {...}, ...},
        last_synced_min: "2026-05-03T21:06:41",
        last_synced_max: "2026-05-03T21:06:41",
      }
    """
    products = _iter_product_images()

    total_images = 0
    none_cnt = weak_cnt = good_cnt = 0
    by_type: dict[str, dict[str, int]] = {}
    last_synced_vals = []

    desc_total_all = 0
    desc_missing_all = 0

    for p in products:
        ptype = p["type"] or "(unknown)"
        bucket = by_type.setdefault(ptype, {"products": 0, "images": 0, "none": 0, "weak": 0, "good": 0})
        bucket["products"] += 1
        if p["last_synced"]:
            last_synced_vals.append(p["last_synced"])
        for im in p["images"]:
            status = classify_alt(im.get("alt"))
            total_images += 1
            bucket["images"] += 1
            if status == "none":
                none_cnt += 1
                bucket["none"] += 1
            elif status == "weak":
                weak_cnt += 1
                bucket["weak"] += 1
            else:
                good_cnt += 1
                bucket["good"] += 1
        dt, dm = _count_desc_images(p.get("body_html"))
        desc_total_all += dt
        desc_missing_all += dm

    conn = db.get_conn()
    total_products = conn.execute("SELECT COUNT(*) FROM haravan_products").fetchone()[0]
    conn.close()

    combined_total = total_images + desc_total_all
    combined_good = good_cnt + (desc_total_all - desc_missing_all)
    coverage = round(combined_good / combined_total * 100, 1) if combined_total else 0.0

    return {
        "total_products": total_products,
        "products_with_images": len(products),
        "total_images": total_images,
        "desc_total": desc_total_all,
        "combined_total": combined_total,
        "combined_good": combined_good,
        "none": none_cnt,
        "weak": weak_cnt,
        "good": good_cnt,
        "coverage_percent": coverage,
        "by_type": by_type,
        "last_synced_min": min(last_synced_vals) if last_synced_vals else None,
        "last_synced_max": max(last_synced_vals) if last_synced_vals else None,
    }


def list_products_paginated(
    page: int = 1,
    page_size: int = 50,
    only_missing: bool = True,
    filter_type: str | None = None,
    filter_vendor: str | None = None,
    search: str | None = None,
    sort: str = "missing_desc",
) -> dict[str, Any]:
    """List SP có ảnh + ALT classification, có filter/sort/paginate cho UI table.

    sort:
      missing_desc — nhiều ảnh thiếu/yếu trước (default)
      total_desc   — nhiều ảnh trước
      handle_asc   — handle A→Z
    """
    products = _iter_product_images()
    items = []
    for p in products:
        none_cnt = weak_cnt = good_cnt = 0
        for im in p["images"]:
            s = classify_alt(im.get("alt"))
            if s == "none":
                none_cnt += 1
            elif s == "weak":
                weak_cnt += 1
            else:
                good_cnt += 1
        missing = none_cnt + weak_cnt
        total = none_cnt + weak_cnt + good_cnt

        if only_missing and missing == 0:
            continue
        if filter_type and (p["type"] or "") != filter_type:
            continue
        if filter_vendor and (p["vendor"] or "") != filter_vendor:
            continue
        if search:
            kw = search.lower()
            if (kw not in (p["handle"] or "").lower()
                    and kw not in (p["title"] or "").lower()
                    and kw not in str(p["product_id"] or "")):
                continue

        items.append({
            "product_id": p["product_id"],
            "handle": p["handle"],
            "title": p["title"],
            "type": p["type"],
            "vendor": p["vendor"],
            "status": p["status"],
            "total": total,
            "none": none_cnt,
            "weak": weak_cnt,
            "good": good_cnt,
            "missing_score": missing,
            "thumb": (p["images"][0].get("src") if p["images"] else None),
            "alt_synced_at": _fmt_alt_synced(p.get("alt_synced_at")),
        })

    if sort == "total_desc":
        items.sort(key=lambda x: (-x["total"], x["handle"] or ""))
    elif sort == "handle_asc":
        items.sort(key=lambda x: (x["handle"] or ""))
    else:  # missing_desc default
        items.sort(key=lambda x: (-x["missing_score"], -x["total"]))

    total_count = len(items)
    page = max(1, page)
    page_size = max(10, min(page_size, 500))
    start = (page - 1) * page_size
    end = start + page_size
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    return {
        "rows": items[start:end],
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "pages": total_pages,
    }


def list_filter_options() -> dict[str, list[str]]:
    """Trả list product_type + vendor unique cho dropdown filter."""
    products = _iter_product_images()
    types = sorted({(p["type"] or "").strip() for p in products if (p["type"] or "").strip()})
    vendors = sorted({(p["vendor"] or "").strip() for p in products if (p["vendor"] or "").strip()})
    return {"types": types, "vendors": vendors}


def get_product_for_editor(product_id: int) -> dict[str, Any] | None:
    """Lấy 1 SP + danh sách images với ALT classification cho P3 editor."""
    conn = db.get_conn()
    row = conn.execute("""
        SELECT haravan_id, handle, title, product_type, vendor, status, images, last_synced
        FROM haravan_products WHERE haravan_id = ?
    """, (product_id,)).fetchone()
    conn.close()
    if not row:
        return None
    try:
        imgs = json.loads(row["images"] or "[]") or []
    except Exception:
        imgs = []
    images_with_status = []
    for i, im in enumerate(imgs):
        images_with_status.append({
            "id": im.get("id"),
            "src": im.get("src", ""),
            "alt": im.get("alt") or "",
            "position": im.get("position", i + 1),
            "status": classify_alt(im.get("alt")),
        })
    return {
        "product_id": row["haravan_id"],
        "handle": row["handle"],
        "title": row["title"],
        "type": row["product_type"],
        "vendor": row["vendor"],
        "images": images_with_status,
    }


def update_image_alt_local(product_id: int, image_id: int, new_alt: str) -> bool:
    """Update ALT text trong DB local + recalc images_no_alt column."""
    conn = db.get_conn()
    row = conn.execute(
        "SELECT images FROM haravan_products WHERE haravan_id = ?", (product_id,)
    ).fetchone()
    if not row:
        conn.close()
        return False
    try:
        imgs = json.loads(row["images"] or "[]") or []
    except Exception:
        conn.close()
        return False
    updated = False
    for im in imgs:
        if im.get("id") == image_id:
            im["alt"] = new_alt
            updated = True
            break
    if updated:
        # Recalc images_no_alt để bulk gen biết skip SP đã xong
        no_alt_count = sum(1 for im in imgs if classify_alt(im.get("alt")) != "good")
        conn.execute(
            "UPDATE haravan_products SET images = ?, images_no_alt = ?, alt_synced_at = ? "
            "WHERE haravan_id = ?",
            (json.dumps(imgs, ensure_ascii=False), no_alt_count,
             datetime.now().isoformat(timespec="seconds"), product_id),
        )
        conn.commit()
    conn.close()
    return updated


def worst_products(limit: int = 50, only_with_missing: bool = True) -> list[dict[str, Any]]:
    """Top SP có nhiều ảnh thiếu/yếu ALT nhất. Sort: (none + weak) DESC, ties: total_images DESC.

    Mỗi item:
      {product_id, handle, title, type, vendor, total: N, none: N, weak: N, good: N,
       missing_score: none+weak, thumb: src ảnh đầu}
    """
    products = _iter_product_images()
    items = []
    for p in products:
        none_cnt = weak_cnt = good_cnt = 0
        for im in p["images"]:
            s = classify_alt(im.get("alt"))
            if s == "none":
                none_cnt += 1
            elif s == "weak":
                weak_cnt += 1
            else:
                good_cnt += 1
        missing = none_cnt + weak_cnt
        if only_with_missing and missing == 0:
            continue
        items.append({
            "product_id": p["product_id"],
            "handle": p["handle"],
            "title": p["title"],
            "type": p["type"],
            "vendor": p["vendor"],
            "total": none_cnt + weak_cnt + good_cnt,
            "none": none_cnt,
            "weak": weak_cnt,
            "good": good_cnt,
            "missing_score": missing,
            "thumb": (p["images"][0].get("src") if p["images"] else None),
            "alt_synced_at": _fmt_alt_synced(p.get("alt_synced_at")),
        })
    items.sort(key=lambda x: (-x["missing_score"], -x["total"]))
    return items[:limit]


# ─────────────────────────── P5 DESC IMAGES ───────────────────────────

_DESC_ALT_TEMPLATES = [
    "{name} — ảnh mô tả chi tiết",
    "{name} — thông số kỹ thuật",
    "{name} — thiết kế và màu sắc",
    "{name} — hình thực tế sản phẩm",
    "{name} — tính năng nổi bật",
    "{name} — kết nối và phụ kiện",
    "{name} — đóng gói và bảo hành",
    "{name} — góc nhìn toàn diện",
]

_RE_IMG_TAG = re.compile(r"<img[^>]*?>|<img[^>]*>", re.IGNORECASE | re.DOTALL)
_RE_ALT_ATTR = re.compile(r"""\s*alt\s*=\s*(?:"[^"]*"|'[^']*')""", re.IGNORECASE)
_RE_SRC_ATTR = re.compile(r"""src\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def gen_alt_for_desc_image(name: str, idx: int) -> str:
    tpl = _DESC_ALT_TEMPLATES[idx % len(_DESC_ALT_TEMPLATES)]
    alt = tpl.format(name=name)
    if len(alt) > 125:
        alt = alt[:125].rsplit(" ", 1)[0]
    return alt


def get_product_desc_images(product_id: int) -> tuple[list[dict[str, Any]], str]:
    """Fetch body_html LIVE từ Haravan API → parse img tags.

    Trả (images_list, body_html_live). Không đọc DB (DB snapshot cũ).
    """
    import haravan_client as hv_client
    product_data = hv_client.get_product(product_id)
    body_html = product_data.get("body_html") or ""
    result = []
    for i, m in enumerate(_RE_IMG_TAG.finditer(body_html)):
        tag = m.group(0)
        src_m = _RE_SRC_ATTR.search(tag)
        alt_m = re.search(r"""alt\s*=\s*["']([^"']*)["']""", tag, re.IGNORECASE)
        src = src_m.group(1) if src_m else ""
        alt = alt_m.group(1) if alt_m else ""
        result.append({
            "index": i,
            "src": src,
            "alt": alt,
            "status": classify_alt(alt if alt_m else None),
        })
    return result, body_html


def save_desc_image_alts(product_id: int, updates: list[dict[str, Any]], body_html: str) -> str:
    """Inject ALT attrs vào body_html live rồi trả new_html.

    Caller phải truyền body_html live (đã fetch từ Haravan trước đó).
    updates = [{index: int, alt: str}, ...]
    """
    if not body_html:
        return ""
    alt_map = {int(u["index"]): u["alt"] for u in updates}
    idx = 0

    def _replace(m: re.Match) -> str:
        nonlocal idx
        tag = m.group(0)
        new_alt = alt_map.get(idx)
        idx += 1
        if new_alt is None:
            return tag
        tag = _RE_ALT_ATTR.sub("", tag)
        safe_alt = new_alt.replace('"', "&quot;")
        tag = re.sub(r"\s*/?>$", lambda x: f' alt="{safe_alt}"' + x.group(0), tag)
        return tag

    return _RE_IMG_TAG.sub(_replace, body_html)


# ─────────────────────────── P3.5 GEN & SAVE ALL (single SP) ───────────────────────────

def gen_and_save_all_alts(product_id: int) -> dict[str, Any]:
    """Gen + save ALT cho TẤT CẢ ảnh (product + desc) của 1 SP.

    - Ảnh SP: dùng _gen_alt_for_position, PUT /products/{id}/images/{image_id}
    - Ảnh mô tả: fetch live body_html, inject ALT, PUT /products/{id}
    - Bỏ qua ảnh đã good.
    Returns: {ok, saved_product, saved_desc, failed, total}
    """
    from content_writer import _gen_alt_for_position
    import haravan_client as hv_client

    saved_product = 0
    saved_desc = 0
    failed = 0

    # Part 1: product images
    product = get_product_for_editor(product_id)
    if not product:
        return {"ok": False, "error": "SP not found"}

    title = (product.get("title") or product.get("handle") or "").strip()
    imgs = product.get("images", [])
    total_imgs = len(imgs)

    for i, im in enumerate(imgs):
        if classify_alt(im.get("alt")) == "good":
            continue
        image_id = im.get("id")
        if not image_id:
            failed += 1
            continue
        try:
            new_alt = _gen_alt_for_position(title, i + 1, total_imgs)
            result = hv_client.put_image_alt(product_id, image_id, new_alt)
            if result.get("ok"):
                update_image_alt_local(product_id, image_id, new_alt)
                saved_product += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    # Part 2: desc images (live fetch)
    try:
        desc_imgs, live_html = get_product_desc_images(product_id)
        if live_html:
            updates = []
            for im in desc_imgs:
                if classify_alt(im.get("alt")) == "good":
                    continue
                new_alt = gen_alt_for_desc_image(title, im["index"])
                updates.append({"index": im["index"], "alt": new_alt})
            if updates:
                new_html = save_desc_image_alts(product_id, updates, live_html)
                try:
                    hv_client.update_product(product_id, {"body_html": new_html})
                    saved_desc = len(updates)
                    db.mark_alt_synced(product_id)  # cột "Ngày sync"
                except Exception:
                    failed += len(updates)
    except Exception:
        pass  # desc images optional — product images may already have saved fine

    return {
        "ok": True,
        "saved_product": saved_product,
        "saved_desc": saved_desc,
        "failed": failed,
        "total": saved_product + saved_desc,
    }


# ─────────────────────────── P4 BULK GEN JOB ───────────────────────────

_bulk_gen_state: dict[str, Any] = {
    "running": False,
    "stop_requested": False,
    "total": 0,
    "processed": 0,
    "saved": 0,
    "failed": 0,
    "skipped": 0,
    "current": "",
    "started_at": None,
    "finished_at": None,
    "message": "",
}
_bulk_gen_lock = threading.Lock()


def bulk_gen_job_state() -> dict[str, Any]:
    with _bulk_gen_lock:
        out = dict(_bulk_gen_state)
    # Alias cho UI template (đọc saved_imgs/worklist_count)
    out["saved_imgs"] = out.get("saved", 0)
    if not out.get("running"):
        try:
            row = db.get_conn().execute("SELECT COALESCE(SUM(images_no_alt),0) FROM haravan_products").fetchone()
            out["worklist_count"] = row[0] if row else 0
        except Exception:
            out["worklist_count"] = 0
    else:
        out["worklist_count"] = out.get("total", 0)
    return out


def stop_bulk_gen() -> bool:
    with _bulk_gen_lock:
        if _bulk_gen_state["running"]:
            _bulk_gen_state["stop_requested"] = True
            _bulk_gen_state["message"] = "⏹️ Đang dừng — chờ ảnh hiện tại xong..."
            return True
    return False


def run_bulk_gen():
    """Worker: gen ALT + PUT Haravan cho tất cả ảnh (SP + desc). Chạy trong background thread."""
    from content_writer import _gen_alt_for_position
    import haravan_client as hv_client

    products = _iter_product_images()

    # Build task list: mỗi item là 1 product cần xử lý (SP images + desc images)
    product_tasks = []
    sp_img_count = 0
    for p in products:
        imgs = p["images"]
        missing_sp = [
            (i, im) for i, im in enumerate(imgs)
            if classify_alt(im.get("alt")) != "good"
        ]
        # Đếm ảnh SP thiếu + ước tính desc (sẽ fetch live khi chạy)
        sp_img_count += len(missing_sp)
        if missing_sp:
            product_tasks.append({
                "product_id": p["product_id"],
                "title": (p["title"] or p["handle"] or "").strip(),
                "images": imgs,
                "missing_sp": missing_sp,
            })

    with _bulk_gen_lock:
        _bulk_gen_state.update({
            "running": True,
            "stop_requested": False,
            "total": sp_img_count,  # sẽ update khi biết thêm desc count
            "processed": 0,
            "saved": 0,
            "failed": 0,
            "skipped": 0,
            "current": "",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
            "message": f"Đang gen {len(product_tasks)} SP ({sp_img_count} ảnh SP + ảnh mô tả)...",
        })

    for pt in product_tasks:
        with _bulk_gen_lock:
            if _bulk_gen_state["stop_requested"]:
                break
            _bulk_gen_state["current"] = pt["title"][:60]

        product_id = pt["product_id"]
        title = pt["title"]
        imgs = pt["images"]
        total_sp = len(imgs)

        # ── Part 1: SP images ──
        for i, im in pt["missing_sp"]:
            image_id = im.get("id")
            if not image_id:
                with _bulk_gen_lock:
                    _bulk_gen_state["skipped"] += 1
                    _bulk_gen_state["processed"] += 1
                continue
            try:
                new_alt = _gen_alt_for_position(title, i + 1, total_sp)
                result = hv_client.put_image_alt(product_id, image_id, new_alt)
                if result.get("ok"):
                    update_image_alt_local(product_id, image_id, new_alt)
                    with _bulk_gen_lock:
                        _bulk_gen_state["saved"] += 1
                else:
                    with _bulk_gen_lock:
                        _bulk_gen_state["failed"] += 1
            except Exception:
                with _bulk_gen_lock:
                    _bulk_gen_state["failed"] += 1
            with _bulk_gen_lock:
                _bulk_gen_state["processed"] += 1
            time.sleep(0.8)

        # ── Part 2: desc images (fetch live) ──
        try:
            desc_imgs, live_html = get_product_desc_images(product_id)
            updates = []
            for im in desc_imgs:
                if classify_alt(im.get("alt")) != "good":
                    new_alt = gen_alt_for_desc_image(title, im["index"])
                    updates.append({"index": im["index"], "alt": new_alt})
            if updates and live_html:
                new_html = save_desc_image_alts(product_id, updates, live_html)
                try:
                    hv_client.update_product(product_id, {"body_html": new_html})
                    db.mark_alt_synced(product_id)  # cột "Ngày sync"
                    with _bulk_gen_lock:
                        _bulk_gen_state["saved"] += len(updates)
                        _bulk_gen_state["total"] += len(updates)
                        _bulk_gen_state["processed"] += len(updates)
                except Exception:
                    with _bulk_gen_lock:
                        _bulk_gen_state["failed"] += len(updates)
        except Exception:
            pass  # desc optional, không break SP đã save

        time.sleep(0.6)

    with _bulk_gen_lock:
        stop_req = _bulk_gen_state["stop_requested"]
        done = _bulk_gen_state["saved"]
        fail = _bulk_gen_state["failed"]
        _bulk_gen_state.update({
            "running": False,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "message": (
                f"⏹️ Đã dừng — đã lưu {done} ảnh"
                if stop_req else
                f"✅ Xong! Lưu {done} (SP + mô tả) · lỗi {fail}"
            ),
        })


def start_bulk_gen_async() -> bool:
    """Khởi chạy bulk gen trong background thread. Trả False nếu đang chạy rồi."""
    with _bulk_gen_lock:
        if _bulk_gen_state["running"]:
            return False
    t = threading.Thread(target=run_bulk_gen, daemon=True)
    t.start()
    return True


# ─────────────────── DUAL AI BULK GEN (Codex + Claude song song) ───────────────────

def _gen_alts_ai_for_product(title: str, n: int, provider: str) -> list:
    """1 AI call (codex hoặc claude) → list n câu ALT cho n ảnh SP. Có thể trả < n (caller fallback)."""
    import re as _re
    sys_p = ("Bạn là chuyên gia SEO ảnh. Viết ALT text tiếng Việt cho ảnh sản phẩm máy tính/linh kiện. "
             "Mô tả trung tính, rõ ràng, KHÔNG marketing, KHÔNG giá, KHÔNG emoji. Mỗi ALT tối đa 125 ký tự.")
    user_p = (f"Sản phẩm: {title}\n"
              f"Viết đúng {n} câu ALT KHÁC NHAU cho {n} ảnh của sản phẩm này "
              f"(ảnh 1 = ảnh chính/hero, ảnh cuối = ảnh tổng thể, các ảnh giữa = góc/chi tiết khác). "
              f"CHỈ trả về {n} dòng, mỗi dòng 1 ALT, KHÔNG đánh số, KHÔNG giải thích, KHÔNG ký tự thừa.")
    try:
        if provider == "codex":
            raw = codex_provider.call_codex(sys_p, user_p, timeout=120, reasoning_effort="low")
        else:
            raw = claude_provider.call_claude(sys_p, user_p, timeout=120)
    except Exception:
        return []
    out = []
    for ln in (raw or "").splitlines():
        s = _re.sub(r'^\s*[\d\-\*\.\)\:]+\s*', '', ln).strip().strip('"').strip("'").strip()
        if s:
            out.append(s[:125])
    return out


def _process_product_ai(pt: dict, provider: str):
    """Gen + PUT ALT cho 1 SP bằng provider chỉ định. Cập nhật _bulk_gen_state (locked)."""
    from content_writer import _gen_alt_for_position
    import haravan_client as hv_client
    title = pt["title"]
    product_id = pt["product_id"]
    total_sp = len(pt["images"])
    missing = pt["missing_sp"]
    skey = "codex_saved" if provider == "codex" else "claude_saved"

    ai_lines = _gen_alts_ai_for_product(title, len(missing), provider)

    # Part 1: ảnh SP gallery
    for k, (i, im) in enumerate(missing):
        with _bulk_gen_lock:
            if _bulk_gen_state["stop_requested"]:
                return
        image_id = im.get("id")
        if not image_id:
            with _bulk_gen_lock:
                _bulk_gen_state["skipped"] += 1
                _bulk_gen_state["processed"] += 1
            continue
        alt = ai_lines[k] if k < len(ai_lines) and ai_lines[k] else _gen_alt_for_position(title, i + 1, total_sp)
        ok = False
        for attempt in range(2):  # 1 retry (giảm fail do rate-limit nhất thời)
            try:
                res = hv_client.put_image_alt(product_id, image_id, alt)
                if res.get("ok"):
                    ok = True
                    break
            except Exception:
                pass
            time.sleep(0.8 * (attempt + 1))
        if ok:
            update_image_alt_local(product_id, image_id, alt)
            with _bulk_gen_lock:
                _bulk_gen_state["saved"] += 1
                _bulk_gen_state[skey] = _bulk_gen_state.get(skey, 0) + 1
        else:
            with _bulk_gen_lock:
                _bulk_gen_state["failed"] += 1
        with _bulk_gen_lock:
            _bulk_gen_state["processed"] += 1
        time.sleep(0.3)

    # Part 2: ảnh mô tả (giữ template — nhẹ, đa số đã good)
    try:
        desc_imgs, live_html = get_product_desc_images(product_id)
        updates = [{"index": im["index"], "alt": gen_alt_for_desc_image(title, im["index"])}
                   for im in desc_imgs if classify_alt(im.get("alt")) != "good"]
        if updates and live_html:
            new_html = save_desc_image_alts(product_id, updates, live_html)
            hv_client.update_product(product_id, {"body_html": new_html})
            db.mark_alt_synced(product_id)
            with _bulk_gen_lock:
                _bulk_gen_state["saved"] += len(updates)
                _bulk_gen_state[skey] = _bulk_gen_state.get(skey, 0) + len(updates)
                _bulk_gen_state["total"] += len(updates)
                _bulk_gen_state["processed"] += len(updates)
    except Exception:
        pass


def run_bulk_gen_dual(workers_per: int = 3):
    """N worker/provider song song (Codex + Claude) chia hàng đợi chung. Gen ALT bằng AI."""
    import queue as _q
    workers_per = max(1, min(int(workers_per or 3), 8))
    products = _iter_product_images()
    tasks, sp_count = [], 0
    for p in products:
        missing = [(i, im) for i, im in enumerate(p["images"]) if classify_alt(im.get("alt")) != "good"]
        if missing:
            sp_count += len(missing)
            tasks.append({"product_id": p["product_id"],
                          "title": (p["title"] or p["handle"] or "").strip(),
                          "images": p["images"], "missing_sp": missing})

    with _bulk_gen_lock:
        _bulk_gen_state.update({
            "running": True, "stop_requested": False, "total": sp_count,
            "processed": 0, "saved": 0, "failed": 0, "skipped": 0,
            "codex_saved": 0, "claude_saved": 0, "current": "",
            "current_codex": "", "current_claude": "", "mode": "dual",
            "workers_per": workers_per,
            "started_at": datetime.now().isoformat(timespec="seconds"), "finished_at": None,
            "message": f"⚡ Dual AI (Codex×{workers_per} + Claude×{workers_per}) — {len(tasks)} SP / {sp_count} ảnh gallery...",
        })

    q = _q.Queue()
    for t in tasks:
        q.put(t)

    def worker(provider):
        while True:
            with _bulk_gen_lock:
                if _bulk_gen_state["stop_requested"]:
                    return
            try:
                pt = q.get_nowait()
            except _q.Empty:
                return
            ckey = "current_codex" if provider == "codex" else "current_claude"
            with _bulk_gen_lock:
                _bulk_gen_state[ckey] = pt["title"][:50]
                _bulk_gen_state["current"] = f"[{provider}] {pt['title'][:50]}"
            _process_product_ai(pt, provider)

    threads = []
    for _ in range(workers_per):
        threads.append(threading.Thread(target=worker, args=("codex",), daemon=True))
        threads.append(threading.Thread(target=worker, args=("claude",), daemon=True))
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    with _bulk_gen_lock:
        stop_req = _bulk_gen_state["stop_requested"]
        done = _bulk_gen_state["saved"]
        fail = _bulk_gen_state["failed"]
        cx = _bulk_gen_state.get("codex_saved", 0)
        cl = _bulk_gen_state.get("claude_saved", 0)
        _bulk_gen_state.update({
            "running": False,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "message": (f"⏹️ Đã dừng — lưu {done} ảnh (Codex {cx} · Claude {cl})"
                        if stop_req else
                        f"✅ Xong! Lưu {done} ảnh (Codex {cx} · Claude {cl}) · lỗi {fail}"),
        })


def start_bulk_gen_dual_async(workers_per: int = 3) -> bool:
    """Khởi chạy dual AI bulk gen (Codex×N + Claude×N). False nếu đang chạy."""
    with _bulk_gen_lock:
        if _bulk_gen_state["running"]:
            return False
    threading.Thread(target=run_bulk_gen_dual, args=(workers_per,), daemon=True).start()
    return True
