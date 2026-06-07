# -*- coding: utf-8 -*-
"""SEO × GA4 PERIOD-LEVEL join (Mode B).

GSC cache chỉ có page-level TỔNG KỲ (không date+URL) → KHÔNG daily join.
Join key = normalized_path, kỳ GA4 ALIGN về đúng kỳ GSC cache (derive từ performance.daily).
Refresh = backend (gọi GA4 period-level 1 lần) + lock; render chỉ đọc SQLite.
"""
import os
import json
import hashlib
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

import db
from services import ga4_config, ga4_client
from services.url_normalize import normalize_landing_path
from services.ga4_report_service import classify_page_type

ROOT = Path(__file__).resolve().parent.parent
GSC_CACHE_PATH = ROOT / "data" / "gsc_cache.json"
NORMALIZE_VERSION = "v1"
# _fetch_gsc_cache.py đọc 'Trang'!A2:E2000 → trần sheet 2000 dòng. GSC UI tự cap ~top-1000.
GSC_EXPORT_RANGE_LIMIT = 2000

GA4_METRICS = ["activeUsers", "newUsers", "sessions", "engagedSessions", "engagementRate",
               "screenPageViews", "keyEvents", "ecommercePurchases", "purchaseRevenue"]
_GA4_MAP = {"activeUsers": "ga4_active_users", "newUsers": "ga4_new_users", "sessions": "ga4_sessions",
            "engagedSessions": "ga4_engaged_sessions", "engagementRate": "ga4_engagement_rate",
            "screenPageViews": "ga4_screen_page_views", "keyEvents": "ga4_key_events",
            "ecommercePurchases": "ga4_ecommerce_purchases", "purchaseRevenue": "ga4_purchase_revenue"}
_GA4_SUM = {"ga4_sessions", "ga4_engaged_sessions", "ga4_screen_page_views",
            "ga4_key_events", "ga4_ecommerce_purchases", "ga4_purchase_revenue"}
_GA4_MAX = {"ga4_active_users", "ga4_new_users"}

_lock = threading.Lock()
_run = {"started_at": None}


# ─────────────── GSC cache ───────────────
def load_gsc_cache_meta():
    if not GSC_CACHE_PATH.exists():
        return {"ok": False, "error": "gsc_cache_missing"}
    try:
        c = json.loads(GSC_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "error": "gsc_cache_unreadable:" + str(e)[:60]}
    perf = c.get("performance") or {}
    daily = perf.get("daily") or []
    pages = perf.get("pages") or []
    dates = [r.get("date") for r in daily if r.get("date")]
    df = min(dates) if dates else None
    dt = max(dates) if dates else None
    fetched = c.get("fetched_at")
    age = None
    try:
        fd = datetime.fromisoformat(fetched).date()
        age = (date.today() - fd).days
    except Exception:
        pass
    stale_days = int(ga4_config.load_config().get("gsc_join_stale_days", 7))

    # Export coverage: KHÔNG suy diễn complete nếu không chứng minh được.
    pcount = len(pages)
    pages_imp = sum(r.get("imp", 0) for r in pages)
    daily_imp = sum(r.get("imp", 0) for r in daily)
    imp_cover = (pages_imp / daily_imp) if daily_imp else None
    if pcount >= 1000:                              # chạm cap GSC top-N → chắc chắn bị giới hạn
        scope, complete = "top_pages_limited", False
    elif imp_cover is not None and imp_cover >= 0.99:
        scope, complete = "complete", True
    else:
        scope, complete = "unknown", None
    note = ("pages=%d (cap GSC top-N); impression coverage ~%s%% so true total — long-tail URL có thể thiếu"
            % (pcount, round(imp_cover * 100, 1) if imp_cover is not None else "?"))

    return {"ok": bool(df and dt), "gsc_date_from": df, "gsc_date_to": dt,
            "gsc_fetched_at": fetched, "gsc_cache_age_days": age,
            "gsc_stale": (age is None) or (age > stale_days),
            "pages_count": pcount,
            "gsc_pages_export_count": pcount,
            "gsc_pages_export_limit": GSC_EXPORT_RANGE_LIMIT,
            "gsc_export_scope": scope,
            "gsc_export_complete": complete,
            "gsc_export_note": note,
            "error": None if (df and dt) else "gsc_period_underivable"}


