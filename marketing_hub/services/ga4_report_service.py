# -*- coding: utf-8 -*-
"""GA4 report service — CHỈ đọc SQLite/cache, shape dữ liệu cho dashboard.
KHÔNG gọi GA4 API khi render report (trừ realtime có cache 60s).
Query parameterized, sort/order whitelist, không nối raw SQL từ query params.
"""
import json
import time
from datetime import date, datetime, timedelta

import db
from services import ga4_config, ga4_client
from services import ga4_sync_service

RANGE_DAYS = {"7": 7, "28": 28, "90": 90}


# ─────────────── period / delta / meta ───────────────
def _latest_data_date(conn):
    return conn.execute("SELECT MAX(date) FROM ga4_daily_summary").fetchone()[0]


def resolve_period(args, conn):
    df, dt = args.get("date_from"), args.get("date_to")
    if df and dt:
        return df, dt
    days = RANGE_DAYS.get(str(args.get("range", "28")), 28)
    anchor = _latest_data_date(conn) or (date.today() - timedelta(days=1)).isoformat()
    end = datetime.strptime(anchor, "%Y-%m-%d").date()
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def previous_period(df, dt):
    a = datetime.strptime(df, "%Y-%m-%d").date()
    b = datetime.strptime(dt, "%Y-%m-%d").date()
    length = (b - a).days + 1
    pb = a - timedelta(days=1)
    pa = pb - timedelta(days=length - 1)
    return pa.isoformat(), pb.isoformat()


def _delta(cur, prev):
    cur = cur or 0
    prev = prev or 0
    d = cur - prev
    dp = None if not prev else round(d / prev * 100, 1)   # previous=0 → delta_percent None
    return {"current": cur, "previous": prev, "delta": d, "delta_percent": dp}


def _compare_on(args):
    return str(args.get("compare_previous", "true")).lower() not in ("0", "false", "no")


def _int(v, default, maxv):
    try:
        n = int(v)
        return max(0, min(n, maxv))
    except Exception:
        return default


def _cache_meta(conn, cfg):
    ls = ga4_sync_service.latest_sync()
    fetched_at = ls["finished_at"] if ls else None
    latest = _latest_data_date(conn)
    age, stale = None, True
    if fetched_at:
        try:
            age = int((datetime.now() - datetime.strptime(fetched_at, "%Y-%m-%d %H:%M:%S")).total_seconds())
            stale = age > int(cfg.get("cache_ttl_minutes", 30)) * 60
        except Exception:
            pass
    return {"latest_data_date": latest, "fetched_at": fetched_at,
            "cache_age_seconds": age, "stale": stale}


def _envelope(data, filters, period, prev, meta, tracking_state="ok", error=None, extra=None):
    env = {
        "ok": error is None,
        "data": data,
        "filters": filters,
        "period": {"date_from": period[0], "date_to": period[1]} if period else None,
        "previous_period": ({"date_from": prev[0], "date_to": prev[1]} if prev else None),
        "meta": meta,
        "latest_data_date": meta.get("latest_data_date"),
        "fetched_at": meta.get("fetched_at"),
        "cache_age_seconds": meta.get("cache_age_seconds"),
        "stale": meta.get("stale"),
        "tracking_state": tracking_state,
        "error": error,
    }
    if extra:
        env.update(extra)
    return env


def _sort_paginate(rows, sort, order, allowed, default, limit, offset):
    key = sort if sort in allowed else default
    rev = str(order or "desc").lower() != "asc"
    rows.sort(key=lambda r: (r.get(key) is None, r.get(key) if r.get(key) is not None else 0), reverse=rev)
    total = len(rows)
    return rows[offset:offset + limit], total


def classify_page_type(path):
    if not path or path == "(not set)":
        return "other"
    if path == "/":
        return "homepage"
    if path == "/pages/xay-dung-cau-hinh":
        return "build_pc"
    if path.startswith("/products/"):
        return "product"
    if path.startswith("/collections/"):
        return "collection"
    if path.startswith("/blogs/"):
        return "blog"
    if path.startswith("/pages/"):
        return "page"
    return "other"


