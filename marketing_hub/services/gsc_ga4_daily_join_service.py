# -*- coding: utf-8 -*-
"""SEO × GA4 daily-aligned partial-coverage join (organic v1).

gsc_pages_daily (Search Console API, top rows) ⋈ ga4_landing_pages_channel_daily (Organic Search)
ON date + normalized_path. GA4 all-channel sessions chỉ là metric PHỤ tham khảo.
KHÔNG exact / full / clicks=sessions. max_confidence = medium. Fallback Mode B period-level (Sheet) riêng.
"""
import json
import threading
from datetime import date, datetime, timedelta

import db
from services import gsc_api_client, gsc_sync_service
from services import ga4_channel_landing_sync_service as ga4ch
from services.ga4_report_service import classify_page_type

JOIN_MODE = "daily_aligned_partial_coverage"
GSC_SOURCE_MODE = "search_console_api"
GSC_COVERAGE_MODE = "api_top_rows"
GSC_TZ, GA4_TZ = "PT", "Asia/Ho_Chi_Minh"
TZ_ALIGN = "different_calendar_day_boundaries"
CLICKS_SESSIONS = "directional_only"
MAX_CONFIDENCE = "medium"
STATUS_KEY = "default"

_lock = threading.Lock()
_run = {"started_at": None, "sync_type": None}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _cfg():
    return gsc_api_client.load_config()


def is_running():
    return _lock.locked()


# ─────────────── join row build ───────────────
def _opportunity(js, page_type, clk, imp, ctr, sess, er, kev):
    if js == "gsc_only":
        return "gsc_only_needs_review", "needs_review"
    if js == "ga4_only":
        return "ga4_organic_only_needs_review", "needs_review"
    # matched
    if page_type == "build_pc" and sess > 0 and kev == 0:
        return "build_pc_organic_no_key_event", "medium"
    if imp >= 500 and ctr < 2.0:
        return "impressions_high_ctr_low", "medium"
    if sess >= 30 and er < 0.4:
        return "organic_clicks_high_engagement_low", "medium"
    if clk > 0 and er >= 0.5:
        return "maintain_page", "low"
    return "needs_review", "low"


def _confidence(js, path_ok, in_overlap):
    if not path_ok or not in_overlap:
        return "low"
    return "medium" if js == "matched" else "low"   # KHÔNG high


def build_join(date_from, date_to, cfg):
    """Full outer join gsc_pages_daily(web) × ga4 organic landing trong [date_from,date_to]."""
    ver = cfg.get("seo_join_version", "daily-organic-v1")
    conn = db.get_conn()
    gsc = {}
    for r in conn.execute("SELECT date,normalized_path,full_url,clicks,impressions,ctr,position "
                          "FROM gsc_pages_daily WHERE search_type='web' AND date BETWEEN ? AND ?",
                          (date_from, date_to)):
        gsc[(r["date"], r["normalized_path"])] = dict(r)
    org = {}
    for r in conn.execute("SELECT date,normalized_path,sessions,active_users,new_users,engaged_sessions,"
                          "engagement_rate,screen_page_views,key_events,ecommerce_purchases,purchase_revenue "
                          "FROM ga4_landing_pages_channel_daily WHERE session_default_channel_group='Organic Search' "
                          "AND date BETWEEN ? AND ?", (date_from, date_to)):
        org[(r["date"], r["normalized_path"])] = dict(r)
    allses = {}
    for r in conn.execute("SELECT date,normalized_path,sessions FROM ga4_landing_pages_daily "
                          "WHERE date BETWEEN ? AND ?", (date_from, date_to)):
        allses[(r["date"], r["normalized_path"])] = r["sessions"]
    conn.close()

    keys = set(gsc) | set(org)
    fetched = _now()
    rows, counts = [], {"matched": 0, "gsc_only": 0, "ga4_only": 0}
    conf_dist = {"medium": 0, "low": 0}
    for (d, npath) in keys:
        g, a = gsc.get((d, npath)), org.get((d, npath))
        js = "matched" if (g and a) else ("gsc_only" if g else "ga4_only")
        counts[js] += 1
        path_ok = bool(npath) and npath != "(not set)"
        clk = (g or {}).get("clicks") or 0
        imp = (g or {}).get("impressions") or 0
        ctr = (g or {}).get("ctr") or 0
        sess = (a or {}).get("sessions") or 0
        er = (a or {}).get("engagement_rate") or 0
        kev = (a or {}).get("key_events") or 0
        pt = classify_page_type(npath)
        opp, prio = _opportunity(js, pt, clk, imp, ctr, sess, er, kev)
        cf = _confidence(js, path_ok, in_overlap=True)
        conf_dist[cf] = conf_dist.get(cf, 0) + 1
        rows.append({
            "date": d, "normalized_path": npath, "search_type": "web", "join_version": ver,
            "full_url": (g or {}).get("full_url") or ("https://sintech.vn" + npath if npath.startswith("/") else None),
            "page_type": pt, "join_status": js,
            "gsc_clicks": (g or {}).get("clicks"), "gsc_impressions": (g or {}).get("impressions"),
            "gsc_ctr": (g or {}).get("ctr"), "gsc_position": (g or {}).get("position"),
            "ga4_organic_sessions": (a or {}).get("sessions"), "ga4_organic_active_users": (a or {}).get("active_users"),
            "ga4_organic_new_users": (a or {}).get("new_users"), "ga4_organic_engaged_sessions": (a or {}).get("engaged_sessions"),
            "ga4_organic_engagement_rate": (a or {}).get("engagement_rate"),
            "ga4_organic_screen_page_views": (a or {}).get("screen_page_views"),
            "ga4_organic_key_events": (a or {}).get("key_events"),
            "ga4_organic_ecommerce_purchases": (a or {}).get("ecommerce_purchases"),
            "ga4_organic_purchase_revenue": (a or {}).get("purchase_revenue"),
            "ga4_all_sessions": allses.get((d, npath)),
            "opportunity_type": opp, "priority": prio, "tracking_confidence": cf,
            "gsc_source_mode": GSC_SOURCE_MODE, "gsc_coverage_mode": GSC_COVERAGE_MODE, "gsc_coverage_complete": 0,
            "gsc_timezone": GSC_TZ, "ga4_timezone": GA4_TZ, "timezone_alignment": TZ_ALIGN,
            "clicks_sessions_comparable": CLICKS_SESSIONS, "fetched_at": fetched,
        })
    return {"rows": rows, "counts": counts, "conf_dist": conf_dist, "version": ver}


