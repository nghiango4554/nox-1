import json
import os
import sqlite3
import time
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
CREATE INDEX IF NOT EXISTS idx_seo_links_target ON seo_links(target_url);
-- ⚡ 6/8/2026: /seo/history gom `GROUP BY target_url` mà lại cần status_code +
-- error_kind — 2 cột KHÔNG có trong idx_seo_links_target, nên SQLite phải tra bảng
-- đủ 693.587 lần (mất 7,8s). Index phủ đủ 4 cột trả lời trọn gói: còn 214ms (36×).
-- Tốn thêm ~31 MB. Bỏ index này thì trang chậm lại y như cũ.
CREATE INDEX IF NOT EXISTS idx_seo_links_health
    ON seo_links(target_url, status_code, error_kind, is_internal);

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

CREATE TABLE IF NOT EXISTS seo_history_url_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    url_type TEXT,
    score INTEGER,
    status_code INTEGER,
    issue_codes_json TEXT,
    severity TEXT,
    captured_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_seo_hui_snap ON seo_history_url_issues(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_seo_hui_url ON seo_history_url_issues(url);

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
    spec_conflict_json TEXT,           -- [{"field","body","web"}] spec gốc LỆCH spec web (chờ vợ verify)
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

CREATE TABLE IF NOT EXISTS seo_cwv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'mobile',
    scanned_at TEXT,
    performance_score INTEGER,
    lcp_ms INTEGER,
    cls_score REAL,
    tbt_ms INTEGER,
    fcp_ms INTEGER,
    tti_ms INTEGER,
    speed_index_ms INTEGER,
    field_data_ok INTEGER DEFAULT 0,
    lcp_field_ms INTEGER,
    cls_field REAL,
    inp_field_ms INTEGER,
    fcp_field_ms INTEGER,
    overall_category TEXT,
    UNIQUE(url, strategy)
);
CREATE INDEX IF NOT EXISTS idx_seo_cwv_url ON seo_cwv(url);
CREATE INDEX IF NOT EXISTS idx_seo_cwv_score ON seo_cwv(performance_score);

CREATE TABLE IF NOT EXISTS seo_cwv_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_no INTEGER NOT NULL,
    year INTEGER NOT NULL,
    url TEXT NOT NULL,
    strategy TEXT NOT NULL DEFAULT 'mobile',
    scanned_at TEXT,
    performance_score INTEGER,
    lcp_ms INTEGER,
    cls_score REAL,
    tbt_ms INTEGER,
    fcp_ms INTEGER,
    tti_ms INTEGER,
    speed_index_ms INTEGER,
    field_data_ok INTEGER DEFAULT 0,
    lcp_field_ms INTEGER,
    cls_field REAL,
    inp_field_ms INTEGER,
    fcp_field_ms INTEGER,
    overall_category TEXT,
    snapshot_at TEXT NOT NULL,
    UNIQUE(week_no, year, url, strategy)
);
CREATE INDEX IF NOT EXISTS idx_seo_cwv_history_week ON seo_cwv_history(year, week_no, strategy);
CREATE INDEX IF NOT EXISTS idx_seo_cwv_history_url ON seo_cwv_history(url, strategy);

CREATE TABLE IF NOT EXISTS seo_schema_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_no INTEGER NOT NULL,
    year INTEGER NOT NULL,
    captured_at TEXT NOT NULL,
    total_audited INTEGER DEFAULT 0,
    sp_total INTEGER DEFAULT 0,
    sp_has_product INTEGER DEFAULT 0,
    blog_total INTEGER DEFAULT 0,
    blog_has_article INTEGER DEFAULT 0,
    blog_has_faq INTEGER DEFAULT 0,
    col_total INTEGER DEFAULT 0,
    col_has_itemlist INTEGER DEFAULT 0,
    UNIQUE(week_no, year)
);
CREATE INDEX IF NOT EXISTS idx_seo_schema_history_week ON seo_schema_history(year, week_no);

-- Map collection (handle) → product, sync 1 lần từ Haravan API.
-- Dùng cho phân tầng SP ở /seo/title-meta (Tầng 1→2→3 = collection).
CREATE TABLE IF NOT EXISTS collection_products (
    collection_handle TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    product_handle TEXT,
    product_title TEXT,
    product_url TEXT,
    synced_at TEXT,
    PRIMARY KEY (collection_handle, product_id)
);
CREATE INDEX IF NOT EXISTS idx_colprod_handle ON collection_products(collection_handle);
CREATE INDEX IF NOT EXISTS idx_colprod_url ON collection_products(product_url);
"""


_WAL_SET = False  # journal_mode=WAL chỉ cần set 1 LẦN/tiến trình (bền trong file DB)


def get_conn():
    global _WAL_SET
    conn = sqlite3.connect(DB_PATH, timeout=30)  # 30s busy timeout
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")    # đặt TRƯỚC để mọi pragma sau tôn trọng
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous=NORMAL")    # per-conn, non-blocking
    # WAL là persistent property của file DB → set 1 lần lúc khởi động (không contention).
    # Trước đây set MỖI connection → khi đang crawl ghi liên tục, pragma này kẹt chờ lock
    # tới 30s/lần → vào trang title-meta lúc crawl bị treo ~60s. Giờ bỏ khỏi hot path.
    if not _WAL_SET:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            _WAL_SET = True
        except Exception:
            pass
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
        "desc_h1_fixed_at": "TEXT",  # thời điểm fix H1→H2 + PUT Haravan (cột "Ngày sync")
        "desc_word_count": "INTEGER",
        "desc_empty_scanned_at": "TEXT",
        # Schema validator (Task 4 SEO Crawl Optimization, 30/5/2026)
        "schema_types": "TEXT",                   # JSON array: ["Product", "BreadcrumbList"]
        "schema_count": "INTEGER DEFAULT 0",      # số <script type="application/ld+json"> block
        "schema_has_product": "INTEGER DEFAULT 0",
        "schema_has_faq": "INTEGER DEFAULT 0",
        "schema_has_article": "INTEGER DEFAULT 0",
        "schema_errors": "TEXT",                  # JSON array các parse error
        "schema_scanned_at": "TEXT",
    }
    for col, col_type in new_seo_cols.items():
        if col not in seo_cols:
            conn.execute(f"ALTER TABLE seo_pages ADD COLUMN {col} {col_type}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_seo_pages_indexable ON seo_pages(indexable)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_seo_pages_schema_scanned ON seo_pages(schema_scanned_at)")

    # seo_history: per url_type breakdown (Phase H1 SEO History Hub, 30/5/2026)
    sh_cols = {r["name"] for r in conn.execute("PRAGMA table_info(seo_history)").fetchall()}
    sh_new = {
        "avg_score_product": "REAL DEFAULT 0",
        "avg_score_blog": "REAL DEFAULT 0",
        "avg_score_collection": "REAL DEFAULT 0",
    }
    for col, col_type in sh_new.items():
        if col not in sh_cols:
            conn.execute(f"ALTER TABLE seo_history ADD COLUMN {col} {col_type}")

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
    if "spec_conflict_json" not in cj_cols:
        conn.execute("ALTER TABLE content_jobs ADD COLUMN spec_conflict_json TEXT")
    # Default sync_meta_title + sync_meta_desc = 1 (em đã chốt sync hết, không cần tick)
    conn.execute("UPDATE content_jobs SET sync_meta_title=1, sync_meta_desc=1 WHERE sync_meta_title=0 OR sync_meta_desc=0")

    # haravan_products: cột alt_synced_at — cột "Ngày sync" ở /alt-manager (lúc PUT alt lên Haravan)
    hv_cols = {r["name"] for r in conn.execute("PRAGMA table_info(haravan_products)").fetchall()}
    if "alt_synced_at" not in hv_cols:
        conn.execute("ALTER TABLE haravan_products ADD COLUMN alt_synced_at TEXT")

    # Audit log mọi thay đổi đẩy lên Haravan (PUT/POST/DELETE) — truy vết + an toàn
    conn.execute("""
        CREATE TABLE IF NOT EXISTS haravan_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            method TEXT, path TEXT,
            resource_type TEXT, resource_id TEXT,
            summary TEXT,
            ok INTEGER, status_code INTEGER, error TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_haravan_audit_id ON haravan_audit(id DESC)")

    # Hàng đợi job nền (worker process riêng chạy — tách khỏi tiến trình web)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            payload TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            stop_requested INTEGER DEFAULT 0,
            progress TEXT,
            created_at TEXT, started_at TEXT, finished_at TEXT,
            error TEXT, worker_pid INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, id)")

    # ─── Blog Pillar/Cluster (T4) ───
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blog_pillars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            intent TEXT,
            content_group TEXT,
            audience TEXT,
            reason TEXT,
            priority TEXT,
            target_category TEXT,
            layer TEXT,
            cluster_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    # blog_jobs: base table — bug 17/7: trước KHÔNG có CREATE, DB mới crash ngay ALTER.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS blog_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_url TEXT UNIQUE NOT NULL,
            handle TEXT,
            haravan_article_id INTEGER,
            haravan_blog_id INTEGER,
            article_title TEXT,
            edited_title TEXT,
            edited_meta TEXT,
            edited_body_html TEXT,
            ai_generated_at TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            error TEXT,
            synced_at TEXT,
            quality_score INTEGER,
            readability_score INTEGER,
            quality_breakdown TEXT,
            word_count INTEGER,
            click INTEGER DEFAULT 0,
            impression INTEGER DEFAULT 0,
            pos REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    # blog_jobs: cột mới cho bài AI Pillar/Cluster (net-new, chưa có URL thật)
    bj_cols = {r["name"] for r in conn.execute("PRAGMA table_info(blog_jobs)").fetchall()}
    bj_new = {
        "pillar_id": "INTEGER",
        "pillar": "TEXT",
        "keyword": "TEXT",
        "intent": "TEXT",
        "content_layer": "TEXT",        # money / support / media
        "unique_angle": "TEXT",
        "internal_link_hint": "TEXT",
        "priority": "TEXT",             # Cao / Trung bình / Thấp
        "article_type": "TEXT",         # Trend / Evergreen / How-to / So sánh / Giải thích
        "is_external": "INTEGER DEFAULT 0",   # 1 = bài ngoài lề có kiểm soát
        "source": "TEXT DEFAULT 'seo_seed'",  # seo_seed | ai_pillar
        "target_blog": "TEXT",          # huong-dan | news (loại blog Haravan dự kiến)
        "outline": "TEXT",              # H2/H3 outline do AI research (## H2\n### H3...)
    }
    for col, col_type in bj_new.items():
        if col not in bj_cols:
            conn.execute(f"ALTER TABLE blog_jobs ADD COLUMN {col} {col_type}")

    # ─── GA4 Analytics (additive, idempotent) ───
    _init_ga4_tables(conn)

    # ─── GSC direct API daily sync (additive, idempotent) ───
    _init_gsc_api_tables(conn)

    # ─── SEO × GA4 daily-aligned organic join (additive, idempotent) ───
    _init_gsc_ga4_join_tables(conn)

    # ─── Tracking audit (event catalog + findings, additive, idempotent) ───
    _init_tracking_tables(conn)

    # ─── Task Center (reuse ga4_tasks, additive ALTER) ───
    _init_task_center(conn)

    # ─── Analytics daily orchestration (additive) ───
    _init_analytics_ops(conn)

    conn.commit()
    conn.close()


def _init_analytics_ops(conn):
    """Analytics daily orchestration run log — additive, idempotent."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS analytics_daily_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger TEXT, status TEXT,
            steps_json TEXT, alert_sent INTEGER DEFAULT 0,
            new_p0 INTEGER, new_p1 INTEGER, failed_steps INTEGER,
            duration_seconds REAL, error_type TEXT, error_message_safe TEXT,
            started_at TEXT, finished_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_adr_started ON analytics_daily_runs(started_at DESC);
    """)


