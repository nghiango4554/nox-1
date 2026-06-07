# -*- coding: utf-8 -*-
"""Tracking report — đọc catalog/findings/funnel cho UI. KHÔNG gọi GA4 live khi render."""
import json
from datetime import date, datetime, timedelta

import db
from services import tracking_audit_service as audit

_FCAT = {"ecommerce", "lead", "support_contact", "build_pc", "custom_unknown", "automatic"}
_SEV = {"P0", "P1", "P2", "P3"}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_status():
    conn = db.get_conn()
    cat_n = conn.execute("SELECT COUNT(*) FROM tracking_event_catalog").fetchone()[0]
    detected = conn.execute("SELECT COUNT(*) FROM tracking_event_catalog WHERE source_status='detected'").fetchone()[0]
    expected = conn.execute("SELECT COUNT(*) FROM tracking_event_catalog WHERE expected=1").fetchone()[0]
    missing = conn.execute("SELECT COUNT(*) FROM tracking_event_catalog WHERE expected=1 AND source_status!='detected'").fetchone()[0]
    open_find = conn.execute("SELECT COUNT(*) FROM tracking_findings WHERE status='open'").fetchone()[0]
    prio = {p: conn.execute("SELECT COUNT(*) FROM tracking_findings WHERE status='open' AND implementation_priority=?", (p,)).fetchone()[0] for p in ("P0", "P1", "P2", "P3")}
    latest_ev = conn.execute("SELECT MAX(date) FROM ga4_events_daily").fetchone()[0]
    # health per nhóm = % expected detected
    def health(cat):
        ex = conn.execute("SELECT COUNT(*) FROM tracking_event_catalog WHERE expected=1 AND category=?", (cat,)).fetchone()[0]
        de = conn.execute("SELECT COUNT(*) FROM tracking_event_catalog WHERE expected=1 AND category=? AND source_status='detected'", (cat,)).fetchone()[0]
        return {"expected": ex, "detected": de, "percent": (round(de / ex * 100) if ex else None)}
    h_ecom, h_lead, h_contact, h_bpc = health("ecommerce"), health("lead"), health("support_contact"), health("build_pc")
    conn.close()
    run = audit.latest_run()
    return {
        "ok": True, "configured": cat_n > 0, "catalog_count": cat_n,
        "detected_events": detected, "expected_events": expected, "missing_events": missing,
        "open_findings": open_find, "priority_counts": prio,
        "ecommerce_health": h_ecom, "lead_health": h_lead,
        "contact_health": h_contact, "build_pc_health": h_bpc,
        "event_data_latest_date": latest_ev,
        "last_audit": run, "is_running": audit.is_running(),
        "warning": ["Missing event KHÔNG đồng nghĩa bug chắc chắn — cần kiểm tra deploy.",
                    "GTM/theme nằm ngoài repo — triển khai event phải làm thủ công.",
                    "Ads conversion import giữ nguyên, không tự rename."],
    }


def list_events(args):
    conn = db.get_conn()
    where, params = [], []
    if args.get("category"):
        where.append("category=?"); params.append(args["category"])
    if args.get("source_status"):
        where.append("source_status=?"); params.append(args["source_status"])
    if args.get("search"):
        where.append("event_name LIKE ?"); params.append("%" + args["search"] + "%")
    wsql = (" WHERE " + " AND ".join(where)) if where else ""
    sort = args.get("sort") if args.get("sort") in ("count_28d", "event_name", "category") else "count_28d"
    order = "ASC" if str(args.get("order", "desc")).lower() == "asc" else "DESC"
    rows = conn.execute("SELECT * FROM tracking_event_catalog%s ORDER BY %s %s NULLS LAST" % (wsql, sort, order), params).fetchall()
    conn.close()
    return {"ok": True, "data": [dict(r) for r in rows]}


def list_findings(args):
    conn = db.get_conn()
    where, params = [], []
    for k, col in (("status", "status"), ("severity", "severity"), ("priority", "implementation_priority"), ("category", "category")):
        if args.get(k):
            where.append(col + "=?"); params.append(args[k])
    wsql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute("SELECT * FROM tracking_findings%s ORDER BY CASE implementation_priority "
                        "WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END, id DESC" % wsql, params).fetchall()
    conn.close()
    return {"ok": True, "data": [dict(r) for r in rows]}


def funnel():
    """Ecommerce funnel 28 ngày (từ ga4_events_daily) — directional."""
    conn = db.get_conn()
    cut = (date.today() - timedelta(days=27)).isoformat()
    steps = ["view_item", "add_to_cart", "remove_from_cart", "view_cart", "begin_checkout",
             "add_payment_info", "add_shipping_info", "purchase", "refund"]
    out = []
    for s in steps:
        r = conn.execute("SELECT SUM(event_count) c, SUM(total_users) u, MAX(date) last FROM ga4_events_daily WHERE event_name=? AND date>=?", (s, cut)).fetchone()
        out.append({"event": s, "count": (r["c"] if r and r["c"] else None), "users": (r["u"] if r and r["u"] else None), "last_seen": (r["last"] if r else None),
                    "present": bool(r and r["c"])})
    conn.close()
    return {"ok": True, "steps": out}


def set_finding_status(fid, status, snooze_days=None):
    conn = db.get_conn()
    now = _now()
    if status == "resolved":
        cd = (datetime.now() + timedelta(days=int(snooze_days or 7))).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE tracking_findings SET status='resolved',resolved_at=?,cooldown_until=?,updated_at=? WHERE id=?", (now, cd, now, fid))
    elif status == "snoozed":
        cd = (datetime.now() + timedelta(days=int(snooze_days or 7))).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE tracking_findings SET status='snoozed',cooldown_until=?,updated_at=? WHERE id=?", (cd, now, fid))
    else:  # reopen
        conn.execute("UPDATE tracking_findings SET status='open',resolved_at=NULL,cooldown_until=NULL,updated_at=? WHERE id=?", (now, fid))
    ok = conn.total_changes > 0
    conn.commit()
    conn.close()
    return {"ok": ok, "status": status}
