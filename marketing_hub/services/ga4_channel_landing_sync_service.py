# -*- coding: utf-8 -*-
"""GA4 landing × channel daily cache — sync landing page theo sessionDefaultChannelGroup.

Phase đầu chỉ sync channel cần cho SEO join (Organic Search). Bảng general
ga4_landing_pages_channel_daily tái dùng cho channel khác sau (Direct/Social/...).
KHÔNG sửa ga4_landing_pages_daily (all-channel) — đó là metric phụ.
"""
from datetime import date, datetime, timedelta

import db
from services import ga4_client, gsc_api_client
from services.url_normalize import normalize_landing_path

GA4_CH_METRICS = ["activeUsers", "newUsers", "sessions", "engagedSessions", "engagementRate",
                  "screenPageViews", "keyEvents", "ecommercePurchases", "purchaseRevenue"]
_MAP = {"activeUsers": "active_users", "newUsers": "new_users", "sessions": "sessions",
        "engagedSessions": "engaged_sessions", "engagementRate": "engagement_rate",
        "screenPageViews": "screen_page_views", "keyEvents": "key_events",
        "ecommercePurchases": "ecommerce_purchases", "purchaseRevenue": "purchase_revenue"}
_SUM = {"sessions", "engaged_sessions", "screen_page_views", "key_events", "ecommerce_purchases", "purchase_revenue"}
_MAX = {"active_users", "new_users"}   # user-scoped: MAX fallback khi normalized collision (xấp xỉ)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _num(col, v):
    try:
        return float(v) if col == "engagement_rate" else int(round(float(v)))
    except Exception:
        return None


def _upsert(conn, data):
    cols = list(data.keys())
    ph = ",".join("?" for _ in cols)
    pk = ["date", "normalized_path", "session_default_channel_group"]
    upd = ",".join("%s=excluded.%s" % (c, c) for c in cols if c not in pk)
    conn.execute("INSERT INTO ga4_landing_pages_channel_daily (%s) VALUES (%s) "
                 "ON CONFLICT(date,normalized_path,session_default_channel_group) DO UPDATE SET %s"
                 % (",".join(cols), ph, upd), [data[c] for c in cols])


def _sync_day_channel(conn, ds, channel, cfg, fetched):
    """Query GA4 1 ngày, filter channel, dims=[landingPage]. Normalize + aggregate collision."""
    flt = ga4_client.dimension_filter_eq("sessionDefaultChannelGroup", channel)
    # cfg=None → ga4_client tự load GA4 config (property_id). cfg ở đây là GSC config (channel/lookback).
    rows, used, _deg = ga4_client.run_report(["landingPage"], GA4_CH_METRICS, ds, ds,
                                             dimension_filter=flt, cfg=None)
    used_cols = [_MAP.get(m, m) for m in used]
    agg = {}
    for r in rows:
        dv = r.get("dimensionValues", [])
        raw = dv[0]["value"] if dv else None
        npath = normalize_landing_path(raw)
        if npath == "(not set)":
            continue
        mv = r.get("metricValues", [])
        vals = {used_cols[i]: _num(used_cols[i], mv[i]["value"]) for i in range(len(used_cols)) if i < len(mv)}
        slot = agg.get(npath)
        if slot is None:
            slot = {"landing_page_raw": raw}
            for c in _SUM | _MAX:
                slot[c] = 0
            agg[npath] = slot
        for c in _SUM:
            slot[c] = (slot[c] or 0) + (vals.get(c) or 0)
        for c in _MAX:
            slot[c] = max(slot[c] or 0, vals.get(c) or 0)
    n = 0
    for npath, slot in agg.items():
        sess = slot.get("sessions") or 0
        eng = slot.get("engaged_sessions") or 0
        data = {"date": ds, "normalized_path": npath, "session_default_channel_group": channel,
                "landing_page_raw": slot["landing_page_raw"],
                "engagement_rate": round(eng / sess, 4) if sess else 0.0, "fetched_at": fetched}
        for c in _SUM | _MAX:
            data[c] = slot.get(c)
        _upsert(conn, data)
        n += 1
    return n


def sync_organic_landing(date_from, date_to, cfg=None):
    """Sync landing × channel cho window [date_from,date_to]. Trả (rows, channels)."""
    cfg = cfg or gsc_api_client.load_config()
    channels = cfg.get("seo_join_channel_groups", ["Organic Search"])
    fetched = _now()
    conn = db.get_conn()
    total = 0
    try:
        start = datetime.fromisoformat(date_from).date()
        end = datetime.fromisoformat(date_to).date()
        for ch in channels:
            d = start
            while d <= end:
                total += _sync_day_channel(conn, d.isoformat(), ch, cfg, fetched)
                conn.commit()      # checkpoint per-day
                d += timedelta(days=1)
        return {"ok": True, "rows": total, "channels": channels}
    finally:
        conn.close()