def _init_task_center(conn):
    """Task Center reuse ga4_tasks (reserved). Thêm cột additive nếu thiếu (ALTER ADD COLUMN, KHÔNG drop).
    Tách implementation_priority (ưu tiên triển khai) khỏi severity (mức incident)."""
    have = {r[1] for r in conn.execute("PRAGMA table_info(ga4_tasks)")}
    if "implementation_priority" not in have:
        conn.execute("ALTER TABLE ga4_tasks ADD COLUMN implementation_priority TEXT")
    if "source" not in have:
        conn.execute("ALTER TABLE ga4_tasks ADD COLUMN source TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ga4_tasks_prio ON ga4_tasks(implementation_priority)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ga4_tasks_type ON ga4_tasks(task_type)")


def _init_tracking_tables(conn):
    """Tracking event catalog + audit findings — additive, idempotent. Dùng data live từ
    ga4_events_daily/ga4_ecommerce_daily. ga4_tracking_audit/ga4_tasks (reserved) giữ nguyên."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tracking_audit_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_from TEXT, date_to TEXT, status TEXT,
            events_checked INTEGER, findings_count INTEGER,
            started_at TEXT, finished_at TEXT, error_type TEXT, error_message_safe TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tar_started ON tracking_audit_runs(started_at DESC);

        CREATE TABLE IF NOT EXISTS tracking_event_catalog (
            event_name TEXT PRIMARY KEY,
            category TEXT, expected INTEGER, source_type TEXT, source_status TEXT,
            business_value TEXT, implementation_priority TEXT, key_event_recommended INTEGER,
            noise_risk TEXT, implementation_status TEXT,
            count_28d INTEGER, users_28d INTEGER, key_28d INTEGER, last_seen TEXT,
            note TEXT, updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tec_cat ON tracking_event_catalog(category);
        CREATE INDEX IF NOT EXISTS idx_tec_status ON tracking_event_catalog(source_status);

        CREATE TABLE IF NOT EXISTS tracking_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_key TEXT UNIQUE, severity TEXT, implementation_priority TEXT,
            category TEXT, title TEXT, description TEXT, metric_snapshot_json TEXT,
            status TEXT DEFAULT 'open', first_seen_at TEXT, last_seen_at TEXT,
            resolved_at TEXT, cooldown_until TEXT, updated_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tf_status ON tracking_findings(status);
        CREATE INDEX IF NOT EXISTS idx_tf_sev ON tracking_findings(severity);
        CREATE INDEX IF NOT EXISTS idx_tf_prio ON tracking_findings(implementation_priority);
        CREATE INDEX IF NOT EXISTS idx_tf_cat ON tracking_findings(category);
    """)


def _init_gsc_ga4_join_tables(conn):
    """SEO × GA4 daily-aligned partial-coverage join (organic v1) — 4 bảng additive.
    LƯU Ý: ga4_seo_landing_join_daily & ga4_seo_landing_join_period là LEGACY/RESERVED —
    do NOT use for organic daily-aligned v1 (giữ nguyên, không drop). Metric chính = GA4 Organic Search;
    all-channel (ga4_landing_pages_daily) chỉ là tham khảo."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ga4_landing_pages_channel_daily (
            date TEXT, normalized_path TEXT, session_default_channel_group TEXT,
            landing_page_raw TEXT,
            active_users INTEGER, new_users INTEGER, sessions INTEGER,
            engaged_sessions INTEGER, engagement_rate REAL, screen_page_views INTEGER,
            key_events INTEGER, ecommerce_purchases INTEGER, purchase_revenue REAL,
            fetched_at TEXT,
            PRIMARY KEY (date, normalized_path, session_default_channel_group)
        );
        CREATE INDEX IF NOT EXISTS idx_ga4lc_date ON ga4_landing_pages_channel_daily(date);
        CREATE INDEX IF NOT EXISTS idx_ga4lc_path ON ga4_landing_pages_channel_daily(normalized_path);
        CREATE INDEX IF NOT EXISTS idx_ga4lc_chan ON ga4_landing_pages_channel_daily(session_default_channel_group);
        CREATE INDEX IF NOT EXISTS idx_ga4lc_date_chan ON ga4_landing_pages_channel_daily(date, session_default_channel_group);

        CREATE TABLE IF NOT EXISTS gsc_ga4_join_daily (
            date TEXT, normalized_path TEXT, search_type TEXT, join_version TEXT,
            full_url TEXT, page_type TEXT, join_status TEXT,
            gsc_clicks INTEGER, gsc_impressions INTEGER, gsc_ctr REAL, gsc_position REAL,
            ga4_organic_sessions INTEGER, ga4_organic_active_users INTEGER, ga4_organic_new_users INTEGER,
            ga4_organic_engaged_sessions INTEGER, ga4_organic_engagement_rate REAL,
            ga4_organic_screen_page_views INTEGER, ga4_organic_key_events INTEGER,
            ga4_organic_ecommerce_purchases INTEGER, ga4_organic_purchase_revenue REAL,
            ga4_all_sessions INTEGER,
            opportunity_type TEXT, priority TEXT, tracking_confidence TEXT,
            gsc_source_mode TEXT, gsc_coverage_mode TEXT, gsc_coverage_complete INTEGER,
            gsc_timezone TEXT, ga4_timezone TEXT, timezone_alignment TEXT, clicks_sessions_comparable TEXT,
            fetched_at TEXT,
            PRIMARY KEY (date, normalized_path, search_type, join_version)
        );
        CREATE INDEX IF NOT EXISTS idx_jd_date ON gsc_ga4_join_daily(date);
        CREATE INDEX IF NOT EXISTS idx_jd_path ON gsc_ga4_join_daily(normalized_path);
        CREATE INDEX IF NOT EXISTS idx_jd_ptype ON gsc_ga4_join_daily(page_type);
        CREATE INDEX IF NOT EXISTS idx_jd_status ON gsc_ga4_join_daily(join_status);
        CREATE INDEX IF NOT EXISTS idx_jd_conf ON gsc_ga4_join_daily(tracking_confidence);
        CREATE INDEX IF NOT EXISTS idx_jd_opp ON gsc_ga4_join_daily(opportunity_type);
        CREATE INDEX IF NOT EXISTS idx_jd_date_st ON gsc_ga4_join_daily(date, search_type);
        CREATE INDEX IF NOT EXISTS idx_jd_date_pt ON gsc_ga4_join_daily(date, page_type);

        CREATE TABLE IF NOT EXISTS gsc_ga4_join_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            join_version TEXT, sync_type TEXT, date_from TEXT, date_to TEXT,
            search_type TEXT, channel_group TEXT, status TEXT, rows_written INTEGER DEFAULT 0,
            matched_count INTEGER, gsc_only_count INTEGER, ga4_only_count INTEGER,
            latest_gsc_date TEXT, latest_ga4_date TEXT, overlap_date_from TEXT, overlap_date_to TEXT,
            warning_json TEXT, error_type TEXT, error_message TEXT,
            started_at TEXT, finished_at TEXT, created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_jr_started ON gsc_ga4_join_runs(started_at DESC);

        CREATE TABLE IF NOT EXISTS gsc_ga4_join_status (
            status_key TEXT PRIMARY KEY,
            join_version TEXT, join_mode TEXT, source_mode TEXT, fallback_available INTEGER,
            search_type TEXT, channel_group TEXT,
            latest_gsc_date TEXT, latest_ga4_date TEXT, overlap_date_from TEXT, overlap_date_to TEXT,
            overlap_days INTEGER, matched_count INTEGER, gsc_only_count INTEGER, ga4_only_count INTEGER,
            confidence_distribution_json TEXT, warning_json TEXT,
            last_success_at TEXT, last_failure_at TEXT, last_error_type TEXT, last_error_message_safe TEXT,
            sync_running INTEGER, sync_started_at TEXT, updated_at TEXT
        );
    """)


def _init_gsc_api_tables(conn):
    """GSC Search Console API daily sync — 7 bảng additive. CREATE IF NOT EXISTS, idempotent.
    Giữ search_type ngay từ đầu (phase đầu chỉ sync 'web'). Sheet cache (gsc_cache.json) là fallback."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS gsc_sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_type TEXT, source_mode TEXT,
            date_from TEXT, date_to TEXT, search_types_json TEXT,
            status TEXT, rows_written INTEGER DEFAULT 0,
            latest_available_date TEXT,
            error_type TEXT, error_message TEXT,
            started_at TEXT, finished_at TEXT, created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_gsc_sync_started ON gsc_sync_runs(started_at DESC);

        CREATE TABLE IF NOT EXISTS gsc_daily_summary (
            date TEXT, search_type TEXT,
            clicks INTEGER, impressions INTEGER, ctr REAL, position REAL,
            fetched_at TEXT,
            PRIMARY KEY (date, search_type)
        );

        CREATE TABLE IF NOT EXISTS gsc_pages_daily (
            date TEXT, normalized_path TEXT, search_type TEXT,
            full_url TEXT, clicks INTEGER, impressions INTEGER, ctr REAL, position REAL,
            fetched_at TEXT,
            PRIMARY KEY (date, normalized_path, search_type)
        );
        CREATE INDEX IF NOT EXISTS idx_gsc_pages_date ON gsc_pages_daily(date);
        CREATE INDEX IF NOT EXISTS idx_gsc_pages_path ON gsc_pages_daily(normalized_path);

        CREATE TABLE IF NOT EXISTS gsc_queries_daily (
            date TEXT, query TEXT, search_type TEXT,
            clicks INTEGER, impressions INTEGER, ctr REAL, position REAL,
            fetched_at TEXT,
            PRIMARY KEY (date, query, search_type)
        );
        CREATE INDEX IF NOT EXISTS idx_gsc_queries_date ON gsc_queries_daily(date);

        CREATE TABLE IF NOT EXISTS gsc_devices_daily (
            date TEXT, device TEXT, search_type TEXT,
            clicks INTEGER, impressions INTEGER, ctr REAL, position REAL,
            fetched_at TEXT,
            PRIMARY KEY (date, device, search_type)
        );

        CREATE TABLE IF NOT EXISTS gsc_countries_daily (
            date TEXT, country TEXT, search_type TEXT,
            clicks INTEGER, impressions INTEGER, ctr REAL, position REAL,
            fetched_at TEXT,
            PRIMARY KEY (date, country, search_type)
        );
        CREATE INDEX IF NOT EXISTS idx_gsc_countries_date ON gsc_countries_daily(date);

        CREATE TABLE IF NOT EXISTS gsc_cache_status (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            source_mode TEXT, coverage_mode TEXT, coverage_complete INTEGER,
            latest_available_date TEXT, fetched_at TEXT,
            cache_age_days INTEGER, data_age_days INTEGER,
            last_success_at TEXT, last_failure_at TEXT,
            last_error_type TEXT, last_error_message TEXT,
            sheet_fallback_available INTEGER, updated_at TEXT
        );
    """)