def derive_gsc_period(meta=None):
    meta = meta or load_gsc_cache_meta()
    return meta.get("gsc_date_from"), meta.get("gsc_date_to")


def extract_gsc_pages():
    """Đọc pages tổng kỳ, normalize → aggregate theo normalized_path (collision: sum clicks/imp,
    ctr recompute, position weighted by impressions)."""
    c = json.loads(GSC_CACHE_PATH.read_text(encoding="utf-8"))
    agg = {}
    for r in (c.get("performance") or {}).get("pages") or []:
        url = r.get("url")
        npath = normalize_landing_path(url)
        if npath == "(not set)":
            continue
        clicks = r.get("click") or 0
        imp = r.get("imp") or 0
        pos = r.get("pos") or 0
        s = agg.get(npath)
        if s is None:
            s = {"normalized_path": npath, "full_url": url, "gsc_clicks": 0,
                 "gsc_impressions": 0, "_pos_w": 0.0, "_top_clicks": -1}
            agg[npath] = s
        s["gsc_clicks"] += clicks
        s["gsc_impressions"] += imp
        s["_pos_w"] += pos * imp
        if clicks > s["_top_clicks"]:
            s["_top_clicks"] = clicks
            s["full_url"] = url
    out = {}
    for npath, s in agg.items():
        imp = s["gsc_impressions"]
        out[npath] = {"normalized_path": npath, "full_url": s["full_url"],
                      "gsc_clicks": s["gsc_clicks"], "gsc_impressions": imp,
                      "gsc_ctr": round(s["gsc_clicks"] / imp * 100, 2) if imp else 0.0,
                      "gsc_position": round(s["_pos_w"] / imp, 2) if imp else 0.0}
    return out


# ─────────────── GA4 period-level ───────────────
def fetch_ga4_landing_period(df, dt, cfg=None):
    """Query GA4 landingPage period-level (KHÔNG dùng daily rows) → exact unique users theo kỳ.
    Degrade gracefully nếu metric incompatible. Trả dict normalized_path → metrics."""
    rows, used, _deg = ga4_client.run_report(["landingPage"], GA4_METRICS, df, dt, cfg=cfg)
    used_cols = [_GA4_MAP.get(m, m) for m in used]
    agg = {}
    for r in rows:
        dv = r.get("dimensionValues", [])
        raw = dv[0]["value"] if dv else None
        npath = normalize_landing_path(raw)
        if npath == "(not set)":
            continue
        mv = r.get("metricValues", [])
        vals = {}
        for i, col in enumerate(used_cols):
            try:
                vals[col] = float(mv[i]["value"]) if i < len(mv) else None
            except Exception:
                vals[col] = None
        s = agg.get(npath)
        if s is None:
            s = {c: 0.0 for c in (_GA4_SUM | _GA4_MAX)}
            s["normalized_path"] = npath
            agg[npath] = s
        for c in _GA4_SUM:
            s[c] = (s[c] or 0) + (vals.get(c) or 0)
        for c in _GA4_MAX:
            s[c] = max(s[c] or 0, vals.get(c) or 0)
    for s in agg.values():
        sess = s.get("ga4_sessions") or 0
        eng = s.get("ga4_engaged_sessions") or 0
        s["ga4_engagement_rate"] = round(eng / sess, 4) if sess else 0.0
    return agg


# ─────────────── join + confidence ───────────────
def _confidence(join_status, stale, path_ok, aligned, export_complete):
    # high CHỈ khi: period aligned + GSC fresh + export complete + matched
    if not path_ok or not aligned:
        return "low"
    if join_status == "matched":
        if (not stale) and (export_complete is True):
            return "high"
        return "medium"
    return "medium"   # gsc_only / ga4_only — luôn cap medium


