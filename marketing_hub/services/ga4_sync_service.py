# -*- coding: utf-8 -*-
"""GA4 sync service — pull report từ Data API → upsert SQLite (idempotent) + sync run log.

Batch 2: 6 bảng daily (summary, channels, landing, devices, events, ecommerce).
Join / tracking audit / tasks: batch sau (bảng đã tạo, chưa populate).
Chạy nền (thread) — KHÔNG gọi API khi render trang.
"""
import json
import threading
from datetime import date, timedelta

import db
from services import ga4_config, ga4_client
from services.ga4_client import GA4Error
from services.url_normalize import normalize_landing_path

_FATAL = {"token_expired", "permission_denied", "wrong_property", "quota", "token_missing"}
_lock = threading.Lock()

CAMEL2SNAKE = {
    "activeUsers": "active_users", "newUsers": "new_users", "sessions": "sessions",
    "engagedSessions": "engaged_sessions", "engagementRate": "engagement_rate",
    "screenPageViews": "screen_page_views", "keyEvents": "key_events",
    "ecommercePurchases": "ecommerce_purchases", "purchaseRevenue": "purchase_revenue",
    "totalRevenue": "total_revenue", "averageSessionDuration": "average_session_duration",
    "userEngagementDuration": "user_engagement_duration", "eventCount": "event_count",
    "totalUsers": "total_users", "eventValue": "event_value",
    "itemsViewed": "items_viewed", "itemsAddedToCart": "items_added_to_cart",
    "itemsCheckedOut": "items_checked_out", "itemsPurchased": "items_purchased",
}
_INT_METRICS = {
    "active_users", "new_users", "sessions", "engaged_sessions", "screen_page_views",
    "key_events", "ecommerce_purchases", "event_count", "total_users",
    "items_viewed", "items_added_to_cart", "items_checked_out", "items_purchased",
}

# table, dims [(ga4_dim, db_col)], metrics [ga4_met], pk [db_cols]
REPORTS = [
    {"table": "ga4_daily_summary", "pk": ["date"],
     "dims": [("date", "date")],
     "mets": ["activeUsers", "newUsers", "sessions", "engagedSessions", "engagementRate",
              "screenPageViews", "keyEvents", "ecommercePurchases", "purchaseRevenue",
              "totalRevenue", "averageSessionDuration", "userEngagementDuration"]},
    {"table": "ga4_channels_daily",
     "pk": ["date", "session_default_channel_group", "session_source_medium"],
     "dims": [("date", "date"), ("sessionDefaultChannelGroup", "session_default_channel_group"),
              ("sessionSourceMedium", "session_source_medium")],
     "mets": ["activeUsers", "sessions", "engagedSessions", "engagementRate",
              "keyEvents", "ecommercePurchases", "purchaseRevenue"]},
    {"table": "ga4_landing_pages_daily", "pk": ["date", "normalized_path"],
     "dims": [("date", "date"), ("landingPage", "landing_page_raw")],
     "mets": ["activeUsers", "newUsers", "sessions", "engagedSessions", "engagementRate",
              "screenPageViews", "keyEvents", "ecommercePurchases", "purchaseRevenue"],
     "landing": True},
    {"table": "ga4_devices_daily", "pk": ["date", "device_category"],
     "dims": [("date", "date"), ("deviceCategory", "device_category")],
     "mets": ["activeUsers", "sessions", "engagedSessions", "engagementRate",
              "keyEvents", "purchaseRevenue"]},
    {"table": "ga4_events_daily", "pk": ["date", "event_name"],
     "dims": [("date", "date"), ("eventName", "event_name")],
     "mets": ["eventCount", "totalUsers", "keyEvents", "eventValue"]},
    {"table": "ga4_ecommerce_daily", "pk": ["date"],
     "dims": [("date", "date")],
     "mets": ["itemsViewed", "itemsAddedToCart", "itemsCheckedOut", "itemsPurchased",
              "ecommercePurchases", "purchaseRevenue", "totalRevenue"]},
]


def _ga4_date(s):
    s = str(s)
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else s


def _num(db_col, raw):
    try:
        if db_col in _INT_METRICS:
            return int(float(raw))
        return float(raw)
    except Exception:
        return None


def _upsert(conn, table, pk_cols, data):
    cols = list(data.keys())
    ph = ",".join("?" for _ in cols)
    upd = ",".join(f"{c}=excluded.{c}" for c in cols if c not in pk_cols)
    sql = (f"INSERT INTO {table} ({','.join(cols)}) VALUES ({ph}) "
           f"ON CONFLICT({','.join(pk_cols)}) DO UPDATE SET {upd}")
    conn.execute(sql, [data[c] for c in cols])