def _persist(conn, built, over_from, over_to):
    ver = built["version"]
    conn.execute("DELETE FROM gsc_ga4_join_daily WHERE join_version=? AND date BETWEEN ? AND ?",
                 (ver, over_from, over_to))
    cols = list(built["rows"][0].keys()) if built["rows"] else []
    if cols:
        ph = ",".join("?" for _ in cols)
        for r in built["rows"]:
            conn.execute("INSERT INTO gsc_ga4_join_daily (%s) VALUES (%s)" % (",".join(cols), ph),
                         [r[c] for c in cols])
    return len(built["rows"])


# ─────────────── refresh ───────────────
def refresh_join(sync_type="incremental"):
    cfg = _cfg()
    if not gsc_api_client.config_state()["configured"] or not gsc_api_client.token_present():
        return {"ok": False, "error": "not_configured"}
    conn = db.get_conn()
    n_gsc = conn.execute("SELECT COUNT(*) FROM gsc_pages_daily WHERE search_type='web'").fetchone()[0]
    latest_gsc = conn.execute("SELECT MAX(date) FROM gsc_pages_daily WHERE search_type='web'").fetchone()[0]
    started = _now()
    cur = conn.execute("INSERT INTO gsc_ga4_join_runs (join_version,sync_type,channel_group,status,started_at,created_at) "
                       "VALUES (?,?,?,?,?,?)", (cfg.get("seo_join_version"), sync_type, "Organic Search", "running", started, started))
    run_id = cur.lastrowid
    conn.commit()
    conn.close()

    fatal, warnings = None, []
    counts = {"matched": 0, "gsc_only": 0, "ga4_only": 0}
    conf_dist = {"medium": 0, "low": 0}
    over_from = over_to = latest_ga4 = None
    rows_written = 0
    try:
        if not n_gsc or not latest_gsc:
            raise RuntimeError("no_gsc_daily_rows")
        end = datetime.fromisoformat(latest_gsc).date()
        days = int(cfg.get("seo_join_initial_backfill_days", 90)) if sync_type == "backfill" \
            else int(cfg.get("seo_join_incremental_lookback_days", 7))
        start = end - timedelta(days=max(0, days - 1))
        # 1. sync GA4 organic landing cho window
        ga4ch.sync_organic_landing(start.isoformat(), end.isoformat(), cfg)
        # 2. derive overlap thật giữa GSC daily & GA4 organic daily
        conn = db.get_conn()
        g_dates = [r[0] for r in conn.execute(
            "SELECT DISTINCT date FROM gsc_pages_daily WHERE search_type='web' AND date BETWEEN ? AND ?",
            (start.isoformat(), end.isoformat()))]
        a_dates = [r[0] for r in conn.execute(
            "SELECT DISTINCT date FROM ga4_landing_pages_channel_daily WHERE session_default_channel_group='Organic Search' "
            "AND date BETWEEN ? AND ?", (start.isoformat(), end.isoformat()))]
        latest_ga4 = max(a_dates) if a_dates else None
        conn.close()
        if not g_dates or not a_dates:
            warnings.append("Chưa đủ overlap GSC×GA4 organic — join rỗng.")
            over_from = over_to = None
        else:
            over_from = max(min(g_dates), min(a_dates))
            over_to = min(max(g_dates), max(a_dates))
            if over_from > over_to:
                warnings.append("Không có ngày overlap giữa GSC và GA4 organic.")
                over_from = over_to = None
        if over_from and over_to:
            built = build_join(over_from, over_to, cfg)
            counts, conf_dist = built["counts"], built["conf_dist"]
            conn = db.get_conn()
            rows_written = _persist(conn, built, over_from, over_to)
            conn.commit()
            conn.close()
    except Exception as e:
        fatal = str(e)[:120]
    finally:
        warnings += ["Daily-aligned partial coverage (API top rows) — directional comparison, không exact.",
                     "Search Console dùng PT, GA4 dùng Asia/Ho_Chi_Minh — có thể lệch nhẹ ở ranh giới ngày."]
        status = "error" if fatal else "success"
        conn = db.get_conn()
        conn.execute("UPDATE gsc_ga4_join_runs SET date_from=?,date_to=?,search_type=?,status=?,rows_written=?,"
                     "matched_count=?,gsc_only_count=?,ga4_only_count=?,latest_gsc_date=?,latest_ga4_date=?,"
                     "overlap_date_from=?,overlap_date_to=?,warning_json=?,error_type=?,error_message=?,finished_at=? WHERE id=?",
                     (over_from, over_to, "web", status, rows_written, counts["matched"], counts["gsc_only"],
                      counts["ga4_only"], latest_gsc, latest_ga4, over_from, over_to,
                      json.dumps(warnings, ensure_ascii=False), ("error" if fatal else None), fatal, _now(), run_id))
        _write_status(conn, cfg, latest_gsc, latest_ga4, over_from, over_to, counts, conf_dist,
                      success=(fatal is None), err=fatal, warnings=warnings)
        conn.commit()
        conn.close()
    return {"ok": fatal is None, "run_id": run_id, "status": status, "rows_written": rows_written,
            "matched": counts["matched"], "gsc_only": counts["gsc_only"], "ga4_only": counts["ga4_only"],
            "overlap": [over_from, over_to], "error": fatal}


