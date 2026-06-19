# -*- coding: utf-8 -*-
"""Import image/alt issues từ LibreCrawl (+ crawler nhà) vào queue /alt-manager.

- Bảng riêng `alt_image_issues` (additive, idempotent).
- Dedup theo (page_url, image_src). Chạy lại không duplicate (ON CONFLICT update last_seen).
- KHÔNG auto apply live, KHÔNG upload, KHÔNG PUT. Chỉ tạo queue để review.

Phân loại type: missing_alt | empty_alt | broken_image_404 | image_no_response
              | cdn_rate_limited_suspected | external_image | wrong_store | ok_ignore
Context: product_main_image | product_gallery | collection_image | blog_hero
         | blog_body_inline | product_description_inline | theme_asset | unknown
"""
import json, re, sqlite3
from datetime import datetime
from urllib.parse import urlparse
import db

STORE_ID = "200000860097"  # Sintech Haravan store id
LC_DB = r"C:/Users/NGHIANGO/.openclaw/workspace/LibreCrawl/data/users.db"

# ─────────────────────────── table ───────────────────────────
def ensure_table():
    conn = db.get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alt_image_issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_url TEXT NOT NULL,
            image_src TEXT NOT NULL,
            issue_type TEXT,
            context TEXT,
            alt_text TEXT,
            source TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            UNIQUE(page_url, image_src)
        )""")
    conn.commit(); conn.close()

# ─────────────────────────── classify ───────────────────────────
_PRIORITY = {"broken_image_404": 90, "image_no_response": 60, "wrong_store": 80,
             "missing_alt": 40, "empty_alt": 40, "external_image": 20,
             "cdn_rate_limited_suspected": 10, "ok_ignore": 0}

def classify_context(page_url: str, src: str) -> str:
    s = (src or "").lower(); p = (page_url or "").lower()
    if "/themes/" in s:
        return "theme_asset"
    if "file.hstatic.net" in s:
        return "product_description_inline"
    if "/products/" in p:
        return "product_gallery"      # main vs gallery khó tách từ crawl → gộp gallery
    if "/collections/" in p:
        return "collection_image"
    if "/blogs/" in p or "/blog/" in p:
        return "blog_body_inline"
    return "unknown"

def classify_broken(issue_label: str, src: str) -> str:
    s = (src or "").lower()
    host = urlparse(src or "").netloc.lower()
    cdn = ("cdn.hstatic.net" in host or "product.hstatic.net" in host)
    if "404" in issue_label:
        return "broken_image_404"           # file thật không tồn tại (kể cả trên CDN)
    # No Response / 403 trên CDN Haravan = nghi rate-limit, không phải hỏng thật
    if cdn:
        return "cdn_rate_limited_suspected"
    return "image_no_response"

def _alt_type(src: str) -> str:
    host = urlparse(src or "").netloc.lower()
    if host and ("hstatic.net" not in host and "sintech.vn" not in host):
        return "external_image"
    if "hstatic.net" in host and STORE_ID not in (src or ""):
        return "wrong_store"
    return "missing_alt"

# ─────────────────────────── upsert ───────────────────────────
def _upsert(conn, page_url, image_src, issue_type, context, alt_text, source):
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("""
        INSERT INTO alt_image_issues
          (page_url,image_src,issue_type,context,alt_text,source,status,priority,first_seen,last_seen)
        VALUES (?,?,?,?,?,?,'pending',?,?,?)
        ON CONFLICT(page_url,image_src) DO UPDATE SET
          issue_type=excluded.issue_type, context=excluded.context,
          source=excluded.source, priority=excluded.priority, last_seen=excluded.last_seen
    """, (page_url, image_src, issue_type, context, alt_text, source,
          _PRIORITY.get(issue_type, 0), now, now))

# ─────────────────────────── import ───────────────────────────
def import_from_librecrawl(crawl_id: int = None, lc_db: str = LC_DB,
                           include_theme_alt: bool = False) -> dict:
    """Import broken images (mọi) + missing-alt (dedup page+src) từ LibreCrawl.
    missing-alt: bỏ theme_asset mặc định (nhiễu) trừ khi include_theme_alt."""
    ensure_table()
    stats = {"broken": 0, "missing_alt": 0, "skipped_theme": 0, "rows_touched": 0}
    lc = sqlite3.connect(f"file:{lc_db}?mode=ro&immutable=1", uri=True)
    if crawl_id is None:
        crawl_id = lc.execute("SELECT MAX(crawl_id) FROM crawled_urls").fetchone()[0]
    conn = db.get_conn()
    # 1) broken images từ crawl_issues
    for row in lc.execute(
        "SELECT url,issue,details FROM crawl_issues WHERE crawl_id=? AND category='Content' AND issue LIKE 'Broken Image%'",
        (crawl_id,)):
        page, label, details = row
        m = re.search(r"(https?://\S+)", details or "")
        if not m:
            continue
        src = m.group(1)
        it = classify_broken(label, src)
        _upsert(conn, page, src, it, classify_context(page, src), "", "librecrawl")
        stats["broken"] += 1; stats["rows_touched"] += 1
    # 2) missing-alt từ crawled_urls.images
    for row in lc.execute(
        "SELECT url,images FROM crawled_urls WHERE crawl_id=? AND images IS NOT NULL AND images NOT IN ('','[]')",
        (crawl_id,)):
        page, imgs_json = row
        try:
            imgs = json.loads(imgs_json)
        except Exception:
            continue
        for im in imgs:
            src = (im.get("src") or "").strip()
            if not src:
                continue
            alt = (im.get("alt") or "").strip()
            if alt:
                continue  # có alt → bỏ
            ctx = classify_context(page, src)
            if ctx == "theme_asset" and not include_theme_alt:
                stats["skipped_theme"] += 1; continue
            it = _alt_type(src)
            _upsert(conn, page, src, it, ctx, "", "librecrawl")
            stats["missing_alt"] += 1; stats["rows_touched"] += 1
    conn.commit(); conn.close(); lc.close()
    return stats

# ─────────────────────────── query API ───────────────────────────
def counts() -> dict:
    ensure_table(); conn = db.get_conn()
    total = conn.execute("SELECT COUNT(*) FROM alt_image_issues").fetchone()[0]
    by_type = dict(conn.execute("SELECT issue_type,COUNT(*) FROM alt_image_issues GROUP BY issue_type").fetchall())
    by_ctx = dict(conn.execute("SELECT context,COUNT(*) FROM alt_image_issues GROUP BY context").fetchall())
    by_status = dict(conn.execute("SELECT status,COUNT(*) FROM alt_image_issues GROUP BY status").fetchall())
    conn.close()
    return {"total": total, "by_type": by_type, "by_context": by_ctx, "by_status": by_status}

def list_issues(issue_type=None, context=None, status=None, limit=200, offset=0) -> list:
    ensure_table(); conn = db.get_conn()
    sql = "SELECT id,page_url,image_src,issue_type,context,source,status,priority,last_seen FROM alt_image_issues WHERE 1=1"
    args = []
    for col, val in (("issue_type", issue_type), ("context", context), ("status", status)):
        if val:
            sql += f" AND {col}=?"; args.append(val)
    sql += " ORDER BY priority DESC, id ASC LIMIT ? OFFSET ?"; args += [int(limit), int(offset)]
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    conn.close(); return rows

def mark(issue_id: int, status: str) -> bool:
    if status not in ("pending", "reviewed", "ignored"):
        return False
    ensure_table(); conn = db.get_conn()
    conn.execute("UPDATE alt_image_issues SET status=? WHERE id=?", (status, int(issue_id)))
    conn.commit(); conn.close(); return True

def export_rows() -> list:
    ensure_table(); conn = db.get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT page_url,image_src,issue_type,context,source,status,priority,first_seen,last_seen "
        "FROM alt_image_issues ORDER BY priority DESC, id ASC").fetchall()]
    conn.close(); return rows
