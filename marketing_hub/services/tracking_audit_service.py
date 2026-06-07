# -*- coding: utf-8 -*-
"""Tracking audit — đối chiếu event catalog kỳ vọng với data live GA4 (ga4_events_daily).

KHÔNG fake số (DB không có → N/A, không dùng 0 giả). KHÔNG gọi missing event là bug chắc chắn.
severity (incident) TÁCH khỏi implementation_priority (mức độ ưu tiên triển khai tracking).
Dedup theo finding_key + cooldown. Reserved ga4_tracking_audit/ga4_tasks giữ nguyên.
"""
import json
import threading
from datetime import date, datetime, timedelta

import db

_lock = threading.Lock()
_run = {"started_at": None}

# Event biết rõ là automatic / enhanced GA4 (không phải gap)
KNOWN_AUTO = {"page_view", "session_start", "first_visit", "user_engagement", "scroll", "click",
              "view_search_results", "form_start", "file_download", "video_start", "video_progress",
              "video_complete", "page_load", "site_search"}

# Catalog kỳ vọng: (event, category, source_type, business_value, impl_priority, key_event_recommended, noise_risk)
EXPECTED = [
    # ecommerce chuẩn
    ("view_item", "ecommerce", "theme", "medium", "P2", 0, "medium"),
    ("add_to_cart", "ecommerce", "theme", "high", "P2", 0, "low"),
    ("remove_from_cart", "ecommerce", "theme", "low", "P3", 0, "low"),
    ("view_cart", "ecommerce", "theme", "medium", "P2", 0, "low"),
    ("begin_checkout", "ecommerce", "theme", "high", "P2", 0, "low"),
    ("add_payment_info", "ecommerce", "theme", "medium", "P2", 0, "low"),
    ("add_shipping_info", "ecommerce", "theme", "medium", "P2", 0, "low"),
    ("purchase", "ecommerce", "theme", "high", "P1", 1, "low"),
    ("refund", "ecommerce", "backend", "low", "P3", 0, "low"),
    # lead / contact
    ("generate_lead", "lead", "gtm", "high", "P1", 1, "low"),
    ("form_submit", "lead", "gtm", "medium", "P2", 0, "low"),
    ("phone_click", "support_contact", "gtm", "high", "P0", 1, "low"),
    ("zalo_click", "support_contact", "gtm", "high", "P0", 1, "low"),
    ("messenger_click", "support_contact", "gtm", "high", "P0", 1, "low"),
    ("chat_click", "support_contact", "gtm", "medium", "P1", 0, "medium"),
    ("email_click", "support_contact", "gtm", "medium", "P2", 0, "low"),
    ("map_click", "support_contact", "gtm", "medium", "P1", 0, "low"),
    ("contact", "support_contact", "gtm", "medium", "P2", 0, "low"),
    # build pc
    ("build_pc_start", "build_pc", "theme", "high", "P1", 0, "medium"),
    ("build_pc_add_component", "build_pc", "theme", "medium", "P2", 0, "high"),
    ("build_pc_remove_component", "build_pc", "theme", "low", "P3", 0, "high"),
    ("build_pc_complete", "build_pc", "theme", "high", "P1", 1, "low"),
    ("build_pc_add_to_cart", "build_pc", "theme", "high", "P1", 1, "low"),
    ("build_pc_export_quote", "build_pc", "theme", "high", "P1", 1, "low"),
    ("build_pc_export_image", "build_pc", "theme", "medium", "P2", 0, "low"),
    ("build_pc_print", "build_pc", "theme", "low", "P3", 0, "low"),
    ("build_pc_reset", "build_pc", "theme", "low", "P3", 0, "medium"),
    # existing imported / unknown
    ("send", "custom_unknown", "unknown", "low", "P2", 0, "medium"),
    ("ads_conversion_Giỏ_hàng", "ecommerce", "ads_import", "medium", "P3", 0, "low"),
    ("ads_conversion_Thanh_toán", "ecommerce", "ads_import", "medium", "P3", 0, "low"),
]

PURCHASE_STALE_DAYS = 7


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_running():
    return _lock.locked()


def _live_events(conn, cut):
    out = {}
    for r in conn.execute("SELECT event_name, SUM(event_count) c, SUM(total_users) u, SUM(key_events) k, MAX(date) last "
                          "FROM ga4_events_daily WHERE date>=? GROUP BY event_name", (cut,)):
        out[r["event_name"]] = {"count": r["c"] or 0, "users": r["u"] or 0, "key": r["k"] or 0, "last": r["last"]}
    return out


