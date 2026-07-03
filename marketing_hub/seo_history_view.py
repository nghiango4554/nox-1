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
        st = r["status_code"]
        owner = _owner_for(set(codes), st)
        first = next((c for c in codes if c in SUGGESTED_ACTION), codes[0] if codes else None)
        out.append({
            "url": r["url"], "url_type": r["url_type"] or "other",
            "status_code": st, "score": r["score"],
            "issue_count": len(arr), "issues": codes,
            "issue_labels": [ISSUE_LABEL_VI.get(c, c) for c in codes],
            "severity": severity, "last_crawled": r["last_crawled"],
            "owner": owner, "real_broken": bool(st and st >= 400),
            "action": SUGGESTED_ACTION.get(first, "Rà soát trang"),
            "groups": sorted({_CODE_GROUP[c] for c in codes if c in _CODE_GROUP}),
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


# ─────────────── Owner (dev/content/seo/review) + gợi ý hành động ───────────────
_DEV_CODES = {"broken", "fetch_fail", "no_canonical", "canonical_other",
              "noindex_meta", "noindex_header", "redirect_chain",
              "redirect_long_chain", "slow", "very_slow"}
_CONTENT_CODES = {"no_title", "title_long", "title_short", "no_meta",
                  "meta_short", "meta_long", "no_h1", "multi_h1", "no_h2",
                  "many_h2", "h2_after_h3", "low_content", "thin_content",
                  "readability", "img_no_alt", "h1_in_desc", "meta_no_cta"}
_SEO_CODES = {"no_schema", "no_og", "few_internal", "no_internal"}

SUGGESTED_ACTION = {
    "broken": "Sửa trang lỗi 4xx", "fetch_fail": "Kiểm tra trang không tải được",
    "no_canonical": "Thêm/kiểm tra canonical", "canonical_other": "Rà canonical trỏ sai",
    "noindex_meta": "Kiểm tra noindex (có chủ đích?)",
    "noindex_header": "Kiểm tra X-Robots noindex",
    "redirect_chain": "Rút gọn chuỗi redirect", "redirect_long_chain": "Rút gọn chuỗi redirect dài",
    "slow": "Tối ưu tốc độ tải", "very_slow": "Tối ưu tốc độ tải (rất chậm)",
    "no_title": "Viết thẻ title (30–60 ký tự)", "title_long": "Rút title ≤60 ký tự",
    "title_short": "Viết title dài hơn", "no_meta": "Viết meta description (120–160)",
    "meta_short": "Viết meta dài hơn", "meta_long": "Rút meta ≤160 ký tự",
    "no_h1": "Thêm H1 đúng chủ đề", "multi_h1": "Chỉ giữ 1 H1",
    "no_h2": "Thêm H2 phân mục", "many_h2": "Gom bớt H2",
    "h2_after_h3": "Sửa thứ tự heading", "low_content": "Bổ sung nội dung",
    "thin_content": "Bổ sung nội dung (thin)", "readability": "Rút gọn câu, dễ đọc hơn",
    "img_no_alt": "Thêm alt cho ảnh", "h1_in_desc": "Bỏ H1 trùng trong mô tả",
    "meta_no_cta": "Thêm CTA vào meta",
    "no_schema": "Thêm schema JSON-LD", "no_og": "Thêm OG tags",
    "few_internal": "Thêm internal link", "no_internal": "Thêm internal link",
}


ISSUE_LABEL_VI = {
    "broken": "Trang lỗi 4xx", "fetch_fail": "Không tải được",
    "no_canonical": "Thiếu canonical", "canonical_other": "Canonical trỏ nơi khác",
    "noindex_meta": "Bị noindex (meta)", "noindex_header": "Bị noindex (header)",
    "redirect_chain": "Chuỗi redirect", "redirect_long_chain": "Chuỗi redirect dài",
    "slow": "Tải chậm", "very_slow": "Tải rất chậm",
    "no_title": "Thiếu title", "title_long": "Title quá dài", "title_short": "Title quá ngắn",
    "no_meta": "Thiếu meta", "meta_short": "Meta quá ngắn", "meta_long": "Meta quá dài",
    "no_h1": "Thiếu H1", "multi_h1": "Nhiều H1", "no_h2": "Thiếu H2", "many_h2": "Quá nhiều H2",
    "h2_after_h3": "Heading sai thứ tự", "low_content": "Nội dung ít", "thin_content": "Nội dung mỏng",
    "readability": "Khó đọc", "img_no_alt": "Ảnh thiếu alt", "h1_in_desc": "H1 trong mô tả",
    "meta_no_cta": "Meta thiếu CTA", "no_schema": "Thiếu schema", "no_og": "Thiếu OG tags",
    "few_internal": "Ít internal link", "no_internal": "Không internal link",
}


def _owner_for(codes: set, status) -> str:
    if (status and status >= 400) or (codes & _DEV_CODES):
        return "dev"
    if codes & _CONTENT_CODES:
        return "content"
    if codes & _SEO_CODES:
        return "seo"
    return "review"


def build_action_queue(top_urls: list, links: dict, labels: dict = None,
                       per_owner: int = 15) -> dict:
    """Xếp URL vào 4 owner: dev / content / seo + review (từ link bucket)."""
    labels = labels or ISSUE_LABEL_VI
    owner_sets = {"dev": _DEV_CODES, "content": _CONTENT_CODES, "seo": _SEO_CODES}
    q = {"dev": [], "content": [], "seo": [], "review": []}
    for u in top_urls:
        codes = set(u["issues"])
        owner = _owner_for(codes, u.get("status_code"))
        if owner == "review":
            continue
        pick = next((c for c in u["issues"] if c in owner_sets[owner]), None)
        if pick is None and (u.get("status_code") or 0) >= 400:
            pick = "broken"
        reason = labels.get(pick, pick) if pick else "Nhiều lỗi"
        q[owner].append({
            "url": u["url"], "url_type": u["url_type"],
            "severity": u["severity"], "score": u["score"],
            "status_code": u["status_code"], "owner": owner,
            "reason": reason, "action": SUGGESTED_ACTION.get(pick, "Rà soát trang"),
        })
    for k in ("dev", "content", "seo"):
        q[k].sort(key=lambda x: (x["score"] if x["score"] is not None else 0))
        q[k] = q[k][:per_owner]
    # Review = link bucket không phải gãy thật
    review_map = [
        ("external_unknown", "Circuit-breaker/không rõ", "Crawl lại nhẹ hoặc bỏ qua"),
        ("timeout", "Timeout/mạng", "Tăng timeout hoặc giảm worker"),
        ("blocked_403", "Bị chặn 403", "Bỏ qua (bot bị chặn)"),
        ("rate_limited_429", "Giới hạn 429", "Giảm worker / thêm delay"),
        ("cdn_blocked", "CDN chặn", "Bỏ qua (CDN)"),
        ("unchecked", "Chưa check", "Chạy link-check lại"),
    ]
    for key, reason, action in review_map:
        n = links["buckets"].get(key, 0)
        if n > 0:
            q["review"].append({"bucket": key, "count": n, "reason": reason,
                                "action": action, "owner": "review"})
    return q


def build_insights(summary, health, links, issue_groups, compare) -> list:
    """3–5 insight tự động từ data. severity: good|warning|danger|info."""
    ins = []
    bt = links["broken_true"]
    if health["score"] >= 80:
        ins.append({"severity": "good", "icon": "shield-check",
                    "text": f"Site đang tốt: {health['score']}/100"
                            + (f", chỉ {bt} link gãy thật." if bt else ", không có link gãy thật."),
                    "action_label": None, "action": None})
    elif health["score"] >= 60:
        ins.append({"severity": "warning", "icon": "triangle-alert",
                    "text": f"Site cần chú ý: {health['score']}/100 — rà nhóm lỗi lớn nhất.",
                    "action_label": "Xem URL", "action": "top"})
    else:
        ins.append({"severity": "danger", "icon": "triangle-alert",
                    "text": f"Site đang có vấn đề: {health['score']}/100 — ưu tiên sửa ngay.",
                    "action_label": "Xem URL", "action": "top"})
    if bt > 0:
        ins.append({"severity": "danger", "icon": "link",
                    "text": f"Có {bt} link gãy THẬT (4xx/5xx) cần sửa.",
                    "action_label": "Chi tiết link", "action": "links"})
    eu = links["buckets"].get("external_unknown", 0) + links["buckets"].get("timeout", 0) \
        + links["buckets"].get("blocked_403", 0) + links["buckets"].get("rate_limited_429", 0)
    if eu > 500 and eu > bt * 5:
        ins.append({"severity": "warning", "icon": "triangle-alert",
                    "text": f"{eu:,} link blocked/timeout/unknown — KHÔNG phải gãy thật; "
                            "nên crawl lại nhẹ hơn hoặc giảm worker.",
                    "action_label": "Chi tiết link", "action": "links"})
    if issue_groups:
        g0 = issue_groups[0]
        if g0["total"] > 0:
            ins.append({"severity": "info", "icon": "list-checks",
                        "text": f"“{g0['group']}” là nhóm lỗi lớn nhất với {g0['total']:,} lần xuất hiện.",
                        "action_label": "Lọc nhóm", "action": f"group:{g0['group']}"})
        if len(issue_groups) > 1 and issue_groups[1]["total"] > 0:
            g1 = issue_groups[1]
            ins.append({"severity": "info", "icon": "list-checks",
                        "text": f"“{g1['group']}” đứng thứ 2 với {g1['total']:,} lỗi.",
                        "action_label": "Lọc nhóm", "action": f"group:{g1['group']}"})
    d = compare.get("deltas") or {}
    if d:
        good_d, tot_d, sc_d = d.get("good", 0), d.get("total", 0), d.get("avg_score", 0)
        sev = "good" if sc_d >= 0 else "warning"
        parts = []
        if good_d:
            parts.append(f"{'+' if good_d > 0 else ''}{good_d} trang tốt")
        if tot_d:
            parts.append(f"tổng URL {'+' if tot_d > 0 else ''}{tot_d}")
        if sc_d:
            parts.append(f"điểm {'+' if sc_d > 0 else ''}{sc_d}")
        if parts:
            ins.append({"severity": sev, "icon": "git-compare",
                        "text": "So với snapshot trước: " + ", ".join(parts) + ".",
                        "action_label": None, "action": None})
    order = {"danger": 0, "warning": 1, "good": 2, "info": 3}
    ins.sort(key=lambda x: order.get(x["severity"], 4))
    return ins[:5]


def data_quality_flags(links, compare, url_compare) -> list:
    """Banner cảnh báo giới hạn data để tránh hiểu sai số."""
    flags = []
    eu = links["buckets"].get("external_unknown", 0)
    if eu > 1000:
        flags.append({"tone": "amber",
                      "text": f"{eu:,} link đang ở trạng thái external_unknown/circuit-breaker — "
                              "đây KHÔNG phải link gãy thật. Nên chạy lại link-check nhẹ hơn hoặc chia batch."})
    latest = compare.get("latest") or {}
    if latest and (latest.get("broken_links") or 0) == 0 and links["broken_true"] >= 0:
        flags.append({"tone": "slate",
                      "text": "Một số snapshot cũ chụp trước bước link-check nên cột “Gãy (snapshot)” = 0; "
                              "số link gãy thật lấy trực tiếp từ link hiện tại."})
    if not (url_compare or {}).get("available"):
        flags.append({"tone": "slate",
                      "text": "Cần thêm snapshot per-URL để so sánh lỗi mới / đã fix "
                              "(tự tích lũy từ lần “Chụp snapshot” kế tiếp)."})
    return flags


def summary_report_text(ctx) -> str:
    """Text report ngắn để copy gửi dev/content."""
    s, h, l = ctx["summary"], ctx["health"], ctx["links"]
    cmp = ctx["compare"]
    lines = [
        "BÁO CÁO SEO — sintech.vn",
        f"Health score: {h['score']}/100 ({h['badge']})",
        f"URL đã scan: {s['total']} · điểm TB {s['avg_score']} · tốt {s['good']} / OK {s['ok']} / cần sửa {s['bad']}",
        f"Link gãy THẬT (4xx/5xx): {l['broken_true']}"
        f" · blocked/timeout/unknown (không tính gãy): "
        f"{l['buckets'].get('external_unknown',0)+l['buckets'].get('timeout',0)+l['buckets'].get('blocked_403',0)+l['buckets'].get('rate_limited_429',0)+l['buckets'].get('cdn_blocked',0)}",
        f"Trang lỗi 4xx/5xx: {s['err_4xx']+s['err_5xx']} · thiếu title {s['miss_title']} · thiếu meta {s['miss_meta']} · thiếu schema {s['miss_schema']}",
    ]
    if ctx.get("issue_groups"):
        top = " · ".join(f"{g['group']}: {g['total']}" for g in ctx["issue_groups"][:4] if g["total"])
        lines.append("Top nhóm lỗi: " + top)
    d = cmp.get("deltas") or {}
    if d:
        lines.append(f"So lần trước: điểm {d.get('avg_score',0):+} · trang tốt {d.get('good',0):+} · tổng URL {d.get('total',0):+}")
    aq = ctx.get("action_queue") or {}
    lines.append(f"Hàng đợi: Dev {len(aq.get('dev',[]))} · Content {len(aq.get('content',[]))} · SEO {len(aq.get('seo',[]))}")
    return "\n".join(lines)


def url_compare() -> dict:
    """So sánh per-URL giữa 2 snapshot mới nhất (bảng seo_history_url_issues)."""
    try:
        return db.seo_history_url_compare()
    except Exception as e:
        return {"available": False, "error": f"{e.__class__.__name__}: {e}"}


BUCKET_INFO = {
    "broken_4xx": ("Link đích trả 4xx", "Sửa hoặc bỏ link"),
    "server_5xx": ("Máy chủ đích 5xx", "Kiểm tra server đích"),
    "blocked_403": ("Bị chặn 403", "Bỏ qua (bot bị chặn)"),
    "rate_limited_429": ("Giới hạn 429", "Giảm worker / thêm delay"),
    "timeout": ("Timeout / mạng", "Tăng timeout hoặc giảm worker"),
    "cdn_blocked": ("CDN chặn bot", "Bỏ qua (CDN)"),
    "redirect": ("Redirect 3xx", "Trỏ thẳng URL đích"),
    "external_unknown": ("Không rõ / circuit-breaker", "Crawl lại nhẹ hoặc bỏ qua"),
    "unchecked": ("Chưa check", "Chạy link-check lại"),
    "ok": ("OK", ""),
}


def issues_export_rows(limit: int = 2000) -> list:
    """Rows cho export URL issues CSV."""
    out = []
    for u in top_affected_urls(limit=limit):
        codes = u["issues"]
        owner = _owner_for(set(codes), u.get("status_code"))
        first = next((c for c in codes if c in SUGGESTED_ACTION), codes[0] if codes else None)
        out.append({
            "url": u["url"], "page_type": u["url_type"], "severity": u["severity"],
            "score": u["score"], "status_code": u["status_code"],
            "issues": " | ".join(ISSUE_LABEL_VI.get(c, c) for c in codes),
            "suggested_action": SUGGESTED_ACTION.get(first, ""), "owner": owner,
        })
    return out


def links_export_rows(limit: int = 20000) -> list:
    """Rows cho export link health CSV (mỗi cặp source→target)."""
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT source_url, target_url, status_code, error_kind "
        "FROM seo_links ORDER BY target_url LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        b = _classify_link(r["status_code"], r["error_kind"])
        reason, action = BUCKET_INFO.get(b, ("", ""))
        out.append({
            "source_url": r["source_url"], "target_url": r["target_url"],
            "bucket": b, "status_code": r["status_code"],
            "reason": reason, "suggested_action": action,
        })
    return out


def dashboard_context() -> dict:
    """Gom toàn bộ cho template /seo/history."""
    summary = scan_summary()
    health = health_score(summary)
    links = link_health()
    groups = issue_group_breakdown(summary["issue_counts"])
    top_urls = top_affected_urls(limit=500)
    compare = latest_prev()
    ucmp = url_compare()
    ctx = {
        "summary": summary,
        "health": health,
        "links": links,
        "issue_groups": groups,
        "top_urls": top_urls,
        "compare": compare,
        "url_compare": ucmp,
        "action_queue": build_action_queue(top_urls, links),
    }
    ctx["insights"] = build_insights(summary, health, links, groups, compare)
    ctx["data_quality"] = data_quality_flags(links, compare, ucmp)
    ctx["report_text"] = summary_report_text(ctx)
    return ctx
