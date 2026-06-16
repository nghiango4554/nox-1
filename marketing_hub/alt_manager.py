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
    if len(words) < 5:
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

def gen_and_save_all_alts(product_id: int, desc_only: bool = False) -> dict[str, Any]:
    """Gen + save ALT cho ảnh của 1 SP.

    - Ảnh SP: dùng _gen_alt_for_position, PUT /products/{id}/images/{image_id}
    - Ảnh mô tả: fetch live body_html, inject ALT, PUT /products/{id}
    - Bỏ qua ảnh đã good.
    - desc_only=True: CHỈ xử lý ảnh mô tả (bỏ qua ảnh SP).
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

    if not desc_only:
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
        return dict(_bulk_gen_state)


def stop_bulk_gen() -> bool:
    with _bulk_gen_lock:
        if _bulk_gen_state["running"]:
            _bulk_gen_state["stop_requested"] = True
            _bulk_gen_state["message"] = "⏹️ Đang dừng — chờ ảnh hiện tại xong..."
            return True
    return False


def run_bulk_gen(desc_only: bool = False):
    """Worker: gen ALT + PUT Haravan cho ảnh. Chạy trong background thread.

    desc_only=True: CHỈ xử lý ảnh mô tả (body_html), bỏ qua ảnh SP.
    """
    from content_writer import _gen_alt_for_position
    import haravan_client as hv_client

    products = _iter_product_images()

    # Build task list: mỗi item là 1 product cần xử lý (SP images + desc images)
    product_tasks = []
    sp_img_count = 0
    for p in products:
        imgs = p["images"]
        if desc_only:
            # Chỉ chọn SP có ảnh mô tả thiếu ALT (lọc theo DB snapshot để né API thừa)
            missing_sp = []
            _, desc_missing = _count_desc_images(p.get("body_html"))
            if desc_missing == 0:
                continue
        else:
            missing_sp = [
                (i, im) for i, im in enumerate(imgs)
                if classify_alt(im.get("alt")) != "good"
            ]
            # Đếm ảnh SP thiếu + ước tính desc (sẽ fetch live khi chạy)
            sp_img_count += len(missing_sp)
            if not missing_sp:
                continue
        product_tasks.append({
            "product_id": p["product_id"],
            "title": (p["title"] or p["handle"] or "").strip(),
            "images": imgs,
            "missing_sp": missing_sp,
        })

    mode_label = "ảnh mô tả" if desc_only else f"{sp_img_count} ảnh SP + ảnh mô tả"
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
            "message": f"Đang gen {len(product_tasks)} SP ({mode_label})...",
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


def start_bulk_gen_async(desc_only: bool = False) -> bool:
    """Khởi chạy bulk gen trong background thread. Trả False nếu đang chạy rồi.

    desc_only=True: chỉ gen ALT cho ảnh mô tả.
    """
    with _bulk_gen_lock:
        if _bulk_gen_state["running"]:
            return False
    t = threading.Thread(target=run_bulk_gen, kwargs={"desc_only": desc_only}, daemon=True)
    t.start()
    return True


# ════════════════════════════════════════════════════════════════════════════
#  ALT MÔ TẢ — FETCH (live) → AI GEN / DUAL AI GEN
#  Flow mới: (1) Fetch ảnh thiếu ALT trong mô tả LIVE từ Haravan → worklist
#            (2) AI gen (fallback chain) HOẶC Dual AI gen (Codex ∥ Claude)
#            → inject ALT + PUT thẳng lên Haravan.
# ════════════════════════════════════════════════════════════════════════════

# Worklist: list[{product_id, title, missing_count}] — SP có ảnh mô tả thiếu ALT.
_alt_worklist: list[dict[str, Any]] = []

_alt_fetch_state: dict[str, Any] = {
    "running": False, "stop_requested": False,
    "total": 0, "scanned": 0,
    "found_products": 0, "found_images": 0,
    "current": "", "started_at": None, "finished_at": None,
    "message": "", "done": False,
}
_alt_fetch_lock = threading.Lock()

_alt_gen_state: dict[str, Any] = {
    "running": False, "stop_requested": False, "mode": None,
    "total": 0, "processed": 0, "saved_imgs": 0, "failed": 0,
    "current": "", "current_codex": "", "current_claude": "",
    "providers": [], "started_at": None, "finished_at": None, "message": "",
}
_alt_gen_lock = threading.Lock()


def alt_fetch_state() -> dict[str, Any]:
    with _alt_fetch_lock:
        return dict(_alt_fetch_state)


def alt_gen_state() -> dict[str, Any]:
    with _alt_gen_lock:
        st = dict(_alt_gen_state)
    st["worklist_count"] = len(_alt_worklist)
    return st


def stop_alt_fetch() -> bool:
    with _alt_fetch_lock:
        if _alt_fetch_state["running"]:
            _alt_fetch_state["stop_requested"] = True
            return True
    return False


def stop_alt_gen() -> bool:
    with _alt_gen_lock:
        if _alt_gen_state["running"]:
            _alt_gen_state["stop_requested"] = True
            _alt_gen_state["message"] = "⏹️ Đang dừng — chờ SP hiện tại xong..."
            return True
    return False


# ─────────────────────────── FETCH (live Haravan) ───────────────────────────

def _candidates_with_desc_images() -> list[dict[str, Any]]:
    """SP có khả năng chứa ảnh mô tả (DB body_html có <img). Pre-filter để né
    quét live toàn shop. Trả [{product_id, title}]."""
    conn = db.get_conn()
    rows = conn.execute("""
        SELECT haravan_id, handle, title
        FROM haravan_products
        WHERE body_html LIKE '%<img%'
    """).fetchall()
    conn.close()
    return [{"product_id": r["haravan_id"],
             "title": (r["title"] or r["handle"] or "").strip()} for r in rows]


def run_alt_fetch():
    """Worker: quét LIVE body_html từng SP → đếm ảnh mô tả thiếu ALT → build worklist."""
    global _alt_worklist
    cands = _candidates_with_desc_images()
    _alt_worklist = []

    with _alt_fetch_lock:
        _alt_fetch_state.update({
            "running": True, "stop_requested": False,
            "total": len(cands), "scanned": 0,
            "found_products": 0, "found_images": 0,
            "current": "", "done": False,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
            "message": f"Đang quét live {len(cands)} SP có ảnh mô tả...",
        })

    found_imgs = 0
    for c in cands:
        with _alt_fetch_lock:
            if _alt_fetch_state["stop_requested"]:
                break
            _alt_fetch_state["current"] = c["title"][:60]
        try:
            desc_imgs, _ = get_product_desc_images(c["product_id"])
            missing = sum(1 for im in desc_imgs if classify_alt(im.get("alt")) != "good")
        except Exception:
            missing = 0
        if missing > 0:
            _alt_worklist.append({
                "product_id": c["product_id"],
                "title": c["title"],
                "missing_count": missing,
            })
            found_imgs += missing
        with _alt_fetch_lock:
            _alt_fetch_state["scanned"] += 1
            _alt_fetch_state["found_products"] = len(_alt_worklist)
            _alt_fetch_state["found_images"] = found_imgs
        time.sleep(0.25)

    with _alt_fetch_lock:
        stop_req = _alt_fetch_state["stop_requested"]
        _alt_fetch_state.update({
            "running": False, "done": True, "current": "",
            "finished_at": datetime.now().isoformat(timespec="seconds"),
            "message": (
                f"{'⏹️ Dừng' if stop_req else '✅ Quét xong'} — "
                f"{len(_alt_worklist)} SP / {found_imgs} ảnh mô tả thiếu ALT."
            ),
        })


def start_alt_fetch_async() -> dict[str, Any]:
    with _alt_fetch_lock:
        if _alt_fetch_state["running"]:
            return {"ok": False, "error": "Đang fetch rồi."}
    with _alt_gen_lock:
        if _alt_gen_state["running"]:
            return {"ok": False, "error": "Đang gen — dừng gen trước khi fetch lại."}
    threading.Thread(target=run_alt_fetch, daemon=True).start()
    return {"ok": True}


# ─────────────────────────── AI GEN (single + dual) ───────────────────────────

_ALT_GEN_SYSTEM = (
    "Bạn là chuyên gia SEO tiếng Việt, viết ALT text cho ảnh trong phần mô tả "
    "sản phẩm máy tính/linh kiện. Mỗi ALT 6–14 từ, mô tả tự nhiên, có chứa tên/loại "
    "sản phẩm, KHÔNG nhồi từ khoá, KHÔNG dùng dấu ngoặc kép, KHÔNG đánh số thứ tự."
)


def _gen_alts_via_ai(title: str, n: int, provider: str | None) -> list[str]:
    """Gọi AI gen n ALT cho 1 SP. provider=None → fallback chain; ngược lại ghim 1 provider.
    Trả list[str] đúng n phần tử (fallback template nếu thiếu)."""
    import ai_provider
    user = (
        f"Sản phẩm: {title}\n"
        f"Hãy viết {n} câu ALT khác nhau cho {n} ảnh mô tả (theo thứ tự). "
        f"Trả về DUY NHẤT một mảng JSON gồm {n} chuỗi, không giải thích. "
        f'Ví dụ: ["chuột gaming Logitech thiết kế công thái học", "..."]'
    )
    if provider:
        raw = ai_provider.call_ai_single(provider, _ALT_GEN_SYSTEM, user, timeout=120)
    else:
        raw = ai_provider.call_ai(_ALT_GEN_SYSTEM, user, timeout=120)
    alts: list[str] = []
    m = re.search(r"\[.*\]", raw or "", re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(0))
            alts = [str(x).strip().strip('"').replace('"', "")[:125] for x in arr if str(x).strip()]
        except Exception:
            alts = []
    # Bù cho đủ n (template) nếu AI trả thiếu / lỗi parse
    for i in range(len(alts), n):
        alts.append(gen_alt_for_desc_image(title, i))
    return alts[:n]


def _gen_save_one_product(product_id: int, title: str, provider: str | None) -> int:
    """Re-fetch live → gen ALT các ảnh thiếu → inject → PUT Haravan. Trả số ảnh đã lưu.
    Raise nếu AI provider hết quota (caller xử lý cho dual)."""
    import haravan_client as hv_client
    desc_imgs, live_html = get_product_desc_images(product_id)
    if not live_html:
        return 0
    missing = [im for im in desc_imgs if classify_alt(im.get("alt")) != "good"]
    if not missing:
        return 0
    alts = _gen_alts_via_ai(title, len(missing), provider)
    updates = [{"index": im["index"], "alt": a} for im, a in zip(missing, alts)]
    new_html = save_desc_image_alts(product_id, updates, live_html)
    hv_client.update_product(product_id, {"body_html": new_html})
    db.mark_alt_synced(product_id)
    return len(updates)


def run_alt_gen(dual: bool):
    """Worker gen ALT trên worklist. dual=False: 1 luồng fallback chain.
    dual=True: 2 luồng Codex ∥ Claude (mỗi luồng ghim 1 provider)."""
    global _alt_worklist
    import ai_provider
    queue = list(_alt_worklist)

    with _alt_gen_lock:
        _alt_gen_state.update({
            "running": True, "stop_requested": False,
            "mode": "dual" if dual else "single",
            "total": len(queue), "processed": 0, "saved_imgs": 0, "failed": 0,
            "current": "", "current_codex": "", "current_claude": "",
            "providers": ["codex", "claude"] if dual else ai_provider.available_providers(),
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
            "message": (f"Dual-AI (Codex ∥ Claude): gen {len(queue)} SP."
                        if dual else f"AI gen: {len(queue)} SP."),
        })

    quota_flag = {"codex": False, "claude": False, "single": False}

    def worker(provider: str | None):
        cur_key = f"current_{provider}" if provider else "current"
        qkey = provider or "single"
        while True:
            with _alt_gen_lock:
                if _alt_gen_state["stop_requested"] or not queue:
                    break
                item = queue.pop(0)
                _alt_gen_state[cur_key] = item["title"][:60]
            try:
                saved = _gen_save_one_product(item["product_id"], item["title"], provider)
                with _alt_gen_lock:
                    _alt_gen_state["saved_imgs"] += saved
                    _alt_gen_state["processed"] += 1
                    _alt_gen_state[cur_key] = ""
            except ai_provider.AIQuotaError:
                # Trả SP về hàng đợi cho luồng kia; luồng này nghỉ.
                with _alt_gen_lock:
                    queue.insert(0, item)
                    quota_flag[qkey] = True
                    _alt_gen_state[cur_key] = ""
                break
            except Exception:
                with _alt_gen_lock:
                    _alt_gen_state["failed"] += 1
                    _alt_gen_state["processed"] += 1
                    _alt_gen_state[cur_key] = ""
            time.sleep(0.5)

    if dual:
        tc = threading.Thread(target=worker, args=("codex",), daemon=True)
        tk = threading.Thread(target=worker, args=("claude",), daemon=True)
        tc.start(); tk.start(); tc.join(); tk.join()
    else:
        worker(None)

    with _alt_gen_lock:
        st = _alt_gen_state
        stop_req = st["stop_requested"]
        leftover = len(queue)
        st.update({
            "running": False, "mode": None, "current": "",
            "current_codex": "", "current_claude": "",
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        })
        if stop_req:
            prefix = "⏹️ Đã dừng"
        elif dual and quota_flag["codex"] and quota_flag["claude"]:
            prefix = "⛔ Cả Codex + Claude hết quota"
        elif quota_flag["single"]:
            prefix = "⛔ Hết quota AI"
        else:
            prefix = "🏁 Hoàn tất"
        st["message"] = (
            f"{prefix} — lưu {st['saved_imgs']} ảnh (❌ {st['failed']}) / {st['total']} SP."
            + (f" Còn {leftover} SP chưa làm." if leftover else "")
        )
    # Worklist còn lại = phần chưa làm (cho lần bấm sau)
    _alt_worklist = queue


def start_alt_gen_async(dual: bool) -> dict[str, Any]:
    """Khởi chạy gen trên worklist đã fetch. dual=True cần CẢ Codex + Claude khả dụng."""
    import ai_provider
    if not _alt_worklist:
        return {"ok": False, "error": "Chưa có data — bấm 'Fetch ảnh' trước."}
    with _alt_fetch_lock:
        if _alt_fetch_state["running"]:
            return {"ok": False, "error": "Đang fetch — đợi xong rồi gen."}
    with _alt_gen_lock:
        if _alt_gen_state["running"]:
            return {"ok": False, "error": "Đang gen rồi."}
    if dual:
        avail = ai_provider.available_providers()
        missing = [p for p in ("codex", "claude") if p not in avail]
        if missing:
            return {"ok": False,
                    "error": f"Dual-AI cần CẢ Codex + Claude. Thiếu: {', '.join(missing)} "
                             f"(đang có: {', '.join(avail) or 'không có'})."}
    else:
        if not ai_provider.available_providers():
            return {"ok": False, "error": "Không có provider AI nào khả dụng."}
    threading.Thread(target=run_alt_gen, kwargs={"dual": dual}, daemon=True).start()
    return {"ok": True, "count": len(_alt_worklist), "mode": "dual" if dual else "single"}
