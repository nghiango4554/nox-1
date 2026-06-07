# -*- coding: utf-8 -*-
"""GSC direct API daily sync — pull Search Console → SQLite (idempotent) + sync log.

Sync THEO TỪNG NGÀY (checkpoint per-day, resume được), per search_type. Mỗi ngày query
5 report riêng (summary/pages/queries/devices/countries) — KHÔNG nhồi [date,page] một cục.
coverage_complete LUÔN false (API top rows). Fallback Sheet cache khi API lỗi (nếu config bật).
"""
import json
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

import db
from services import gsc_api_client as gsc
from services.gsc_api_client import GSCError, SOURCE_MODE, COVERAGE_MODE
from services.url_normalize import normalize_landing_path

ROOT = Path(__file__).resolve().parent.parent
SHEET_CACHE = ROOT / "data" / "gsc_cache.json"

# Lỗi auth/quyền/quota → abort cả run. temporary/api_error → ghi partial theo ngày, chạy tiếp.
_FATAL = {"token_expired", "reconnect_required", "permission_denied", "wrong_property",
          "quota_exceeded", "token_missing"}
_lock = threading.Lock()
_run = {"started_at": None, "sync_type": None}
STALE_MINUTES = 30


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _i(v):
    try:
        return int(round(float(v)))
    except Exception:
        return None


def _f(v):
    try:
        return float(v)
    except Exception:
        return None


def _upsert(conn, table, pk, data):
    cols = list(data.keys())
    ph = ",".join("?" for _ in cols)
    upd = ",".join("%s=excluded.%s" % (c, c) for c in cols if c not in pk)
    conn.execute("INSERT INTO %s (%s) VALUES (%s) ON CONFLICT(%s) DO UPDATE SET %s"
                 % (table, ",".join(cols), ph, ",".join(pk), upd), [data[c] for c in cols])


# ─────────────── latest available date ───────────────
def find_latest_available_date(cfg):
    """GSC trễ 2-3 ngày → KHÔNG assume hôm qua có data. Query summary dims=[date] 10 ngày gần nhất."""
    today = date.today()
    stype = (cfg.get("search_types") or ["web"])[0]
    rows = gsc.query_search_analytics((today - timedelta(days=11)).isoformat(), today.isoformat(),
                                      ["date"], stype, cfg=cfg)
    dates = [r["keys"][0] for r in rows if (r.get("clicks") or r.get("impressions"))]
    return max(dates) if dates else None


# ─────────────── per-day sync ───────────────
def _day_done(conn, ds, stype):
    return conn.execute("SELECT 1 FROM gsc_daily_summary WHERE date=? AND search_type=?",
                        (ds, stype)).fetchone() is not None


def _sync_day(conn, ds, stype, cfg, fetched):
    n = 0
    # summary (no dimension)
    srows = gsc.query_search_analytics(ds, ds, [], stype, cfg=cfg)
    if srows:
        r = srows[0]
        _upsert(conn, "gsc_daily_summary", ["date", "search_type"], {
            "date": ds, "search_type": stype, "clicks": _i(r.get("clicks")),
            "impressions": _i(r.get("impressions")), "ctr": _f(r.get("ctr")),
            "position": _f(r.get("position")), "fetched_at": fetched})
        n += 1
    # pages (top rows)
    for r in gsc.query_search_analytics(ds, ds, ["page"], stype, cfg=cfg):
        url = r["keys"][0]
        npath = normalize_landing_path(url)
        if npath == "(not set)":
            continue
        _upsert(conn, "gsc_pages_daily", ["date", "normalized_path", "search_type"], {
            "date": ds, "normalized_path": npath, "search_type": stype, "full_url": url,
            "clicks": _i(r.get("clicks")), "impressions": _i(r.get("impressions")),
            "ctr": _f(r.get("ctr")), "position": _f(r.get("position")), "fetched_at": fetched})
        n += 1
    # queries (top rows)
    for r in gsc.query_search_analytics(ds, ds, ["query"], stype, cfg=cfg):
        _upsert(conn, "gsc_queries_daily", ["date", "query", "search_type"], {
            "date": ds, "query": r["keys"][0], "search_type": stype,
            "clicks": _i(r.get("clicks")), "impressions": _i(r.get("impressions")),
            "ctr": _f(r.get("ctr")), "position": _f(r.get("position")), "fetched_at": fetched})
        n += 1
    # devices
    for r in gsc.query_search_analytics(ds, ds, ["device"], stype, cfg=cfg):
        _upsert(conn, "gsc_devices_daily", ["date", "device", "search_type"], {
            "date": ds, "device": r["keys"][0], "search_type": stype,
            "clicks": _i(r.get("clicks")), "impressions": _i(r.get("impressions")),
            "ctr": _f(r.get("ctr")), "position": _f(r.get("position")), "fetched_at": fetched})
        n += 1
    # countries
    for r in gsc.query_search_analytics(ds, ds, ["country"], stype, cfg=cfg):
        _upsert(conn, "gsc_countries_daily", ["date", "country", "search_type"], {
            "date": ds, "country": r["keys"][0], "search_type": stype,
            "clicks": _i(r.get("clicks")), "impressions": _i(r.get("impressions")),
            "ctr": _f(r.get("ctr")), "position": _f(r.get("position")), "fetched_at": fetched})
        n += 1
    return n


