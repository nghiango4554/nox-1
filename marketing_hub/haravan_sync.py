"""Sync products từ Haravan API → DB local + audit SEO/content."""
import json
import re
import threading
import time
from datetime import datetime

from bs4 import BeautifulSoup

import db
import haravan_client as hv


PAGE_LIMIT = 50  # Haravan max 250, dùng 50 cho an toàn rate-limit
PER_PAGE_DELAY = 0.5  # giây giữa mỗi trang


_sync_lock = threading.Lock()
_sync_state = {
    "run_id": None,
    "status": "idle",   # idle|fetching|done|failed
    "total": 0,
    "fetched": 0,
    "failed": 0,
    "started_at": None,
    "message": "",
}


def sync_state():
    with _sync_lock:
        return dict(_sync_state)


def _set_state(**kw):
    with _sync_lock:
        _sync_state.update(kw)


# ─────────────────────────── AUDIT ───────────────────────────


HV_ISSUE_LABELS = {
    "no_title":            ("🔴", "Thiếu tiêu đề", "Bắt buộc có title sản phẩm."),
    "title_short":         ("🟡", "Title ngắn", "Mở rộng 30-65 ký tự, có tên SP + USP."),
    "title_long":          ("🟡", "Title dài", "Rút xuống ≤65 ký tự."),
    "no_body":             ("🔴", "Thiếu mô tả", "Viết mô tả sản phẩm ≥300 từ (Sintech chuẩn ≥800)."),
    "body_thin":           ("🟡", "Mô tả mỏng", "Tăng nội dung ≥800 từ — Google đánh giá cao trang chi tiết."),
    "no_images":           ("🔴", "Không có ảnh", "Thêm ít nhất 3 ảnh sản phẩm."),
    "few_images":          ("🟡", "Ít ảnh", "Thêm ≥3 ảnh: chính diện, góc cạnh, chi tiết, đóng gói."),
    "images_no_alt":       ("🟡", "Ảnh thiếu alt", "Thêm alt text mô tả ảnh — tốt SEO + accessibility."),
    "no_meta_title":       ("🟡", "Thiếu meta title", "Đặt meta title 30-65 ký tự để hiện trên Google."),
    "no_meta_desc":        ("🟡", "Thiếu meta description", "Viết meta 140-160 ký tự + CTA viết HOA."),
    "meta_desc_short":     ("🟡", "Meta description ngắn", "Mở rộng lên 140-160 ký tự."),
    "meta_desc_long":      ("🟡", "Meta description dài", "Rút xuống ≤160 ký tự — Google sẽ cắt phần thừa."),
    "meta_no_cta":         ("🟡", "Meta thiếu CTA HOA", "Thêm CTA: 'XEM NGAY tại Sintech', 'CHỌN NGAY', 'KHÁM PHÁ NGAY'."),
    "no_tags":             ("🔵", "Thiếu tags", "Thêm tags để filter và internal linking."),
    "no_vendor":           ("🔵", "Thiếu vendor", "Đặt vendor (thương hiệu) để gom theo brand."),
    "no_product_type":     ("🔵", "Thiếu product type", "Đặt product_type để phân loại."),
    "no_inventory":        ("🟡", "Hết hàng", "Inventory = 0 — cập nhật hoặc bỏ trạng thái 'available'."),
    "draft":               ("🔵", "Đang draft", "Sản phẩm chưa publish."),
    "missing_sintech":     ("🟡", "Thiếu section Sintech", "Bổ sung 'Vì sao mua tại Sintech' + 'Câu hỏi thường gặp'."),
    "sintech_in_title":    ("🟡", "Title chứa 'Sintech'", "Bỏ 'Sintech' khỏi title — rule nội bộ."),
}


def hv_enrich_issue(it: dict) -> dict:
    icon, label, fix = HV_ISSUE_LABELS.get(it.get("code", ""), ("⚪", it.get("code", ""), ""))
    return {**it, "icon": icon, "label": label, "fix": fix}