def _er(eng, sess):
    return round(eng / sess, 4) if sess else 0.0


# ─────────────── 3. OVERVIEW ───────────────
# Phân loại độ chính xác metric:
#   additive (SUM daily đúng tuyệt đối): sessions/engaged/screen_views/key_events/purchases/revenue/engagement_duration
#   non-additive (user trùng giữa ngày): active_users/new_users → dùng exact period cache nếu có, không thì daily-sum (approximate)
#   recomputed: engagement_rate = engaged/sessions; average_session_duration = weighted theo sessions
_ADDITIVE = ["sessions", "engaged_sessions", "screen_page_views", "key_events",
             "ecommerce_purchases", "purchase_revenue", "total_revenue", "user_engagement_duration"]
_NONADD = ["active_users", "new_users"]


def _period_cache_get(conn, df, dt):
    r = conn.execute("SELECT payload_json FROM ga4_period_report_cache WHERE cache_key=?",
                     ("overview:%s:%s" % (df, dt),)).fetchone()
    return json.loads(r["payload_json"]) if r and r["payload_json"] else None


def overview(args):
    conn = db.get_conn()
    cfg = ga4_config.load_config()
    df, dt = resolve_period(args, conn)
    pf, pt = previous_period(df, dt)
    compare = _compare_on(args)

    def agg(a, b):
        cols = ", ".join("SUM(%s) AS %s" % (c, c) for c in (_ADDITIVE + _NONADD))
        return conn.execute(
            "SELECT %s, SUM(average_session_duration*sessions) AS asd_w "
            "FROM ga4_daily_summary WHERE date BETWEEN ? AND ?" % cols, (a, b)).fetchone()

    cur_d = agg(df, dt)
    prev_d = agg(pf, pt) if compare else None
    cur_e = _period_cache_get(conn, df, dt)
    prev_e = _period_cache_get(conn, pf, pt) if compare else None

    def v(r, c):
        return (r[c] if r and r[c] is not None else 0)

    kpis = {c: _delta(v(cur_d, c), v(prev_d, c) if prev_d else 0) for c in _ADDITIVE}

    # non-additive: exact period cache nếu có, fallback daily-sum
    for c in _NONADD:
        curv = (cur_e.get(c) or 0) if cur_e is not None else v(cur_d, c)
        if compare:
            prevv = (prev_e.get(c) or 0) if prev_e is not None else (v(prev_d, c) if prev_d else 0)
        else:
            prevv = 0
        kpis[c] = _delta(curv, prevv)

    kpis["engagement_rate"] = _delta(_er(v(cur_d, "engaged_sessions"), v(cur_d, "sessions")),
                                     _er(v(prev_d, "engaged_sessions"), v(prev_d, "sessions")) if prev_d else 0)

    def asd(r):
        s = v(r, "sessions")
        return round(r["asd_w"] / s, 2) if (r and r["asd_w"] and s) else 0.0
    kpis["average_session_duration"] = _delta(asd(cur_d), asd(prev_d) if prev_d else 0)

    def organic(a, b):
        r = conn.execute("SELECT SUM(sessions) s FROM ga4_channels_daily WHERE date BETWEEN ? AND ? "
                         "AND session_default_channel_group='Organic Search'", (a, b)).fetchone()
        return r["s"] or 0
    kpis["organic_search_sessions"] = _delta(organic(df, dt), organic(pf, pt) if compare else 0)

    user_acc = "exact_period_cache" if cur_e is not None else "approximate_daily_sum"
    accuracy = {c: "exact_additive" for c in _ADDITIVE}
    accuracy.update({
        "active_users": user_acc, "new_users": user_acc,
        "engagement_rate": "exact_recomputed",
        "average_session_duration": "weighted_recomputed",
        "organic_search_sessions": "exact_additive",
    })
    meta = _cache_meta(conn, cfg)
    meta["metric_accuracy"] = accuracy
    meta["accuracy_note"] = ("active/new_users daily-sum có thể đếm trùng user giữa ngày; "
                             "sessions & revenue additive; engagement_rate phải tính lại")
    has_data = bool(v(cur_d, "sessions"))
    conn.close()
    return _envelope(kpis, {"range": args.get("range"), "compare_previous": compare},
                     (df, dt), (pf, pt) if compare else None, meta,
                     tracking_state=("ok" if has_data else "not_configured"))