def _opportunity(row, export_complete):
    """Gợi ý NHẸ + priority (chưa task center). ga4_only KHÔNG gọi là 'no organic traffic'
    trừ khi export GSC chứng minh complete."""
    js = row["join_status"]
    sess = row.get("ga4_sessions") or 0
    er = row.get("ga4_engagement_rate") or 0
    imp = row.get("gsc_impressions") or 0
    ctr = row.get("gsc_ctr") or 0
    clk = row.get("gsc_clicks") or 0
    kev = row.get("ga4_key_events") or 0
    if js == "gsc_only":
        # priority tối đa needs_review — cần kiểm tra tracking/redirect/chênh nguồn
        return "gsc_clicks_but_no_ga4_sessions", "needs_review"
    if js == "ga4_only":
        if export_complete is True and sess > 0:
            return "ga4_sessions_without_gsc_clicks", "needs_review"
        # export chưa complete → KHÔNG kết luận URL thiếu organic traffic
        return "ga4_only_needs_review", "needs_review"
    if js == "matched":
        if row.get("page_type") == "build_pc" and sess > 0 and kev == 0:
            return "build_pc_traffic_no_key_event", "medium"
        if imp >= 500 and ctr < 2.0:
            return "impressions_high_ctr_low", "medium"
        if sess >= 50 and er < 0.4:
            return "traffic_high_engagement_low", "medium"
        if clk > 0 and er >= 0.5:
            return "maintain_good_page", "low"
    return "needs_review", "low"


def build_period_join(cfg=None):
    cfg = cfg or ga4_config.load_config()
    meta = load_gsc_cache_meta()
    if not meta.get("ok"):
        return {"ok": False, "error": meta.get("error"), "meta": meta}
    gsc_from, gsc_to = meta["gsc_date_from"], meta["gsc_date_to"]
    gsc = extract_gsc_pages()
    ga4 = fetch_ga4_landing_period(gsc_from, gsc_to, cfg)   # ALIGN kỳ GA4 = kỳ GSC
    aligned = True   # ta luôn align GA4 đúng kỳ GSC
    stale = bool(meta["gsc_stale"])
    export_complete = meta.get("gsc_export_complete")

    keys = set(gsc.keys()) | set(ga4.keys())
    rows = []
    fetched = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for k in keys:
        g, a = gsc.get(k), ga4.get(k)
        js = "matched" if (g and a) else ("gsc_only" if g else "ga4_only")
        path_ok = bool(k) and k != "(not set)"
        row = {
            "normalized_path": k,
            "full_url": (g or {}).get("full_url") or ("https://sintech.vn" + k if k.startswith("/") else None),
            "page_type": classify_page_type(k),
            "join_status": js,
            "gsc_clicks": (g or {}).get("gsc_clicks"), "gsc_impressions": (g or {}).get("gsc_impressions"),
            "gsc_ctr": (g or {}).get("gsc_ctr"), "gsc_position": (g or {}).get("gsc_position"),
            "ga4_sessions": (a or {}).get("ga4_sessions"), "ga4_active_users": (a or {}).get("ga4_active_users"),
            "ga4_new_users": (a or {}).get("ga4_new_users"), "ga4_engaged_sessions": (a or {}).get("ga4_engaged_sessions"),
            "ga4_engagement_rate": (a or {}).get("ga4_engagement_rate"), "ga4_screen_page_views": (a or {}).get("ga4_screen_page_views"),
            "ga4_key_events": (a or {}).get("ga4_key_events"), "ga4_ecommerce_purchases": (a or {}).get("ga4_ecommerce_purchases"),
            "ga4_purchase_revenue": (a or {}).get("ga4_purchase_revenue"),
            "fetched_at": fetched,
        }
        opp, prio = _opportunity(row, export_complete)
        row["opportunity_type"] = opp
        row["priority"] = prio
        row["tracking_confidence"] = _confidence(js, stale, path_ok, aligned, export_complete)
        rows.append(row)

    return {"ok": True, "meta": meta, "ga4_period": [gsc_from, gsc_to],
            "aligned": aligned, "cache_key": _cache_key(meta, cfg), "rows": rows}


def _cache_key(meta, cfg):
    prop = str(cfg.get("property_id") or "")
    raw = "|".join([str(meta.get("gsc_date_from")), str(meta.get("gsc_date_to")),
                    str(meta.get("gsc_fetched_at")), prop, NORMALIZE_VERSION])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ─────────────── persist + refresh ───────────────