def _init_ga4_tables(conn):
    """GA4 Analytics schema — 11 bảng additive. CREATE TABLE/INDEX IF NOT EXISTS,
    idempotent, không destructive, tách hẳn schema cũ. Xem services/ga4_sync_service.py."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ga4_sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sync_type TEXT,                 -- backfill | incremental | realtime
            date_from TEXT, date_to TEXT,
            status TEXT,                    -- running | success | error
            rows_written INTEGER DEFAULT 0,
            started_at TEXT, finished_at TEXT,
            error_message TEXT,
            quota_snapshot_json TEXT,
            latest_data_date TEXT,
            created_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_sync_started ON ga4_sync_runs(started_at DESC);

        CREATE TABLE IF NOT EXISTS ga4_daily_summary (
            date TEXT PRIMARY KEY,
            active_users INTEGER, new_users INTEGER, sessions INTEGER,
            engaged_sessions INTEGER, engagement_rate REAL, screen_page_views INTEGER,
            key_events INTEGER, ecommerce_purchases INTEGER,
            purchase_revenue REAL, total_revenue REAL,
            average_session_duration REAL, user_engagement_duration REAL,
            fetched_at TEXT
        );

        CREATE TABLE IF NOT EXISTS ga4_channels_daily (
            date TEXT, session_default_channel_group TEXT, session_source_medium TEXT,
            active_users INTEGER, sessions INTEGER, engaged_sessions INTEGER,
            engagement_rate REAL, key_events INTEGER, ecommerce_purchases INTEGER,
            purchase_revenue REAL, fetched_at TEXT,
            PRIMARY KEY (date, session_default_channel_group, session_source_medium)
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_channels_date ON ga4_channels_daily(date);

        CREATE TABLE IF NOT EXISTS ga4_landing_pages_daily (
            date TEXT, normalized_path TEXT,
            landing_page_raw TEXT, landing_page_plus_query_string_raw TEXT,
            active_users INTEGER, new_users INTEGER, sessions INTEGER,
            engaged_sessions INTEGER, engagement_rate REAL, screen_page_views INTEGER,
            key_events INTEGER, ecommerce_purchases INTEGER, purchase_revenue REAL,
            fetched_at TEXT,
            PRIMARY KEY (date, normalized_path)
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_landing_date ON ga4_landing_pages_daily(date);
        CREATE INDEX IF NOT EXISTS idx_ga4_landing_path ON ga4_landing_pages_daily(normalized_path);

        CREATE TABLE IF NOT EXISTS ga4_devices_daily (
            date TEXT, device_category TEXT,
            active_users INTEGER, sessions INTEGER, engaged_sessions INTEGER,
            engagement_rate REAL, key_events INTEGER, purchase_revenue REAL,
            fetched_at TEXT,
            PRIMARY KEY (date, device_category)
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_devices_date ON ga4_devices_daily(date);

        CREATE TABLE IF NOT EXISTS ga4_events_daily (
            date TEXT, event_name TEXT,
            event_count INTEGER, total_users INTEGER, key_events INTEGER,
            event_value REAL, fetched_at TEXT,
            PRIMARY KEY (date, event_name)
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_events_date ON ga4_events_daily(date);

        CREATE TABLE IF NOT EXISTS ga4_ecommerce_daily (
            date TEXT PRIMARY KEY,
            items_viewed INTEGER, items_added_to_cart INTEGER,
            items_checked_out INTEGER, items_purchased INTEGER, checkouts INTEGER,
            ecommerce_purchases INTEGER, purchase_revenue REAL, total_revenue REAL,
            fetched_at TEXT
        );

        CREATE TABLE IF NOT EXISTS ga4_realtime_cache (
            cache_key TEXT PRIMARY KEY,
            payload_json TEXT, fetched_at TEXT, expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS ga4_seo_landing_join_daily (
            date TEXT, normalized_path TEXT, full_url TEXT, page_type TEXT,
            gsc_clicks INTEGER, gsc_impressions INTEGER, gsc_ctr REAL, gsc_position REAL,
            ga4_sessions INTEGER, ga4_active_users INTEGER, ga4_engaged_sessions INTEGER,
            ga4_engagement_rate REAL, ga4_key_events INTEGER,
            ga4_ecommerce_purchases INTEGER, ga4_purchase_revenue REAL,
            opportunity_type TEXT, priority TEXT, tracking_confidence TEXT,
            fetched_at TEXT,
            PRIMARY KEY (date, normalized_path)
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_join_date ON ga4_seo_landing_join_daily(date);
        CREATE INDEX IF NOT EXISTS idx_ga4_join_path ON ga4_seo_landing_join_daily(normalized_path);

        CREATE TABLE IF NOT EXISTS ga4_tracking_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT UNIQUE,
            event_group TEXT,               -- automatic | ecommerce | custom
            expected INTEGER DEFAULT 0, detected INTEGER DEFAULT 0,
            last_seen_at TEXT, event_count INTEGER DEFAULT 0,
            key_event_status TEXT, business_value TEXT, recommended_setup TEXT,
            status TEXT, note TEXT, updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS ga4_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_type TEXT, severity TEXT,  -- P0 | P1 | P2 | P3
            title TEXT, description TEXT,
            affected_url TEXT, affected_query TEXT,
            metric_snapshot_json TEXT,
            status TEXT DEFAULT 'open',
            dedup_key TEXT UNIQUE, cooldown_until TEXT,
            created_at TEXT, updated_at TEXT, resolved_at TEXT,
            note TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_tasks_status ON ga4_tasks(status);
        CREATE INDEX IF NOT EXISTS idx_ga4_tasks_severity ON ga4_tasks(severity);

        CREATE TABLE IF NOT EXISTS ga4_period_report_cache (
            cache_key TEXT PRIMARY KEY,
            report_type TEXT,
            date_from TEXT, date_to TEXT,
            filters_json TEXT,
            payload_json TEXT,
            fetched_at TEXT, expires_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_period_type ON ga4_period_report_cache(report_type);

        -- SEO × GA4 PERIOD-LEVEL join (Mode B): GSC pages tổng kỳ × GA4 landing theo kỳ, theo normalized_path.
        -- ga4_seo_landing_join_daily (date PK) GIỮ NGUYÊN — reserved for future GSC page-level daily data.
        CREATE TABLE IF NOT EXISTS ga4_seo_landing_join_period (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT NOT NULL,
            gsc_date_from TEXT NOT NULL, gsc_date_to TEXT NOT NULL, gsc_fetched_at TEXT,
            ga4_date_from TEXT NOT NULL, ga4_date_to TEXT NOT NULL,
            normalized_path TEXT NOT NULL, full_url TEXT, page_type TEXT, join_status TEXT,
            gsc_clicks REAL, gsc_impressions REAL, gsc_ctr REAL, gsc_position REAL,
            ga4_sessions REAL, ga4_active_users REAL, ga4_new_users REAL,
            ga4_engaged_sessions REAL, ga4_engagement_rate REAL, ga4_screen_page_views REAL,
            ga4_key_events REAL, ga4_ecommerce_purchases REAL, ga4_purchase_revenue REAL,
            opportunity_type TEXT, priority TEXT, tracking_confidence TEXT,
            fetched_at TEXT NOT NULL,
            UNIQUE(cache_key, normalized_path)
        );
        CREATE INDEX IF NOT EXISTS idx_ga4_join_period_key ON ga4_seo_landing_join_period(cache_key);
        CREATE INDEX IF NOT EXISTS idx_ga4_join_period_path ON ga4_seo_landing_join_period(normalized_path);
        CREATE INDEX IF NOT EXISTS idx_ga4_join_period_ptype ON ga4_seo_landing_join_period(page_type);
        CREATE INDEX IF NOT EXISTS idx_ga4_join_period_status ON ga4_seo_landing_join_period(join_status);
        CREATE INDEX IF NOT EXISTS idx_ga4_join_period_prio ON ga4_seo_landing_join_period(priority);
    """)

    # CWV LCP (P0A/P0B/P0C) — schema additive + idempotent, chạy 1 lần lúc startup
    cwv_lcp_harden_schema()


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
        "schema_types", "schema_count", "schema_has_product",
        "schema_has_article", "schema_has_faq", "schema_errors", "schema_scanned_at",
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


def seo_upsert_pages_batch(pairs: list):
    """Batch write crawl results. pairs = [(data_dict, links_list), ...].
    One connection, one commit — ~50x ít commit hơn so với gọi từng URL.
    """
    fields = [
        "url", "url_type", "last_run_id", "status_code", "final_url",
        "title", "title_len", "meta_desc", "meta_desc_len",
        "h1", "h1_count", "word_count",
        "images_total", "images_no_alt",
        "internal_links", "external_links",
        "has_canonical", "canonical_url", "has_og", "has_schema",
        "schema_types", "schema_count", "schema_has_product",
        "schema_has_article", "schema_has_faq", "schema_errors", "schema_scanned_at",
        "indexable", "indexability_reason", "page_size_bytes",
        "h2_list", "redirect_chain",
        "desc_h1_count", "desc_h1_text", "desc_h1_scanned_at",
        "load_ms", "score", "issues", "last_crawled",
    ]
    cols = ", ".join(fields)
    placeholders = ", ".join("?" * len(fields))
    updates = ", ".join(f"{f}=excluded.{f}" for f in fields if f != "url")
    conn = get_conn()
    try:
        for data, links in pairs:
            conn.execute(
                f"INSERT INTO seo_pages ({cols}) VALUES ({placeholders}) "
                f"ON CONFLICT(url) DO UPDATE SET {updates}",
                [data.get(f) for f in fields],
            )
            url = data.get("url")
            if url:
                conn.execute("DELETE FROM seo_links WHERE source_url = ?", (url,))
                if links:
                    conn.executemany(
                        "INSERT OR IGNORE INTO seo_links (source_url, target_url, is_internal) VALUES (?, ?, ?)",
                        [(url, t, int(bool(i))) for t, i in links],
                    )
        conn.commit()
    finally:
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
                    desc_h1_fixed_at, title, score
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


def seo_mark_desc_h1_fixed(url: str, fixed_at: str):
    """Ghi thời điểm fix H1→H2 + PUT Haravan thành công (cột 'Ngày sync')."""
    conn = get_conn()
    conn.execute("UPDATE seo_pages SET desc_h1_fixed_at = ? WHERE url = ?", (fixed_at, url))
    conn.commit()
    conn.close()


def seo_urls_by_type(types: list) -> list:
    """Tất cả URL trong seo_pages thuộc các url_type cho trước (dùng cho re-crawl FULL)."""
    if not types:
        return []
    conn = get_conn()
    ph = ",".join("?" * len(types))
    rows = conn.execute(
        f"SELECT url FROM seo_pages WHERE url_type IN ({ph}) AND url IS NOT NULL",
        list(types),
    ).fetchall()
    conn.close()
    return [r["url"] for r in rows]


def execute_write(sql: str, params=(), retries: int = 8):
    """Execute 1 câu write + commit, RETRY khi 'database is locked' (vd lúc re-crawl ghi DB nặng).
    Mỗi lần mở/đóng connection riêng → retry an toàn. Backoff tăng dần."""
    import time as _t
    for attempt in range(retries):
        conn = get_conn()
        try:
            conn.execute(sql, params)
            conn.commit()
            conn.close()
            return
        except sqlite3.OperationalError as e:
            conn.close()
            if "locked" in str(e).lower() and attempt < retries - 1:
                _t.sleep(min(0.4 * (attempt + 1), 3.0))
                continue
            raise


def haravan_audit_log(method, path, resource_type=None, resource_id=None,
                      summary=None, ok=1, status_code=None, error=None):
    """Ghi 1 dòng audit thay đổi Haravan (best-effort, có retry khi DB lock)."""
    execute_write(
        "INSERT INTO haravan_audit (ts, method, path, resource_type, resource_id, summary, ok, status_code, error) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (datetime.now().isoformat(timespec="seconds"), method, path, resource_type,
         resource_id, summary, 1 if ok else 0, status_code, error),
    )


