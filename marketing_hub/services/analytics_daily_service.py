# -*- coding: utf-8 -*-
"""Analytics daily orchestration — chạy tuần tự pipeline phân tích + alert Telegram P0/P1.

Steps: GA4 incremental → GSC API incremental → GSC×GA4 daily join → Tracking audit → Task generate → Alert.
Orchestration lock riêng (KHÔNG trùng). Step nào fail → ghi lại, step phụ thuộc phía sau skip phù hợp.
KHÔNG trộn Sheet fallback vào daily join. Alert chỉ P0/P1 mới hoặc sync fail (im lặng khi OK).
"""
import json
import threading
from datetime import datetime
from pathlib import Path

import db
from services import gsc_api_client

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT.parent / "state" / "analytics_daily_config.json"

_lock = threading.Lock()
_run = {"started_at": None, "trigger": None}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_config():
    cfg = {"enabled": False, "hour": 6, "minute": 30, "timezone": "Asia/Ho_Chi_Minh",
           "retry": 1, "timeout_seconds": 1200, "telegram_alert_enabled": True, "weekly_digest_enabled": False}
    if CONFIG.exists():
        try:
            cfg.update(json.loads(CONFIG.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def is_running():
    return _lock.locked()


def _open_pp_counts(conn):
    """Đếm theo INCIDENT SEVERITY (KHÔNG phải implementation_priority) — Telegram alert chỉ cho
    incident severity P0/P1. implementation_priority P0 (vd contact gap) KHÔNG tự gửi cảnh báo khẩn."""
    p0 = conn.execute("SELECT COUNT(*) FROM ga4_tasks WHERE status='open' AND severity='P0'").fetchone()[0]
    p1 = conn.execute("SELECT COUNT(*) FROM ga4_tasks WHERE status='open' AND severity='P1'").fetchone()[0]
    return p0, p1


def _step(name, fn):
    """Chạy 1 step, trả dict status/duration/error (không raise ra ngoài)."""
    t0 = datetime.now()
    rec = {"step": name, "status": "ok", "error": None}
    try:
        res = fn()
        if isinstance(res, dict) and res.get("ok") is False:
            rec["status"] = "error"
            rec["error"] = res.get("error") or res.get("status")
    except Exception as e:
        rec["status"] = "error"
        rec["error"] = str(e)[:120]
    rec["duration_seconds"] = round((datetime.now() - t0).total_seconds(), 1)
    return rec


def run_orchestration(trigger="manual"):
    cfg = load_config()
    started = _now()
    t0 = datetime.now()
    conn = db.get_conn()
    p0_before, p1_before = _open_pp_counts(conn)
    cur = conn.execute("INSERT INTO analytics_daily_runs (trigger,status,started_at) VALUES (?,?,?)", (trigger, "running", started))
    run_id = cur.lastrowid
    conn.commit()
    conn.close()

    steps = []
    gsc_ready = gsc_api_client.config_state()["configured"] and gsc_api_client.token_present()
    # lazy import để tránh vòng lặp + chỉ load khi chạy
    from services import ga4_sync_service, gsc_sync_service, gsc_ga4_daily_join_service
    from services import tracking_audit_service, task_center_service

    steps.append(_step("ga4_incremental_sync", lambda: ga4_sync_service.run_sync("incremental")))
    if gsc_ready:
        gsc_rec = _step("gsc_api_incremental_sync", lambda: gsc_sync_service.run_sync("incremental"))
        steps.append(gsc_rec)
        # join chỉ chạy nếu GSC sync không fail (dependency)
        if gsc_rec["status"] == "ok":
            steps.append(_step("gsc_ga4_daily_join", lambda: gsc_ga4_daily_join_service.refresh_join("incremental")))
        else:
            steps.append({"step": "gsc_ga4_daily_join", "status": "skipped", "error": "gsc sync failed", "duration_seconds": 0})
    else:
        steps.append({"step": "gsc_api_incremental_sync", "status": "skipped", "error": "not_configured", "duration_seconds": 0})
        steps.append({"step": "gsc_ga4_daily_join", "status": "skipped", "error": "gsc not configured", "duration_seconds": 0})
    steps.append(_step("tracking_audit", lambda: tracking_audit_service.run_audit()))
    steps.append(_step("task_generate", lambda: task_center_service.generate()))

    conn = db.get_conn()
    p0_after, p1_after = _open_pp_counts(conn)
    failed = [s for s in steps if s["status"] == "error"]
    new_p0 = max(0, p0_after - p0_before)
    new_p1 = max(0, p1_after - p1_before)
    overall = "error" if failed else "success"

    # alert P0/P1 mới hoặc sync fail (im lặng khi OK)
    alert_sent = 0
    if cfg.get("telegram_alert_enabled") and (failed or new_p0 or new_p1):
        try:
            alert_sent = 1 if _send_alert(overall, steps, new_p0, new_p1, p0_after, p1_after) else 0
        except Exception:
            alert_sent = 0

    dur = round((datetime.now() - t0).total_seconds(), 1)
    conn.execute("UPDATE analytics_daily_runs SET status=?,steps_json=?,alert_sent=?,new_p0=?,new_p1=?,failed_steps=?,"
                 "duration_seconds=?,finished_at=? WHERE id=?",
                 (overall, json.dumps(steps, ensure_ascii=False), alert_sent, new_p0, new_p1, len(failed), dur, _now(), run_id))
    conn.commit()
    conn.close()
    return {"ok": not failed, "run_id": run_id, "status": overall, "steps": steps,
            "new_p0": new_p0, "new_p1": new_p1, "failed_steps": len(failed), "alert_sent": bool(alert_sent), "duration_seconds": dur}


def _send_alert(overall, steps, new_p0, new_p1, p0_total, p1_total):
    """Gửi Telegram alert (reuse notifier). KHÔNG gửi token/stacktrace dài."""
    try:
        import notifier
    except Exception:
        return False
    fails = [s["step"] for s in steps if s["status"] == "error"]
    lines = ["<b>[Marketing Hub] Analytics Daily Alert</b>",
             "Status: <b>%s</b>" % ("⚠️ có sự cố" if (overall == "error" or new_p0 or new_p1) else "OK")]
    if fails:
        lines.append("Step lỗi: " + ", ".join(fails))
    if new_p0:
        lines.append("🔴 Incident severity P0 mới: %d" % new_p0)
    if new_p1:
        lines.append("🟠 Incident severity P1 mới: %d" % new_p1)
    lines.append("Open incident severity: P0=%d · P1=%d" % (p0_total, p1_total))
    lines.append("Dashboard: /tasks · /seo/tracking")
    return notifier.send_telegram("\n".join(lines))


def alert_preview(mock=True):
    """Dry-run alert (KHÔNG gửi live). Trả text sẽ gửi."""
    conn = db.get_conn()
    p0, p1 = _open_pp_counts(conn)
    conn.close()
    lines = ["[Marketing Hub] Analytics Daily Alert", "Status: %s" % ("OK" if not (p0 or p1) else "⚠️ có sự cố"),
             "Open incident severity: P0=%d · P1=%d" % (p0, p1), "Dashboard: /tasks · /seo/tracking",
             "(eligibility theo incident severity — implementation_priority P0 như contact gap KHÔNG gửi khẩn)"]
    return {"ok": True, "would_send": bool(p0 or p1), "mock": mock, "text": "\n".join(lines)}


def start_async(trigger="manual"):
    if not _lock.acquire(blocking=False):
        return {"started": False, "reason": "already_running", "started_at": _run["started_at"]}
    _run["started_at"] = _now()
    _run["trigger"] = trigger

    def _w():
        try:
            run_orchestration(trigger)
        except Exception:
            pass
        finally:
            _run["started_at"] = None
            _run["trigger"] = None
            _lock.release()
    threading.Thread(target=_w, daemon=True).start()
    return {"started": True, "started_at": _run["started_at"], "trigger": trigger}


def reconcile_stale(max_minutes=60):
    conn = db.get_conn()
    fixed = 0
    for r in conn.execute("SELECT id, started_at FROM analytics_daily_runs WHERE status='running'").fetchall():
        old = True
        try:
            old = (datetime.now() - datetime.strptime(r["started_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() > max_minutes * 60
        except Exception:
            old = True
        if old:
            conn.execute("UPDATE analytics_daily_runs SET status='error',error_type='stale',finished_at=? WHERE id=?", (_now(), r["id"]))
            fixed += 1
    conn.commit()
    conn.close()
    return fixed


def get_status():
    reconcile_stale()
    cfg = load_config()
    conn = db.get_conn()
    last = conn.execute("SELECT * FROM analytics_daily_runs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    last = dict(last) if last else None
    if last and last.get("steps_json"):
        try:
            last["steps"] = json.loads(last["steps_json"])
        except Exception:
            last["steps"] = []
    return {
        "ok": True, "enabled": cfg.get("enabled"), "schedule": "%02d:%02d %s" % (cfg.get("hour", 6), cfg.get("minute", 30), cfg.get("timezone")),
        "telegram_alert_enabled": cfg.get("telegram_alert_enabled"), "weekly_digest_enabled": cfg.get("weekly_digest_enabled"),
        "is_running": is_running(), "started_at": _run.get("started_at"), "last_run": last,
        "pipeline": ["ga4_incremental_sync", "gsc_api_incremental_sync", "gsc_ga4_daily_join", "tracking_audit", "task_generate", "alert"],
    }