def audit_product(p: dict) -> tuple:
    """Phân tích product Haravan → (score, issues_list).

    p: product dict đã chuẩn hoá (output của _normalize_product).
    """
    issues = []
    score = 0

    title = (p.get("title") or "").strip()
    title_len = len(title)
    if not title:
        issues.append({"level": "error", "code": "no_title", "msg": "Thiếu title"})
    elif title_len < 20:
        issues.append({"level": "warn", "code": "title_short", "msg": f"Title {title_len} ký tự"})
        score += 5
    elif title_len > 70:
        issues.append({"level": "warn", "code": "title_long", "msg": f"Title {title_len} ký tự"})
        score += 5
    else:
        score += 15
    if title and "sintech" in title.lower():
        issues.append({"level": "warn", "code": "sintech_in_title", "msg": "Title chứa 'Sintech'"})

    body_html = p.get("body_html") or ""
    body_text = ""
    if body_html:
        try:
            body_text = BeautifulSoup(body_html, "lxml").get_text(" ", strip=True)
        except Exception:
            body_text = re.sub(r"<[^>]+>", " ", body_html)
    word_count = len(re.findall(r"\w+", body_text, flags=re.UNICODE))
    p["word_count"] = word_count
    if not body_html.strip():
        issues.append({"level": "error", "code": "no_body", "msg": "Thiếu mô tả"})
    elif word_count < 300:
        issues.append({"level": "warn", "code": "body_thin", "msg": f"Mô tả {word_count} từ"})
        score += 5
    elif word_count < 800:
        issues.append({"level": "info", "code": "body_thin", "msg": f"Mô tả {word_count} từ (chuẩn ≥800)"})
        score += 10
    else:
        score += 20

    body_lower = body_text.lower()
    has_sintech_section = "vì sao" in body_lower and "sintech" in body_lower
    has_faq = any(x in body_lower for x in ("câu hỏi thường gặp", "faq", "hỏi đáp"))
    if not has_sintech_section and not has_faq:
        issues.append({"level": "warn", "code": "missing_sintech", "msg": "Thiếu section Sintech / FAQ"})
    elif has_sintech_section and has_faq:
        score += 5

    images_count = p.get("images_count", 0)
    images_no_alt = p.get("images_no_alt", 0)
    if images_count == 0:
        issues.append({"level": "error", "code": "no_images", "msg": "Không có ảnh"})
    elif images_count < 3:
        issues.append({"level": "warn", "code": "few_images", "msg": f"Chỉ {images_count} ảnh"})
        score += 5
    else:
        score += 10
    if images_count > 0 and images_no_alt > 0:
        if images_no_alt >= images_count:
            issues.append({"level": "warn", "code": "images_no_alt", "msg": f"{images_no_alt}/{images_count} ảnh thiếu alt"})
        else:
            issues.append({"level": "info", "code": "images_no_alt", "msg": f"{images_no_alt}/{images_count} ảnh thiếu alt"})
            score += 5
    elif images_count > 0:
        score += 10

    meta_title = (p.get("meta_title") or "").strip()
    meta_desc = (p.get("meta_description") or "").strip()
    if not meta_title:
        issues.append({"level": "warn", "code": "no_meta_title", "msg": "Thiếu meta title"})
    else:
        score += 5

    if not meta_desc:
        issues.append({"level": "warn", "code": "no_meta_desc", "msg": "Thiếu meta description"})
    else:
        meta_len = len(meta_desc)
        if meta_len < 140:
            issues.append({"level": "warn", "code": "meta_desc_short", "msg": f"Meta {meta_len} ký tự"})
            score += 5
        elif meta_len > 160:
            issues.append({"level": "warn", "code": "meta_desc_long", "msg": f"Meta {meta_len} ký tự"})
            score += 5
        else:
            score += 10
        cta_keywords = ["XEM NGAY", "CHỌN NGAY", "THAM KHẢO NGAY", "KHÁM PHÁ NGAY", "MUA NGAY"]
        if not any(kw in meta_desc for kw in cta_keywords):
            issues.append({"level": "warn", "code": "meta_no_cta", "msg": "Meta thiếu CTA HOA"})
        else:
            score += 5

    if not (p.get("tags") or "").strip():
        issues.append({"level": "info", "code": "no_tags", "msg": "Thiếu tags"})
    else:
        score += 5
    if not (p.get("vendor") or "").strip():
        issues.append({"level": "info", "code": "no_vendor", "msg": "Thiếu vendor"})
    else:
        score += 3
    if not (p.get("product_type") or "").strip():
        issues.append({"level": "info", "code": "no_product_type", "msg": "Thiếu product type"})
    else:
        score += 2

    if (p.get("inventory_total") or 0) <= 0:
        issues.append({"level": "warn", "code": "no_inventory", "msg": "Inventory = 0"})

    if p.get("status") == "draft":
        issues.append({"level": "info", "code": "draft", "msg": "Sản phẩm draft"})

    return min(100, max(0, score)), issues


# ─────────────────────────── NORMALIZE ───────────────────────────