def _upsert_catalog(conn, row):
    cols = list(row.keys())
    ph = ",".join("?" for _ in cols)
    upd = ",".join("%s=excluded.%s" % (c, c) for c in cols if c != "event_name")
    conn.execute("INSERT INTO tracking_event_catalog (%s) VALUES (%s) ON CONFLICT(event_name) DO UPDATE SET %s"
                 % (",".join(cols), ph, upd), [row[c] for c in cols])


def _upsert_finding(conn, key, severity, prio, category, title, desc, snapshot):
    now = _now()
    ex = conn.execute("SELECT id,status,cooldown_until FROM tracking_findings WHERE finding_key=?", (key,)).fetchone()
    if ex:
        status = ex["status"]
        # reopen chỉ khi đã resolved VÀ qua cooldown
        if status == "resolved":
            cd = ex["cooldown_until"]
            past = True
            try:
                past = (not cd) or (datetime.now() > datetime.strptime(cd, "%Y-%m-%d %H:%M:%S"))
            except Exception:
                past = True
            if past:
                status = "open"
            else:
                # còn cooldown → giữ resolved, chỉ cập nhật last_seen
                conn.execute("UPDATE tracking_findings SET last_seen_at=?,metric_snapshot_json=?,updated_at=? WHERE id=?",
                             (now, json.dumps(snapshot, ensure_ascii=False), now, ex["id"]))
                return
        conn.execute("UPDATE tracking_findings SET severity=?,implementation_priority=?,category=?,title=?,description=?,"
                     "metric_snapshot_json=?,status=?,last_seen_at=?,updated_at=? WHERE id=?",
                     (severity, prio, category, title, desc, json.dumps(snapshot, ensure_ascii=False), status, now, now, ex["id"]))
    else:
        conn.execute("INSERT INTO tracking_findings (finding_key,severity,implementation_priority,category,title,description,"
                     "metric_snapshot_json,status,first_seen_at,last_seen_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (key, severity, prio, category, title, desc, json.dumps(snapshot, ensure_ascii=False), "open", now, now, now))


def run_audit():
    today = date.today()
    cut = (today - timedelta(days=27)).isoformat()
    started = _now()
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO tracking_audit_runs (date_from,date_to,status,started_at) VALUES (?,?,?,?)",
                       (cut, today.isoformat(), "running", started))
    run_id = cur.lastrowid
    conn.commit()
    findings = 0
    try:
        live = _live_events(conn, cut)
        now = _now()
        # 1. catalog — expected
        expected_names = set()
        for (name, cat, src, val, prio, kev, noise) in EXPECTED:
            expected_names.add(name)
            lv = live.get(name)
            detected = lv is not None and lv["count"] > 0
            status = "detected" if detected else "missing"
            impl_status = "implemented" if detected else ("external" if src == "ads_import" else "not_implemented")
            note = None
            if name == "send":
                note = "unknown_source_needs_review"
            elif src == "ads_import":
                note = "Google Ads conversion import — không tự rename"
            _upsert_catalog(conn, {
                "event_name": name, "category": cat, "expected": 1, "source_type": src, "source_status": status,
                "business_value": val, "implementation_priority": prio, "key_event_recommended": kev,
                "noise_risk": noise, "implementation_status": impl_status,
                "count_28d": lv["count"] if lv else None, "users_28d": lv["users"] if lv else None,
                "key_28d": lv["key"] if lv else None, "last_seen": lv["last"] if lv else None,
                "note": note, "updated_at": now})
        # 2. catalog — observed not expected (automatic/enhanced/custom_unknown)
        for name, lv in live.items():
            if name in expected_names:
                continue
            cat = "automatic" if name in KNOWN_AUTO else "custom_unknown"
            _upsert_catalog(conn, {
                "event_name": name, "category": cat, "expected": 0, "source_type": "auto" if cat == "automatic" else "unknown",
                "source_status": "detected", "business_value": "low", "implementation_priority": "P3",
                "key_event_recommended": 0, "noise_risk": "high" if cat == "automatic" else "medium",
                "implementation_status": "implemented", "count_28d": lv["count"], "users_28d": lv["users"],
                "key_28d": lv["key"], "last_seen": lv["last"],
                "note": None if cat == "automatic" else "custom_unknown — cần xác minh nguồn", "updated_at": now})
        conn.commit()

        # 3. findings
        def grp_missing(cat):
            return [n for (n, c, s, v, p, k, ns) in EXPECTED if c == cat and (live.get(n) is None or live.get(n, {}).get("count", 0) == 0)]

        contact_missing = grp_missing("support_contact")
        if contact_missing:
            _upsert_finding(conn, "contact_tracking_gap", "P2", "P0", "support_contact",
                            "Thiếu tracking click liên hệ", "Chưa thấy: " + ", ".join(contact_missing) + ". Shop bán qua inbox/điện thoại nên đây là gap giá trị cao (đo qua GTM click trigger).",
                            {"missing": contact_missing})
            findings += 1
        bpc_missing = grp_missing("build_pc")
        if len(bpc_missing) >= 5:
            _upsert_finding(conn, "build_pc_tracking_gap", "P2", "P1", "build_pc",
                            "Thiếu funnel Build PC", "/pages/xay-dung-cau-hinh (top organic) chưa có event: " + ", ".join(bpc_missing[:6]) + "…",
                            {"missing": bpc_missing})
            findings += 1
        ecom_missing = [n for n in ("view_cart", "add_payment_info", "add_shipping_info") if live.get(n) is None or live.get(n, {}).get("count", 0) == 0]
        if ecom_missing:
            _upsert_finding(conn, "ecommerce_funnel_gap", "P2", "P2", "ecommerce",
                            "Thiếu bước giữa funnel ecommerce", "Chưa thấy: " + ", ".join(ecom_missing) + ". Funnel có thể rớt mạnh.",
                            {"missing": ecom_missing})
            findings += 1
        # purchase stale
        pur = live.get("purchase")
        if pur and pur["last"]:
            try:
                age = (today - datetime.fromisoformat(pur["last"]).date()).days
                if age > PURCHASE_STALE_DAYS:
                    _upsert_finding(conn, "purchase_stale", "P2", "P2", "ecommerce",
                                    "purchase event stale (cần rà)", "purchase last seen %s (%d ngày). Cần kiểm tra, CHƯA kết luận bug." % (pur["last"], age),
                                    {"last_seen": pur["last"], "age_days": age, "count_28d": pur["count"]})
                    findings += 1
            except Exception:
                pass
        # remove > add
        rm, ad = live.get("remove_from_cart"), live.get("add_to_cart")
        if rm and ad and rm["count"] > ad["count"]:
            _upsert_finding(conn, "remove_gt_add", "P2", "P2", "ecommerce",
                            "remove_from_cart > add_to_cart (cần kiểm tra)", "remove_from_cart=%d > add_to_cart=%d (event count). Nghi ngờ, chưa đủ bằng chứng kết luận." % (rm["count"], ad["count"]),
                            {"remove": rm["count"], "add": ad["count"]})
            findings += 1
        # send unknown
        if live.get("send"):
            _upsert_finding(conn, "send_unknown_source", "P2", "P2", "custom_unknown",
                            "Event 'send' chưa rõ nguồn", "send=%d (cả realtime). unknown_source_needs_review — tìm nguồn phát (gtag/form?)." % live["send"]["count"],
                            {"count_28d": live["send"]["count"]})
            findings += 1
        conn.commit()

        conn.execute("UPDATE tracking_audit_runs SET status=?,events_checked=?,findings_count=?,finished_at=? WHERE id=?",
                     ("success", len(live), findings, _now(), run_id))
        conn.commit()
        conn.close()
        return {"ok": True, "run_id": run_id, "events_checked": len(live), "findings": findings}
    except Exception as e:
        conn.execute("UPDATE tracking_audit_runs SET status='error',error_type='exception',error_message_safe=?,finished_at=? WHERE id=?",
                     (str(e)[:160], _now(), run_id))
        conn.commit()
        conn.close()
        return {"ok": False, "error": str(e)[:160], "run_id": run_id}


def start_audit_async():
    if not _lock.acquire(blocking=False):
        return {"started": False, "reason": "already_running", "started_at": _run["started_at"]}
    _run["started_at"] = _now()

    def _w():
        try:
            run_audit()
        except Exception:
            pass
        finally:
            _run["started_at"] = None
            _lock.release()
    threading.Thread(target=_w, daemon=True).start()
    return {"started": True, "started_at": _run["started_at"]}


def latest_run():
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM tracking_audit_runs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(r) if r else None