def _persist(conn, built):
    key = built["cache_key"]
    meta, gp = built["meta"], built["ga4_period"]
    conn.execute("DELETE FROM ga4_seo_landing_join_period WHERE cache_key=?", (key,))
    cols = ["cache_key", "gsc_date_from", "gsc_date_to", "gsc_fetched_at", "ga4_date_from", "ga4_date_to",
            "normalized_path", "full_url", "page_type", "join_status",
            "gsc_clicks", "gsc_impressions", "gsc_ctr", "gsc_position",
            "ga4_sessions", "ga4_active_users", "ga4_new_users", "ga4_engaged_sessions",
            "ga4_engagement_rate", "ga4_screen_page_views", "ga4_key_events",
            "ga4_ecommerce_purchases", "ga4_purchase_revenue",
            "opportunity_type", "priority", "tracking_confidence", "fetched_at"]
    ph = ",".join("?" for _ in cols)
    for r in built["rows"]:
        base = {"cache_key": key, "gsc_date_from": meta["gsc_date_from"], "gsc_date_to": meta["gsc_date_to"],
                "gsc_fetched_at": meta["gsc_fetched_at"], "ga4_date_from": gp[0], "ga4_date_to": gp[1]}
        base.update(r)
        conn.execute("INSERT INTO ga4_seo_landing_join_period (%s) VALUES (%s)" % (",".join(cols), ph),
                     [base.get(c) for c in cols])
    return len(built["rows"])


def refresh_period_join(cfg=None):
    cfg = cfg or ga4_config.load_config()
    if not ga4_config.config_state()["configured"] or not ga4_client.token_present():
        return {"ok": False, "error": "not_configured"}
    conn = db.get_conn()
    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("INSERT INTO ga4_sync_runs (sync_type,status,started_at,created_at) VALUES (?,?,?,?)",
                       ("seo_join", "running", started, started))
    run_id = cur.lastrowid
    conn.commit()
    try:
        built = build_period_join(cfg)
        if not built.get("ok"):
            raise RuntimeError(built.get("error") or "build_failed")
        n = _persist(conn, built)
        conn.commit()
        conn.execute("UPDATE ga4_sync_runs SET status=?,rows_written=?,finished_at=?,latest_data_date=? WHERE id=?",
                     ("success", n, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), built["meta"]["gsc_date_to"], run_id))
        conn.commit()
        conn.close()
        return {"ok": True, "run_id": run_id, "rows_written": n, "cache_key": built["cache_key"],
                "ga4_period": built["ga4_period"], "meta": built["meta"]}
    except Exception as e:
        try:
            err = ga4_client.classify_exception(e).code
        except Exception:
            err = str(e)[:80]
        conn.execute("UPDATE ga4_sync_runs SET status=?,finished_at=?,error_message=? WHERE id=?",
                     ("error", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), err, run_id))
        conn.commit()
        conn.close()
        return {"ok": False, "error": err, "run_id": run_id}


def start_refresh_async():
    if not _lock.acquire(blocking=False):
        return {"started": False, "reason": "already_running", "started_at": _run["started_at"]}
    _run["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _w():
        try:
            refresh_period_join()
        except Exception:
            pass
        finally:
            _run["started_at"] = None
            _lock.release()

    threading.Thread(target=_w, daemon=True).start()
    return {"started": True, "started_at": _run["started_at"]}


def is_running():
    return _lock.locked()


# ─────────────── read (render) ───────────────
_SORT = {"gsc_clicks", "gsc_impressions", "gsc_ctr", "gsc_position", "ga4_sessions",
         "ga4_active_users", "ga4_engagement_rate", "ga4_key_events", "ga4_purchase_revenue"}


def _latest_key(conn):
    r = conn.execute("SELECT cache_key FROM ga4_seo_landing_join_period ORDER BY fetched_at DESC, id DESC LIMIT 1").fetchone()
    return r["cache_key"] if r else None


def list_period_join(args):
    conn = db.get_conn()
    key = _latest_key(conn)
    if not key:
        conn.close()
        return {"ok": True, "data": [], "total_rows": 0, "status": get_join_status(), "empty": True}
    where, params = ["cache_key=?"], [key]
    if args.get("page_type"):
        where.append("page_type=?"); params.append(args["page_type"])
    if args.get("join_status"):
        where.append("join_status=?"); params.append(args["join_status"])
    if args.get("priority"):
        where.append("priority=?"); params.append(args["priority"])
    if args.get("search"):
        where.append("(normalized_path LIKE ? OR full_url LIKE ?)")
        kw = "%" + args["search"] + "%"; params += [kw, kw]
    sort = args.get("sort") if args.get("sort") in _SORT else "gsc_clicks"
    order = "ASC" if str(args.get("order", "desc")).lower() == "asc" else "DESC"
    try:
        limit = max(0, min(int(args.get("limit", 50)), 1000))
    except Exception:
        limit = 50
    try:
        offset = max(0, int(args.get("offset", 0)))
    except Exception:
        offset = 0
    wsql = " AND ".join(where)
    total = conn.execute("SELECT COUNT(*) FROM ga4_seo_landing_join_period WHERE " + wsql, params).fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM ga4_seo_landing_join_period WHERE %s ORDER BY %s %s LIMIT ? OFFSET ?" % (wsql, sort, order),
        params + [limit, offset]).fetchall()
    conn.close()
    return {"ok": True, "data": [dict(r) for r in rows], "total_rows": total,
            "limit": limit, "offset": offset, "status": get_join_status(),
            "filters": {"page_type": args.get("page_type"), "join_status": args.get("join_status"),
                        "priority": args.get("priority"), "search": args.get("search")}}