def _normalize_product(raw: dict) -> dict:
    """Chuẩn hoá product Haravan → dict cho hv_upsert_product."""
    images = raw.get("images") or []
    images_count = len(images)
    images_no_alt = sum(1 for img in images if not (img.get("alt") or "").strip())
    img_summary = [
        {
            "id": img.get("id"),
            "src": img.get("src"),
            "alt": img.get("alt") or "",
            "position": img.get("position"),
        }
        for img in images
    ]

    variants = raw.get("variants") or []
    prices = [float(v.get("price") or 0) for v in variants if v.get("price")]
    inventory = sum(int(v.get("inventory_quantity") or 0) for v in variants)

    # SEO meta — Haravan có thể trả 'metafields_global_title_tag' / 'metafields_global_description_tag'
    meta_title = raw.get("metafields_global_title_tag") or raw.get("meta_title") or ""
    meta_desc = raw.get("metafields_global_description_tag") or raw.get("meta_description") or ""

    return {
        "haravan_id": raw.get("id"),
        "handle": raw.get("handle"),
        "title": raw.get("title"),
        "vendor": raw.get("vendor"),
        "product_type": raw.get("product_type"),
        "status": raw.get("published_at") and "active" or "draft",
        "body_html": raw.get("body_html"),
        "tags": raw.get("tags"),
        "images_count": images_count,
        "images_no_alt": images_no_alt,
        "images": json.dumps(img_summary, ensure_ascii=False) if img_summary else None,
        "variants_count": len(variants),
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "inventory_total": inventory,
        "meta_title": meta_title or None,
        "meta_description": meta_desc or None,
        "created_at_haravan": raw.get("created_at"),
        "updated_at_haravan": raw.get("updated_at"),
        "published_at": raw.get("published_at"),
    }


def upsert_with_audit(raw: dict):
    """Chuẩn hoá + audit + lưu DB."""
    p = _normalize_product(raw)
    score, issues = audit_product(p)
    p["audit_score"] = score
    p["audit_issues"] = json.dumps(issues, ensure_ascii=False)
    p["last_synced"] = datetime.now().isoformat(timespec="seconds")
    p["last_audited"] = p["last_synced"]
    db.hv_upsert_product(p)


# ─────────────────────────── SYNC RUNNER ───────────────────────────


def run_sync(limit_pages: int = None):
    """Sync toàn bộ products từ Haravan.

    `limit_pages`: nếu set, chỉ sync N trang đầu (test).
    """
    run_id = db.hv_create_sync(notes="manual" if limit_pages else "full")
    _set_state(
        run_id=run_id, status="fetching",
        total=0, fetched=0, failed=0,
        started_at=datetime.now().isoformat(timespec="seconds"),
        message="Đang đếm tổng SP...",
    )
    try:
        total = hv.count_products()
        _set_state(total=total, message=f"Sync {total} sản phẩm...")
        fetched = 0
        failed = 0
        page = 1
        while True:
            try:
                items = hv.list_products(page=page, limit=PAGE_LIMIT)
            except Exception as e:
                _set_state(message=f"Lỗi page {page}: {e.__class__.__name__}")
                failed += 1
                break
            if not items:
                break
            for raw in items:
                try:
                    upsert_with_audit(raw)
                    fetched += 1
                except Exception:
                    failed += 1
            db.hv_update_sync(run_id, total, fetched, failed)
            _set_state(fetched=fetched, failed=failed, message=f"Page {page}: {fetched}/{total}")
            page += 1
            if limit_pages and page > limit_pages:
                break
            time.sleep(PER_PAGE_DELAY)

        db.hv_finish_sync(run_id, "done", total, fetched, failed)
        _set_state(status="done", message=f"Xong: {fetched}/{total} ({failed} lỗi).")
        try:
            import notifier
            notifier.notify_haravan_sync_done(sync_state(), db.hv_stats())
            db.activity_log(
                kind="hv_sync_done", icon="🛒",
                title=f"Sync Haravan xong: {fetched} SP",
                description=f"Lỗi: {failed}",
                href="/haravan",
            )
        except Exception:
            pass
    except Exception as e:
        db.hv_finish_sync(run_id, "failed", 0, 0, 0)
        _set_state(status="failed", message=f"Lỗi: {e.__class__.__name__}: {str(e)[:200]}")
        try:
            import notifier
            notifier.send_telegram(f"❌ Sync Haravan lỗi: {e.__class__.__name__}: {str(e)[:200]}")
        except Exception:
            pass


def start_sync_async(limit_pages: int = None) -> bool:
    snap = sync_state()
    if snap["status"] == "fetching":
        return False
    t = threading.Thread(target=run_sync, args=(limit_pages,), daemon=True)
    t.start()
    return True


