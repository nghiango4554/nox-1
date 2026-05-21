import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "data" / "posts.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    scheduled_date TEXT,
    scheduled_time TEXT,
    type TEXT,
    status TEXT DEFAULT 'draft',
    caption TEXT,
    image_path TEXT,
    images TEXT DEFAULT '[]',
    link TEXT,
    fb_post_id TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_posts_date ON posts(scheduled_date);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_type ON posts(type);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS seo_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT DEFAULT 'pending',
    total INTEGER DEFAULT 0,
    success INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS seo_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    url_type TEXT,
    last_run_id INTEGER,
    status_code INTEGER,
    final_url TEXT,
    title TEXT,
    title_len INTEGER,
    meta_desc TEXT,
    meta_desc_len INTEGER,
    h1 TEXT,
    h1_count INTEGER,
    word_count INTEGER,
    images_total INTEGER,
    images_no_alt INTEGER,
    internal_links INTEGER,
    external_links INTEGER,
    has_canonical INTEGER,
    canonical_url TEXT,
    has_og INTEGER,
    has_schema INTEGER,
    indexable INTEGER,
    indexability_reason TEXT,
    page_size_bytes INTEGER,
    load_ms INTEGER,
    score INTEGER,
    issues TEXT,
    last_crawled TEXT
);

CREATE INDEX IF NOT EXISTS idx_seo_pages_score ON seo_pages(score);
CREATE INDEX IF NOT EXISTS idx_seo_pages_type ON seo_pages(url_type);
CREATE INDEX IF NOT EXISTS idx_seo_pages_status ON seo_pages(status_code);

CREATE TABLE IF NOT EXISTS seo_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    target_url TEXT NOT NULL,
    is_internal INTEGER NOT NULL,
    status_code INTEGER,
    last_checked TEXT,
    UNIQUE(source_url, target_url)
);

CREATE INDEX IF NOT EXISTS idx_seo_links_source ON seo_links(source_url);
CREATE INDEX IF NOT EXISTS idx_seo_links_status ON seo_links(status_code);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    icon TEXT,
    title TEXT NOT NULL,
    description TEXT,
    href TEXT,
    meta TEXT
);
CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_activity_kind ON activity_log(kind);

CREATE TABLE IF NOT EXISTS competitor_urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competitor TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    url_type TEXT,
    title TEXT,
    topic TEXT,
    keywords TEXT,
    lastmod TEXT,
    last_seen TEXT
);
CREATE INDEX IF NOT EXISTS idx_competitor_url ON competitor_urls(competitor);
CREATE INDEX IF NOT EXISTS idx_competitor_topic ON competitor_urls(topic);
CREATE INDEX IF NOT EXISTS idx_competitor_type ON competitor_urls(url_type);

CREATE TABLE IF NOT EXISTS seo_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    total INTEGER DEFAULT 0,
    avg_score REAL DEFAULT 0,
    good INTEGER DEFAULT 0,
    ok_count INTEGER DEFAULT 0,
    bad INTEGER DEFAULT 0,
    broken_links INTEGER DEFAULT 0,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_seo_history_at ON seo_history(captured_at);

CREATE TABLE IF NOT EXISTS haravan_products (
    id INTEGER PRIMARY KEY,
    haravan_id INTEGER UNIQUE NOT NULL,
    handle TEXT,
    title TEXT,
    vendor TEXT,
    product_type TEXT,
    status TEXT,
    body_html TEXT,
    tags TEXT,
    images_count INTEGER DEFAULT 0,
    images_no_alt INTEGER DEFAULT 0,
    images TEXT,
    variants_count INTEGER DEFAULT 0,
    price_min REAL,
    price_max REAL,
    inventory_total INTEGER DEFAULT 0,
    meta_title TEXT,
    meta_description TEXT,
    created_at_haravan TEXT,
    updated_at_haravan TEXT,
    published_at TEXT,
    word_count INTEGER DEFAULT 0,
    audit_score INTEGER,
    audit_issues TEXT,
    last_synced TEXT,
    last_audited TEXT
);

CREATE INDEX IF NOT EXISTS idx_hv_products_vendor ON haravan_products(vendor);
CREATE INDEX IF NOT EXISTS idx_hv_products_type ON haravan_products(product_type);
CREATE INDEX IF NOT EXISTS idx_hv_products_status ON haravan_products(status);
CREATE INDEX IF NOT EXISTS idx_hv_products_score ON haravan_products(audit_score);

CREATE TABLE IF NOT EXISTS haravan_sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    total INTEGER DEFAULT 0,
    fetched INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS content_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_url TEXT UNIQUE NOT NULL,
    haravan_id INTEGER,
    handle TEXT,
    product_title TEXT,
    vendor TEXT,
    product_type TEXT,
    -- nguồn vấn đề (vì sao SP vào job này)
    current_word_count INTEGER DEFAULT 0,
    current_internal_links INTEGER DEFAULT 0,
    reason TEXT,                       -- 'empty_desc' | 'short_desc' | 'missing_links' | nhiều giá trị join '|'
    -- output AI
    ai_analysis_md TEXT,               -- phase "Phân tích" (keyword, intent, đối tượng, bảng internal link plan)
    ai_titles_json TEXT,               -- ["title 1", "title 2", "title 3"]
    ai_metas_json TEXT,                -- ["meta 1", "meta 2", "meta 3"]
    ai_keywords TEXT,
    ai_outline TEXT,
    ai_body_md TEXT,
    ai_body_html TEXT,
    internal_links_json TEXT,          -- [{"url":..., "anchor":..., "score":...}, ...]
    ai_stats_json TEXT,                -- {"word_count":..., "model":..., "cost":...}
    ai_generated_at TEXT,
    -- người dùng chỉnh sửa & chọn
    selected_title_idx INTEGER,        -- 0|1|2 (radio)
    selected_meta_idx INTEGER,         -- 0|1|2 (radio)
    edited_title TEXT,                 -- nếu vợ chỉnh trên radio đã chọn
    edited_meta TEXT,
    edited_body_html TEXT,             -- editor inline
    -- workflow status
    status TEXT NOT NULL DEFAULT 'pending',
       -- pending → SP mới được đẩy vào, chưa gen AI
       -- drafting → đang gọi AI gen
       -- draft → AI gen xong, chờ vợ review
       -- approved → vợ duyệt rồi, chờ sync
       -- synced → đã push lên Haravan
       -- failed → AI gen lỗi hoặc sync lỗi
    error TEXT,
    -- sync options + history
    sync_body INTEGER DEFAULT 1,
    sync_meta_title INTEGER DEFAULT 1,
    sync_meta_desc INTEGER DEFAULT 1,
    approved_at TEXT,
    synced_at TEXT,
    -- timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_content_jobs_status ON content_jobs(status);