def haravan_audit_list(limit: int = 200, offset: int = 0, only_fail: bool = False) -> list:
    conn = get_conn()
    sql = "SELECT * FROM haravan_audit"
    if only_fail:
        sql += " WHERE ok=0"
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    rows = conn.execute(sql, (limit, offset)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def haravan_audit_stats() -> dict:
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM haravan_audit").fetchone()[0]
    fail = conn.execute("SELECT COUNT(*) FROM haravan_audit WHERE ok=0").fetchone()[0]
    today = conn.execute("SELECT COUNT(*) FROM haravan_audit WHERE ts >= date('now','localtime')").fetchone()[0]
    conn.close()
    return {"total": total, "fail": fail, "today": today}


# ─────────────────────── JOB QUEUE (worker nền) ───────────────────────

def job_enqueue(jtype: str, payload: dict = None) -> int:
    """Thêm 1 job vào hàng đợi. Trả job_id. Worker process riêng sẽ nhặt + chạy."""
    now = datetime.now().isoformat(timespec="seconds")
    for attempt in range(8):
        conn = get_conn()
        try:
            cur = conn.execute(
                "INSERT INTO jobs (type, payload, status, created_at) VALUES (?,?,'queued',?)",
                (jtype, json.dumps(payload or {}, ensure_ascii=False), now),
            )
            jid = cur.lastrowid
            conn.commit(); conn.close()
            return jid
        except sqlite3.OperationalError as e:
            conn.close()
            if "locked" in str(e).lower() and attempt < 7:
                time.sleep(0.4 * (attempt + 1)); continue
            raise


def job_claim_next(types: list = None) -> dict:
    """Worker gọi: nhặt job 'queued' cũ nhất → set 'running' (atomic). None nếu rỗng."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        sql = "SELECT * FROM jobs WHERE status='queued'"
        args = []
        if types:
            sql += " AND type IN (%s)" % ",".join("?" * len(types)); args += list(types)
        sql += " ORDER BY id ASC LIMIT 1"
        row = conn.execute(sql, args).fetchone()
        if not row:
            conn.execute("COMMIT"); conn.close(); return None
        conn.execute("UPDATE jobs SET status='running', started_at=?, worker_pid=? WHERE id=?",
                     (datetime.now().isoformat(timespec="seconds"), os.getpid(), row["id"]))
        conn.execute("COMMIT")
        job = dict(row); job["status"] = "running"
        conn.close()
        return job
    except Exception:
        try: conn.execute("ROLLBACK")
        except Exception: pass
        conn.close(); return None


def job_update_progress(job_id: int, progress: dict):
    execute_write("UPDATE jobs SET progress=? WHERE id=?",
                  (json.dumps(progress, ensure_ascii=False), job_id))


def job_finish(job_id: int, status: str, error: str = None):
    execute_write("UPDATE jobs SET status=?, finished_at=?, error=? WHERE id=?",
                  (status, datetime.now().isoformat(timespec="seconds"), error, job_id))


def job_request_stop(job_id: int):
    execute_write("UPDATE jobs SET stop_requested=1 WHERE id=?", (job_id,))


def job_stop_requested(job_id: int) -> bool:
    conn = get_conn()
    r = conn.execute("SELECT stop_requested FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    return bool(r and r[0])


def job_get(job_id: int) -> dict:
    conn = get_conn()
    r = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


def job_active(jtype: str) -> dict:
    """Job đang queued/running mới nhất của 1 type (cho UI hiện trạng thái)."""
    conn = get_conn()
    r = conn.execute(
        "SELECT * FROM jobs WHERE type=? AND status IN ('queued','running') ORDER BY id DESC LIMIT 1",
        (jtype,)).fetchone()
    conn.close()
    return dict(r) if r else None


def job_latest(jtype: str) -> dict:
    """Job mới nhất (mọi status) của 1 type — để hiện kết quả lần chạy gần nhất."""
    conn = get_conn()
    r = conn.execute("SELECT * FROM jobs WHERE type=? ORDER BY id DESC LIMIT 1", (jtype,)).fetchone()
    conn.close()
    return dict(r) if r else None


def jobs_requeue_stale_running():
    """Khi worker khởi động lại: job 'running' mồ côi (worker chết) → đánh 'failed'."""
    execute_write(
        "UPDATE jobs SET status='failed', error='worker restart — job mồ côi', "
        "finished_at=? WHERE status='running'",
        (datetime.now().isoformat(timespec="seconds"),))


def mark_alt_synced(product_id: int, synced_at: str = None):
    """Ghi thời điểm PUT ALT (ảnh SP/mô tả) lên Haravan — cột 'Ngày sync' ở /alt-manager."""
    conn = get_conn()
    conn.execute(
        "UPDATE haravan_products SET alt_synced_at = ? WHERE haravan_id = ?",
        (synced_at or datetime.now().isoformat(timespec="seconds"), product_id),
    )
    conn.commit()
    conn.close()


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
    """Link cần check: TẤT CẢ external + internal link trỏ tới URL CHƯA được
    crawler chính verify 200 (tức ngoài sitemap → có thể 404, vd collection chết).
    Internal link đã là trang 200 trong seo_pages thì BỎ (khỏi check lại).

    `only_targets`: nếu có, chỉ check đúng các URL trong list (vd re-check broken).
    """
    conn = get_conn()
    args = []
    # internal link ngoài tập trang 200 đã crawl → cần kiểm (bắt dead internal link)
    sql = """SELECT target_url, is_internal, COUNT(*) refs
             FROM seo_links
             WHERE (is_internal = 0
                    OR (is_internal = 1 AND target_url NOT IN
                        (SELECT url FROM seo_pages WHERE status_code = 200))) """
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
    # Mặc định loại social share button (Pinterest/FB/Twitter share) ra khỏi
    # broken — bọn này luôn trả 429/403 cho bot, không phải link gãy thật.
    # Nếu caller filter explicit error_kind thì cho qua để xem chi tiết.
    if not filters.get("error_kind"):
        sql += " AND (error_kind IS NULL OR error_kind NOT IN ('social_share_skip', 'asset_cdn_skip')) "
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
    # ⚡ 6/8/2026: cùng bẫy như seo_count_broken_filtered — GROUP BY target_url dụ
    # SQLite quét cả idx_seo_links_target. Lọc trước bằng CTE: 2.478ms → 31ms.
    rows = conn.execute(
        f"""WITH b AS MATERIALIZED (
                SELECT target_url, status_code, error_kind, source_url, is_internal
                FROM seo_links {where_sql}
            )
            SELECT target_url, status_code, MAX(error_kind) error_kind, COUNT(*) refs,
                  GROUP_CONCAT(source_url, '|') sources, MAX(is_internal) is_internal
            FROM b
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
    # ⚡ 6/8/2026: COUNT(DISTINCT) trực tiếp làm SQLite chọn quét TOÀN BỘ
    # idx_seo_links_target (693.587 dòng) thay vì lọc trước còn 8.701 dòng → 2,4s.
    # CTE MATERIALIZED ép lọc xong mới gom: 2.433ms → 23ms. Xem _broken_cte().
    n = conn.execute(
        f"WITH b AS MATERIALIZED (SELECT target_url FROM seo_links {where_sql}) "
        f"SELECT COUNT(DISTINCT target_url) c FROM b",
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
            COUNT(DISTINCT CASE WHEN (status_code >= 400 OR status_code = 0)
                                 AND (error_kind IS NULL OR error_kind NOT IN ('social_share_skip', 'asset_cdn_skip'))
                                THEN target_url END) broken,
            COUNT(DISTINCT CASE WHEN status_code IS NULL
                                THEN target_url END) unchecked,
            COUNT(DISTINCT CASE WHEN status_code IS NOT NULL
                                 AND ((status_code > 0 AND status_code < 400)
                                      OR error_kind IN ('social_share_skip', 'asset_cdn_skip'))
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
    """Snapshot điểm SEO hiện tại vào bảng seo_history. Trả id row vừa tạo.
    Lưu cả per url_type avg score (product/blog/collection) cho timeline chart.
    """
    stats = seo_stats()
    conn = get_conn()
    # broken_links = link GÃY THẬT (4xx trừ 403/429 + 5xx) — KHÔNG gộp
    # blocked/timeout/circuit-breaker (để khớp broken_true của dashboard).
    real_broken = conn.execute(
        """SELECT COUNT(DISTINCT target_url) c FROM seo_links
           WHERE status_code >= 500
              OR (status_code BETWEEN 400 AND 499 AND status_code NOT IN (403, 429))"""
    ).fetchone()["c"]
    per_type_rows = conn.execute(
        """SELECT url_type, ROUND(AVG(score), 1) avg_s
           FROM seo_pages
           WHERE score IS NOT NULL AND url_type IN ('product', 'blog', 'collection')
           GROUP BY url_type"""
    ).fetchall()
    per_type = {r["url_type"]: r["avg_s"] for r in per_type_rows}
    cur = conn.execute(
        """INSERT INTO seo_history
           (captured_at, total, avg_score, good, ok_count, bad, broken_links, note,
            avg_score_product, avg_score_blog, avg_score_collection)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            stats["total"], stats["avg_score"],
            stats["good"], stats["ok"], stats["bad"],
            real_broken,
            note,
            per_type.get("product") or 0,
            per_type.get("blog") or 0,
            per_type.get("collection") or 0,
        ),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    # Per-URL issue snapshot (going-forward; phục vụ so sánh new/fixed).
    try:
        seo_capture_url_issues(rid)
    except Exception:
        pass
    # Auto-cleanup giữ 52 snapshot mới nhất (1 năm nếu weekly)
    try:
        seo_history_cleanup(keep=52)
    except Exception:
        pass
    return rid


def seo_capture_url_issues(snapshot_id: int) -> int:
    """Lưu trạng thái issue per-URL của snapshot (từ seo_pages). Idempotent theo snapshot_id."""
    conn = get_conn()
    exists = conn.execute(
        "SELECT 1 FROM seo_history_url_issues WHERE snapshot_id=? LIMIT 1", (snapshot_id,)
    ).fetchone()
    if exists:
        conn.close()
        return 0
    cap = datetime.now().isoformat(timespec="seconds")
    rows = conn.execute(
        """SELECT url, url_type, score, status_code, issues
           FROM seo_pages
           WHERE last_crawled IS NOT NULL
             AND issues IS NOT NULL AND issues != '' AND issues != '[]'"""
    ).fetchall()
    payload = []
    for r in rows:
        try:
            arr = json.loads(r["issues"]) or []
        except (ValueError, TypeError):
            arr = []
        codes = sorted({it.get("code") for it in arr if it.get("code")})
        has_err = any(it.get("level") == "error" for it in arr)
        sc = r["score"] if r["score"] is not None else 0
        severity = "critical" if (has_err or sc < 50) else ("warning" if sc < 65 else "ok")
        payload.append((snapshot_id, r["url"], r["url_type"], r["score"],
                        r["status_code"], json.dumps(codes), severity, cap))
    conn.executemany(
        """INSERT INTO seo_history_url_issues
           (snapshot_id, url, url_type, score, status_code, issue_codes_json, severity, captured_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        payload,
    )
    conn.commit()
    conn.close()
    return len(payload)


def seo_history_url_compare() -> dict:
    """So per-URL 2 snapshot mới nhất trong seo_history_url_issues.
    Return available=False nếu <2 snapshot. Ngược lại: new_issue_urls, fixed_urls,
    regressed, improved (mỗi cái list dict + count)."""
    conn = get_conn()
    snaps = conn.execute(
        "SELECT DISTINCT snapshot_id FROM seo_history_url_issues ORDER BY snapshot_id DESC LIMIT 2"
    ).fetchall()
    if len(snaps) < 2:
        conn.close()
        return {"available": False, "snapshots": len(snaps)}
    latest_id, prev_id = snaps[0]["snapshot_id"], snaps[1]["snapshot_id"]

    def _load(sid):
        return {r["url"]: r for r in conn.execute(
            "SELECT url, url_type, score, status_code, issue_codes_json, severity "
            "FROM seo_history_url_issues WHERE snapshot_id=?", (sid,)).fetchall()}

    cur, prev = _load(latest_id), _load(prev_id)
    conn.close()

    def _codes(row):
        try:
            return set(json.loads(row["issue_codes_json"]) or [])
        except (ValueError, TypeError):
            return set()

    new_issue, fixed, regressed, improved = [], [], [], []
    for url, cr in cur.items():
        pr = prev.get(url)
        cc = _codes(cr)
        pc = _codes(pr) if pr else set()
        if pr is None:
            if cc:
                new_issue.append({"url": url, "url_type": cr["url_type"],
                                  "new_codes": sorted(cc), "severity": cr["severity"]})
            continue
        added = cc - pc
        if added:
            new_issue.append({"url": url, "url_type": cr["url_type"],
                              "new_codes": sorted(added), "severity": cr["severity"]})
        cs = cr["score"] if cr["score"] is not None else 0
        ps = pr["score"] if pr["score"] is not None else 0
        if cs < ps - 2:
            regressed.append({"url": url, "url_type": cr["url_type"],
                              "from": ps, "to": cs})
        elif cs > ps + 2:
            improved.append({"url": url, "url_type": cr["url_type"],
                             "from": ps, "to": cs})
    for url, pr in prev.items():
        cr = cur.get(url)
        pc = _codes(pr)
        cc = _codes(cr) if cr else set()
        removed = pc - cc
        if removed:
            fixed.append({"url": url, "url_type": pr["url_type"],
                          "fixed_codes": sorted(removed)})
    return {
        "available": True, "latest_id": latest_id, "prev_id": prev_id,
        "new_issue": new_issue[:200], "new_issue_count": len(new_issue),
        "fixed": fixed[:200], "fixed_count": len(fixed),
        "regressed": regressed[:200], "regressed_count": len(regressed),
        "improved": improved[:200], "improved_count": len(improved),
    }


def seo_history_cleanup(keep: int = 52) -> int:
    """Giữ `keep` snapshot mới nhất, xóa cũ hơn. Return số row đã xóa."""
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM seo_history ORDER BY id DESC LIMIT 1 OFFSET ?", (keep,)
    ).fetchone()
    if not row:
        conn.close()
        return 0
    cutoff = row["id"]
    cur = conn.execute("DELETE FROM seo_history WHERE id <= ?", (cutoff,))
    conn.execute("DELETE FROM seo_history_url_issues WHERE snapshot_id <= ?", (cutoff,))
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


def seo_history_regression_check() -> dict:
    """So sánh snapshot mới nhất vs snapshot trước nó. Return:
        {has_regression: bool, delta: float, prev_id, latest_id, prev_avg, latest_avg}
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, avg_score FROM seo_history ORDER BY id DESC LIMIT 2"
    ).fetchall()
    conn.close()
    if len(rows) < 2:
        return {"has_regression": False}
    latest = rows[0]
    prev = rows[1]
    delta = round((latest["avg_score"] or 0) - (prev["avg_score"] or 0), 1)
    return {
        "has_regression": delta <= -5,
        "delta": delta,
        "prev_id": prev["id"],
        "latest_id": latest["id"],
        "prev_avg": prev["avg_score"],
        "latest_avg": latest["avg_score"],
    }


def seo_history_get(snapshot_id: int) -> dict:
    """Lấy 1 snapshot theo id (cho trang compare). Return None nếu ko có."""
    conn = get_conn()
    r = conn.execute("SELECT * FROM seo_history WHERE id=?", (snapshot_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


def seo_history_list(limit: int = 200) -> list:
    """Trả list snapshot lịch sử (mới nhất trước)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM seo_history ORDER BY captured_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def gsc_ctr_tracking_list(limit: int = 200) -> list:
    """CTR Rescue tracking records (đọc DB, KHÔNG gọi GSC API). [] nếu chưa có bảng."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM gsc_ctr_tracking ORDER BY landing_group, baseline_impressions DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


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
        "avg_score_product": [r.get("avg_score_product") or 0 for r in items],
        "avg_score_blog": [r.get("avg_score_blog") or 0 for r in items],
        "avg_score_collection": [r.get("avg_score_collection") or 0 for r in items],
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


def hv_all_product_ids() -> set:
    """Tập tất cả haravan_id đang có trong cache (dùng cho prune SP chết)."""
    conn = get_conn()
    rows = conn.execute("SELECT haravan_id FROM haravan_products").fetchall()
    conn.close()
    return {r[0] for r in rows}


def hv_delete_products(haravan_ids) -> int:
    """Xóa SP khỏi cache theo list haravan_id. Trả số dòng xóa."""
    ids = [int(x) for x in haravan_ids]
    if not ids:
        return 0
    conn = get_conn()
    n = 0
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        ph = ",".join("?" * len(chunk))
        cur = conn.execute(
            f"DELETE FROM haravan_products WHERE haravan_id IN ({ph})", chunk
        )
        n += cur.rowcount
    conn.commit()
    conn.close()
    return n


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
    execute_write(  # retry khi DB locked (vd đang crawl)
        f"UPDATE content_jobs SET {sets} WHERE id=?",
        [*[fields[k] for k in keys], job_id],
    )


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


# ═══════════════════════════════════════════════════════════════════════════
# CWV (Core Web Vitals) — PageSpeed Insights data
# ═══════════════════════════════════════════════════════════════════════════

def cwv_upsert(data: dict):
    """Upsert 1 kết quả PSI scan vào seo_cwv."""
    conn = get_conn()
    conn.execute("""
        INSERT INTO seo_cwv
            (url, strategy, scanned_at, performance_score, lcp_ms, cls_score,
             tbt_ms, fcp_ms, tti_ms, speed_index_ms,
             field_data_ok, lcp_field_ms, cls_field, inp_field_ms, fcp_field_ms, overall_category)
        VALUES
            (:url, :strategy, :scanned_at, :performance_score, :lcp_ms, :cls_score,
             :tbt_ms, :fcp_ms, :tti_ms, :speed_index_ms,
             :field_data_ok, :lcp_field_ms, :cls_field, :inp_field_ms, :fcp_field_ms, :overall_category)
        ON CONFLICT(url, strategy) DO UPDATE SET
            scanned_at=excluded.scanned_at,
            performance_score=excluded.performance_score,
            lcp_ms=excluded.lcp_ms, cls_score=excluded.cls_score,
            tbt_ms=excluded.tbt_ms, fcp_ms=excluded.fcp_ms,
            tti_ms=excluded.tti_ms, speed_index_ms=excluded.speed_index_ms,
            field_data_ok=excluded.field_data_ok,
            lcp_field_ms=excluded.lcp_field_ms, cls_field=excluded.cls_field,
            inp_field_ms=excluded.inp_field_ms, fcp_field_ms=excluded.fcp_field_ms,
            overall_category=excluded.overall_category
    """, {
        "url": data.get("url"), "strategy": data.get("strategy", "mobile"),
        "scanned_at": data.get("scanned_at"),
        "performance_score": data.get("performance_score"),
        "lcp_ms": data.get("lcp_ms"), "cls_score": data.get("cls_score"),
        "tbt_ms": data.get("tbt_ms"), "fcp_ms": data.get("fcp_ms"),
        "tti_ms": data.get("tti_ms"), "speed_index_ms": data.get("speed_index_ms"),
        "field_data_ok": data.get("field_data_ok", 0),
        "lcp_field_ms": data.get("lcp_field_ms"), "cls_field": data.get("cls_field"),
        "inp_field_ms": data.get("inp_field_ms"), "fcp_field_ms": data.get("fcp_field_ms"),
        "overall_category": data.get("overall_category", ""),
    })
    conn.commit()
    conn.close()


def cwv_list(strategy: str = "mobile", limit: int = 100, offset: int = 0,
             sort: str = "performance_score", order: str = "asc") -> list:
    """Lấy danh sách CWV results, join với seo_pages để lấy url_type."""
    safe_sort = sort if sort in (
        "performance_score", "lcp_ms", "cls_score", "tbt_ms",
        "lcp_field_ms", "cls_field", "inp_field_ms", "scanned_at"
    ) else "performance_score"
    safe_order = "DESC" if order == "desc" else "ASC"
    conn = get_conn()
    rows = conn.execute(f"""
        SELECT c.*, p.url_type, p.title
        FROM seo_cwv c
        LEFT JOIN seo_pages p ON p.url = c.url
        WHERE c.strategy = ?
        ORDER BY c.{safe_sort} {safe_order} NULLS LAST
        LIMIT ? OFFSET ?
    """, (strategy, limit, offset)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cwv_count(strategy: str = "mobile") -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM seo_cwv WHERE strategy=?", (strategy,)).fetchone()[0]
    conn.close()
    return n


def cwv_stats(strategy: str = "mobile") -> dict:
    """Summary stats: avg score, LCP distribution, CLS distribution."""
    conn = get_conn()
    row = conn.execute("""
        SELECT
            COUNT(*) total,
            ROUND(AVG(performance_score), 1) avg_perf,
            ROUND(AVG(lcp_ms), 0) avg_lcp,
            ROUND(AVG(cls_score), 4) avg_cls,
            ROUND(AVG(tbt_ms), 0) avg_tbt,
            SUM(CASE WHEN performance_score >= 90 THEN 1 ELSE 0 END) perf_good,
            SUM(CASE WHEN performance_score >= 50 AND performance_score < 90 THEN 1 ELSE 0 END) perf_ok,
            SUM(CASE WHEN performance_score < 50 OR performance_score IS NULL THEN 1 ELSE 0 END) perf_bad,
            SUM(CASE WHEN lcp_ms <= 2500 THEN 1 ELSE 0 END) lcp_good,
            SUM(CASE WHEN lcp_ms > 2500 AND lcp_ms <= 4000 THEN 1 ELSE 0 END) lcp_ok,
            SUM(CASE WHEN lcp_ms > 4000 THEN 1 ELSE 0 END) lcp_bad,
            SUM(CASE WHEN cls_score <= 0.1 THEN 1 ELSE 0 END) cls_good,
            SUM(CASE WHEN cls_score > 0.1 AND cls_score <= 0.25 THEN 1 ELSE 0 END) cls_ok,
            SUM(CASE WHEN cls_score > 0.25 THEN 1 ELSE 0 END) cls_bad
        FROM seo_cwv WHERE strategy=?
    """, (strategy,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def cwv_top_urls(limit: int = 50, url_type: str = "product", skip_scanned: bool = False,
                 strategy: str = "mobile", since: str = None) -> list:
    """Lấy top URL từ seo_pages theo internal_links (trang quan trọng nhất).
    `since`: chỉ trả URL CHƯA quét TRONG ĐỢT này (không có scan với scanned_at >= since) →
             dùng cho resume: dừng giữa chừng rồi quét tiếp đúng phần còn lại của đợt."""
    conn = get_conn()
    if since:
        rows = conn.execute("""
            SELECT p.url FROM seo_pages p
            WHERE p.url_type=? AND p.status_code=200 AND p.indexable=1
            AND NOT EXISTS (SELECT 1 FROM seo_cwv c
                            WHERE c.url=p.url AND c.strategy=? AND c.scanned_at >= ?)
            ORDER BY p.internal_links DESC
            LIMIT ?
        """, (url_type, strategy, since, limit)).fetchall()
    elif skip_scanned:
        rows = conn.execute("""
            SELECT p.url FROM seo_pages p
            WHERE p.url_type=? AND p.status_code=200 AND p.indexable=1
            AND NOT EXISTS (SELECT 1 FROM seo_cwv c WHERE c.url=p.url AND c.strategy=?)
            ORDER BY p.internal_links DESC
            LIMIT ?
        """, (url_type, strategy, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT url FROM seo_pages
            WHERE url_type=? AND status_code=200 AND indexable=1
            ORDER BY internal_links DESC LIMIT ?
        """, (url_type, limit)).fetchall()
    conn.close()
    return [r["url"] for r in rows]


def cwv_progress(strategy: str = "mobile") -> list:
    """Per url_type: total pages, scanned, unscanned."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.url_type,
               COUNT(*) as total,
               COUNT(c.url) as scanned
        FROM seo_pages p
        LEFT JOIN seo_cwv c ON c.url=p.url AND c.strategy=?
        WHERE p.status_code=200 AND p.indexable=1
        GROUP BY p.url_type
        ORDER BY total DESC
    """, (strategy,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({
            "url_type": r["url_type"],
            "total": r["total"],
            "scanned": r["scanned"],
            "unscanned": r["total"] - r["scanned"],
        })
    return out


def cwv_clear(strategy: str = None):
    conn = get_conn()
    if strategy:
        conn.execute("DELETE FROM seo_cwv WHERE strategy=?", (strategy,))
    else:
        conn.execute("DELETE FROM seo_cwv")
    conn.commit()
    conn.close()


def cwv_history_has_week(week_no: int, year: int, strategy: str = None) -> bool:
    """Check tuần (week_no, year) đã snapshot chưa — dùng cho idempotency."""
    conn = get_conn()
    if strategy:
        row = conn.execute(
            "SELECT 1 FROM seo_cwv_history WHERE week_no=? AND year=? AND strategy=? LIMIT 1",
            (week_no, year, strategy),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT 1 FROM seo_cwv_history WHERE week_no=? AND year=? LIMIT 1",
            (week_no, year),
        ).fetchone()
    conn.close()
    return row is not None


_CWV_PASS_TYPES = ("product", "collection", "blog", "page")


def cwv_pass_stats(since: str = None) -> dict:
    """Tiến độ 1 ĐỢT quét toàn bộ (mobile + desktop).
    total = số URL hợp lệ × 2 strategy · scanned = số (url,strategy) đã quét trong đợt
    (scanned_at >= since) · remaining = total - scanned. Nhẹ (2 COUNT)."""
    conn = get_conn()
    ph = ",".join("?" * len(_CWV_PASS_TYPES))
    eligible = conn.execute(
        f"SELECT COUNT(*) FROM seo_pages WHERE status_code=200 AND indexable=1 "
        f"AND url_type IN ({ph})", _CWV_PASS_TYPES).fetchone()[0]
    total = eligible * 2
    scanned = 0
    if since:
        scanned = conn.execute(
            f"SELECT COUNT(*) FROM seo_cwv c JOIN seo_pages p ON p.url=c.url "
            f"WHERE p.status_code=200 AND p.indexable=1 AND p.url_type IN ({ph}) "
            f"AND c.scanned_at >= ?", (*_CWV_PASS_TYPES, since)).fetchone()[0]
    conn.close()
    return {"total": total, "scanned": scanned,
            "remaining": max(0, total - scanned), "eligible_urls": eligible}


# ─── seo_cwv_lcp — bảng phân tích LCP (P0A) + UI read-only (P0B) ───
_CWV_LCP_CANON = [
    ("lab_lcp_latest", "INTEGER"), ("lab_lcp_median", "INTEGER"),
    ("lab_run_count", "INTEGER"), ("lab_scanned_at", "TEXT"),
    ("field_lcp_p75", "INTEGER"), ("field_scope", "TEXT"),
    ("field_source", "TEXT"), ("field_category", "TEXT"),
    ("fcp", "INTEGER"), ("tbt", "INTEGER"), ("ttfb", "INTEGER"),
    ("primary_opportunity", "TEXT"), ("opportunity_saving_ms", "INTEGER"),
    ("lcp_asset_url", "TEXT"),
]


def cwv_lcp_harden_schema():
    """Harden bảng seo_cwv_lcp — ADDITIVE only (CREATE IF NOT EXISTS + ALTER ADD COLUMN).
    Idempotent, không destructive. Backfill cột canonical từ cột cũ (nếu có)."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seo_cwv_lcp (
            url TEXT, strategy TEXT, page_type TEXT, lcp_element TEXT,
            lab_lcp_latest INTEGER, lab_lcp_median INTEGER, lab_run_count INTEGER, lab_scanned_at TEXT,
            field_lcp_p75 INTEGER, field_scope TEXT, field_source TEXT, field_category TEXT,
            fcp INTEGER, tbt INTEGER, ttfb INTEGER,
            primary_opportunity TEXT, opportunity_saving_ms INTEGER, lcp_asset_url TEXT,
            PRIMARY KEY (url, strategy)
        )
    """)
    existing = {r[1] for r in conn.execute("PRAGMA table_info(seo_cwv_lcp)").fetchall()}
    for name, typ in _CWV_LCP_CANON:
        if name not in existing:
            conn.execute(f"ALTER TABLE seo_cwv_lcp ADD COLUMN {name} {typ}")
    # Lịch sử mỗi lần đo lab (P0C) — additive, mỗi enrich ghi thêm 1 dòng
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seo_cwv_lcp_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT, strategy TEXT, page_type TEXT, scanned_at TEXT,
            lcp INTEGER, fcp INTEGER, tbt INTEGER, ttfb INTEGER, performance_score INTEGER,
            primary_opportunity TEXT, opportunity_saving_ms INTEGER,
            lcp_element TEXT, lcp_asset_url TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cwv_lcp_runs ON seo_cwv_lcp_runs(url, strategy, id DESC)")
    conn.commit()
    conn.close()
    _cwv_lcp_backfill_canon()
    _cwv_lcp_seed_legacy_runs()


def _cwv_lcp_seed_legacy_runs():
    """Đưa các lần đo PSI THẬT đã có vào seo_cwv_lcp_runs để lab_run_count = số run lịch sử thật.
    Nguồn (ghi cột `source`): 'legacy:cwv_scan' (seo_cwv chain) + 'legacy:p0a_enrich' (lần re-đo P0A).
    KHÔNG tạo dữ liệu giả — chỉ chuyển số đo đã lưu vào bảng lịch sử + ghi rõ nguồn. Idempotent."""
    import statistics
    conn = get_conn()
    runcols = {r[1] for r in conn.execute("PRAGMA table_info(seo_cwv_lcp_runs)").fetchall()}
    if "source" not in runcols:
        conn.execute("ALTER TABLE seo_cwv_lcp_runs ADD COLUMN source TEXT")
    lcpcols = {r[1] for r in conn.execute("PRAGMA table_info(seo_cwv_lcp)").fetchall()}
    seeded = conn.execute("SELECT COUNT(*) FROM seo_cwv_lcp_runs WHERE source LIKE 'legacy:%'").fetchone()[0]
    if seeded > 0 or "lcp_lab_stored" not in lcpcols:   # đã seed / bảng fresh → thôi
        conn.commit(); conn.close(); return
    cwv = {(r["url"], r["strategy"]): r for r in conn.execute(
        "SELECT url, strategy, scanned_at, fcp_ms, tbt_ms, performance_score FROM seo_cwv").fetchall()}
    ins = ("INSERT INTO seo_cwv_lcp_runs (url,strategy,page_type,scanned_at,lcp,fcp,tbt,ttfb,"
           "performance_score,primary_opportunity,opportunity_saving_ms,lcp_element,lcp_asset_url,source) "
           "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
    for r in conn.execute("""SELECT url, strategy, page_type, lcp_lab_stored, lcp_lab_fresh,
                                    fcp, tbt, ttfb, primary_opportunity, opportunity_saving_ms,
                                    lcp_element, lcp_asset_url, lab_scanned_at FROM seo_cwv_lcp""").fetchall():
        d = dict(r); c = cwv.get((d["url"], d["strategy"]))
        if d["lcp_lab_stored"] is not None:   # Run A — đo từ seo_cwv chain
            conn.execute(ins, (d["url"], d["strategy"], d["page_type"],
                (c["scanned_at"] if c else None), d["lcp_lab_stored"],
                (c["fcp_ms"] if c else None), (c["tbt_ms"] if c else None), None,
                (c["performance_score"] if c else None), None, None, None, None, "legacy:cwv_scan"))
        if d["lcp_lab_fresh"] is not None:    # Run B — lần re-đo P0A
            conn.execute(ins, (d["url"], d["strategy"], d["page_type"], d["lab_scanned_at"],
                d["lcp_lab_fresh"], d["fcp"], d["tbt"], d["ttfb"], None, d["primary_opportunity"],
                d["opportunity_saving_ms"], d["lcp_element"], d["lcp_asset_url"], "legacy:p0a_enrich"))
    conn.commit()
    for k in conn.execute("SELECT DISTINCT url, strategy FROM seo_cwv_lcp_runs").fetchall():
        lcps = [x[0] for x in conn.execute(
            "SELECT lcp FROM seo_cwv_lcp_runs WHERE url=? AND strategy=? AND lcp IS NOT NULL "
            "ORDER BY scanned_at DESC, id DESC", (k["url"], k["strategy"])).fetchall()]
        if lcps:
            conn.execute("UPDATE seo_cwv_lcp SET lab_run_count=?, lab_lcp_latest=?, lab_lcp_median=? "
                         "WHERE url=? AND strategy=?",
                         (len(lcps), lcps[0], round(statistics.median(lcps[:3])), k["url"], k["strategy"]))
    conn.commit()
    conn.close()


def cwv_lcp_record_run(d: dict):
    """Ghi 1 lần đo enrich vào seo_cwv_lcp_runs + cập nhật summary seo_cwv_lcp (canonical).
    lab_lcp_latest = lần mới nhất · lab_lcp_median = median 3 lần gần nhất · lab_run_count = tổng số lần.
    Không phụ thuộc backfill — script gọi hàm này cho mỗi URL."""
    import statistics
    conn = get_conn()
    conn.execute("""
        INSERT INTO seo_cwv_lcp_runs
            (url, strategy, page_type, scanned_at, lcp, fcp, tbt, ttfb, performance_score,
             primary_opportunity, opportunity_saving_ms, lcp_element, lcp_asset_url)
        VALUES (:url,:strategy,:page_type,:scanned_at,:lcp,:fcp,:tbt,:ttfb,:performance_score,
             :primary_opportunity,:opportunity_saving_ms,:lcp_element,:lcp_asset_url)
    """, d)
    # tính lại từ lịch sử (mới nhất theo THỜI GIAN đo, không theo id chèn)
    runs = conn.execute(
        "SELECT lcp FROM seo_cwv_lcp_runs WHERE url=? AND strategy=? AND lcp IS NOT NULL "
        "ORDER BY scanned_at DESC, id DESC",
        (d["url"], d["strategy"])).fetchall()
    lcps = [r[0] for r in runs]
    run_count = len(lcps)
    latest = lcps[0] if lcps else None
    median = round(statistics.median(lcps[:3])) if lcps else None   # median 3 lần gần nhất
    conn.execute("""
        INSERT INTO seo_cwv_lcp
            (url, strategy, page_type, lcp_element, lab_lcp_latest, lab_lcp_median, lab_run_count,
             lab_scanned_at, field_lcp_p75, field_scope, field_source, field_category,
             fcp, tbt, ttfb, primary_opportunity, opportunity_saving_ms, lcp_asset_url)
        VALUES (:url,:strategy,:page_type,:lcp_element,:lab_lcp_latest,:lab_lcp_median,:lab_run_count,
             :scanned_at,:field_lcp_p75,:field_scope,:field_source,:field_category,
             :fcp,:tbt,:ttfb,:primary_opportunity,:opportunity_saving_ms,:lcp_asset_url)
        ON CONFLICT(url, strategy) DO UPDATE SET
            page_type=excluded.page_type, lcp_element=excluded.lcp_element,
            lab_lcp_latest=excluded.lab_lcp_latest, lab_lcp_median=excluded.lab_lcp_median,
            lab_run_count=excluded.lab_run_count, lab_scanned_at=excluded.lab_scanned_at,
            field_lcp_p75=excluded.field_lcp_p75, field_scope=excluded.field_scope,
            field_source=excluded.field_source, field_category=excluded.field_category,
            fcp=excluded.fcp, tbt=excluded.tbt, ttfb=excluded.ttfb,
            primary_opportunity=excluded.primary_opportunity,
            opportunity_saving_ms=excluded.opportunity_saving_ms, lcp_asset_url=excluded.lcp_asset_url
    """, {**d, "lab_lcp_latest": latest, "lab_lcp_median": median, "lab_run_count": run_count})
    conn.commit()
    conn.close()
    return {"run_count": run_count, "latest": latest, "median": median}


def _cwv_lcp_backfill_canon():
    """Map cột cũ (P0A) → cột canonical cho các dòng đã có. Chỉ ghi khi canonical còn NULL."""
    import statistics
    conn = get_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(seo_cwv_lcp)").fetchall()}
    if "lcp_lab_stored" not in cols:   # bảng đã canonical sẵn (fresh) → khỏi backfill
        conn.close()
        return
    pending = conn.execute("SELECT COUNT(*) FROM seo_cwv_lcp "
                           "WHERE lab_lcp_median IS NULL AND lcp_lab_stored IS NOT NULL").fetchone()[0]
    if pending == 0:                   # không còn dòng cần backfill → thoát sớm (rẻ khi page load)
        conn.close()
        return
    # overall_category field từ seo_cwv (origin CrUX) để suy field_category
    catmap = {}
    for r in conn.execute("SELECT url, strategy, overall_category FROM seo_cwv").fetchall():
        catmap[(r["url"], r["strategy"])] = r["overall_category"]
    rows = conn.execute("""SELECT url, strategy, lcp_lab_stored, lcp_lab_fresh, lcp_field_ms,
                                  fcp_ms, tbt_ms, ttfb_ms, top_opp, top_opp_ms, lcp_asset, captured_at,
                                  lab_lcp_median
                           FROM seo_cwv_lcp""").fetchall()
    for r in rows:
        d = dict(r)
        if d.get("lab_lcp_median") is not None:   # đã backfill rồi
            continue
        runs = [v for v in (d["lcp_lab_stored"], d["lcp_lab_fresh"]) if v is not None]
        latest = d["lcp_lab_fresh"] if d["lcp_lab_fresh"] is not None else d["lcp_lab_stored"]
        median = round(statistics.median(runs)) if runs else None
        fp75 = d["lcp_field_ms"]
        if fp75 is not None:
            scope, source = "origin", "originLoadingExperience"   # đã chứng minh field = origin-level
        else:
            scope, source = "none", "none"
        fcat = catmap.get((d["url"], d["strategy"])) or (
            "FAST" if (fp75 and fp75 <= 2500) else "AVERAGE" if (fp75 and fp75 <= 4000) else "SLOW" if fp75 else "none")
        conn.execute("""UPDATE seo_cwv_lcp SET
            lab_lcp_latest=?, lab_lcp_median=?, lab_run_count=?, lab_scanned_at=?,
            field_lcp_p75=?, field_scope=?, field_source=?, field_category=?,
            fcp=?, tbt=?, ttfb=?, primary_opportunity=?, opportunity_saving_ms=?, lcp_asset_url=?
            WHERE url=? AND strategy=?""",
            (latest, median, len(runs), d["captured_at"], fp75, scope, source, fcat,
             d["fcp_ms"], d["tbt_ms"], d["ttfb_ms"], d["top_opp"], d["top_opp_ms"], d["lcp_asset"],
             d["url"], d["strategy"]))
    conn.commit()
    conn.close()


def cwv_lcp_list(strategy="mobile", page_type=None, field_scope=None,
                 opportunity=None, limit=200):
    """Đọc top URL LCP tệ nhất từ seo_cwv_lcp — sort lab_lcp_median DESC. READ-ONLY."""
    conn = get_conn()
    sql = "SELECT * FROM seo_cwv_lcp WHERE strategy=?"
    args = [strategy]
    if page_type:
        sql += " AND page_type=?"; args.append(page_type)
    if field_scope:
        sql += " AND field_scope=?"; args.append(field_scope)
    if opportunity:
        sql += " AND primary_opportunity=?"; args.append(opportunity)
    sql += " ORDER BY lab_lcp_median DESC, lab_lcp_latest DESC LIMIT ?"
    args.append(limit)
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    conn.close()
    return rows


def cwv_lcp_filters(strategy="mobile"):
    """Giá trị cho dropdown filter (page_type, opportunity) theo strategy."""
    conn = get_conn()
    pts = [r[0] for r in conn.execute(
        "SELECT DISTINCT page_type FROM seo_cwv_lcp WHERE strategy=? AND page_type IS NOT NULL ORDER BY page_type",
        (strategy,)).fetchall()]
    opps = [r[0] for r in conn.execute(
        "SELECT DISTINCT primary_opportunity FROM seo_cwv_lcp WHERE strategy=? AND primary_opportunity IS NOT NULL "
        "AND primary_opportunity<>'' ORDER BY primary_opportunity", (strategy,)).fetchall()]
    conn.close()
    return {"page_types": pts, "opportunities": opps}


def cwv_lcp_summary(strategy="mobile"):
    """Summary cho UI: đếm field scope + lab kém theo page type (trong bảng seo_cwv_lcp)."""
    conn = get_conn()
    scope = {"url": 0, "origin": 0, "none": 0}
    for r in conn.execute("SELECT field_scope, COUNT(*) c FROM seo_cwv_lcp WHERE strategy=? GROUP BY field_scope",
                          (strategy,)).fetchall():
        scope[(r["field_scope"] or "none")] = r["c"]
    bad_by_type = {r["page_type"]: r["c"] for r in conn.execute(
        "SELECT page_type, COUNT(*) c FROM seo_cwv_lcp WHERE strategy=? GROUP BY page_type ORDER BY c DESC",
        (strategy,)).fetchall()}
    total = conn.execute("SELECT COUNT(*) FROM seo_cwv_lcp WHERE strategy=?", (strategy,)).fetchone()[0]
    last = conn.execute("SELECT MAX(lab_scanned_at) FROM seo_cwv_lcp WHERE strategy=?", (strategy,)).fetchone()[0]
    cwv_total = conn.execute("SELECT COUNT(*) FROM seo_cwv WHERE strategy=?", (strategy,)).fetchone()[0]
    low_conf = conn.execute("SELECT COUNT(*) FROM seo_cwv_lcp WHERE strategy=? AND COALESCE(lab_run_count,0)<3",
                            (strategy,)).fetchone()[0]
    conn.close()
    return {"field_url": scope.get("url", 0), "field_origin": scope.get("origin", 0),
            "field_none": scope.get("none", 0), "bad_by_type": bad_by_type,
            "total": total, "last_scanned": last, "cwv_total": cwv_total, "low_conf": low_conf}


def cwv_history_snapshot(week_no: int, year: int, snapshot_at: str = None,
                         replace: bool = False) -> int:
    """Copy toàn bộ seo_cwv hiện tại vào seo_cwv_history với tag (week_no, year).
    Return số row đã insert. Mặc định idempotent (tuần đã có → return 0).
    `replace=True`: xoá data tuần đó rồi snapshot lại (đợt quét mới đè điểm tuần cũ)."""
    if cwv_history_has_week(week_no, year):
        if not replace:
            return 0
        _c = get_conn()
        _c.execute("DELETE FROM seo_cwv_history WHERE week_no=? AND year=?", (week_no, year))
        _c.commit()
        _c.close()
    if not snapshot_at:
        snapshot_at = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    before = conn.execute("SELECT COUNT(*) FROM seo_cwv_history").fetchone()[0]
    conn.execute("""
        INSERT INTO seo_cwv_history
            (week_no, year, url, strategy, scanned_at, performance_score,
             lcp_ms, cls_score, tbt_ms, fcp_ms, tti_ms, speed_index_ms,
             field_data_ok, lcp_field_ms, cls_field, inp_field_ms, fcp_field_ms,
             overall_category, snapshot_at)
        SELECT
            ?, ?, url, strategy, scanned_at, performance_score,
            lcp_ms, cls_score, tbt_ms, fcp_ms, tti_ms, speed_index_ms,
            field_data_ok, lcp_field_ms, cls_field, inp_field_ms, fcp_field_ms,
            overall_category, ?
        FROM seo_cwv
    """, (week_no, year, snapshot_at))
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM seo_cwv_history").fetchone()[0]
    conn.close()
    return after - before


def cwv_history_timeline(limit: int = 52) -> dict:
    """Aggregate CWV history per (week_no, year, strategy) cho timeline chart.

    Return:
        {
          "labels": ["W21/2026", "W22/2026", ...],
          "mobile_avg": [71.8, 73.5, ...],
          "desktop_avg": [88.6, 89.7, ...],
          "mobile_lcp_ms": [3200, 3100, ...],
          "desktop_lcp_ms": [1800, 1750, ...],
          "url_count": [2486, 2486, ...],
        }
    """
    conn = get_conn()
    rows = conn.execute("""
        SELECT week_no, year, strategy,
               ROUND(AVG(performance_score), 1) avg_score,
               ROUND(AVG(lcp_ms), 0) avg_lcp,
               COUNT(*) n_urls
        FROM seo_cwv_history
        GROUP BY week_no, year, strategy
        ORDER BY year ASC, week_no ASC
    """).fetchall()
    conn.close()

    weeks = {}
    for r in rows:
        key = (r["year"], r["week_no"])
        if key not in weeks:
            weeks[key] = {"mobile_avg": None, "desktop_avg": None,
                          "mobile_lcp_ms": None, "desktop_lcp_ms": None,
                          "url_count": 0}
        s = r["strategy"]
        if s == "mobile":
            weeks[key]["mobile_avg"] = r["avg_score"]
            weeks[key]["mobile_lcp_ms"] = r["avg_lcp"]
        elif s == "desktop":
            weeks[key]["desktop_avg"] = r["avg_score"]
            weeks[key]["desktop_lcp_ms"] = r["avg_lcp"]
        weeks[key]["url_count"] = max(weeks[key]["url_count"], r["n_urls"])

    sorted_keys = sorted(weeks.keys())[-limit:]
    return {
        "labels": [f"W{w}/{y}" for (y, w) in sorted_keys],
        "mobile_avg": [weeks[k]["mobile_avg"] for k in sorted_keys],
        "desktop_avg": [weeks[k]["desktop_avg"] for k in sorted_keys],
        "mobile_lcp_ms": [weeks[k]["mobile_lcp_ms"] for k in sorted_keys],
        "desktop_lcp_ms": [weeks[k]["desktop_lcp_ms"] for k in sorted_keys],
        "url_count": [weeks[k]["url_count"] for k in sorted_keys],
    }


def cwv_history_get_week(week_no: int, year: int, strategy: str = "mobile") -> list:
    """Lấy lại snapshot 1 tuần để diff."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT url, performance_score, lcp_ms, cls_score, tbt_ms,
               fcp_ms, lcp_field_ms, cls_field, inp_field_ms, scanned_at, snapshot_at
        FROM seo_cwv_history
        WHERE week_no=? AND year=? AND strategy=?
    """, (week_no, year, strategy)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# Schema validator (Task 4 SEO Crawl Optimization) — JSON-LD audit
# ═══════════════════════════════════════════════════════════════════════════

def seo_schema_upsert(url: str, data: dict):
    """Update kết quả scan schema cho 1 URL vào seo_pages."""
    conn = get_conn()
    conn.execute("""
        UPDATE seo_pages
        SET schema_types=?, schema_count=?,
            schema_has_product=?, schema_has_faq=?, schema_has_article=?,
            schema_errors=?, schema_scanned_at=?
        WHERE url=?
    """, (
        data.get("schema_types"),
        data.get("schema_count", 0),
        1 if data.get("has_product") else 0,
        1 if data.get("has_faq") else 0,
        1 if data.get("has_article") else 0,
        data.get("schema_errors"),
        data.get("scanned_at"),
        url,
    ))
    conn.commit()
    conn.close()


def seo_schema_stats(url_type: str = None) -> dict:
    """Breakdown count + percent per schema type (Product/FAQ/Article)."""
    conn = get_conn()
    where = "WHERE status_code=200 AND indexable=1 AND schema_scanned_at IS NOT NULL"
    args = []
    if url_type:
        where += " AND url_type=?"
        args.append(url_type)
    row = conn.execute(f"""
        SELECT
            COUNT(*) total_audited,
            SUM(schema_has_product) has_product,
            SUM(schema_has_faq) has_faq,
            SUM(schema_has_article) has_article,
            SUM(CASE WHEN schema_count=0 THEN 1 ELSE 0 END) no_schema,
            SUM(CASE WHEN schema_errors IS NOT NULL AND schema_errors != '' AND schema_errors != '[]'
                THEN 1 ELSE 0 END) has_errors
        FROM seo_pages
        {where}
    """, args).fetchone()
    n_total = conn.execute(f"""
        SELECT COUNT(*) FROM seo_pages
        WHERE status_code=200 AND indexable=1
        {'AND url_type=?' if url_type else ''}
    """, args).fetchone()[0]
    conn.close()
    out = dict(row) if row else {}
    out["total_indexable"] = n_total
    out["audited_pct"] = round(100.0 * (out.get("total_audited", 0) or 0) / n_total, 1) if n_total else 0.0
    if out.get("total_audited"):
        t = out["total_audited"]
        out["pct_has_product"] = round(100.0 * (out.get("has_product") or 0) / t, 1)
        out["pct_has_faq"] = round(100.0 * (out.get("has_faq") or 0) / t, 1)
        out["pct_has_article"] = round(100.0 * (out.get("has_article") or 0) / t, 1)
        out["pct_no_schema"] = round(100.0 * (out.get("no_schema") or 0) / t, 1)
    return out


def seo_schema_list(url_type: str = None, missing: str = None, limit: int = 100,
                    offset: int = 0, only_audited: bool = True) -> list:
    """List URL với cột schema cho UI page /seo/schema, có filter + pagination."""
    conn = get_conn()
    sql = """SELECT id, url, url_type, title, status_code,
                    schema_types, schema_count, schema_has_product,
                    schema_has_faq, schema_has_article, schema_errors, schema_scanned_at
             FROM seo_pages
             WHERE status_code=200 AND indexable=1"""
    args = []
    if only_audited:
        sql += " AND schema_scanned_at IS NOT NULL"
    if url_type:
        sql += " AND url_type=?"
        args.append(url_type)
    if missing == "product":
        sql += " AND schema_has_product=0"
    elif missing == "faq":
        sql += " AND schema_has_faq=0"
    elif missing == "article":
        sql += " AND schema_has_article=0"
    elif missing == "itemlist":
        sql += " AND (schema_types IS NULL OR schema_types NOT LIKE '%ItemList%')"
    elif missing == "any":
        sql += " AND schema_count=0"
    elif missing == "errors":
        sql += " AND schema_errors IS NOT NULL AND schema_errors != '' AND schema_errors != '[]'"
    sql += " ORDER BY url_type, url LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seo_schema_count(url_type: str = None, missing: str = None,
                     only_audited: bool = True) -> int:
    """Đếm tổng URL match filter (cho pagination)."""
    conn = get_conn()
    sql = "SELECT COUNT(*) FROM seo_pages WHERE status_code=200 AND indexable=1"
    args = []
    if only_audited:
        sql += " AND schema_scanned_at IS NOT NULL"
    if url_type:
        sql += " AND url_type=?"
        args.append(url_type)
    if missing == "product":
        sql += " AND schema_has_product=0"
    elif missing == "faq":
        sql += " AND schema_has_faq=0"
    elif missing == "article":
        sql += " AND schema_has_article=0"
    elif missing == "itemlist":
        sql += " AND (schema_types IS NULL OR schema_types NOT LIKE '%ItemList%')"
    elif missing == "any":
        sql += " AND schema_count=0"
    elif missing == "errors":
        sql += " AND schema_errors IS NOT NULL AND schema_errors != '' AND schema_errors != '[]'"
    n = conn.execute(sql, args).fetchone()[0]
    conn.close()
    return n


def seo_schema_history_capture(week_no: int = None, year: int = None,
                               captured_at: str = None) -> int:
    """Snapshot trạng thái schema audit hiện tại vào seo_schema_history.
    Idempotent: nếu (week_no, year) đã có row → UPDATE thay vì INSERT.
    Default week_no/year = ISO tuần hiện tại.
    Return id row (insert hoặc update).
    """
    if week_no is None or year is None:
        iso = datetime.now().isocalendar()
        week_no = week_no if week_no is not None else iso.week
        year = year if year is not None else iso.year
    if not captured_at:
        captured_at = datetime.now().isoformat(timespec="seconds")

    sp = seo_schema_stats(url_type="product")
    bl = seo_schema_stats(url_type="blog")
    col = seo_schema_stats(url_type="collection")

    conn = get_conn()
    col_missing_itemlist = conn.execute("""
        SELECT COUNT(*) FROM seo_pages
        WHERE url_type='collection' AND status_code=200 AND indexable=1
        AND schema_scanned_at IS NOT NULL
        AND schema_types IS NOT NULL AND schema_types LIKE '%ItemList%'
    """).fetchone()[0]

    total_audited = (sp.get("total_audited") or 0) + (bl.get("total_audited") or 0) + (col.get("total_audited") or 0)
    payload = {
        "week_no": week_no, "year": year, "captured_at": captured_at,
        "total_audited": total_audited,
        "sp_total": sp.get("total_audited") or 0,
        "sp_has_product": sp.get("has_product") or 0,
        "blog_total": bl.get("total_audited") or 0,
        "blog_has_article": bl.get("has_article") or 0,
        "blog_has_faq": bl.get("has_faq") or 0,
        "col_total": col.get("total_audited") or 0,
        "col_has_itemlist": col_missing_itemlist,
    }

    existing = conn.execute(
        "SELECT id FROM seo_schema_history WHERE week_no=? AND year=?",
        (week_no, year),
    ).fetchone()
    if existing:
        conn.execute("""
            UPDATE seo_schema_history SET
                captured_at=:captured_at, total_audited=:total_audited,
                sp_total=:sp_total, sp_has_product=:sp_has_product,
                blog_total=:blog_total, blog_has_article=:blog_has_article,
                blog_has_faq=:blog_has_faq,
                col_total=:col_total, col_has_itemlist=:col_has_itemlist
            WHERE week_no=:week_no AND year=:year
        """, payload)
        rid = existing["id"]
    else:
        cur = conn.execute("""
            INSERT INTO seo_schema_history
                (week_no, year, captured_at, total_audited,
                 sp_total, sp_has_product,
                 blog_total, blog_has_article, blog_has_faq,
                 col_total, col_has_itemlist)
            VALUES
                (:week_no, :year, :captured_at, :total_audited,
                 :sp_total, :sp_has_product,
                 :blog_total, :blog_has_article, :blog_has_faq,
                 :col_total, :col_has_itemlist)
        """, payload)
        rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def seo_schema_history_timeline(limit: int = 52) -> dict:
    """Output dict chuẩn Chart.js cho timeline schema coverage per tuần."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT week_no, year, total_audited,
               sp_total, sp_has_product,
               blog_total, blog_has_article, blog_has_faq,
               col_total, col_has_itemlist
        FROM seo_schema_history
        ORDER BY year ASC, week_no ASC
    """).fetchall()
    conn.close()
    items = [dict(r) for r in rows][-limit:]

    def pct(n, d):
        return round(100.0 * (n or 0) / d, 1) if d else 0.0

    return {
        "labels": [f"W{r['week_no']}/{r['year']}" for r in items],
        "sp_pct_product": [pct(r["sp_has_product"], r["sp_total"]) for r in items],
        "blog_pct_faq": [pct(r["blog_has_faq"], r["blog_total"]) for r in items],
        "blog_pct_article": [pct(r["blog_has_article"], r["blog_total"]) for r in items],
        "col_pct_itemlist": [pct(r["col_has_itemlist"], r["col_total"]) for r in items],
        "total_audited": [r["total_audited"] for r in items],
    }


def seo_schema_missing(missing: str = "product", url_type: str = None, limit: int = 500) -> list:
    """List URL thiếu schema priority (Product cho SP, Article cho blog, FAQ cho cả 2).
    `missing` = 'product' | 'faq' | 'article' | 'any' (any = schema_count=0).
    """
    conn = get_conn()
    sql = """SELECT url, url_type, title, schema_types, schema_count, schema_scanned_at
             FROM seo_pages
             WHERE status_code=200 AND indexable=1 AND schema_scanned_at IS NOT NULL"""
    args = []
    if missing == "product":
        sql += " AND schema_has_product=0"
    elif missing == "faq":
        sql += " AND schema_has_faq=0"
    elif missing == "article":
        sql += " AND schema_has_article=0"
    elif missing == "any":
        sql += " AND schema_count=0"
    if url_type:
        sql += " AND url_type=?"
        args.append(url_type)
    sql += " ORDER BY url_type, url LIMIT ?"
    args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────── Collection → Product map (phân tầng /seo/title-meta) ───────────

def collection_products_replace(collection_handle: str, products: list, synced_at: str = None):
    """Xóa + ghi lại toàn bộ SP của 1 collection. products = list dict Haravan
    (cần id; handle/title optional). Idempotent per collection."""
    if synced_at is None:
        synced_at = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    conn.execute("DELETE FROM collection_products WHERE collection_handle=?", (collection_handle,))
    rows = []
    for p in products:
        pid = p.get("id")
        if pid is None:
            continue
        h = p.get("handle")
        url = f"https://sintech.vn/products/{h}" if h else None
        rows.append((collection_handle, pid, h, p.get("title"), url, synced_at))
    if rows:
        conn.executemany(
            "INSERT OR REPLACE INTO collection_products "
            "(collection_handle, product_id, product_handle, product_title, product_url, synced_at) "
            "VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    return len(rows)


def collection_products_urls(handles) -> set:
    """Set product_url (distinct) thuộc bất kỳ collection nào trong `handles`."""
    handles = [h for h in (handles or []) if h]
    if not handles:
        return set()
    conn = get_conn()
    ph = ",".join("?" * len(handles))
    rows = conn.execute(
        f"SELECT DISTINCT product_url FROM collection_products "
        f"WHERE collection_handle IN ({ph}) AND product_url IS NOT NULL", handles).fetchall()
    conn.close()
    return {r["product_url"] for r in rows}


def collection_products_rows(handles) -> list:
    """List dict {product_url, product_handle, product_title} distinct cho handles."""
    handles = [h for h in (handles or []) if h]
    if not handles:
        return []
    conn = get_conn()
    ph = ",".join("?" * len(handles))
    rows = conn.execute(
        f"SELECT product_url, MAX(product_handle) handle, MAX(product_title) title "
        f"FROM collection_products WHERE collection_handle IN ({ph}) AND product_url IS NOT NULL "
        f"GROUP BY product_url", handles).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def collection_products_handle_counts() -> dict:
    """handle → số SP đã sync."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT collection_handle, COUNT(*) n FROM collection_products GROUP BY collection_handle").fetchall()
    conn.close()
    return {r["collection_handle"]: r["n"] for r in rows}


def collection_products_stats() -> dict:
    conn = get_conn()
    r = conn.execute(
        "SELECT COUNT(DISTINCT collection_handle) n_col, COUNT(*) n_rows, "
        "COUNT(DISTINCT product_url) n_products, MAX(synced_at) last_sync "
        "FROM collection_products").fetchone()
    conn.close()
    return {"collections": r["n_col"] or 0, "rows": r["n_rows"] or 0,
            "products": r["n_products"] or 0, "last_sync": r["last_sync"]}


def seo_pages_by_urls(urls) -> dict:
    """url → dict (cột title/meta/score/issues...) cho danh sách urls. Phục vụ
    chế độ 'xem tất cả SP' (kể cả SP không có lỗi title/meta)."""
    urls = [u for u in (urls or []) if u]
    if not urls:
        return {}
    conn = get_conn()
    out = {}
    CH = 400
    for i in range(0, len(urls), CH):
        chunk = urls[i:i + CH]
        ph = ",".join("?" * len(chunk))
        rows = conn.execute(
            f"SELECT id, url, url_type, title, title_len, meta_desc, meta_desc_len, "
            f"score, issues, last_crawled FROM seo_pages WHERE url IN ({ph})", chunk).fetchall()
        for r in rows:
            out[r["url"]] = dict(r)
    conn.close()
    return out