def run_sync_incremental():
    """Incremental sync: chỉ pull SP có updated_at > lần sync cuối trong DB.

    Nhanh hơn full sync vì bỏ qua SP không đổi.
    SP mới thêm cũng được bắt (created_at > last_sync cũng nằm trong updated_at_min).
    """
    conn = db.get_conn()
    row = conn.execute("SELECT MAX(last_synced) as last FROM haravan_products").fetchone()
    last_synced = (row["last"] if row and row["last"] else None)
    conn.close()

    # Lấy updated_at_min: dùng last_synced - 1 phút để tránh race condition
    if last_synced:
        from datetime import datetime, timedelta
        dt = datetime.fromisoformat(last_synced) - timedelta(minutes=1)
        updated_at_min = dt.isoformat(timespec="seconds")
    else:
        updated_at_min = None  # fallback: sync toàn bộ

    run_id = db.hv_create_sync(notes=f"incremental since {updated_at_min or 'all'}")
    _set_state(
        run_id=run_id, status="fetching",
        total=0, fetched=0, failed=0,
        started_at=datetime.now().isoformat(timespec="seconds"),
        message=f"Incremental sync từ {updated_at_min or 'đầu'}...",
    )
    try:
        total = hv.count_products(updated_at_min=updated_at_min)
        _set_state(total=total, message=f"Có {total} SP cần cập nhật...")
        if total == 0:
            db.hv_finish_sync(run_id, "done", 0, 0, 0)
            _set_state(status="done", message="✅ Không có SP nào thay đổi kể từ lần sync cuối.")
            return

        fetched = 0
        failed = 0
        page = 1
        while True:
            try:
                items = hv.list_products(page=page, limit=PAGE_LIMIT,
                                         updated_at_min=updated_at_min)
            except Exception as e:
                _set_state(message=f"Lỗi page {page}: {e.__class__.__name__}")
                failed += 1
                break
            if not items:
                break
            for raw in items:
                try:
                    upsert_with_audit(raw)
                    fetched += 1
                except Exception:
                    failed += 1
            db.hv_update_sync(run_id, total, fetched, failed)
            _set_state(fetched=fetched, failed=failed,
                       message=f"Incremental page {page}: {fetched}/{total}")
            page += 1
            time.sleep(PER_PAGE_DELAY)

        db.hv_finish_sync(run_id, "done", total, fetched, failed)
        _set_state(status="done",
                   message=f"✅ Incremental xong: {fetched} SP cập nhật ({failed} lỗi)")
    except Exception as e:
        db.hv_finish_sync(run_id, "failed", 0, 0, 0)
        _set_state(status="failed", message=f"Lỗi: {e.__class__.__name__}: {str(e)[:200]}")


def start_sync_incremental_async() -> bool:
    """Chạy incremental sync trong background thread."""
    snap = sync_state()
    if snap["status"] == "fetching":
        return False
    t = threading.Thread(target=run_sync_incremental, daemon=True)
    t.start()
    return True


def _fetch_all_live_ids() -> set:
    """Kéo TOÀN BỘ haravan_id còn sống trên Haravan (page-based + retry).
    Raise nếu fetch dở dang để CALLER không dám xóa nhầm."""
    expected = hv.count_products()
    live, page, errs = set(), 1, 0
    while page <= 200:
        try:
            items = hv.list_products(page=page, limit=PAGE_LIMIT, fields="id")
        except Exception:
            errs += 1
            if errs > 3:
                raise RuntimeError(f"Fetch live ids lỗi liên tục tại page {page}")
            time.sleep(2)
            continue
        if not items:
            break
        live.update(p["id"] for p in items)
        page += 1
        errs = 0
        time.sleep(PER_PAGE_DELAY)
    # Safety: thiếu >5% so với count → coi như fetch dở, KHÔNG cho xóa
    if expected and len(live) < expected * 0.95:
        raise RuntimeError(f"Fetch chỉ được {len(live)}/{expected} SP — bỏ prune để tránh xóa nhầm")
    return live


def prune_stale_products(dry_run: bool = False) -> dict:
    """Dọn SP 'chết' trong cache = SP còn trong haravan_products nhưng KHÔNG còn trên Haravan live.
    Có safety: chỉ xóa khi đã kéo đủ ≥95% danh sách live. dry_run=True chỉ đếm, không xóa."""
    live = _fetch_all_live_ids()
    cache = db.hv_all_product_ids()
    stale = sorted(cache - live)
    missing = sorted(live - cache)  # SP live chưa có trong cache (chỉ báo, không xử lý ở đây)
    deleted = 0
    if stale and not dry_run:
        deleted = db.hv_delete_products(stale)
    return {
        "live": len(live), "cache_before": len(cache),
        "stale": len(stale), "deleted": deleted,
        "missing_in_cache": len(missing), "dry_run": dry_run,
    }