# ─────────────── 3b. TIMESERIES (chart, đọc SQLite) ───────────────
def timeseries(args):
    conn = db.get_conn()
    cfg = ga4_config.load_config()
    df, dt = resolve_period(args, conn)
    rows = conn.execute(
        "SELECT date, sessions, engaged_sessions, key_events, purchase_revenue "
        "FROM ga4_daily_summary WHERE date BETWEEN ? AND ? ORDER BY date", (df, dt)).fetchall()
    org = {r["date"]: (r["s"] or 0) for r in conn.execute(
        "SELECT date, SUM(sessions) s FROM ga4_channels_daily WHERE date BETWEEN ? AND ? "
        "AND session_default_channel_group='Organic Search' GROUP BY date", (df, dt)).fetchall()}
    series = []
    for r in rows:
        s = r["sessions"] or 0
        eng = r["engaged_sessions"] or 0
        series.append({"date": r["date"], "sessions": s, "organic_search_sessions": org.get(r["date"], 0),
                       "engagement_rate": _er(eng, s), "key_events": r["key_events"] or 0,
                       "purchase_revenue": r["purchase_revenue"] or 0})
    meta = _cache_meta(conn, cfg)
    conn.close()
    return _envelope(series, {"range": args.get("range")}, (df, dt), None, meta)


# ─────────────── 4. CHANNELS ───────────────
_CH_SORT = {"sessions", "active_users", "engaged_sessions", "engagement_rate",
            "key_events", "ecommerce_purchases", "purchase_revenue"}


def channels(args):
    conn = db.get_conn()
    cfg = ga4_config.load_config()
    df, dt = resolve_period(args, conn)
    pf, pt = previous_period(df, dt)
    compare = _compare_on(args)

    where, params = ["date BETWEEN ? AND ?"], [df, dt]
    if args.get("channel"):
        where.append("session_default_channel_group=?")
        params.append(args["channel"])
    # device KHÔNG áp dụng ở channels (schema channels_daily không có dim device) — đã bỏ khỏi UI

    base = ("SELECT session_default_channel_group AS channel, session_source_medium AS source_medium, "
            "SUM(active_users) active_users, SUM(sessions) sessions, SUM(engaged_sessions) engaged_sessions, "
            "SUM(key_events) key_events, SUM(ecommerce_purchases) ecommerce_purchases, "
            "SUM(purchase_revenue) purchase_revenue "
            "FROM ga4_channels_daily WHERE %s "
            "GROUP BY session_default_channel_group, session_source_medium")
    rows = [dict(r) for r in conn.execute(base % " AND ".join(where), params).fetchall()]

    prev_map = {}
    if compare:
        for r in conn.execute(base % "date BETWEEN ? AND ?", [pf, pt]).fetchall():
            prev_map[(r["channel"], r["source_medium"])] = (r["sessions"] or 0, r["purchase_revenue"] or 0)

    for r in rows:
        r["engagement_rate"] = _er(r["engaged_sessions"], r["sessions"])
        ps, pr = prev_map.get((r["channel"], r["source_medium"]), (0, 0))
        r["delta_sessions"] = (r["sessions"] or 0) - ps
        r["delta_revenue"] = round((r["purchase_revenue"] or 0) - pr, 2)

    limit = _int(args.get("limit"), 50, 500)
    offset = _int(args.get("offset"), 0, 10 ** 9)
    page, total = _sort_paginate(rows, args.get("sort"), args.get("order"), _CH_SORT, "sessions", limit, offset)
    meta = _cache_meta(conn, cfg)
    meta["metric_accuracy"] = {"sessions": "exact_additive", "purchase_revenue": "exact_additive",
                               "engagement_rate": "exact_recomputed", "active_users": "approximate_daily_sum"}
    conn.close()
    return _envelope(page, {"channel": args.get("channel"), "sort": args.get("sort"), "order": args.get("order")},
                     (df, dt), (pf, pt) if compare else None, meta,
                     extra={"total_rows": total, "limit": limit, "offset": offset})


