# -*- coding: utf-8 -*-
"""Blog Rewrite AI — P1 import service (read-only, local DB).

Fetch 233 bài blog Haravan (Open API) → classify dấu hiệu copy → dedup theo
article_id → join traffic GSC/GA4 (DB local) → priority score → upsert candidate.

KHÔNG gọi AI. KHÔNG PUT Haravan. KHÔNG upload ảnh. Chỉ ghi SQLite local.
"""
import json, re, hashlib, math, time, urllib3
from pathlib import Path
from urllib.parse import urlparse
import requests
import db

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_CFG = json.loads((Path(__file__).parent.parent / "state" / "haravan_token.json").read_text(encoding="utf-8"))
_TOK = _CFG.get("blog_access_token")
_BASE = _CFG.get("open_api_base", "https://apis.haravan.com/web")
_BLOG_IDS = _CFG.get("blog_ids", {})          # {"news": id, "huong-dan": id}
_BLOG_NAME_BY_ID = {v: k for k, v in _BLOG_IDS.items()}

PROMPT_VERSION = "BLOG_REWRITE_PROMPT_V1"

# ─── host classification (đồng bộ scan_blog_plagiarism) ───
_OWN = ("hstatic.net", "sintech.vn", "myharavan", "haravan")
_COMP_CDN = ("fptshop", "tgdd", "cellphones", "hacom", "anphat", "phongvu", "hoangha",
             "memoryzone", "gearvn", "didongviet", "phucanh", "nguyenkim", "maytinhcdc")
_VN_NEWS = ("genk.mediacdn", "quantrimang", "tinhte", "sohoa.vnecdn", "thanhnien",
            "channel.mediacdn", "motgame", "canhrau", "trainghiemso", "speedcom",
            "longhungpc", "news.khangz", "kenh14", "cafef", "vnreview", "sforum")
_FOREIGN = ("futurecdn", "wccftech", "pcworld", "makeuseof", "drivereasy", "insider",
            "pcmag", "notebookcheck", "techcrunch", "yankodesign", "cointelegraph",
            "uaetechnician", "cleverfiles", "wondershare", "speedefy", "squarespace",
            "redd.it", "evga", "istockphoto")
_LEGIT = ("googleusercontent", "wikimedia", "ggpht", "ytimg", "youtube")

_GROUP_RISK = {
    "competitor_cdn": "high", "bizweb_sapo": "high",
    "vn_tech_media": "high", "foreign_tech_media": "high",
    "google_docs_youtube": "medium", "strange_host": "review", "text_only": "unknown",
}
_RISK_WEIGHT = {"high": 100, "medium": 40, "review": 20, "unknown": 10}


def _host(u):
    try:
        return (urlparse(u).hostname or "").lower()
    except Exception:
        return ""


def _classify(body_html):
    """Trả (group_primary, groups_all, hosts, evidence)."""
    hosts = set()
    for src in re.findall(r'<img[^>]+src="([^"]+)"', body_html or "", re.I):
        h = _host(src)
        if h and not any(o in h for o in _OWN):
            hosts.add(h)
    groups = []
    if any(any(k in h for k in _COMP_CDN) for h in hosts):
        groups.append("competitor_cdn")
    if any("dktcdn" in h for h in hosts):
        groups.append("bizweb_sapo")
    if any(any(k in h for k in _VN_NEWS) for h in hosts):
        groups.append("vn_tech_media")
    if any(any(k in h for k in _FOREIGN) for h in hosts):
        groups.append("foreign_tech_media")
    if not groups and hosts and all(any(k in h for k in _LEGIT) for h in hosts):
        groups.append("google_docs_youtube")
    if not groups and hosts:
        groups.append("strange_host")
    if not hosts:
        groups.append("text_only")
    # ưu tiên nhóm risk cao nhất
    order = ["competitor_cdn", "bizweb_sapo", "vn_tech_media", "foreign_tech_media",
             "google_docs_youtube", "strange_host", "text_only"]
    primary = min(groups, key=lambda g: order.index(g))
    evidence = {"image_external_hosts": sorted(hosts)}
    return primary, groups, sorted(hosts), evidence