def _write_status(conn, cfg, latest_gsc, latest_ga4, over_from, over_to, counts, conf_dist, success, err, warnings):
    prev = conn.execute("SELECT last_success_at,last_failure_at FROM gsc_ga4_join_status WHERE status_key=?",
                        (STATUS_KEY,)).fetchone()
    last_success = _now() if success else (prev["last_success_at"] if prev else None)
    last_failure = (prev["last_failure_at"] if (success and prev) else (_now() if not success else (prev["last_failure_at"] if prev else None)))
    overlap_days = 0
    if over_from and over_to:
        try:
            overlap_days = (datetime.fromisoformat(over_to).date() - datetime.fromisoformat(over_from).date()).days + 1
        except Exception:
            pass
    data = {
        "status_key": STATUS_KEY, "join_version": cfg.get("seo_join_version"), "join_mode": JOIN_MODE,
        "source_mode": GSC_SOURCE_MODE, "fallback_available": 1, "search_type": "web", "channel_group": "Organic Search",
        "latest_gsc_date": latest_gsc, "latest_ga4_date": latest_ga4,
        "overlap_date_from": over_from, "overlap_date_to": over_to, "overlap_days": overlap_days,
        "matched_count": counts["matched"], "gsc_only_count": counts["gsc_only"], "ga4_only_count": counts["ga4_only"],
        "confidence_distribution_json": json.dumps(conf_dist), "warning_json": json.dumps(warnings, ensure_ascii=False),
        "last_success_at": last_success, "last_failure_at": last_failure,
        "last_error_type": ("error" if err else None), "last_error_message_safe": err,
        "sync_running": 1 if is_running() else 0, "sync_started_at": _run.get("started_at"), "updated_at": _now()}
    cols = list(data.keys())
    ph = ",".join("?" for _ in cols)
    upd = ",".join("%s=excluded.%s" % (c, c) for c in cols if c != "status_key")
    conn.execute("INSERT INTO gsc_ga4_join_status (%s) VALUES (%s) ON CONFLICT(status_key) DO UPDATE SET %s"
                 % (",".join(cols), ph, upd), [data[c] for c in cols])