# ─────────────── 5. LANDING PAGES ───────────────
_LP_SORT = {"sessions", "active_users", "new_users", "engaged_sessions", "engagement_rate",
            "screen_page_views", "key_events", "ecommerce_purchases", "purchase_revenue"}


def landing_pages(args):
    conn = db.get_conn()
    cfg = ga4_config.load_config()
    df, dt = resolve_period(args, conn)
    pf, pt = previous_period(df, dt)
    compare = _compare_on(args)

    where, params = ["date BETWEEN ? AND ?"], [df, dt]
    if args.get("search"):
        where.append("(normalized_path LIKE ? OR landing_page_raw LIKE ?)")
        kw = "%" + args["search"] + "%"
        params += [kw, kw]

    base = ("SELECT normalized_path, "
            "MAX(landing_page_raw) AS landing_page_raw, "
            "SUM(active_users) active_users, SUM(new_users) new_users, SUM(sessions) sessions, "
            "SUM(engaged_sessions) engaged_sessions, SUM(screen_page_views) screen_page_views, "
            "SUM(key_events) key_events, SUM(ecommerce_purchases) ecommerce_purchases, "
            "SUM(purchase_revenue) purchase_revenue "
            "FROM ga4_landing_pages_daily WHERE %s GROUP BY normalized_path")
    rows = [dict(r) for r in conn.execute(base % " AND ".join(where), params).fetchall()]

    prev_map = {}
    if compare:
        for r in conn.execute("SELECT normalized_path, SUM(sessions) s FROM ga4_landing_pages_daily "
                              "WHERE date BETWEEN ? AND ? GROUP BY normalized_path", [pf, pt]).fetchall():
            prev_map[r["normalized_path"]] = r["s"] or 0

    pt_filter = args.get("page_type")
    out = []
    for r in rows:
        r["engagement_rate"] = _er(r["engaged_sessions"], r["sessions"])
        r["page_type"] = classify_page_type(r["normalized_path"])
        r["delta_sessions"] = (r["sessions"] or 0) - prev_map.get(r["normalized_path"], 0)
        r["tracking_state"] = "ok"
        if pt_filter and r["page_type"] != pt_filter:
            continue
        out.append(r)

    limit = _int(args.get("limit"), 50, 1000)
    offset = _int(args.get("offset"), 0, 10 ** 9)
    page, total = _sort_paginate(out, args.get("sort"), args.get("order"), _LP_SORT, "sessions", limit, offset)
    meta = _cache_meta(conn, cfg)
    meta["metric_accuracy"] = {"sessions": "exact_additive", "purchase_revenue": "exact_additive",
                               "engagement_rate": "exact_recomputed",
                               "active_users": "approximate_daily_sum", "new_users": "approximate_daily_sum"}
    conn.close()
    return _envelope(page, {"search": args.get("search"), "page_type": pt_filter,
                            "sort": args.get("sort"), "order": args.get("order")},
                     (df, dt), (pf, pt) if compare else None, meta,
                     extra={"total_rows": total, "limit": limit, "offset": offset})


# ─────────────── 6. DEVICES ───────────────
_DV_SORT = {"sessions", "active_users", "engaged_sessions", "engagement_rate", "key_events", "purchase_revenue"}


def devices(args):
    conn = db.get_conn()
    cfg = ga4_config.load_config()
    df, dt = resolve_period(args, conn)
    rows = [dict(r) for r in conn.execute(
        "SELECT device_category, SUM(active_users) active_users, SUM(sessions) sessions, "
        "SUM(engaged_sessions) engaged_sessions, SUM(key_events) key_events, "
        "SUM(purchase_revenue) purchase_revenue FROM ga4_devices_daily "
        "WHERE date BETWEEN ? AND ? GROUP BY device_category", (df, dt)).fetchall()]
    for r in rows:
        r["engagement_rate"] = _er(r["engaged_sessions"], r["sessions"])
    limit = _int(args.get("limit"), 20, 100)
    offset = _int(args.get("offset"), 0, 10 ** 9)
    page, total = _sort_paginate(rows, args.get("sort"), args.get("order"), _DV_SORT, "sessions", limit, offset)
    meta = _cache_meta(conn, cfg)
    conn.close()
    return _envelope(page, {"sort": args.get("sort"), "order": args.get("order")},
                     (df, dt), None, meta, extra={"total_rows": total})