_MAX_METRICS = 10   # GA4 Data API: tối đa 10 metric / runReport


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _sync_report(conn, spec, start, end, fetched_at, cfg):
    """Pull report; tự chia metric thành chunk ≤10 rồi merge theo khóa dimension."""
    dims = [d[0] for d in spec["dims"]]
    merged = {}   # tuple(dim raw values) -> {"_dims": [...], db_col: value}
    for chunk in _chunks(spec["mets"], _MAX_METRICS):
        rows, used_mets, _deg = ga4_client.run_report(dims, chunk, start, end, cfg=cfg)
        used_cols = [CAMEL2SNAKE.get(m, m) for m in used_mets]
        for r in rows:
            dvals = [d.get("value") for d in r.get("dimensionValues", [])]
            slot = merged.setdefault(tuple(dvals), {"_dims": dvals})
            mvals = r.get("metricValues", [])
            for i, col in enumerate(used_cols):
                slot[col] = _num(col, mvals[i]["value"]) if i < len(mvals) else None

    n = 0
    for slot in merged.values():
        dvals = slot["_dims"]
        data = {}
        for i, (_g, db_col) in enumerate(spec["dims"]):
            v = dvals[i] if i < len(dvals) else None
            data[db_col] = _ga4_date(v) if db_col == "date" else v
        if spec.get("landing"):
            data["normalized_path"] = normalize_landing_path(data.get("landing_page_raw"))
        for col, val in slot.items():
            if col != "_dims":
                data[col] = val
        data["fetched_at"] = fetched_at
        _upsert(conn, spec["table"], spec["pk"], data)
        n += 1
    return n


# Landing aggregate: cộng được vs KHÔNG cộng mù quáng
_LANDING_SUM = {"sessions", "engaged_sessions", "screen_page_views",
                "key_events", "ecommerce_purchases", "purchase_revenue"}
_LANDING_MAX = {"active_users", "new_users"}   # user-scoped: lấy MAX (an toàn, tránh overcount)


def _sync_landing(conn, spec, start, end, fetched_at, cfg):
    """Landing aggregate theo normalized_path → chống last-wins.
    SUM cho metric cộng được; active/new_users lấy MAX (không cộng mù quáng vì user trùng);
    engagement_rate tính lại = engaged_sessions / sessions.
    Trả (rows, raw_count, collisions)."""
    dims = [d[0] for d in spec["dims"]]
    rows, used_mets, _deg = ga4_client.run_report(dims, spec["mets"], start, end, cfg=cfg)
    used_cols = [CAMEL2SNAKE.get(m, m) for m in used_mets]

    agg = {}            # (date_iso, normalized_path) -> accumulator
    raw_count = 0
    for r in rows:
        dvals = [d.get("value") for d in r.get("dimensionValues", [])]
        mvals = r.get("metricValues", [])
        date_iso = _ga4_date(dvals[0]) if dvals else None
        raw = dvals[1] if len(dvals) > 1 else None
        npath = normalize_landing_path(raw)
        key = (date_iso, npath)
        raw_count += 1
        vals = {used_cols[i]: (_num(used_cols[i], mvals[i]["value"]) if i < len(mvals) else None)
                for i in range(len(used_cols))}
        slot = agg.get(key)
        if slot is None:
            slot = {"landing_page_raw": raw, "_variants": 0, "_top_sessions": -1}
            for c in _LANDING_SUM | _LANDING_MAX:
                slot[c] = 0
            agg[key] = slot
        slot["_variants"] += 1
        for c in _LANDING_SUM:
            slot[c] = (slot[c] or 0) + (vals.get(c) or 0)
        for c in _LANDING_MAX:
            slot[c] = max(slot[c] or 0, vals.get(c) or 0)
        s = vals.get("sessions") or 0
        if s > slot["_top_sessions"]:                 # giữ raw của variant nhiều session nhất
            slot["_top_sessions"] = s
            slot["landing_page_raw"] = raw

    collisions = sum(1 for s in agg.values() if s["_variants"] > 1)
    n = 0
    for (date_iso, npath), slot in agg.items():
        sess = slot.get("sessions") or 0
        eng = slot.get("engaged_sessions") or 0
        data = {"date": date_iso, "normalized_path": npath,
                "landing_page_raw": slot["landing_page_raw"],
                "engagement_rate": (eng / sess) if sess else 0.0,
                "fetched_at": fetched_at}
        for c in _LANDING_SUM | _LANDING_MAX:
            data[c] = slot.get(c)
        _upsert(conn, spec["table"], spec["pk"], data)
        n += 1
    return n, raw_count, collisions


