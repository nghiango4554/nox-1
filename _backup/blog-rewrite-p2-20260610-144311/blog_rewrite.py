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


if __name__ == "__main__":
    import sys
    dry = "--apply" not in sys.argv
    res = build_candidates(dry_run=dry)
    print(json.dumps(res["summary"], ensure_ascii=False, indent=2))