def start_refresh_async(sync_type="incremental"):
    if not _lock.acquire(blocking=False):
        return {"started": False, "reason": "already_running", "started_at": _run["started_at"], "sync_type": _run["sync_type"]}
    _run["started_at"] = _now()
    _run["sync_type"] = sync_type

    def _w():
        try:
            refresh_join(sync_type)
        except Exception:
            pass
        finally:
            _run["started_at"] = None
            _run["sync_type"] = None
            _lock.release()
    threading.Thread(target=_w, daemon=True).start()
    return {"started": True, "started_at": _run["started_at"], "sync_type": sync_type}


def reconcile_stale_runs(max_minutes=30):
    conn = db.get_conn()
    fixed = 0
    for r in conn.execute("SELECT id, started_at FROM gsc_ga4_join_runs WHERE status='running'").fetchall():
        old = True
        try:
            old = (datetime.now() - datetime.strptime(r["started_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() > max_minutes * 60
        except Exception:
            old = True
        if old:
            conn.execute("UPDATE gsc_ga4_join_runs SET status='error',error_type='stale',finished_at=? WHERE id=?", (_now(), r["id"]))
            fixed += 1
    conn.commit()
    conn.close()
    return fixed


# ─────────────── read ───────────────
_SORT = {"gsc_clicks", "gsc_impressions", "gsc_ctr", "gsc_position",
         "ga4_organic_sessions", "ga4_organic_active_users", "ga4_organic_engagement_rate",
         "ga4_organic_key_events", "ga4_organic_purchase_revenue", "ga4_all_sessions"}


def list_join(args):
    cfg = _cfg()
    ver = cfg.get("seo_join_version")
    conn = db.get_conn()
    where, params = ["join_version=?"], [ver]
    for k, col in (("page_type", "page_type"), ("join_status", "join_status"),
                   ("opportunity", "opportunity_type"), ("confidence", "tracking_confidence")):
        if args.get(k):
            where.append(col + "=?"); params.append(args[k])
    if args.get("date_from") and args.get("date_to"):
        where.append("date BETWEEN ? AND ?"); params += [args["date_from"], args["date_to"]]
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
    total = conn.execute("SELECT COUNT(*) FROM gsc_ga4_join_daily WHERE " + wsql, params).fetchone()[0]
    rows = conn.execute("SELECT * FROM gsc_ga4_join_daily WHERE %s ORDER BY %s %s LIMIT ? OFFSET ?" % (wsql, sort, order),
                        params + [limit, offset]).fetchall()
    conn.close()
    return {"ok": True, "data": [dict(r) for r in rows], "total_rows": total, "limit": limit, "offset": offset,
            "max_confidence": MAX_CONFIDENCE, "join_mode": JOIN_MODE,
            "filters": {k: args.get(k) for k in ("page_type", "join_status", "opportunity", "confidence", "search")}}


def get_status():
    conn = db.get_conn()
    st = conn.execute("SELECT * FROM gsc_ga4_join_status WHERE status_key=?", (STATUS_KEY,)).fetchone()
    have = conn.execute("SELECT COUNT(*) FROM gsc_ga4_join_daily").fetchone()[0]
    conn.close()
    st = dict(st) if st else {}
    daily_available = have > 0 and bool(st.get("overlap_date_from"))
    warnings = json.loads(st.get("warning_json") or "[]") if st.get("warning_json") else []
    return {
        "ok": True, "join_mode": JOIN_MODE, "max_confidence": MAX_CONFIDENCE,
        "source_mode": GSC_SOURCE_MODE, "gsc_coverage_mode": GSC_COVERAGE_MODE, "gsc_coverage_complete": False,
        "gsc_timezone": GSC_TZ, "ga4_timezone": GA4_TZ, "timezone_alignment": TZ_ALIGN,
        "clicks_sessions_comparable": CLICKS_SESSIONS,
        "join_version": st.get("join_version"), "search_type": st.get("search_type"),
        "channel_group": st.get("channel_group"),
        "latest_gsc_date": st.get("latest_gsc_date"), "latest_ga4_date": st.get("latest_ga4_date"),
        "overlap_date_from": st.get("overlap_date_from"), "overlap_date_to": st.get("overlap_date_to"),
        "overlap_days": st.get("overlap_days"),
        "matched_count": st.get("matched_count"), "gsc_only_count": st.get("gsc_only_count"),
        "ga4_only_count": st.get("ga4_only_count"),
        "confidence_distribution": json.loads(st.get("confidence_distribution_json") or "{}") if st.get("confidence_distribution_json") else {},
        "daily_available": daily_available, "fallback_available": True,
        "fallback_mode": "sheet_period_level", "fallback_route": "/api/ga4/seo-join",
        "last_success_at": st.get("last_success_at"), "last_failure_at": st.get("last_failure_at"),
        "last_error_type": st.get("last_error_type"), "last_error_message_safe": st.get("last_error_message_safe"),
        "sync_running": is_running(), "sync_started_at": _run.get("started_at"),
        "warning": warnings,
    }