# ─────────────── 7. EVENTS ───────────────
_EV_SORT = {"event_count", "total_users", "key_events", "event_value"}


def events(args):
    conn = db.get_conn()
    cfg = ga4_config.load_config()
    df, dt = resolve_period(args, conn)
    rows = [dict(r) for r in conn.execute(
        "SELECT event_name, SUM(event_count) event_count, SUM(total_users) total_users, "
        "SUM(key_events) key_events, SUM(event_value) event_value, MAX(date) last_seen_date "
        "FROM ga4_events_daily WHERE date BETWEEN ? AND ? GROUP BY event_name", (df, dt)).fetchall()]
    limit = _int(args.get("limit"), 100, 1000)
    offset = _int(args.get("offset"), 0, 10 ** 9)
    page, total = _sort_paginate(rows, args.get("sort"), args.get("order"), _EV_SORT, "event_count", limit, offset)
    meta = _cache_meta(conn, cfg)
    ts = "ok" if total else "not_configured"
    conn.close()
    return _envelope(page, {"sort": args.get("sort"), "order": args.get("order")},
                     (df, dt), None, meta, tracking_state=ts, extra={"total_rows": total})


# ─────────────── 8. ECOMMERCE ───────────────
def ecommerce(args):
    conn = db.get_conn()
    cfg = ga4_config.load_config()
    df, dt = resolve_period(args, conn)
    cols = ["items_viewed", "items_added_to_cart", "items_checked_out", "items_purchased",
            "checkouts", "ecommerce_purchases", "purchase_revenue", "total_revenue"]
    r = conn.execute("SELECT %s FROM ga4_ecommerce_daily WHERE date BETWEEN ? AND ?" %
                     ", ".join("SUM(%s) %s" % (c, c) for c in cols), (df, dt)).fetchone()
    data = {c: (r[c] if r and r[c] is not None else 0) for c in cols}
    # tracking_state: chưa track ecommerce nếu toàn bộ lịch sử = 0
    allrow = conn.execute("SELECT SUM(items_viewed+items_added_to_cart+items_checked_out+"
                          "items_purchased+ecommerce_purchases) t FROM ga4_ecommerce_daily").fetchone()
    ts = "ok" if (allrow and (allrow["t"] or 0) > 0) else "not_configured"
    meta = _cache_meta(conn, cfg)
    meta["notes"] = "items_* là số lượng item (không phải user); checkouts/funnel count chuẩn lấy từ event table sau"
    conn.close()
    return _envelope(data, {"range": args.get("range")}, (df, dt), None, meta, tracking_state=ts)


# ─────────────── 9. REALTIME (cache 60s) ───────────────
# NGOẠI LỆ: /api/ga4/realtime là endpoint DUY NHẤT có thể gọi GA4 API khi render —
# nhưng vẫn qua cache 60s (cache fresh → SQLite, stale/none → gọi API → ghi cache).
# Các endpoint report khác CHỈ đọc SQLite, không gọi GA4.
def _fetch_realtime(cfg):
    payload = {"active_users_30m": 0, "active_users_5m": None,
               "five_minute_state": "not_available", "window_minutes": 30,
               "top_pages": [], "top_events": [], "devices": []}

    def safe(dims, mets, limit, minute_ranges=None):
        try:
            return ga4_client.run_realtime_report(dims, mets, limit=limit,
                                                  minute_ranges=minute_ranges, cfg=cfg)
        except Exception:
            return None

    # primary: 30 phút — KHÔNG nuốt lỗi (để realtime() xử lý fallback/error khi API down)
    pages = ga4_client.run_realtime_report(["unifiedScreenName"], ["activeUsers"], limit=10, cfg=cfg)
    total = 0
    for r in pages:
        au = int(float(r["metricValues"][0]["value"]))
        total += au
        payload["top_pages"].append({"page": r["dimensionValues"][0]["value"], "active_users": au})
    payload["active_users_30m"] = total

    payload["devices"] = [{"device": r["dimensionValues"][0]["value"],
                           "active_users": int(float(r["metricValues"][0]["value"]))}
                          for r in (safe(["deviceCategory"], ["activeUsers"], 5) or [])]
    payload["top_events"] = [{"event": r["dimensionValues"][0]["value"],
                              "count": int(float(r["metricValues"][0]["value"]))}
                             for r in (safe(["eventName"], ["eventCount"], 10) or [])]

    # 5 phút qua minuteRanges (graceful nếu không hỗ trợ)
    m5 = safe([], ["activeUsers"], None,
              minute_ranges=[{"name": "m5", "startMinutesAgo": 5, "endMinutesAgo": 0}])
    if m5 is not None:
        payload["active_users_5m"] = int(float(m5[0]["metricValues"][0]["value"])) if m5 else 0
        payload["five_minute_state"] = "ok"
    return payload


