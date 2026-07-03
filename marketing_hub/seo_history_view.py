"""View-model cho dashboard /seo/history.

Đọc DB THUẦN (KHÔNG gọi Haravan/API live). Gom:
  - scan summary (từ seo_pages, KHÔNG dùng seo_stats.broken vì nó đếm NULL)
  - health score 0-100 (công thức spec SEO_HISTORY_DASHBOARD_SPEC.md §6)
  - link health 10 bucket (KHÔNG gom tất cả thành "broken")
  - issue groups (8 nhóm)
  - top affected URLs
  - latest vs previous delta (từ seo_history)

Mọi số tính riêng ở đây để không đụng seo_stats (dùng chung bởi /seo).
"""
import json

import db

# ─────────────── Issue code → nhóm hiển thị ───────────────
ISSUE_GROUPS = {
    "Metadata": ["no_title", "title_long", "title_short", "no_meta",
                 "meta_short", "meta_long", "no_og", "meta_no_cta"],
    "Content": ["no_h1", "multi_h1", "no_h2", "many_h2", "h2_after_h3",
                "low_content", "thin_content", "readability", "h1_in_desc",
                "img_no_alt"],
    "Links": ["few_internal", "no_internal"],
    "Schema": ["no_schema"],
    "Indexability": ["noindex_meta", "noindex_header", "no_canonical",
                     "canonical_other"],
    "Redirects": ["redirect_chain", "redirect_long_chain"],
    "Performance": ["slow", "very_slow"],
    "Technical": ["broken", "fetch_fail"],
}
# code → nhóm (đảo map)
_CODE_GROUP = {c: g for g, codes in ISSUE_GROUPS.items() for c in codes}

# Link health bucket: nhãn + có phải "gãy thật" không
LINK_BUCKETS = [
    ("broken_4xx", "Lỗi 4xx", True),
    ("server_5xx", "Lỗi máy chủ 5xx", True),
    ("blocked_403", "Bị chặn 403", False),
    ("rate_limited_429", "Giới hạn 429", False),
    ("timeout", "Timeout / mạng", False),
    ("cdn_blocked", "CDN chặn bot", False),
    ("redirect", "Redirect 3xx", False),
    ("external_unknown", "Không rõ (skip/breaker)", False),
    ("unchecked", "Chưa check", False),
    ("ok", "OK", False),
]
_TIMEOUT_KINDS = {"timeout", "read_timeout", "connect_timeout", "dns_fail",
                  "ssl_error", "conn_error"}


def _classify_link(status, kind):
    """(status_code, error_kind) → 1 trong 10 bucket."""
    kind = (kind or "").strip()
    if status is None:
        return "unchecked"
    if status == 0:
        if kind == "asset_cdn_skip":
            return "cdn_blocked"
        if kind == "social_share_skip":
            return "ok"          # link mạng xã hội cố tình bỏ qua, không phải gãy
        if kind in _TIMEOUT_KINDS:
            return "timeout"
        return "external_unknown"   # circuit_breaker_skip / other_error / None
    if status == 403:
        return "blocked_403"
    if status == 429:
        return "rate_limited_429"
    if 400 <= status < 500:
        return "broken_4xx"
    if status >= 500:
        return "server_5xx"
    if 300 <= status < 400:
        return "redirect"
    return "ok"                    # 2xx


def link_health() -> dict:
    """Phân loại toàn bộ link (distinct target) → 10 bucket + tách internal/external."""
    conn = db.get_conn()
    rows = conn.execute(
        """SELECT target_url,
                  MAX(status_code) status_code,
                  MAX(error_kind)  error_kind,
                  MAX(is_internal) is_internal
           FROM seo_links GROUP BY target_url"""
    ).fetchall()
    conn.close()
    buckets = {k: 0 for k, _, _ in LINK_BUCKETS}
    internal = {k: 0 for k, _, _ in LINK_BUCKETS}
    for r in rows:
        b = _classify_link(r["status_code"], r["error_kind"])
        buckets[b] += 1
        if r["is_internal"]:
            internal[b] += 1
    broken_true = buckets["broken_4xx"] + buckets["server_5xx"]
    return {
        "buckets": buckets,
        "internal": internal,
        "broken_true": broken_true,
        "broken_true_internal": internal["broken_4xx"] + internal["server_5xx"],
        "total": sum(buckets.values()),
        "defs": [{"key": k, "label": lbl, "is_broken": br}
                 for k, lbl, br in LINK_BUCKETS],
    }


def issue_counts() -> dict:
    """code → count (mọi issue), từ seo_top_issues (limit cao)."""
    return {it["code"]: it["count"] for it in db.seo_top_issues(limit=100)}


def issue_group_breakdown(counts: dict) -> list:
    """Gom issue theo 8 nhóm → list {group, total, codes:[{code,count}]} sort desc."""
    groups = {g: [] for g in ISSUE_GROUPS}
    for code, n in counts.items():
        g = _CODE_GROUP.get(code)
        if g:
            groups[g].append({"code": code, "count": n})
    out = []
    for g, codes in groups.items():
        codes.sort(key=lambda x: -x["count"])
        out.append({"group": g, "total": sum(c["count"] for c in codes),
                    "codes": codes})
    out.sort(key=lambda x: -x["total"])
    return out