# ─────────────── run ───────────────
def run_sync(sync_type="incremental"):
    cfg = gsc.load_config()
    if not gsc.config_state()["configured"]:
        return {"ok": False, "error": "not_configured"}
    if not gsc.token_present():
        return {"ok": False, "error": "token_missing"}

    fetched = _now()
    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO gsc_sync_runs (sync_type,source_mode,search_types_json,status,started_at,created_at) "
        "VALUES (?,?,?,?,?,?)",
        (sync_type, SOURCE_MODE, json.dumps(cfg.get("search_types")), "running", fetched, fetched))
    run_id = cur.lastrowid
    conn.commit()

    rows_written, partial, fatal, latest = 0, {}, None, None
    start, end = None, None
    try:
        gsc.property_probe(cfg)                       # fail fast nếu auth/permission
        latest = find_latest_available_date(cfg)
        end = datetime.fromisoformat(latest).date() if latest else (date.today() - timedelta(days=3))
        days = int(cfg["initial_backfill_days"]) if sync_type == "backfill" else int(cfg["incremental_lookback_days"])
        start = end - timedelta(days=max(0, days - 1))
        for stype in cfg.get("search_types", ["web"]):
            d = start
            while d <= end:
                ds = d.isoformat()
                if sync_type == "backfill" and _day_done(conn, ds, stype):
                    d += timedelta(days=1)
                    continue
                try:
                    rows_written += _sync_day(conn, ds, stype, cfg, fetched)
                    conn.commit()                     # checkpoint per-day → resume được
                except GSCError as e:
                    if e.code in _FATAL:
                        fatal = e
                        break
                    partial["%s:%s" % (ds, stype)] = e.code
                except Exception as e:
                    partial["%s:%s" % (ds, stype)] = gsc.classify_error(e).code
                d += timedelta(days=1)
            if fatal:
                break
    except GSCError as e:
        fatal = e
    except Exception as e:
        fatal = gsc.classify_error(e)
    finally:
        status = "error" if (fatal and rows_written == 0) else ("partial" if (fatal or partial) else "success")
        err_type = fatal.code if fatal else (list(partial.values())[0] if partial else None)
        err_msg = fatal.message if fatal else (json.dumps(partial, ensure_ascii=False) if partial else None)
        conn.execute(
            "UPDATE gsc_sync_runs SET date_from=?,date_to=?,status=?,rows_written=?,latest_available_date=?,"
            "error_type=?,error_message=?,finished_at=? WHERE id=?",
            (start.isoformat() if start else None, end.isoformat() if end else None,
             status, rows_written, latest, err_type, err_msg, _now(), run_id))
        _update_cache_status(conn, latest, success=(status in ("success", "partial")),
                             err_type=err_type, err_msg=err_msg)
        conn.commit()
        conn.close()

    return {"ok": fatal is None, "run_id": run_id, "status": status, "rows_written": rows_written,
            "latest_available_date": latest, "partial": partial,
            "error": (fatal.code if fatal else None),
            "fallback_to_sheet": bool(cfg.get("fallback_to_sheet")) and fatal is not None}


def _update_cache_status(conn, latest, success, err_type, err_msg):
    prev = conn.execute("SELECT last_success_at,last_failure_at FROM gsc_cache_status WHERE id=1").fetchone()
    last_success = (_now() if success else (prev["last_success_at"] if prev else None))
    last_failure = (prev["last_failure_at"] if (success and prev) else (_now() if not success else (prev["last_failure_at"] if prev else None)))
    data_age = None
    if latest:
        try:
            data_age = (date.today() - datetime.fromisoformat(latest).date()).days
        except Exception:
            pass
    _upsert(conn, "gsc_cache_status", ["id"], {
        "id": 1, "source_mode": SOURCE_MODE, "coverage_mode": COVERAGE_MODE, "coverage_complete": 0,
        "latest_available_date": latest, "fetched_at": _now(),
        "cache_age_days": 0, "data_age_days": data_age,
        "last_success_at": last_success, "last_failure_at": last_failure,
        "last_error_type": err_type, "last_error_message": err_msg,
        "sheet_fallback_available": 1 if SHEET_CACHE.exists() else 0, "updated_at": _now()})


# ─────────────── coverage ───────────────
def coverage(conn=None):
    own = conn is None
    conn = conn or db.get_conn()
    def tot(table):
        r = conn.execute("SELECT SUM(clicks) c, SUM(impressions) i FROM %s WHERE search_type='web'" % table).fetchone()
        return (r["c"] or 0), (r["i"] or 0)
    sc, si = tot("gsc_daily_summary")
    pc, pi = tot("gsc_pages_daily")
    qc, qi = tot("gsc_queries_daily")
    def pct(part, total):
        return round(part / total * 100, 1) if total else None
    out = {"page_click_coverage_percent": pct(pc, sc), "page_impression_coverage_percent": pct(pi, si),
           "query_click_coverage_percent": pct(qc, sc), "query_impression_coverage_percent": pct(qi, si)}
    if own:
        conn.close()
    return out