def _rt_env(payload, stale, cfg, source, fetched_at=None, error=None):
    p = payload or {}
    empty = (payload is None) or (p.get("active_users_30m", 0) == 0 and not p.get("top_pages"))
    return {
        "ok": error is None,
        "data": payload,
        "realtime_source": source,                 # cache | live | cache_fallback | error
        "active_users_30m": p.get("active_users_30m"),
        "active_users_5m": p.get("active_users_5m"),          # null nếu chưa implement / not_available
        "five_minute_state": p.get("five_minute_state", "not_available"),
        "window_minutes": p.get("window_minutes", 30),
        "fetched_at": fetched_at,
        "stale": stale,
        "empty": empty,                            # active_users=0 KHÔNG kết luận "không có khách"
        "tracking_state": "ok",
        "ttl_seconds": int(cfg.get("realtime_cache_ttl_seconds", 60)),
        "error": error,
    }


def realtime(args, force=False):
    cfg = ga4_config.load_config()
    if not ga4_config.config_state()["configured"] or not ga4_client.token_present():
        return {"ok": False, "data": None, "realtime_source": "not_configured",
                "active_users_30m": None, "active_users_5m": None, "window_minutes": 30,
                "stale": True, "empty": True, "tracking_state": "not_configured", "error": "not_configured"}
    conn = db.get_conn()
    key = "default"
    row = conn.execute("SELECT payload_json, fetched_at, expires_at FROM ga4_realtime_cache "
                       "WHERE cache_key=?", (key,)).fetchone()

    def fresh(rw):
        if not rw or not rw["expires_at"]:
            return False
        try:
            return datetime.strptime(rw["expires_at"], "%Y-%m-%d %H:%M:%S") > datetime.now()
        except Exception:
            return False

    if row and fresh(row) and not force:
        payload = json.loads(row["payload_json"])
        conn.close()
        return _rt_env(payload, stale=False, cfg=cfg, source="cache", fetched_at=row["fetched_at"])

    try:
        payload = _fetch_realtime(cfg)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        exp = (datetime.now() + timedelta(seconds=int(cfg.get("realtime_cache_ttl_seconds", 60)))).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO ga4_realtime_cache(cache_key,payload_json,fetched_at,expires_at) VALUES(?,?,?,?) "
            "ON CONFLICT(cache_key) DO UPDATE SET payload_json=excluded.payload_json, "
            "fetched_at=excluded.fetched_at, expires_at=excluded.expires_at",
            (key, json.dumps(payload, ensure_ascii=False), now, exp))
        conn.commit()
        conn.close()
        return _rt_env(payload, stale=False, cfg=cfg, source="live", fetched_at=now)
    except Exception as e:
        err = ga4_client.classify_exception(e).code
        conn.close()
        if row:   # fallback cache cũ
            return _rt_env(json.loads(row["payload_json"]), stale=True, cfg=cfg,
                           source="cache_fallback", fetched_at=row["fetched_at"], error=err)
        return _rt_env(None, stale=True, cfg=cfg, source="error", error=err)