def _content_hash(body_html):
    norm = re.sub(r"\s+", " ", (body_html or "")).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _fetch_all_articles():
    if not _TOK:
        raise RuntimeError("Thiếu blog_access_token trong state/haravan_token.json")
    H = {"Authorization": f"Bearer {_TOK}", "Accept": "application/json"}
    arts = []
    for name, bid in _BLOG_IDS.items():
        page = 1
        while True:
            r = requests.get(f"{_BASE}/blogs/{bid}/articles.json", headers=H,
                             params={"limit": 250, "page": page}, verify=False, timeout=40)
            if r.status_code != 200:
                break
            chunk = r.json().get("articles", [])
            if not chunk:
                break
            for a in chunk:
                a["_blog_name"] = name
            arts += chunk
            if len(chunk) < 250:
                break
            page += 1
    return arts


def _traffic_for_path(conn, path):
    """Tổng GSC clicks/impr + AVG position + GA4 organic sessions, cửa sổ 28 ngày
    (dùng data sẵn có trong gsc_ga4_join_daily — read-only)."""
    row = conn.execute(
        """SELECT COALESCE(SUM(gsc_clicks),0), COALESCE(SUM(gsc_impressions),0),
                  AVG(gsc_position), COALESCE(SUM(ga4_organic_sessions),0)
           FROM gsc_ga4_join_daily
           WHERE normalized_path = ? AND date >= date('now','-28 day')""",
        (path,)).fetchone()
    return (row[0] or 0, row[1] or 0, row[2], row[3] or 0)


def _priority(risk_level, clicks, impr, sessions):
    base = _RISK_WEIGHT.get(risk_level, 10)
    bonus = 10 * math.log10(1 + clicks) + 3 * math.log10(1 + impr) + 8 * math.log10(1 + sessions)
    return round(base + bonus, 2)


def build_candidates(dry_run=True):
    """Fetch + classify + traffic + priority. dry_run=True → KHÔNG ghi DB, trả summary."""
    arts = _fetch_all_articles()
    conn = db.get_conn()
    rows = []
    for a in arts:
        body = a.get("body_html") or ""
        primary, groups, hosts, evidence = _classify(body)
        risk = _GROUP_RISK.get(primary, "unknown")
        blog_name = a.get("_blog_name") or _BLOG_NAME_BY_ID.get(a.get("blog_id"), "news")
        url = f"https://sintech.vn/blogs/{blog_name}/{a.get('handle')}"
        path = f"/blogs/{blog_name}/{a.get('handle')}"
        clicks, impr, pos, sessions = _traffic_for_path(conn, path)
        rows.append({
            "article_id": a.get("id"), "blog_id": a.get("blog_id"),
            "handle": a.get("handle"), "article_url": url, "title": a.get("title", ""),
            "author": a.get("author", ""), "published_year": (a.get("published_at") or "")[:4],
            "source_group_primary": primary, "source_groups_json": json.dumps(groups, ensure_ascii=False),
            "risk_level": risk, "risk_reason": f"image_external_hosts={','.join(hosts[:4])}" if hosts else "no_external_image",
            "source_hosts_json": json.dumps(hosts, ensure_ascii=False),
            "source_evidence_json": json.dumps(evidence, ensure_ascii=False),
            "scan_source": "haravan_open_api_live",
            "gsc_clicks_28d": clicks, "gsc_impressions_28d": impr,
            "gsc_position_28d": round(pos, 2) if pos else None,
            "ga4_organic_sessions_28d": sessions,
            "traffic_data_status": "has_data" if (clicks or impr or sessions) else "no_traffic_data",
            "priority_score": _priority(risk, clicks, impr, sessions),
            "content_hash": _content_hash(body),
            "live_updated_at": a.get("updated_at"),
            "selected_default": 1 if risk == "high" else 0,
        })
    conn.close()
    from collections import Counter
    summary = {
        "raw_rows": len(arts), "dedup_candidates": len(rows),
        "by_risk": dict(Counter(r["risk_level"] for r in rows)),
        "by_group": dict(Counter(r["source_group_primary"] for r in rows)),
        "selected_default": sum(r["selected_default"] for r in rows),
        "gsc_matched": sum(1 for r in rows if r["gsc_clicks_28d"] or r["gsc_impressions_28d"]),
        "ga4_matched": sum(1 for r in rows if r["ga4_organic_sessions_28d"]),
        "no_traffic_data": sum(1 for r in rows if r["traffic_data_status"] == "no_traffic_data"),
        "dry_run": dry_run,
    }
    if not dry_run:
        _upsert(rows)
    return {"summary": summary, "rows_preview": rows[:5] if dry_run else None}