CREATE INDEX IF NOT EXISTS idx_content_jobs_url ON content_jobs(product_url);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)  # 30s busy timeout
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")      # WAL cho concurrent read/write
    conn.execute("PRAGMA busy_timeout=30000")    # retry 30s nếu DB locked (tránh lock khi nhiều job cùng ghi)
    conn.execute("PRAGMA synchronous=NORMAL")    # nhanh hơn FULL, vẫn safe với WAL
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    conn.executescript(SCHEMA)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(posts)").fetchall()}
    if "images" not in cols:
        conn.execute("ALTER TABLE posts ADD COLUMN images TEXT DEFAULT '[]'")
    seo_cols = {r["name"] for r in conn.execute("PRAGMA table_info(seo_pages)").fetchall()}
    new_seo_cols = {
        "final_url": "TEXT",
        "canonical_url": "TEXT",
        "indexable": "INTEGER",
        "indexability_reason": "TEXT",
        "page_size_bytes": "INTEGER",
        "h2_list": "TEXT",
        "redirect_chain": "TEXT",
        "desc_h1_count": "INTEGER DEFAULT 0",
        "desc_h1_text": "TEXT",
        "desc_h1_scanned_at": "TEXT",
        "desc_word_count": "INTEGER",
        "desc_empty_scanned_at": "TEXT",
    }
    for col, col_type in new_seo_cols.items():
        if col not in seo_cols:
            conn.execute(f"ALTER TABLE seo_pages ADD COLUMN {col} {col_type}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_seo_pages_indexable ON seo_pages(indexable)")

    # seo_links: thêm error_kind để phân loại lỗi timeout (dns_fail, ssl_error,...)
    link_cols = {r["name"] for r in conn.execute("PRAGMA table_info(seo_links)").fetchall()}
    if "error_kind" not in link_cols:
        conn.execute("ALTER TABLE seo_links ADD COLUMN error_kind TEXT")

    # content_jobs: migrate column mới
    cj_cols = {r["name"] for r in conn.execute("PRAGMA table_info(content_jobs)").fetchall()}
    if "ai_analysis_md" not in cj_cols:
        conn.execute("ALTER TABLE content_jobs ADD COLUMN ai_analysis_md TEXT")
    if "is_money_product" not in cj_cols:
        conn.execute("ALTER TABLE content_jobs ADD COLUMN is_money_product INTEGER DEFAULT 0")
    # Default sync_meta_title + sync_meta_desc = 1 (em đã chốt sync hết, không cần tick)
    conn.execute("UPDATE content_jobs SET sync_meta_title=1, sync_meta_desc=1 WHERE sync_meta_title=0 OR sync_meta_desc=0")

    conn.commit()
    conn.close()