def run_sync(sync_type="incremental"):
    """Đồng bộ GA4 → SQLite. Trả dict kết quả. KHÔNG raise (graceful)."""
    cfg = ga4_config.load_config()
    if not ga4_config.config_state()["configured"]:
        return {"ok": False, "error": "not_configured"}
    if not ga4_client.token_present():
        return {"ok": False, "error": "token_missing"}

    today = date.today()
    end = today - timedelta(days=1)            # GA4 trễ ~1 ngày
    days = int(cfg.get("initial_backfill_days", 90)) if sync_type == "backfill" \
        else int(cfg.get("sync_lookback_days", 3))
    start = end - timedelta(days=max(0, days - 1))
    sd, ed = start.isoformat(), end.isoformat()
    fetched_at = _now_iso()

    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO ga4_sync_runs (sync_type,date_from,date_to,status,started_at,created_at) "
        "VALUES (?,?,?,?,?,?)", (sync_type, sd, ed, "running", fetched_at, fetched_at))
    run_id = cur.lastrowid
    conn.commit()

    rows_written, partial = 0, {}
    landing_stats = {}
    fatal = None
    try:
        for spec in REPORTS:
            try:
                if spec.get("landing"):
                    n, raw_count, collisions = _sync_landing(conn, spec, sd, ed, fetched_at, cfg)
                    rows_written += n
                    landing_stats = {"rows": n, "raw_count": raw_count, "collisions": collisions}
                else:
                    rows_written += _sync_report(conn, spec, sd, ed, fetched_at, cfg)
            except GA4Error as e:
                if e.code in _FATAL:
                    fatal = e
                    break
                partial[spec["table"]] = e.code            # per-report degrade, ghi log, chạy tiếp
            except Exception as e:
                partial[spec["table"]] = ga4_client.classify_exception(e).code
        conn.commit()
    finally:
        latest = conn.execute(
            "SELECT MAX(date) FROM ga4_daily_summary").fetchone()[0]
        status = "error" if fatal else ("partial" if partial else "success")
        err_msg = (fatal.message if fatal else (json.dumps(partial, ensure_ascii=False) if partial else None))
        quota = ga4_client.last_quota()
        quota_json = json.dumps(quota, ensure_ascii=False) if quota else None
        conn.execute(
            "UPDATE ga4_sync_runs SET status=?,rows_written=?,finished_at=?,error_message=?,"
            "latest_data_date=?,quota_snapshot_json=? WHERE id=?",
            (status, rows_written, _now_iso(), err_msg, latest, quota_json, run_id))
        conn.commit()
        conn.close()

    return {"ok": fatal is None, "run_id": run_id, "status": status,
            "rows_written": rows_written, "partial": partial,
            "error": (fatal.code if fatal else None), "latest_data_date": latest,
            "landing": landing_stats, "quota_saved": bool(quota)}


_run_state = {"started_at": None, "sync_type": None}   # info của run đang chạy trong process này
STALE_MINUTES = 30                                     # run 'running' quá lâu → coi là interrupted


def start_sync_async(sync_type="incremental"):
    """Chạy sync nền với lock atomic. Nếu đang chạy → started=False + already_running.
    Lock release ở cả success lẫn exception (finally)."""
    if not _lock.acquire(blocking=False):
        return {"started": False, "reason": "already_running",
                "started_at": _run_state["started_at"], "sync_type": _run_state["sync_type"]}
    _run_state["started_at"] = _now_iso()
    _run_state["sync_type"] = sync_type

    def _worker():
        try:
            run_sync(sync_type)
        except Exception:
            pass
        finally:
            _run_state["started_at"] = None
            _run_state["sync_type"] = None
            _lock.release()

    threading.Thread(target=_worker, daemon=True).start()
    return {"started": True, "sync_type": sync_type, "started_at": _run_state["started_at"]}


def reconcile_stale_runs(max_minutes=STALE_MINUTES):
    """Đánh dấu các run 'running' bị treo (app restart giữa chừng) thành 'error'.
    Không đụng run đang chạy thật trong process này (lock đang giữ → bỏ qua nếu mới)."""
    from datetime import datetime
    conn = db.get_conn()
    fixed = 0
    for r in conn.execute("SELECT id, started_at FROM ga4_sync_runs WHERE status='running'").fetchall():
        sa = r["started_at"]
        old = True
        try:
            dt = datetime.strptime(sa, "%Y-%m-%d %H:%M:%S")
            old = (datetime.now() - dt).total_seconds() > max_minutes * 60
        except Exception:
            old = True
        if old:
            conn.execute(
                "UPDATE ga4_sync_runs SET status='error', "
                "error_message='stale: interrupted (app restart?)', finished_at=? WHERE id=?",
                (_now_iso(), r["id"]))
            fixed += 1
    conn.commit()
    conn.close()
    return fixed


def latest_sync():
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM ga4_sync_runs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def is_running():
    return _lock.locked()


def running_info():
    return {"is_running": _lock.locked(),
            "started_at": _run_state["started_at"], "sync_type": _run_state["sync_type"]}


def _now_iso():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