_PROTECTED_STATUS = ("queued", "generating", "draft_ready", "review_required",
                     "approved", "applying", "applied", "rejected", "conflict", "rolled_back")


def _upsert(rows):
    conn = db.get_conn()
    try:
        for r in rows:
            ex = conn.execute("SELECT id, status, selected FROM blog_rewrite_candidates WHERE article_id=?",
                              (r["article_id"],)).fetchone()
            if ex:
                # idempotent: cập nhật classification + traffic, GIỮ status/selected nếu đã tiến triển
                keep_status = ex["status"] if ex["status"] in _PROTECTED_STATUS else "imported"
                keep_selected = ex["selected"] if ex["status"] in _PROTECTED_STATUS else r["selected_default"]
                conn.execute("""UPDATE blog_rewrite_candidates SET
                    blog_id=?, handle=?, article_url=?, title=?, author=?, published_year=?,
                    source_group_primary=?, source_groups_json=?, risk_level=?, risk_reason=?,
                    source_hosts_json=?, source_evidence_json=?, scan_source=?,
                    gsc_clicks_28d=?, gsc_impressions_28d=?, gsc_position_28d=?, ga4_organic_sessions_28d=?,
                    traffic_data_status=?, priority_score=?, content_hash=?, live_updated_at=?,
                    status=?, selected=?, updated_at=datetime('now') WHERE article_id=?""",
                    (r["blog_id"], r["handle"], r["article_url"], r["title"], r["author"], r["published_year"],
                     r["source_group_primary"], r["source_groups_json"], r["risk_level"], r["risk_reason"],
                     r["source_hosts_json"], r["source_evidence_json"], r["scan_source"],
                     r["gsc_clicks_28d"], r["gsc_impressions_28d"], r["gsc_position_28d"], r["ga4_organic_sessions_28d"],
                     r["traffic_data_status"], r["priority_score"], r["content_hash"], r["live_updated_at"],
                     keep_status, keep_selected, r["article_id"]))
            else:
                conn.execute("""INSERT INTO blog_rewrite_candidates
                    (article_id, blog_id, handle, article_url, title, author, published_year,
                     source_group_primary, source_groups_json, risk_level, risk_reason,
                     source_hosts_json, source_evidence_json, scan_source,
                     gsc_clicks_28d, gsc_impressions_28d, gsc_position_28d, ga4_organic_sessions_28d,
                     traffic_data_status, priority_score, content_hash, live_updated_at, status, selected)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (r["article_id"], r["blog_id"], r["handle"], r["article_url"], r["title"], r["author"], r["published_year"],
                     r["source_group_primary"], r["source_groups_json"], r["risk_level"], r["risk_reason"],
                     r["source_hosts_json"], r["source_evidence_json"], r["scan_source"],
                     r["gsc_clicks_28d"], r["gsc_impressions_28d"], r["gsc_position_28d"], r["ga4_organic_sessions_28d"],
                     r["traffic_data_status"], r["priority_score"], r["content_hash"], r["live_updated_at"],
                     "imported", r["selected_default"]))
                conn.execute("INSERT INTO blog_rewrite_events (candidate_id, event_type, detail_json) "
                             "VALUES ((SELECT id FROM blog_rewrite_candidates WHERE article_id=?), 'imported', ?)",
                             (r["article_id"], json.dumps({"risk": r["risk_level"]}, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


# ─────────────── query helpers cho API read-only ───────────────
_SORTABLE = {"priority_score", "gsc_clicks_28d", "gsc_impressions_28d",
             "ga4_organic_sessions_28d", "risk_level", "status", "updated_at"}


def list_candidates(risk=None, status=None, source_host=None, traffic=None,
                    q=None, only_selected=False, sort="priority_score",
                    direction="desc", limit=100, offset=0):
    conn = db.get_conn()
    where, args = ["1=1"], []
    if risk:
        where.append("risk_level=?"); args.append(risk)
    if status:
        where.append("status=?"); args.append(status)
    if source_host:
        where.append("source_hosts_json LIKE ?"); args.append(f"%{source_host}%")
    if traffic == "has_data":
        where.append("traffic_data_status='has_data'")
    elif traffic == "no_traffic_data":
        where.append("traffic_data_status='no_traffic_data'")
    if q:
        where.append("(title LIKE ? OR article_url LIKE ?)"); args += [f"%{q}%", f"%{q}%"]
    if only_selected:
        where.append("selected=1")
    sort = sort if sort in _SORTABLE else "priority_score"
    direction = "ASC" if str(direction).lower() == "asc" else "DESC"
    total = conn.execute(f"SELECT COUNT(*) FROM blog_rewrite_candidates WHERE {' AND '.join(where)}", args).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM blog_rewrite_candidates WHERE {' AND '.join(where)} "
        f"ORDER BY {sort} {direction}, id DESC LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
    conn.close()
    return {"total": total, "items": [dict(r) for r in rows], "limit": limit, "offset": offset}


def get_candidate(cid):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM blog_rewrite_candidates WHERE id=?", (cid,)).fetchone()
    ev = conn.execute("SELECT event_type, detail_json, created_at FROM blog_rewrite_events "
                      "WHERE candidate_id=? ORDER BY id DESC LIMIT 20", (cid,)).fetchall()
    conn.close()
    if not r:
        return None
    d = dict(r)
    d["events"] = [dict(e) for e in ev]
    return d


def status_summary():
    conn = db.get_conn()
    def one(sql, *a):
        return conn.execute(sql, a).fetchone()[0]
    s = {
        "total": one("SELECT COUNT(*) FROM blog_rewrite_candidates"),
        "high": one("SELECT COUNT(*) FROM blog_rewrite_candidates WHERE risk_level='high'"),
        "medium": one("SELECT COUNT(*) FROM blog_rewrite_candidates WHERE risk_level='medium'"),
        "review": one("SELECT COUNT(*) FROM blog_rewrite_candidates WHERE risk_level='review'"),
        "unknown": one("SELECT COUNT(*) FROM blog_rewrite_candidates WHERE risk_level='unknown'"),
        "selected": one("SELECT COUNT(*) FROM blog_rewrite_candidates WHERE selected=1"),
        "has_traffic": one("SELECT COUNT(*) FROM blog_rewrite_candidates WHERE traffic_data_status='has_data'"),
        "no_traffic": one("SELECT COUNT(*) FROM blog_rewrite_candidates WHERE traffic_data_status='no_traffic_data'"),
        "prompt_version": PROMPT_VERSION,
    }
    conn.close()
    return s


# ═══════════════════════ P2 — SELECTION ═══════════════════════
MAX_AUTO_BATCH = 20  # >20 cần explicit_confirm


def set_selected(cid, selected):
    conn = db.get_conn()
    conn.execute("UPDATE blog_rewrite_candidates SET selected=?, updated_at=datetime('now') WHERE id=?",
                 (1 if selected else 0, cid))
    conn.commit(); conn.close()
    return True


def bulk_select(mode, limit=5, risk="high", ids=None):
    """mode: select_page | unselect_page | top_priority | clear_all | explicit_ids."""
    conn = db.get_conn()
    try:
        if mode == "clear_all":
            conn.execute("UPDATE blog_rewrite_candidates SET selected=0, updated_at=datetime('now')")
        elif mode in ("select_page", "unselect_page", "explicit_ids") and ids:
            val = 0 if mode == "unselect_page" else 1
            q = ",".join("?" * len(ids))
            conn.execute(f"UPDATE blog_rewrite_candidates SET selected=?, updated_at=datetime('now') WHERE id IN ({q})",
                         [val] + list(ids))
        elif mode == "top_priority":
            where = "risk_level=?" if risk else "1=1"
            args = [risk] if risk else []
            rows = conn.execute(f"SELECT id FROM blog_rewrite_candidates WHERE {where} "
                                f"ORDER BY priority_score DESC, id DESC LIMIT ?", args + [int(limit)]).fetchall()
            sel = [r[0] for r in rows]
            if sel:
                q = ",".join("?" * len(sel))
                conn.execute(f"UPDATE blog_rewrite_candidates SET selected=1, updated_at=datetime('now') WHERE id IN ({q})", sel)
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM blog_rewrite_candidates WHERE selected=1").fetchone()[0]
        return {"ok": True, "selected_total": n}
    finally:
        conn.close()


def selected_ids():
    conn = db.get_conn()
    rows = conn.execute("SELECT id FROM blog_rewrite_candidates WHERE selected=1 ORDER BY priority_score DESC").fetchall()
    conn.close()
    return [r[0] for r in rows]


def _set_candidate_status(cid, status):
    conn = db.get_conn()
    conn.execute("UPDATE blog_rewrite_candidates SET status=?, updated_at=datetime('now') WHERE id=?", (status, cid))
    conn.commit(); conn.close()


# ═══════════════════════ P2 — EVENTS ═══════════════════════
def record_event(event_type, candidate_id=None, draft_id=None, job_id=None, detail=None):
    conn = db.get_conn()
    conn.execute("INSERT INTO blog_rewrite_events (candidate_id, draft_id, job_id, event_type, detail_json) "
                 "VALUES (?,?,?,?,?)",
                 (candidate_id, draft_id, job_id, event_type,
                  json.dumps(detail or {}, ensure_ascii=False)))
    conn.commit(); conn.close()


def candidate_events(cid):
    conn = db.get_conn()
    rows = conn.execute("SELECT event_type, detail_json, created_at FROM blog_rewrite_events "
                        "WHERE candidate_id=? ORDER BY id DESC LIMIT 50", (cid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ═══════════════════════ P2 — JOBS (mock) ═══════════════════════
JOB_ACTIVE = ("queued", "running", "cancel_requested")


def create_job(candidate_ids, mode="selected", explicit_confirm=False):
    ids = [int(x) for x in (candidate_ids or [])]
    if not ids:
        return {"ok": False, "error": "Không có candidate nào được chọn."}
    if len(ids) > MAX_AUTO_BATCH and not explicit_confirm:
        return {"ok": False, "error": f"Chọn {len(ids)} bài (>{MAX_AUTO_BATCH}). Cần explicit_confirm=true.",
                "needs_confirm": True, "count": len(ids)}
    conn = db.get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO blog_rewrite_jobs (mode, status, candidate_count, provider, model, prompt_version, "
            "started_at, last_heartbeat_at) VALUES (?,?,?,?,?,?,NULL,NULL)",
            (mode, "queued", len(ids), "mock", "mock-blog-rewriter-v1", "BLOG_REWRITE_MOCK_V1"))
        job_id = cur.lastrowid
        q = ",".join("?" * len(ids))
        conn.execute(f"UPDATE blog_rewrite_candidates SET status='queued', updated_at=datetime('now') WHERE id IN ({q})", ids)
        for cid in ids:
            conn.execute("INSERT INTO blog_rewrite_events (candidate_id, job_id, event_type, detail_json) "
                         "VALUES (?,?,?,?)", (cid, job_id, "queued", json.dumps({"mode": mode}, ensure_ascii=False)))
        conn.execute("INSERT INTO blog_rewrite_events (job_id, event_type, detail_json) VALUES (?,?,?)",
                     (job_id, "job_created", json.dumps({"count": len(ids), "provider": "mock"}, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "job_id": job_id, "count": len(ids)}


def job_candidate_ids(job_id):
    conn = db.get_conn()
    rows = conn.execute("SELECT DISTINCT candidate_id FROM blog_rewrite_events "
                        "WHERE job_id=? AND event_type='queued' AND candidate_id IS NOT NULL", (job_id,)).fetchall()
    conn.close()
    return [r[0] for r in rows]


def list_jobs(limit=30):
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM blog_rewrite_jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        cc = d.get("candidate_count") or 0
        done = (d.get("completed_count") or 0) + (d.get("failed_count") or 0) + (d.get("skipped_count") or 0)
        d["progress_pct"] = round(done / cc * 100) if cc else 0
        out.append(d)
    return out


def get_job(job_id):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM blog_rewrite_jobs WHERE id=?", (job_id,)).fetchone()
    ev = conn.execute("SELECT event_type, detail_json, created_at, candidate_id FROM blog_rewrite_events "
                      "WHERE job_id=? ORDER BY id DESC LIMIT 80", (job_id,)).fetchall()
    conn.close()
    if not r:
        return None
    d = dict(r)
    d["events"] = [dict(e) for e in ev]
    return d


def cancel_job(job_id):
    conn = db.get_conn()
    j = conn.execute("SELECT status FROM blog_rewrite_jobs WHERE id=?", (job_id,)).fetchone()
    if not j:
        conn.close(); return {"ok": False, "error": "job không tồn tại"}
    if j["status"] in ("completed", "completed_with_errors", "cancelled", "failed"):
        conn.close(); return {"ok": False, "error": "job đã kết thúc"}
    conn.execute("UPDATE blog_rewrite_jobs SET status='cancel_requested', updated_at=datetime('now') WHERE id=?", (job_id,))
    conn.execute("INSERT INTO blog_rewrite_events (job_id, event_type, detail_json) VALUES (?,?,?)",
                 (job_id, "cancel_requested", "{}"))
    conn.commit(); conn.close()
    return {"ok": True}


def retry_failed(job_id):
    """Requeue candidate failed của job → tạo job mock mới (draft version mới, không overwrite)."""
    conn = db.get_conn()
    rows = conn.execute("""SELECT DISTINCT c.id FROM blog_rewrite_candidates c
        JOIN blog_rewrite_events e ON e.candidate_id=c.id AND e.job_id=?
        WHERE c.status='failed'""", (job_id,)).fetchall()
    conn.close()
    ids = [r[0] for r in rows]
    if not ids:
        return {"ok": False, "error": "Không có candidate failed để retry."}
    res = create_job(ids, mode="selected", explicit_confirm=True)
    if res.get("ok"):
        record_event("retry_requested", job_id=job_id, detail={"new_job": res["job_id"], "count": len(ids)})
    return res


# ═══════════════════════ P2 — MOCK DRAFT ═══════════════════════
MOCK_PROMPT_VERSION = "BLOG_REWRITE_MOCK_V1"


def build_mock_draft(candidate):
    """Mock deterministic — KHÔNG gọi network/AI. Đủ để test UI."""
    title = candidate.get("title", "")
    return {
        "search_intent": f"[MOCK] Search intent cho: {title[:60]}",
        "new_outline": [
            {"heading": "Tổng quan", "purpose": "Kiểm tra render outline"},
            {"heading": "Các điểm cần biên tập lại", "purpose": "Kiểm tra draft preview"},
        ],
        "title_options": ["Bản nháp thử nghiệm 1", "Bản nháp thử nghiệm 2", "Bản nháp thử nghiệm 3"],
        "recommended_title": "Bản nháp thử nghiệm — không dùng để publish",
        "meta_description_options": ["Meta mock 1", "Meta mock 2", "Meta mock 3"],
        "recommended_meta_description": "Meta description mock — chỉ dùng kiểm tra workflow",
        "summary_html": "<p>Bản nháp mock dùng để kiểm tra hệ thống.</p>",
        "body_html": "<p>Đây là nội dung mock. Không dùng để cập nhật website.</p>"
                     "<h2>Tổng quan</h2><p>Workflow đang được kiểm tra.</p>",
        "tags_suggestion": [], "internal_links_preserved": [], "external_links_flagged": [],
        "external_images_flagged": [], "facts_to_manual_verify": [],
        "editor_notes": ["MOCK DRAFT — KHÔNG APPLY LIVE"],
    }


def mock_quality(candidate, draft):
    return {
        "mock": True,
        "word_count_original": None, "word_count_draft": len(draft["body_html"].split()),
        "heading_count_draft": draft["body_html"].count("<h2") + draft["body_html"].count("<h3"),
        "normalized_5gram_overlap": 0.0, "longest_common_phrase": 0,
        "html_validation": "mock_ok", "external_link_flag_count": 0, "external_image_flag_count": 0,
        "note": "Mock quality — chưa gọi AI thật",
    }


def save_mock_draft(candidate, job_id):
    """Lưu draft mock vào blog_rewrite_drafts, version tăng dần (không overwrite)."""
    cid = candidate["id"]
    draft = build_mock_draft(candidate)
    qual = mock_quality(candidate, draft)
    conn = db.get_conn()
    try:
        ver = (conn.execute("SELECT COALESCE(MAX(version),0) FROM blog_rewrite_drafts WHERE candidate_id=?",
                            (cid,)).fetchone()[0] or 0) + 1
        cur = conn.execute("""INSERT INTO blog_rewrite_drafts
            (candidate_id, job_id, version, original_title, original_handle, original_content_hash,
             draft_title, draft_body_html, draft_summary_html, draft_tags,
             seo_title_suggestions_json, meta_description_suggestions_json, outline_json,
             quality_json, approval_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (cid, job_id, ver, candidate.get("title"), candidate.get("handle"), candidate.get("content_hash"),
             draft["recommended_title"], draft["body_html"], draft["summary_html"],
             json.dumps(draft["tags_suggestion"], ensure_ascii=False),
             json.dumps(draft["title_options"], ensure_ascii=False),
             json.dumps(draft["meta_description_options"], ensure_ascii=False),
             json.dumps(draft["new_outline"], ensure_ascii=False),
             json.dumps(qual, ensure_ascii=False), "mock_review"))
        draft_id = cur.lastrowid
        conn.commit()
        return draft_id, ver
    finally:
        conn.close()


def get_draft(draft_id):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM blog_rewrite_drafts WHERE id=?", (draft_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


def latest_draft_for_candidate(cid):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM blog_rewrite_drafts WHERE candidate_id=? ORDER BY version DESC LIMIT 1", (cid,)).fetchone()
    conn.close()
    return dict(r) if r else None


# ═══════════════════════ P2 — STALE RECOVERY ═══════════════════════
STALE_MINUTES = 3


def recover_stale_jobs():
    """Job running + heartbeat quá cũ → stale → requeue candidate generating về failed an toàn."""
    conn = db.get_conn()
    try:
        stale = conn.execute(
            "SELECT id FROM blog_rewrite_jobs WHERE status IN ('running','cancel_requested') "
            "AND (last_heartbeat_at IS NULL OR last_heartbeat_at < datetime('now', ?))",
            (f"-{STALE_MINUTES} minutes",)).fetchall()
        n = 0
        for r in stale:
            jid = r[0]
            conn.execute("UPDATE blog_rewrite_jobs SET status='stale', updated_at=datetime('now') WHERE id=?", (jid,))
            cids = [x[0] for x in conn.execute(
                "SELECT DISTINCT candidate_id FROM blog_rewrite_events WHERE job_id=? AND event_type='queued'", (jid,)).fetchall()]
            for cid in cids:
                conn.execute("UPDATE blog_rewrite_candidates SET status='failed', updated_at=datetime('now') "
                             "WHERE id=? AND status IN ('queued','generating')", (cid,))
            conn.execute("INSERT INTO blog_rewrite_events (job_id, event_type, detail_json) VALUES (?,?,?)",
                         (jid, "stale_detected", "{}"))
            conn.execute("INSERT INTO blog_rewrite_events (job_id, event_type, detail_json) VALUES (?,?,?)",
                         (jid, "stale_recovered", "{}"))
            n += 1
        conn.commit()
        return n
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    dry = "--apply" not in sys.argv
    res = build_candidates(dry_run=dry)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=2))