def get_join_status():
    meta = load_gsc_cache_meta()
    conn = db.get_conn()
    key = _latest_key(conn)
    counts = {"matched": 0, "gsc_only": 0, "ga4_only": 0}
    conf = {"high": 0, "medium": 0, "low": 0}
    ga4_period = [None, None]
    last_refresh = None
    if key:
        for r in conn.execute("SELECT join_status, COUNT(*) n FROM ga4_seo_landing_join_period WHERE cache_key=? GROUP BY join_status", (key,)):
            counts[r["join_status"]] = r["n"]
        for r in conn.execute("SELECT tracking_confidence, COUNT(*) n FROM ga4_seo_landing_join_period WHERE cache_key=? GROUP BY tracking_confidence", (key,)):
            if r["tracking_confidence"] in conf:
                conf[r["tracking_confidence"]] = r["n"]
        row = conn.execute("SELECT ga4_date_from, ga4_date_to, fetched_at FROM ga4_seo_landing_join_period WHERE cache_key=? LIMIT 1", (key,)).fetchone()
        if row:
            ga4_period = [row["ga4_date_from"], row["ga4_date_to"]]
            last_refresh = row["fetched_at"]
    conn.close()
    total = sum(counts.values())

    warnings = []
    if meta.get("gsc_stale"):
        warnings.append("GSC cache đang cũ (%s ngày)" % meta.get("gsc_cache_age_days"))
    if meta.get("gsc_export_complete") is not True:
        warnings.append("GSC page export có thể không bao phủ toàn bộ URL (%s)" % meta.get("gsc_export_scope"))
    warnings.append("GA4-only không đồng nghĩa URL không có organic traffic")
    warnings.append("Insight là period-level, không phải daily join")

    return {
        "join_mode": "period_level", "normalize_version": NORMALIZE_VERSION,
        "gsc_date_from": meta.get("gsc_date_from"), "gsc_date_to": meta.get("gsc_date_to"),
        "gsc_fetched_at": meta.get("gsc_fetched_at"), "gsc_cache_age_days": meta.get("gsc_cache_age_days"),
        "gsc_stale": meta.get("gsc_stale"),
        "gsc_pages_export_count": meta.get("gsc_pages_export_count"),
        "gsc_pages_export_limit": meta.get("gsc_pages_export_limit"),
        "gsc_export_scope": meta.get("gsc_export_scope"),
        "gsc_export_complete": meta.get("gsc_export_complete"),
        "gsc_export_note": meta.get("gsc_export_note"),
        "ga4_date_from": ga4_period[0], "ga4_date_to": ga4_period[1], "period_aligned": True,
        "join_rows": total, "join_counts": counts,
        "matched_count": counts["matched"], "gsc_only_count": counts["gsc_only"], "ga4_only_count": counts["ga4_only"],
        "confidence_distribution": conf, "last_refresh": last_refresh,
        "is_running": is_running(), "has_cache": bool(key),
        "warning": warnings,
        "ok": meta.get("ok", False), "error": meta.get("error"),
    }