# ─────────────── lock / async / status ───────────────
def start_sync_async(sync_type="incremental"):
    if not _lock.acquire(blocking=False):
        return {"started": False, "reason": "already_running",
                "started_at": _run["started_at"], "sync_type": _run["sync_type"]}
    _run["started_at"] = _now()
    _run["sync_type"] = sync_type

    def _w():
        try:
            run_sync(sync_type)
        except Exception:
            pass
        finally:
            _run["started_at"] = None
            _run["sync_type"] = None
            _lock.release()
    threading.Thread(target=_w, daemon=True).start()
    return {"started": True, "started_at": _run["started_at"], "sync_type": sync_type}


def is_running():
    return _lock.locked()


def reconcile_stale_runs(max_minutes=STALE_MINUTES):
    conn = db.get_conn()
    fixed = 0
    for r in conn.execute("SELECT id, started_at FROM gsc_sync_runs WHERE status='running'").fetchall():
        old = True
        try:
            old = (datetime.now() - datetime.strptime(r["started_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() > max_minutes * 60
        except Exception:
            old = True
        if old:
            conn.execute("UPDATE gsc_sync_runs SET status='error',error_type='stale',"
                         "error_message='interrupted (app restart?)',finished_at=? WHERE id=?", (_now(), r["id"]))
            fixed += 1
    conn.commit()
    conn.close()
    return fixed


def latest_sync():
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM gsc_sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_status(probe=False):
    """Trạng thái GSC API source cho /api/gsc/status. Tách rõ cache vs data freshness."""
    api = gsc.status(probe=probe)
    conn = db.get_conn()
    cs = conn.execute("SELECT * FROM gsc_cache_status WHERE id=1").fetchone()
    have_rows = conn.execute("SELECT COUNT(*) FROM gsc_daily_summary").fetchone()[0]
    cov = coverage(conn)
    conn.close()
    cs = dict(cs) if cs else {}
    latest = cs.get("latest_available_date")
    data_age = cs.get("data_age_days")
    api_status = api["api_status"]
    err_code = api.get("error_code")
    warnings = []
    if data_age is not None and data_age > 3:
        warnings.append("Dữ liệu Search Console mới nhất hiện dừng tại %s" % latest)
    warnings.append("Chi tiết page/query là top rows API (partial), summary đáng tin hơn detail")
    warnings.append("coverage_complete = false trong chế độ API")

    # oauth_status (an toàn, không lộ token)
    oa_map = {"ok": "connected", "ready": "connected", "not_configured": "not_configured",
              "token_missing": "missing"}
    oauth_status = oa_map.get(api_status)
    if oauth_status is None:
        oauth_status = {"token_expired": "expired", "reconnect_required": "expired",
                        "permission_denied": "no_permission", "wrong_property": "wrong_property",
                        "quota_exceeded": "quota_exceeded"}.get(err_code, "error")

    ls = latest_sync() or {}
    cfg = gsc.load_config()
    return {
        "ok": err_code is None,
        "source_mode": SOURCE_MODE, "coverage_mode": COVERAGE_MODE, "coverage_complete": False,
        "api_status": api_status, "oauth_status": oauth_status,
        "permission_level": api.get("permission_level"),
        "error_code": err_code, "error_message": api.get("error_message"),
        "last_error_message_safe": cs.get("last_error_message") or api.get("error_message"),
        "site_url": api.get("site_url"), "token_present": api.get("token_present"),
        "configured": api.get("configured"),
        "latest_available_date": latest, "data_age_days": data_age,
        "cache_age_days": cs.get("cache_age_days"),
        "fetched_at": cs.get("fetched_at"), "last_success_at": cs.get("last_success_at"),
        "last_failure_at": cs.get("last_failure_at"), "last_error_type": cs.get("last_error_type"),
        "fallback_available": bool(cs.get("sheet_fallback_available")) or SHEET_CACHE.exists(),
        "sheet_fallback_available": bool(cs.get("sheet_fallback_available")) or SHEET_CACHE.exists(),
        "rows_in_db": have_rows, "rows_written": ls.get("rows_written"),
        "search_types": cfg.get("search_types"),
        "coverage": cov,
        "page_click_coverage_percent": cov.get("page_click_coverage_percent"),
        "page_impression_coverage_percent": cov.get("page_impression_coverage_percent"),
        "query_click_coverage_percent": cov.get("query_click_coverage_percent"),
        "query_impression_coverage_percent": cov.get("query_impression_coverage_percent"),
        "join_readiness": "daily_aligned_partial_coverage",
        "gsc_timezone": "PT", "ga4_timezone": "Asia/Ho_Chi_Minh",
        "daily_join_timezone_note": "calendar_day_boundaries_differ",
        "last_sync": ls or None, "sync_running": is_running(), "is_running": is_running(),
        "sync_started_at": _run.get("started_at"), "warning": warnings,
    }
