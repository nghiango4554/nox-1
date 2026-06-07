# -*- coding: utf-8 -*-
"""Task Center — gom task vận hành từ nhiều nguồn (tracking findings, sync fail) vào ga4_tasks.

Dedup theo dedup_key + cooldown. KHÔNG tạo SEO auto-action. KHÔNG sửa theme.
severity (incident) TÁCH implementation_priority. P0 chỉ outage/credential; P1 anomaly nghiêm trọng/pipeline fail.
KHÔNG tạo P0/P1 SEO task từ dữ liệu partial-coverage.
"""
import json
import threading
from datetime import datetime, timedelta

import db

_lock = threading.Lock()
COOLDOWN_DAYS = 3


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _upsert_task(conn, dedup_key, task_type, source, severity, prio, title, desc, snapshot, url=None):
    now = _now()
    ex = conn.execute("SELECT id,status,cooldown_until FROM ga4_tasks WHERE dedup_key=?", (dedup_key,)).fetchone()
    if ex:
        status = ex["status"]
        if status in ("resolved", "snoozed"):
            cd = ex["cooldown_until"]
            past = True
            try:
                past = (not cd) or (datetime.now() > datetime.strptime(cd, "%Y-%m-%d %H:%M:%S"))
            except Exception:
                past = True
            if not past:
                conn.execute("UPDATE ga4_tasks SET metric_snapshot_json=?,updated_at=? WHERE id=?",
                             (json.dumps(snapshot, ensure_ascii=False), now, ex["id"]))
                return 0
            status = "open"   # tái xuất sau cooldown → reopen
        conn.execute("UPDATE ga4_tasks SET task_type=?,source=?,severity=?,implementation_priority=?,title=?,description=?,"
                     "affected_url=?,metric_snapshot_json=?,status=?,updated_at=? WHERE id=?",
                     (task_type, source, severity, prio, title, desc, url, json.dumps(snapshot, ensure_ascii=False), status, now, ex["id"]))
        return 0
    conn.execute("INSERT INTO ga4_tasks (task_type,source,severity,implementation_priority,title,description,affected_url,"
                 "metric_snapshot_json,status,dedup_key,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                 (task_type, source, severity, prio, title, desc, url, json.dumps(snapshot, ensure_ascii=False), "open", dedup_key, now, now))
    return 1


def _latest_run_failed(conn, table):
    r = conn.execute("SELECT status,error_type,error_message,finished_at FROM %s ORDER BY id DESC LIMIT 1" % table).fetchone()
    if r and (r["status"] or "") in ("error",):
        return dict(r)
    return None


def generate():
    """Quét nguồn → upsert task. Idempotent, dedup, cooldown. Trả counts."""
    conn = db.get_conn()
    created = 0
    try:
        # 1. từ tracking_findings (open) → task tracking
        for f in conn.execute("SELECT * FROM tracking_findings WHERE status='open'"):
            created += _upsert_task(conn, "tracking:" + f["finding_key"], "tracking", "tracking_audit",
                                    f["severity"], f["implementation_priority"], f["title"], f["description"],
                                    {"finding_id": f["id"]})
        # 2. sync fail → task P1 (pipeline fail), severity P1
        for table, src, label in (("gsc_sync_runs", "gsc", "GSC API sync"),
                                   ("ga4_sync_runs", "ga4", "GA4 sync"),
                                   ("gsc_ga4_join_runs", "join", "GSC×GA4 daily join")):
            try:
                fail = _latest_run_failed(conn, table)
            except Exception:
                fail = None
            key = "syncfail:" + src
            if fail:
                created += _upsert_task(conn, key, src, "pipeline", "P1", "P1",
                                        label + " lần gần nhất lỗi",
                                        "Run gần nhất status=error (%s). Cần kiểm tra OAuth/permission/network." % (fail.get("error_type") or "?"),
                                        {"error_type": fail.get("error_type"), "finished_at": fail.get("finished_at")})
            else:
                # tự resolve task syncfail nếu run mới đã OK
                conn.execute("UPDATE ga4_tasks SET status='resolved',resolved_at=?,updated_at=? WHERE dedup_key=? AND status='open'",
                             (_now(), _now(), key))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "created": created}


def start_generate_async():
    if not _lock.acquire(blocking=False):
        return {"started": False, "reason": "already_running"}

    def _w():
        try:
            generate()
        except Exception:
            pass
        finally:
            _lock.release()
    threading.Thread(target=_w, daemon=True).start()
    return {"started": True}


def is_running():
    return _lock.locked()


_TYPES = {"tracking", "gsc", "ga4", "join", "seo", "cwv", "sync"}


def list_tasks(args):
    conn = db.get_conn()
    where, params = [], []
    st = args.get("status")
    if st in ("open", "snoozed", "resolved"):
        where.append("status=?"); params.append(st)
    if args.get("priority") in ("P0", "P1", "P2", "P3"):
        where.append("implementation_priority=?"); params.append(args["priority"])
    if args.get("severity") in ("P0", "P1", "P2", "P3"):
        where.append("severity=?"); params.append(args["severity"])
    tt = args.get("type")
    if tt:
        if tt == "sync":
            where.append("source IN ('gsc','ga4','join')")
        else:
            where.append("(task_type=? OR source=?)"); params += [tt, tt]
    wsql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute("SELECT * FROM ga4_tasks%s ORDER BY CASE implementation_priority "
                        "WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END, "
                        "CASE status WHEN 'open' THEN 0 WHEN 'snoozed' THEN 1 ELSE 2 END, id DESC%s"
                        % (wsql, ""), params).fetchall()
    conn.close()
    return {"ok": True, "data": [dict(r) for r in rows]}


def counts():
    conn = db.get_conn()
    def c(sql, p=()):
        return conn.execute("SELECT COUNT(*) FROM ga4_tasks" + sql, p).fetchone()[0]
    out = {
        "all": c(""), "open": c(" WHERE status='open'"), "snoozed": c(" WHERE status='snoozed'"),
        "resolved": c(" WHERE status='resolved'"),
        "P0": c(" WHERE status='open' AND implementation_priority='P0'"),
        "P1": c(" WHERE status='open' AND implementation_priority='P1'"),
        "P2": c(" WHERE status='open' AND implementation_priority='P2'"),
        "P3": c(" WHERE status='open' AND implementation_priority='P3'"),
        "tracking": c(" WHERE status='open' AND task_type='tracking'"),
        "sync": c(" WHERE status='open' AND source IN ('gsc','ga4','join')"),
    }
    conn.close()
    return out


def set_status(tid, status, snooze_days=None):
    conn = db.get_conn()
    now = _now()
    if status == "resolved":
        cd = (datetime.now() + timedelta(days=int(snooze_days or COOLDOWN_DAYS))).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE ga4_tasks SET status='resolved',resolved_at=?,cooldown_until=?,updated_at=? WHERE id=?", (now, cd, now, tid))
    elif status == "snoozed":
        cd = (datetime.now() + timedelta(days=int(snooze_days or 7))).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE ga4_tasks SET status='snoozed',cooldown_until=?,updated_at=? WHERE id=?", (cd, now, tid))
    else:
        conn.execute("UPDATE ga4_tasks SET status='open',resolved_at=NULL,cooldown_until=NULL,updated_at=? WHERE id=?", (now, tid))
    ok = conn.total_changes > 0
    conn.commit()
    conn.close()
    return {"ok": ok, "status": status}