def scan_summary() -> dict:
    """Tổng quan lần scan mới nhất (từ seo_pages latest state)."""
    stats = db.seo_stats()          # total, avg_score, by_type, good, ok, bad (KHÔNG dùng .broken)
    conn = db.get_conn()
    row = conn.execute(
        """SELECT
            SUM(CASE WHEN status_code BETWEEN 400 AND 499 THEN 1 ELSE 0 END) err_4xx,
            SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) err_5xx,
            SUM(CASE WHEN status_code IS NULL THEN 1 ELSE 0 END) not_crawled,
            AVG(CASE WHEN load_ms > 0 THEN load_ms END) avg_load_ms
           FROM seo_pages"""
    ).fetchone()
    conn.close()
    ic = issue_counts()
    return {
        "total": stats["total"],
        "avg_score": stats["avg_score"],
        "by_type": stats["by_type"],
        "good": stats["good"], "ok": stats["ok"], "bad": stats["bad"],
        "err_4xx": row["err_4xx"] or 0,
        "err_5xx": row["err_5xx"] or 0,
        "not_crawled": row["not_crawled"] or 0,
        "avg_load_ms": round(row["avg_load_ms"] or 0),
        "miss_title": ic.get("no_title", 0),
        "miss_meta": ic.get("no_meta", 0),
        "miss_h1": ic.get("no_h1", 0),
        "miss_schema": ic.get("no_schema", 0),
        "miss_canonical": ic.get("no_canonical", 0),
        "noindex": ic.get("noindex_meta", 0) + ic.get("noindex_header", 0),
        "redirect": ic.get("redirect_chain", 0) + ic.get("redirect_long_chain", 0),
        "issue_counts": ic,
    }


def health_score(summary: dict) -> dict:
    """0-100 theo công thức spec §6. Blocked/timeout/403/429 KHÔNG tính broken thật."""
    penalties = [
        ("4xx nội bộ", min(30, 4 * summary["err_4xx"])),
        ("5xx", min(30, 6 * summary["err_5xx"])),
        ("Thiếu title/meta", min(20, 2 * (summary["miss_title"] + summary["miss_meta"]))),
        ("Thiếu H1", min(10, 1 * summary["miss_h1"])),
        ("Thiếu schema", min(15, 1 * summary["miss_schema"])),
        ("Noindex bất thường", min(20, 4 * summary["noindex"])),
    ]
    total_pen = sum(p for _, p in penalties)
    score = max(0, min(100, 100 - total_pen))
    if score >= 80:
        badge, tone = "Good", "emerald"
    elif score >= 60:
        badge, tone = "Needs attention", "amber"
    else:
        badge, tone = "Critical", "rose"
    return {
        "score": score, "badge": badge, "tone": tone,
        "penalties": [{"label": l, "points": p} for l, p in penalties if p > 0],
        "note": "Blocked/timeout/rate-limit KHÔNG tính là link gãy thật. "
                "Điểm trừ schema có thể do crawler tĩnh chưa đọc JSON-LD chèn bằng JS.",
    }


def top_affected_urls(limit: int = 500) -> list:
    """Trang có vấn đề, worst-first (score thấp / nhiều issue)."""
    conn = db.get_conn()
    rows = conn.execute(
        """SELECT url, url_type, status_code, score, issues, last_crawled
           FROM seo_pages
           WHERE last_crawled IS NOT NULL
             AND issues IS NOT NULL AND issues != '' AND issues != '[]'
           ORDER BY score ASC, url ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        try:
            arr = json.loads(r["issues"]) or []
        except (ValueError, TypeError):
            arr = []
        codes = [it.get("code") for it in arr if it.get("code")]
        has_err = any(it.get("level") == "error" for it in arr)
        sc = r["score"] if r["score"] is not None else 0
        severity = "critical" if (has_err or sc < 50) else ("warning" if sc < 65 else "ok")
        out.append({
            "url": r["url"], "url_type": r["url_type"] or "other",
            "status_code": r["status_code"], "score": r["score"],
            "issue_count": len(arr), "issues": codes[:6],
            "severity": severity, "last_crawled": r["last_crawled"],
        })
    return out


def _delta(latest, prev, key):
    a = (latest or {}).get(key) or 0
    b = (prev or {}).get(key) or 0
    return round(a - b, 1)


def latest_prev() -> dict:
    """2 snapshot mới nhất + delta (từ seo_history aggregate)."""
    rows = db.seo_history_list(limit=2)
    latest = rows[0] if rows else None
    prev = rows[1] if len(rows) > 1 else None
    deltas = {}
    if latest and prev:
        for k in ("avg_score", "good", "ok_count", "bad", "total", "broken_links"):
            deltas[k] = _delta(latest, prev, k)
    return {"latest": latest, "prev": prev, "deltas": deltas}


def dashboard_context() -> dict:
    """Gom toàn bộ cho template /seo/history."""
    summary = scan_summary()
    return {
        "summary": summary,
        "health": health_score(summary),
        "links": link_health(),
        "issue_groups": issue_group_breakdown(summary["issue_counts"]),
        "top_urls": top_affected_urls(limit=500),
        "compare": latest_prev(),
    }