def next_post_code():
    conn = get_conn()
    row = conn.execute(
        "SELECT code FROM posts WHERE code LIKE 'FB%' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return "FB0001"
    n = int(row["code"][2:]) + 1
    return f"FB{n:04d}"


def list_posts(date=None, status=None, ptype=None, date_from=None, date_to=None, limit=500):
    conn = get_conn()
    sql = "SELECT * FROM posts WHERE 1=1"
    args = []
    if date:
        sql += " AND scheduled_date = ?"
        args.append(date)
    if date_from:
        sql += " AND scheduled_date >= ?"
        args.append(date_from)
    if date_to:
        sql += " AND scheduled_date <= ?"
        args.append(date_to)
    if status:
        sql += " AND status = ?"
        args.append(status)
    if ptype:
        sql += " AND type = ?"
        args.append(ptype)
    sql += " ORDER BY scheduled_date ASC, scheduled_time ASC LIMIT ?"
    args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_post(post_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_post(data):
    now = datetime.now().isoformat(timespec="seconds")
    code = data.get("code") or next_post_code()
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO posts (code, scheduled_date, scheduled_time, type, status,
            caption, image_path, link, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            code,
            data.get("scheduled_date"),
            data.get("scheduled_time"),
            data.get("type"),
            data.get("status", "draft"),
            data.get("caption"),
            data.get("image_path"),
            data.get("link"),
            now,
            now,
        ),
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid


def update_post(post_id, data):
    fields = [
        "scheduled_date",
        "scheduled_time",
        "type",
        "status",
        "caption",
        "image_path",
        "images",
        "link",
        "fb_post_id",
    ]
    sets = []
    args = []
    for f in fields:
        if f in data:
            sets.append(f"{f} = ?")
            args.append(data[f])
    if not sets:
        return
    sets.append("updated_at = ?")
    args.append(datetime.now().isoformat(timespec="seconds"))
    args.append(post_id)
    conn = get_conn()
    conn.execute(f"UPDATE posts SET {', '.join(sets)} WHERE id = ?", args)
    conn.commit()
    conn.close()


def delete_post(post_id):
    conn = get_conn()
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    conn.close()


# ─────────────────────────── SEO ───────────────────────────


def seo_create_run(notes: str = "") -> int:
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO seo_runs (started_at, status, notes) VALUES (?, 'running', ?)",
        (now, notes),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def seo_finish_run(run_id: int, status: str, total: int, success: int, failed: int):
    conn = get_conn()
    conn.execute(
        "UPDATE seo_runs SET finished_at=?, status=?, total=?, success=?, failed=? WHERE id=?",
        (datetime.now().isoformat(timespec="seconds"), status, total, success, failed, run_id),
    )
    conn.commit()
    conn.close()


def seo_update_run_progress(run_id: int, total: int, success: int, failed: int):
    conn = get_conn()
    conn.execute(
        "UPDATE seo_runs SET total=?, success=?, failed=? WHERE id=?",
        (total, success, failed, run_id),
    )
    conn.commit()
    conn.close()


def seo_get_run(run_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM seo_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def seo_latest_run():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM seo_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def seo_list_runs(limit: int = 20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM seo_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_seed_urls(urls_with_type: list) -> dict:
    """Insert URL+url_type nếu chưa có (không touch field crawl). Trả {added, existing}."""
    conn = get_conn()
    added = 0
    existing = 0
    for url, url_type in urls_with_type:
        cur = conn.execute(
            "INSERT OR IGNORE INTO seo_pages (url, url_type) VALUES (?, ?)",
            (url, url_type),
        )
        if cur.rowcount > 0:
            added += 1
        else:
            existing += 1
            conn.execute(
                "UPDATE seo_pages SET url_type = ? WHERE url = ? AND (url_type IS NULL OR url_type = '')",
                (url_type, url),
            )
    conn.commit()
    conn.close()
    return {"added": added, "existing": existing}


def seo_upsert_page(data: dict):
    """Insert or update by URL."""
    fields = [
        "url", "url_type", "last_run_id", "status_code", "final_url",
        "title", "title_len", "meta_desc", "meta_desc_len",
        "h1", "h1_count", "word_count",
        "images_total", "images_no_alt",
        "internal_links", "external_links",
        "has_canonical", "canonical_url", "has_og", "has_schema",
        "indexable", "indexability_reason", "page_size_bytes",
        "h2_list", "redirect_chain",
        "desc_h1_count", "desc_h1_text", "desc_h1_scanned_at",
        "load_ms", "score", "issues", "last_crawled",
    ]
    cols = ", ".join(fields)
    placeholders = ", ".join("?" * len(fields))
    updates = ", ".join(f"{f}=excluded.{f}" for f in fields if f != "url")
    values = [data.get(f) for f in fields]
    conn = get_conn()
    conn.execute(
        f"INSERT INTO seo_pages ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(url) DO UPDATE SET {updates}",
        values,
    )
    conn.commit()
    conn.close()


def seo_list_pages(
    url_type: str = None,
    min_score: int = None,
    max_score: int = None,
    issue_code: str = None,
    search: str = None,
    sort: str = "score_asc",
    limit: int = 100,
    offset: int = 0,
):
    conn = get_conn()
    sql = "SELECT * FROM seo_pages WHERE 1=1"
    args = []
    if url_type:
        sql += " AND url_type = ?"
        args.append(url_type)
    if min_score is not None:
        sql += " AND score >= ?"
        args.append(min_score)
    if max_score is not None:
        sql += " AND score <= ?"
        args.append(max_score)
    if issue_code:
        sql += " AND issues LIKE ?"
        args.append(f'%"{issue_code}"%')
    if search:
        sql += " AND (url LIKE ? OR title LIKE ?)"
        args.append(f"%{search}%")
        args.append(f"%{search}%")
    sort_map = {
        "score_asc": "score ASC, id DESC",
        "score_desc": "score DESC, id DESC",
        "url": "url ASC",
        "recent": "last_crawled DESC",
    }
    sql += f" ORDER BY {sort_map.get(sort, 'score ASC, id DESC')} LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_count_pages(**filters):
    conn = get_conn()
    sql = "SELECT COUNT(*) c FROM seo_pages WHERE 1=1"
    args = []
    if filters.get("url_type"):
        sql += " AND url_type = ?"; args.append(filters["url_type"])
    if filters.get("min_score") is not None:
        sql += " AND score >= ?"; args.append(filters["min_score"])
    if filters.get("max_score") is not None:
        sql += " AND score <= ?"; args.append(filters["max_score"])
    if filters.get("issue_code"):
        sql += " AND issues LIKE ?"; args.append(f'%"{filters["issue_code"]}"%')
    if filters.get("search"):
        sql += " AND (url LIKE ? OR title LIKE ?)"
        args.append(f"%{filters['search']}%"); args.append(f"%{filters['search']}%")
    n = conn.execute(sql, args).fetchone()["c"]
    conn.close()
    return n


def seo_get_page(page_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM seo_pages WHERE id=?", (page_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def seo_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM seo_pages").fetchone()["c"]
    avg_score = conn.execute("SELECT AVG(score) a FROM seo_pages WHERE score IS NOT NULL").fetchone()["a"] or 0
    by_type = {
        r["url_type"] or "unknown": r["c"]
        for r in conn.execute("SELECT url_type, COUNT(*) c FROM seo_pages GROUP BY url_type").fetchall()
    }
    # Threshold tuned cho Sintech-on-Haravan (2026-05-12):
    # Haravan platform-default trừ ~25 điểm (no_schema, no_og, img_no_alt) → max ~70-75.
    # Good ≥65, OK 50-64, Bad <50 → distribution thực tế meaningful hơn.
    bands = conn.execute(
        """SELECT
            SUM(CASE WHEN score >= 65 THEN 1 ELSE 0 END) good,
            SUM(CASE WHEN score >= 50 AND score < 65 THEN 1 ELSE 0 END) ok,
            SUM(CASE WHEN score < 50 THEN 1 ELSE 0 END) bad
           FROM seo_pages"""
    ).fetchone()
    broken = conn.execute(
        "SELECT COUNT(*) c FROM seo_pages WHERE status_code >= 400 OR status_code IS NULL"
    ).fetchone()["c"]
    conn.close()
    return {
        "total": total,
        "avg_score": round(avg_score or 0, 1),
        "by_type": by_type,
        "good": bands["good"] or 0,
        "ok": bands["ok"] or 0,
        "bad": bands["bad"] or 0,
        "broken": broken,
    }


def seo_inlinks_summary() -> dict:
    """Đếm tổng quan inlinks: total, max, avg, orphans."""
    conn = get_conn()
    crawled_total = conn.execute(
        "SELECT COUNT(*) c FROM seo_pages WHERE last_crawled IS NOT NULL"
    ).fetchone()["c"]
    link_rows = conn.execute(
        "SELECT COUNT(*) c FROM seo_links WHERE is_internal = 1"
    ).fetchone()["c"]
    # Pages có ≥1 inlink (= xuất hiện làm target_url trong seo_links)
    with_inlinks = conn.execute(
        """SELECT COUNT(DISTINCT p.url) c
           FROM seo_pages p
           JOIN seo_links l ON l.target_url = p.url
           WHERE p.last_crawled IS NOT NULL AND l.is_internal = 1"""
    ).fetchone()["c"]
    conn.close()
    return {
        "crawled_total": crawled_total,
        "internal_links_total": link_rows,
        "with_inlinks": with_inlinks,
        "orphans": max(0, crawled_total - with_inlinks),
    }


def seo_top_inlinks(limit: int = 50) -> list:
    """Top trang có nhiều inlinks nhất."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT p.id, p.url, p.url_type, p.title, p.score, p.last_crawled,
                  COUNT(l.id) inlinks
           FROM seo_pages p
           LEFT JOIN seo_links l
             ON l.target_url = p.url AND l.is_internal = 1
           WHERE p.last_crawled IS NOT NULL
           GROUP BY p.id
           ORDER BY inlinks DESC, p.url ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_orphan_pages(url_type: str = None, limit: int = 500) -> list:
    """Trang không có internal link nào trỏ tới (orphan)."""
    conn = get_conn()
    sql = """SELECT p.id, p.url, p.url_type, p.title, p.score, p.last_crawled
             FROM seo_pages p
             LEFT JOIN seo_links l
               ON l.target_url = p.url AND l.is_internal = 1
             WHERE p.last_crawled IS NOT NULL
               AND l.id IS NULL"""
    args = []
    if url_type:
        sql += " AND p.url_type = ?"
        args.append(url_type)
    sql += " ORDER BY p.url_type, p.url LIMIT ?"
    args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_inlinks_for_url(target_url: str, limit: int = 200) -> list:
    """List source URLs trỏ tới target_url."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT source_url, is_internal
           FROM seo_links
           WHERE target_url = ?
           ORDER BY is_internal DESC, source_url
           LIMIT ?""",
        (target_url, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_indexability_stats() -> dict:
    """Đếm trang indexable / non-indexable / chưa crawl."""
    conn = get_conn()
    row = conn.execute(
        """SELECT
            SUM(CASE WHEN indexable = 1 THEN 1 ELSE 0 END) indexable,
            SUM(CASE WHEN indexable = 0 AND last_crawled IS NOT NULL THEN 1 ELSE 0 END) non_indexable,
            SUM(CASE WHEN last_crawled IS NULL THEN 1 ELSE 0 END) not_crawled
           FROM seo_pages"""
    ).fetchone()
    by_reason = {
        (r["indexability_reason"] or "unknown"): r["c"]
        for r in conn.execute(
            """SELECT indexability_reason, COUNT(*) c
               FROM seo_pages
               WHERE indexable = 0 AND last_crawled IS NOT NULL
               GROUP BY indexability_reason
               ORDER BY c DESC"""
        ).fetchall()
    }
    conn.close()
    return {
        "indexable": row["indexable"] or 0,
        "non_indexable": row["non_indexable"] or 0,
        "not_crawled": row["not_crawled"] or 0,
        "by_reason": by_reason,
    }


def seo_list_non_indexable(reason: str = None, limit: int = 500) -> list:
    """Trả list trang non-indexable, optional filter theo reason."""
    conn = get_conn()
    sql = """SELECT id, url, url_type, status_code, final_url, title,
                    indexable, indexability_reason, canonical_url, last_crawled
             FROM seo_pages
             WHERE indexable = 0 AND last_crawled IS NOT NULL"""
    args = []
    if reason:
        sql += " AND indexability_reason = ?"
        args.append(reason)
    sql += " ORDER BY url_type, url LIMIT ?"
    args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_find_duplicates(field: str) -> list:
    """Trả list các giá trị title/meta/h1 bị trùng (xuất hiện ≥2 lần) + URL liên quan."""
    if field not in ("title", "meta_desc", "h1"):
        return []
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT {field} as val, COUNT(*) c, GROUP_CONCAT(url, '|') urls, GROUP_CONCAT(id, ',') ids
            FROM seo_pages
            WHERE {field} IS NOT NULL AND {field} != '' AND last_crawled IS NOT NULL
            GROUP BY {field}
            HAVING c >= 2
            ORDER BY c DESC, {field} ASC"""
    ).fetchall()
    conn.close()
    return [
        {
            "value": r["val"],
            "count": r["c"],
            "urls": r["urls"].split("|") if r["urls"] else [],
            "ids": [int(x) for x in (r["ids"] or "").split(",") if x],
        }
        for r in rows
    ]


def seo_upsert_desc_h1(url: str, url_type: str, desc_h1_count: int,
                       desc_h1_text: str, scanned_at: str):
    """Insert/update chỉ cột desc_h1_* cho 1 URL — dùng cho quick scan độc lập."""
    conn = get_conn()
    conn.execute(
        """INSERT INTO seo_pages (url, url_type, desc_h1_count, desc_h1_text, desc_h1_scanned_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(url) DO UPDATE SET
             url_type = COALESCE(excluded.url_type, seo_pages.url_type),
             desc_h1_count = excluded.desc_h1_count,
             desc_h1_text = excluded.desc_h1_text,
             desc_h1_scanned_at = excluded.desc_h1_scanned_at""",
        (url, url_type, desc_h1_count, desc_h1_text, scanned_at),
    )
    conn.commit()
    conn.close()


def seo_h1_in_desc_list(url_type: str = None, only_violations: bool = True,
                         limit: int = 1000) -> list:
    """List URL đã quét H1-trong-mô-tả. only_violations=True chỉ trả URL có ≥1 H1."""
    conn = get_conn()
    sql = """SELECT url, url_type, desc_h1_count, desc_h1_text, desc_h1_scanned_at,
                    title, score
             FROM seo_pages
             WHERE desc_h1_scanned_at IS NOT NULL"""
    args = []
    if only_violations:
        sql += " AND desc_h1_count > 0"
    if url_type:
        sql += " AND url_type = ?"
        args.append(url_type)
    sql += " ORDER BY desc_h1_count DESC, url ASC LIMIT ?"
    args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_upsert_empty_desc(url: str, url_type: str, word_count: int, scanned_at: str):
    """Insert/update chỉ cột desc_word_count + desc_empty_scanned_at cho 1 URL."""
    conn = get_conn()
    conn.execute(
        """INSERT INTO seo_pages (url, url_type, desc_word_count, desc_empty_scanned_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(url) DO UPDATE SET
             url_type = COALESCE(excluded.url_type, seo_pages.url_type),
             desc_word_count = excluded.desc_word_count,
             desc_empty_scanned_at = excluded.desc_empty_scanned_at""",
        (url, url_type, word_count, scanned_at),
    )
    conn.commit()
    conn.close()


def seo_empty_desc_list(url_type: str = "product", threshold: int = 800,
                         only_empty: bool = True, limit: int = 2000) -> list:
    """List URL đã quét empty-desc. only_empty=True chỉ trả URL có word_count < threshold."""
    conn = get_conn()
    sql = """SELECT url, url_type, desc_word_count, desc_empty_scanned_at,
                    title, score
             FROM seo_pages
             WHERE desc_empty_scanned_at IS NOT NULL"""
    args = []
    if url_type:
        sql += " AND url_type = ?"
        args.append(url_type)
    if only_empty:
        sql += " AND (desc_word_count IS NULL OR desc_word_count < ?)"
        args.append(threshold)
    sql += " ORDER BY desc_word_count ASC, url ASC LIMIT ?"
    args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_empty_desc_summary(threshold: int = 800) -> dict:
    """Tổng hợp: tổng SP đã quét, SP empty (<threshold), breakdown buckets."""
    conn = get_conn()
    row = conn.execute(
        """SELECT
             COUNT(*) FILTER (WHERE desc_empty_scanned_at IS NOT NULL AND url_type='product') AS scanned,
             COUNT(*) FILTER (WHERE desc_word_count = 0 AND url_type='product') AS empty_total,
             COUNT(*) FILTER (WHERE desc_word_count > 0 AND desc_word_count < ? AND url_type='product') AS short_total,
             COUNT(*) FILTER (WHERE desc_word_count >= ? AND url_type='product') AS ok_total
           FROM seo_pages""",
        (threshold, threshold),
    ).fetchone()
    conn.close()
    return {
        "scanned": row["scanned"] or 0,
        "empty": row["empty_total"] or 0,
        "short": row["short_total"] or 0,
        "ok": row["ok_total"] or 0,
        "threshold": threshold,
    }


def seo_h1_in_desc_summary() -> dict:
    """Tổng hợp: tổng đã quét, tổng vi phạm, breakdown theo url_type."""
    conn = get_conn()
    row = conn.execute(
        """SELECT
             COUNT(*) FILTER (WHERE desc_h1_scanned_at IS NOT NULL) AS scanned,
             COUNT(*) FILTER (WHERE desc_h1_count > 0) AS violations
           FROM seo_pages"""
    ).fetchone()
    by_type_rows = conn.execute(
        """SELECT url_type, COUNT(*) c
           FROM seo_pages
           WHERE desc_h1_count > 0
           GROUP BY url_type"""
    ).fetchall()
    conn.close()
    return {
        "scanned": row["scanned"] or 0,
        "violations": row["violations"] or 0,
        "by_type": {r["url_type"] or "other": r["c"] for r in by_type_rows},
    }


def seo_replace_links(source_url: str, links: list):
    """Xoá link cũ của source_url, ghi link mới. links = [(target, is_internal), ...]."""
    conn = get_conn()
    conn.execute("DELETE FROM seo_links WHERE source_url = ?", (source_url,))
    if links:
        conn.executemany(
            "INSERT OR IGNORE INTO seo_links (source_url, target_url, is_internal) VALUES (?, ?, ?)",
            [(source_url, t, int(bool(i))) for t, i in links],
        )
    conn.commit()
    conn.close()


def seo_link_status_update(target_url: str, status_code: int, error_kind: str = None):
    conn = get_conn()
    conn.execute(
        "UPDATE seo_links SET status_code = ?, error_kind = ?, last_checked = ? WHERE target_url = ?",
        (status_code, error_kind, datetime.now().isoformat(timespec="seconds"), target_url),
    )
    conn.commit()
    conn.close()


def seo_link_status_update_batch(rows: list):
    """Batch update status cho nhiều links cùng lúc. Mỗi row là tuple (status, error_kind, target_url).

    Faster ~10x so với gọi seo_link_status_update từng row vì 1 transaction.
    """
    if not rows:
        return
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    conn.executemany(
        "UPDATE seo_links SET status_code = ?, error_kind = ?, last_checked = ? WHERE target_url = ?",
        [(sc, ek, now, t) for sc, ek, t in rows],
    )
    conn.commit()
    conn.close()


def seo_reset_broken_links_for_recheck() -> int:
    """Reset status_code=NULL cho các link broken (status >= 400 hoặc 0)
    để chúng được check lại bởi run_link_check. Trả về số rows đã reset."""
    conn = get_conn()
    cur = conn.execute(
        "UPDATE seo_links SET status_code = NULL, error_kind = NULL "
        "WHERE status_code IS NOT NULL AND (status_code >= 400 OR status_code = 0)"
    )
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


def seo_links_to_check(limit: int = 0, only_targets: list = None) -> list:
    """External link chưa check. Internal link KHÔNG check ở đây vì đã được
    crawler chính verify (status trong seo_pages).

    `only_targets`: nếu có, chỉ check đúng các URL trong list (vd re-check broken).
    """
    conn = get_conn()
    args = []
    sql = """SELECT target_url, is_internal, COUNT(*) refs
             FROM seo_links
             WHERE is_internal = 0 """
    if only_targets:
        placeholders = ",".join("?" * len(only_targets))
        sql += f" AND target_url IN ({placeholders}) "
        args.extend(only_targets)
    else:
        sql += " AND (status_code IS NULL OR last_checked IS NULL) "
    sql += " GROUP BY target_url, is_internal"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [{"target": r["target_url"], "is_internal": bool(r["is_internal"]), "refs": r["refs"]} for r in rows]


def seo_get_broken_target_urls() -> list:
    """List target_url đang broken (4xx/5xx/timeout) — để re-check riêng."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT DISTINCT target_url FROM seo_links
           WHERE is_internal = 0
             AND status_code IS NOT NULL
             AND (status_code >= 400 OR status_code = 0)"""
    ).fetchall()
    conn.close()
    return [r["target_url"] for r in rows]


def seo_clear_internal_link_status() -> int:
    """Reset status_code và error_kind cho TẤT CẢ internal link.
    Dùng để xoá các false positive từ run cũ (bot bị site chặn → toàn 0).
    Internal link không được check lại — coi là OK theo crawler chính."""
    conn = get_conn()
    cur = conn.execute(
        "UPDATE seo_links SET status_code = NULL, error_kind = NULL "
        "WHERE is_internal = 1"
    )
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


def _broken_where_clause(filters: dict) -> tuple:
    """Build WHERE clause + args cho query broken links với filters.
    filters keys: kind (4xx|5xx|timeout), status_code, error_kind, is_internal, search
    """
    sql = " WHERE status_code IS NOT NULL AND (status_code >= 400 OR status_code = 0) "
    args = []
    kind = filters.get("kind")
    if kind == "4xx":
        sql += " AND status_code >= 400 AND status_code < 500 "
    elif kind == "5xx":
        sql += " AND status_code >= 500 "
    elif kind == "timeout":
        sql += " AND status_code = 0 "
    if filters.get("status_code") is not None:
        sql += " AND status_code = ? "
        args.append(int(filters["status_code"]))
    if filters.get("error_kind"):
        sql += " AND error_kind = ? "
        args.append(filters["error_kind"])
    if filters.get("is_internal") is not None:
        sql += " AND is_internal = ? "
        args.append(1 if filters["is_internal"] else 0)
    if filters.get("search"):
        sql += " AND target_url LIKE ? "
        args.append(f"%{filters['search']}%")
    return sql, args


def seo_broken_breakdown() -> dict:
    """Count broken links theo từng nhóm — phục vụ panel filter clickable.

    Trả dict:
    - by_status: list[{status, count}] cho status 4xx + 5xx (sorted desc)
    - by_error_kind: list[{kind, count}] cho status=0 (sorted desc)
    - bucket_4xx: int — tổng 4xx
    - bucket_5xx: int — tổng 5xx
    - bucket_timeout: int — tổng timeout (status=0)
    - by_internal: dict {internal: int, external: int}
    """
    conn = get_conn()
    rows1 = conn.execute(
        """SELECT status_code, COUNT(DISTINCT target_url) c
           FROM seo_links
           WHERE status_code >= 400
           GROUP BY status_code
           ORDER BY c DESC"""
    ).fetchall()
    rows2 = conn.execute(
        """SELECT COALESCE(error_kind, 'other_error') ek, COUNT(DISTINCT target_url) c
           FROM seo_links
           WHERE status_code = 0
           GROUP BY ek
           ORDER BY c DESC"""
    ).fetchall()
    rows3 = conn.execute(
        """SELECT is_internal, COUNT(DISTINCT target_url) c
           FROM seo_links
           WHERE status_code IS NOT NULL AND (status_code >= 400 OR status_code = 0)
           GROUP BY is_internal"""
    ).fetchall()
    bucket_4xx = sum(r["c"] for r in rows1 if 400 <= r["status_code"] < 500)
    bucket_5xx = sum(r["c"] for r in rows1 if r["status_code"] >= 500)
    bucket_timeout = sum(r["c"] for r in rows2)
    by_internal = {"internal": 0, "external": 0}
    for r in rows3:
        if r["is_internal"]:
            by_internal["internal"] = r["c"]
        else:
            by_internal["external"] = r["c"]
    conn.close()
    return {
        "by_status": [{"status": r["status_code"], "count": r["c"]} for r in rows1],
        "by_error_kind": [{"kind": r["ek"], "count": r["c"]} for r in rows2],
        "bucket_4xx": bucket_4xx,
        "bucket_5xx": bucket_5xx,
        "bucket_timeout": bucket_timeout,
        "by_internal": by_internal,
    }


def seo_broken_links_filtered(
    kind: str = None, status_code: int = None, error_kind: str = None,
    is_internal: bool = None, search: str = None,
    sort: str = "refs_desc",
    limit: int = 100, offset: int = 0,
) -> list:
    """Trả list link gãy có filter + pagination. Mỗi item gồm
    target, status_code, error_kind, refs, is_internal, sources (sample 5)."""
    filters = {
        "kind": kind, "status_code": status_code, "error_kind": error_kind,
        "is_internal": is_internal, "search": search,
    }
    where_sql, args = _broken_where_clause(filters)
    sort_map = {
        "refs_desc": "refs DESC, target_url ASC",
        "refs_asc": "refs ASC, target_url ASC",
        "url": "target_url ASC",
        "status": "status_code DESC, refs DESC",
    }
    order_sql = f" ORDER BY {sort_map.get(sort, sort_map['refs_desc'])} "

    conn = get_conn()
    rows = conn.execute(
        f"""SELECT target_url, status_code, MAX(error_kind) error_kind, COUNT(*) refs,
                  GROUP_CONCAT(source_url, '|') sources, MAX(is_internal) is_internal
            FROM seo_links
            {where_sql}
            GROUP BY target_url
            {order_sql}
            LIMIT ? OFFSET ?""",
        args + [limit, offset],
    ).fetchall()
    conn.close()
    return [
        {
            "target": r["target_url"],
            "status_code": r["status_code"],
            "error_kind": r["error_kind"],
            "refs": r["refs"],
            "is_internal": bool(r["is_internal"]),
            "sources": (r["sources"] or "").split("|")[:5],
        }
        for r in rows
    ]


def seo_count_broken_filtered(
    kind: str = None, status_code: int = None, error_kind: str = None,
    is_internal: bool = None, search: str = None,
) -> int:
    filters = {
        "kind": kind, "status_code": status_code, "error_kind": error_kind,
        "is_internal": is_internal, "search": search,
    }
    where_sql, args = _broken_where_clause(filters)
    conn = get_conn()
    n = conn.execute(
        f"SELECT COUNT(DISTINCT target_url) c FROM seo_links {where_sql}",
        args,
    ).fetchone()["c"]
    conn.close()
    return n


def seo_broken_links(limit: int = 200) -> list:
    """LEGACY — giữ wrapper dùng filter mặc định để không break code cũ."""
    return seo_broken_links_filtered(limit=limit)


def seo_broken_link_summary() -> dict:
    """Tổng kết link checker. Phạm vi check = chỉ external link (internal
    đã được crawler chính verify, không HEAD lại để tránh false positive).

    - total: tổng external link unique (phạm vi check)
    - broken / unchecked / ok: của external
    - internal_verified: số internal link unique (auto-OK theo crawler)
    - total_all: tổng cả internal + external (link gom được trên site)
    """
    conn = get_conn()
    ext = conn.execute(
        """SELECT
            COUNT(DISTINCT CASE WHEN status_code >= 400 OR status_code = 0
                                THEN target_url END) broken,
            COUNT(DISTINCT CASE WHEN status_code IS NULL
                                THEN target_url END) unchecked,
            COUNT(DISTINCT CASE WHEN status_code IS NOT NULL
                                 AND status_code > 0
                                 AND status_code < 400
                                THEN target_url END) ok,
            COUNT(DISTINCT target_url) total
           FROM seo_links
           WHERE is_internal = 0"""
    ).fetchone()
    internal_count = conn.execute(
        "SELECT COUNT(DISTINCT target_url) c FROM seo_links WHERE is_internal = 1"
    ).fetchone()["c"]
    total_all = conn.execute(
        "SELECT COUNT(DISTINCT target_url) c FROM seo_links"
    ).fetchone()["c"]
    conn.close()
    return {
        "broken": ext["broken"] or 0,
        "unchecked": ext["unchecked"] or 0,
        "ok": ext["ok"] or 0,
        "total": ext["total"] or 0,
        "internal_verified": internal_count or 0,
        "total_all": total_all or 0,
    }


def seo_top_issues(limit: int = 12) -> list:
    """Đếm top issue codes xuất hiện nhiều nhất."""
    import json as _json
    conn = get_conn()
    rows = conn.execute(
        "SELECT issues FROM seo_pages WHERE issues IS NOT NULL AND issues != '' AND last_crawled IS NOT NULL"
    ).fetchall()
    conn.close()
    counter = {}
    levels = {}
    for r in rows:
        try:
            arr = _json.loads(r["issues"])
        except (ValueError, TypeError):
            continue
        for it in arr:
            code = it.get("code")
            if not code:
                continue
            counter[code] = counter.get(code, 0) + 1
            levels[code] = it.get("level", levels.get(code, "info"))
    sorted_codes = sorted(counter.items(), key=lambda x: -x[1])[:limit]
    return [{"code": c, "count": n, "level": levels.get(c, "info")} for c, n in sorted_codes]


# ─────────────────────────── SEO SNAPSHOTS ───────────────────────────


def seo_export_snapshot() -> dict:
    """Dump current SEO data (runs + pages + links) thành dict serializable."""
    conn = get_conn()
    runs = [dict(r) for r in conn.execute("SELECT * FROM seo_runs").fetchall()]
    pages = [dict(r) for r in conn.execute("SELECT * FROM seo_pages").fetchall()]
    links = [dict(r) for r in conn.execute("SELECT * FROM seo_links").fetchall()]
    conn.close()
    return {
        "version": 1,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {"runs": len(runs), "pages": len(pages), "links": len(links)},
        "runs": runs,
        "pages": pages,
        "links": links,
    }


def seo_clear_all():
    """Xoá toàn bộ data crawl SEO (runs + pages + links)."""
    conn = get_conn()
    conn.execute("DELETE FROM seo_links")
    conn.execute("DELETE FROM seo_pages")
    conn.execute("DELETE FROM seo_runs")
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('seo_runs','seo_pages','seo_links')")
    conn.commit()
    conn.close()


def seo_import_snapshot(data: dict):
    """Restore snapshot: clear current rồi insert lại runs/pages/links."""
    seo_clear_all()
    conn = get_conn()
    for r in data.get("runs", []):
        cols = list(r.keys())
        placeholders = ",".join("?" * len(cols))
        conn.execute(
            f"INSERT INTO seo_runs ({','.join(cols)}) VALUES ({placeholders})",
            [r[c] for c in cols],
        )
    for p in data.get("pages", []):
        cols = list(p.keys())
        placeholders = ",".join("?" * len(cols))
        conn.execute(
            f"INSERT INTO seo_pages ({','.join(cols)}) VALUES ({placeholders})",
            [p[c] for c in cols],
        )
    for lk in data.get("links", []):
        cols = list(lk.keys())
        placeholders = ",".join("?" * len(cols))
        conn.execute(
            f"INSERT INTO seo_links ({','.join(cols)}) VALUES ({placeholders})",
            [lk[c] for c in cols],
        )
    conn.commit()
    conn.close()


# ─────────────────────────── ACTIVITY LOG ───────────────────────────


def activity_log(kind: str, title: str, description: str = None,
                 href: str = None, icon: str = None, meta: dict = None) -> int:
    """Ghi 1 hoạt động vào timeline. Trả id row."""
    import json as _json
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO activity_log (ts, kind, icon, title, description, href, meta)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            kind, icon, title, description, href,
            _json.dumps(meta, ensure_ascii=False) if meta else None,
        ),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def activity_recent(limit: int = 20, kind: str = None) -> list:
    conn = get_conn()
    if kind:
        rows = conn.execute(
            "SELECT * FROM activity_log WHERE kind = ? ORDER BY ts DESC LIMIT ?",
            (kind, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM activity_log ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────── COMPETITOR URLS ───────────────────────────


def competitor_upsert(items: list):
    """Bulk upsert competitor URLs. items = list of dict with required fields."""
    if not items:
        return 0
    fields = ["competitor", "url", "url_type", "title", "topic", "keywords",
              "lastmod", "last_seen"]
    cols = ", ".join(fields)
    placeholders = ", ".join("?" * len(fields))
    updates = ", ".join(f"{f}=excluded.{f}" for f in fields if f != "url")
    conn = get_conn()
    n = 0
    for it in items:
        values = [it.get(f) for f in fields]
        try:
            conn.execute(
                f"INSERT INTO competitor_urls ({cols}) VALUES ({placeholders}) "
                f"ON CONFLICT(url) DO UPDATE SET {updates}",
                values,
            )
            n += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return n


def competitor_clear(competitor: str = None) -> int:
    conn = get_conn()
    if competitor:
        cur = conn.execute("DELETE FROM competitor_urls WHERE competitor = ?", (competitor,))
    else:
        cur = conn.execute("DELETE FROM competitor_urls")
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


def competitor_stats() -> dict:
    """Tổng quan: số URL/competitor + phân loại topic."""
    conn = get_conn()
    by_competitor = {}
    for r in conn.execute(
        "SELECT competitor, COUNT(*) c FROM competitor_urls GROUP BY competitor"
    ).fetchall():
        by_competitor[r["competitor"]] = r["c"]
    by_topic = {}
    for r in conn.execute(
        "SELECT topic, COUNT(*) c FROM competitor_urls "
        "WHERE topic IS NOT NULL GROUP BY topic ORDER BY c DESC"
    ).fetchall():
        by_topic[r["topic"]] = r["c"]
    by_type = {}
    for r in conn.execute(
        "SELECT url_type, COUNT(*) c FROM competitor_urls "
        "WHERE url_type IS NOT NULL GROUP BY url_type ORDER BY c DESC"
    ).fetchall():
        by_type[r["url_type"]] = r["c"]
    total = conn.execute("SELECT COUNT(*) c FROM competitor_urls").fetchone()["c"]
    conn.close()
    return {
        "total": total,
        "by_competitor": by_competitor,
        "by_topic": by_topic,
        "by_type": by_type,
    }


def competitor_topic_gap(min_competitor_count: int = 5) -> list:
    """So sánh topic giữa đối thủ và Sintech (seo_pages url_type='blog').
    Trả list topic gap (đối thủ có nhiều mà Sintech ít)."""
    conn = get_conn()
    comp_topics = {
        r["topic"]: r["c"]
        for r in conn.execute(
            "SELECT topic, COUNT(DISTINCT competitor || ':' || url) c "
            "FROM competitor_urls WHERE topic IS NOT NULL "
            "GROUP BY topic"
        ).fetchall()
        if r["topic"]
    }
    conn.close()
    return [
        {"topic": t, "competitor_count": c}
        for t, c in sorted(comp_topics.items(), key=lambda x: -x[1])
        if c >= min_competitor_count
    ]


def competitor_list(competitor: str = None, topic: str = None,
                    search: str = None, sort: str = "recent",
                    limit: int = 100, offset: int = 0) -> list:
    conn = get_conn()
    sql = "SELECT * FROM competitor_urls WHERE 1=1"
    args = []
    if competitor:
        sql += " AND competitor = ?"
        args.append(competitor)
    if topic:
        sql += " AND topic = ?"
        args.append(topic)
    if search:
        sql += " AND (title LIKE ? OR url LIKE ?)"
        args.append(f"%{search}%"); args.append(f"%{search}%")
    sort_map = {
        "recent": "lastmod DESC, id DESC",
        "title": "title ASC",
        "url": "url ASC",
    }
    sql += f" ORDER BY {sort_map.get(sort, sort_map['recent'])} LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def competitor_count(**filters) -> int:
    conn = get_conn()
    sql = "SELECT COUNT(*) c FROM competitor_urls WHERE 1=1"
    args = []
    if filters.get("competitor"):
        sql += " AND competitor = ?"
        args.append(filters["competitor"])
    if filters.get("topic"):
        sql += " AND topic = ?"
        args.append(filters["topic"])
    if filters.get("search"):
        sql += " AND (title LIKE ? OR url LIKE ?)"
        args.append(f"%{filters['search']}%"); args.append(f"%{filters['search']}%")
    n = conn.execute(sql, args).fetchone()["c"]
    conn.close()
    return n


# ─────────────────────────── SEO HISTORY ───────────────────────────


def seo_capture_history(note: str = "") -> int:
    """Snapshot điểm SEO hiện tại vào bảng seo_history. Trả id row vừa tạo."""
    stats = seo_stats()
    bsum = seo_broken_link_summary()
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO seo_history
           (captured_at, total, avg_score, good, ok_count, bad, broken_links, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            stats["total"], stats["avg_score"],
            stats["good"], stats["ok"], stats["bad"],
            bsum.get("broken", 0),
            note,
        ),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def seo_history_list(limit: int = 200) -> list:
    """Trả list snapshot lịch sử (mới nhất trước)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM seo_history ORDER BY captured_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_history_chart_data(limit: int = 52) -> dict:
    """Data chuẩn cho Chart.js — sort tăng dần theo thời gian."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM seo_history ORDER BY captured_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    items = [dict(r) for r in rows]
    return {
        "labels": [r["captured_at"][:10] for r in items],
        "avg_score": [r["avg_score"] for r in items],
        "good": [r["good"] for r in items],
        "ok": [r["ok_count"] for r in items],
        "bad": [r["bad"] for r in items],
        "total": [r["total"] for r in items],
        "broken_links": [r["broken_links"] for r in items],
    }


# ─────────────────────────── HARAVAN PRODUCTS ───────────────────────────


def hv_upsert_product(p: dict):
    """Insert or update Haravan product by haravan_id."""
    fields = [
        "haravan_id", "handle", "title", "vendor", "product_type", "status",
        "body_html", "tags",
        "images_count", "images_no_alt", "images",
        "variants_count", "price_min", "price_max", "inventory_total",
        "meta_title", "meta_description",
        "created_at_haravan", "updated_at_haravan", "published_at",
        "word_count", "audit_score", "audit_issues",
        "last_synced", "last_audited",
    ]
    cols = ", ".join(fields)
    placeholders = ", ".join("?" * len(fields))
    updates = ", ".join(f"{f}=excluded.{f}" for f in fields if f != "haravan_id")
    values = [p.get(f) for f in fields]
    conn = get_conn()
    conn.execute(
        f"INSERT INTO haravan_products ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(haravan_id) DO UPDATE SET {updates}",
        values,
    )
    conn.commit()
    conn.close()


def hv_list_products(
    vendor: str = None, product_type: str = None, status: str = None,
    issue_code: str = None, search: str = None,
    sort: str = "score_asc", limit: int = 100, offset: int = 0,
):
    conn = get_conn()
    sql = "SELECT * FROM haravan_products WHERE 1=1"
    args = []
    if vendor:
        sql += " AND vendor = ?"; args.append(vendor)
    if product_type:
        sql += " AND product_type = ?"; args.append(product_type)
    if status:
        sql += " AND status = ?"; args.append(status)
    if issue_code:
        sql += " AND audit_issues LIKE ?"; args.append(f'%"{issue_code}"%')
    if search:
        sql += " AND (title LIKE ? OR handle LIKE ?)"
        args.append(f"%{search}%"); args.append(f"%{search}%")
    sort_map = {
        "score_asc": "audit_score ASC, haravan_id DESC",
        "score_desc": "audit_score DESC, haravan_id DESC",
        "title": "title ASC",
        "recent": "updated_at_haravan DESC",
        "synced": "last_synced DESC",
    }
    sql += f" ORDER BY {sort_map.get(sort, 'audit_score ASC')} LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def hv_count_products(**filters) -> int:
    conn = get_conn()
    sql = "SELECT COUNT(*) c FROM haravan_products WHERE 1=1"
    args = []
    if filters.get("vendor"):
        sql += " AND vendor = ?"; args.append(filters["vendor"])
    if filters.get("product_type"):
        sql += " AND product_type = ?"; args.append(filters["product_type"])
    if filters.get("status"):
        sql += " AND status = ?"; args.append(filters["status"])
    if filters.get("issue_code"):
        sql += " AND audit_issues LIKE ?"; args.append(f'%"{filters["issue_code"]}"%')
    if filters.get("search"):
        sql += " AND (title LIKE ? OR handle LIKE ?)"
        args.append(f"%{filters['search']}%"); args.append(f"%{filters['search']}%")
    n = conn.execute(sql, args).fetchone()["c"]
    conn.close()
    return n


def hv_get_product(haravan_id: int):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM haravan_products WHERE haravan_id = ?", (haravan_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def hv_get_product_by_handle(handle: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM haravan_products WHERE handle = ?", (handle,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def hv_stats() -> dict:
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM haravan_products").fetchone()["c"]
    avg_score = conn.execute(
        "SELECT AVG(audit_score) a FROM haravan_products WHERE audit_score IS NOT NULL"
    ).fetchone()["a"] or 0
    by_vendor = {
        (r["vendor"] or "—"): r["c"]
        for r in conn.execute(
            "SELECT vendor, COUNT(*) c FROM haravan_products GROUP BY vendor ORDER BY c DESC LIMIT 12"
        ).fetchall()
    }
    by_type = {
        (r["product_type"] or "—"): r["c"]
        for r in conn.execute(
            "SELECT product_type, COUNT(*) c FROM haravan_products GROUP BY product_type ORDER BY c DESC LIMIT 12"
        ).fetchall()
    }
    by_status = {
        (r["status"] or "—"): r["c"]
        for r in conn.execute("SELECT status, COUNT(*) c FROM haravan_products GROUP BY status").fetchall()
    }
    bands = conn.execute(
        """SELECT
            SUM(CASE WHEN audit_score >= 80 THEN 1 ELSE 0 END) good,
            SUM(CASE WHEN audit_score >= 60 AND audit_score < 80 THEN 1 ELSE 0 END) ok,
            SUM(CASE WHEN audit_score < 60 THEN 1 ELSE 0 END) bad
           FROM haravan_products WHERE audit_score IS NOT NULL"""
    ).fetchone()
    conn.close()
    return {
        "total": total,
        "avg_score": round(avg_score or 0, 1),
        "by_vendor": by_vendor,
        "by_type": by_type,
        "by_status": by_status,
        "good": bands["good"] or 0,
        "ok": bands["ok"] or 0,
        "bad": bands["bad"] or 0,
    }


def hv_top_issues(limit: int = 12) -> list:
    import json as _json
    conn = get_conn()
    rows = conn.execute(
        "SELECT audit_issues FROM haravan_products WHERE audit_issues IS NOT NULL AND audit_issues != ''"
    ).fetchall()
    conn.close()
    counter = {}
    levels = {}
    for r in rows:
        try:
            arr = _json.loads(r["audit_issues"])
        except (ValueError, TypeError):
            continue
        for it in arr:
            code = it.get("code")
            if not code:
                continue
            counter[code] = counter.get(code, 0) + 1
            levels[code] = it.get("level", levels.get(code, "info"))
    sorted_codes = sorted(counter.items(), key=lambda x: -x[1])[:limit]
    return [{"code": c, "count": n, "level": levels.get(c, "info")} for c, n in sorted_codes]


def hv_latest_sync():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM haravan_sync_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def hv_create_sync(notes: str = "") -> int:
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO haravan_sync_runs (started_at, status, notes) VALUES (?, 'running', ?)",
        (now, notes),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def hv_update_sync(run_id: int, total: int, fetched: int, failed: int):
    conn = get_conn()
    conn.execute(
        "UPDATE haravan_sync_runs SET total=?, fetched=?, failed=? WHERE id=?",
        (total, fetched, failed, run_id),
    )
    conn.commit()
    conn.close()


def hv_finish_sync(run_id: int, status: str, total: int, fetched: int, failed: int):
    conn = get_conn()
    conn.execute(
        "UPDATE haravan_sync_runs SET finished_at=?, status=?, total=?, fetched=?, failed=? WHERE id=?",
        (datetime.now().isoformat(timespec="seconds"), status, total, fetched, failed, run_id),
    )
    conn.commit()
    conn.close()


# ─────────────────────────── CONTENT JOBS ───────────────────────────


CONTENT_JOB_STATUSES = ("pending", "drafting", "text_done", "draft", "approved", "synced", "failed")


def content_job_upsert(product_url: str, **fields) -> int:
    """Tạo job mới hoặc update job đang có cho product_url. Trả về id."""
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    row = conn.execute("SELECT id FROM content_jobs WHERE product_url = ?", (product_url,)).fetchone()
    if row:
        job_id = row["id"]
        if fields:
            keys = list(fields.keys())
            sets = ", ".join(f"{k}=?" for k in keys) + ", updated_at=?"
            conn.execute(
                f"UPDATE content_jobs SET {sets} WHERE id=?",
                [*[fields[k] for k in keys], now, job_id],
            )
            conn.commit()
        conn.close()
        return job_id
    base = {
        "product_url": product_url,
        "status": fields.pop("status", "pending"),
        "created_at": now,
        "updated_at": now,
    }
    base.update(fields)
    keys = list(base.keys())
    placeholders = ", ".join("?" for _ in keys)
    cur = conn.execute(
        f"INSERT INTO content_jobs ({', '.join(keys)}) VALUES ({placeholders})",
        [base[k] for k in keys],
    )
    job_id = cur.lastrowid
    conn.commit()
    conn.close()
    return job_id


def content_job_get(job_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM content_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def content_job_get_by_url(url: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM content_jobs WHERE product_url = ?", (url,)).fetchone()
    conn.close()
    return dict(row) if row else None


def content_job_update(job_id: int, **fields):
    if not fields:
        return
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    keys = list(fields.keys())
    sets = ", ".join(f"{k}=?" for k in keys)
    conn = get_conn()
    conn.execute(
        f"UPDATE content_jobs SET {sets} WHERE id=?",
        [*[fields[k] for k in keys], job_id],
    )
    conn.commit()
    conn.close()


def content_job_delete(job_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM content_jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


def content_jobs_list(status: str = None, reason: str = None,
                      search: str = None, cate: str = None,
                      limit: int = 500, offset: int = 0) -> list:
    conn = get_conn()
    sql = "SELECT * FROM content_jobs WHERE 1=1"
    args = []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if reason:
        sql += " AND reason LIKE ?"
        args.append(f"%{reason}%")
    if search:
        sql += " AND (product_url LIKE ? OR product_title LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%"])
    if cate:
        sql += " AND product_type = ?"
        args.append(cate)
    sql += " ORDER BY CASE status"
    sql += " WHEN 'approved' THEN 1 WHEN 'draft' THEN 2 WHEN 'text_done' THEN 3"
    sql += " WHEN 'pending' THEN 4 WHEN 'drafting' THEN 5 WHEN 'failed' THEN 6 WHEN 'synced' THEN 7 ELSE 8 END"
    sql += ", current_word_count ASC, id DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def content_jobs_categories() -> list:
    """List các product_type có jobs + count + count theo status (cho sidebar filter)."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT product_type, COUNT(*) AS total,
                  SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved_cnt,
                  SUM(CASE WHEN status='draft' THEN 1 ELSE 0 END) AS draft_cnt,
                  SUM(CASE WHEN status='synced' THEN 1 ELSE 0 END) AS synced_cnt,
                  SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending_cnt,
                  SUM(CASE WHEN status='text_done' THEN 1 ELSE 0 END) AS text_done_cnt,
                  SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed_cnt
           FROM content_jobs
           WHERE product_type IS NOT NULL AND product_type != ''
           GROUP BY product_type
           ORDER BY total DESC""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def content_jobs_stats() -> dict:
    conn = get_conn()
    by_status = {s: 0 for s in CONTENT_JOB_STATUSES}
    for r in conn.execute("SELECT status, COUNT(*) c FROM content_jobs GROUP BY status").fetchall():
        by_status[r["status"]] = r["c"]
    total = sum(by_status.values())
    conn.close()
    return {"total": total, "by_status": by_status}


def content_jobs_count_by_status() -> dict:
    return content_jobs_stats()["by_status"]


def stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM posts").fetchone()["c"]
    by_status = {
        r["status"]: r["c"]
        for r in conn.execute(
            "SELECT status, COUNT(*) c FROM posts GROUP BY status"
        ).fetchall()
    }
    by_type = {
        r["type"]: r["c"]
        for r in conn.execute(
            "SELECT type, COUNT(*) c FROM posts GROUP BY type"
        ).fetchall()
    }
    today = datetime.now().date().isoformat()
    today_count = conn.execute(
        "SELECT COUNT(*) c FROM posts WHERE scheduled_date = ?", (today,)
    ).fetchone()["c"]
    conn.close()
    return {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "today_count": today_count,
    }
