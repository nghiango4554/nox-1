"""Routes: Tracking Audit — /seo/tracking + /api/tracking/*.

Render đọc SQLite (catalog/findings). Audit chạy nền + lock 409. KHÔNG gọi GA4 live khi render.
"""
from flask import render_template, jsonify, request

from services import tracking_audit_service as audit
from services import tracking_report_service as report


def tracking_page():
    return render_template("seo_tracking.html", status=report.get_status())


def api_status():
    return jsonify(report.get_status())


def api_audit():
    res = audit.start_audit_async()
    if not res.get("started"):
        return jsonify({"ok": False, "status": "already_running", "started_at": res.get("started_at")}), 409
    return jsonify({"ok": True, **res})


def api_events():
    return jsonify(report.list_events(request.args))


def api_findings():
    return jsonify(report.list_findings(request.args))


def api_funnel():
    return jsonify(report.funnel())


def api_finding_resolve(fid):
    d = request.get_json(silent=True) or {}
    return jsonify(report.set_finding_status(fid, "resolved", d.get("snooze_days")))


def api_finding_reopen(fid):
    return jsonify(report.set_finding_status(fid, "open"))


def api_finding_snooze(fid):
    d = request.get_json(silent=True) or {}
    return jsonify(report.set_finding_status(fid, "snoozed", d.get("snooze_days", 7)))


def register(app):
    app.add_url_rule("/seo/tracking", "tracking_page", tracking_page)
    app.add_url_rule("/api/tracking/status", "tracking_status", api_status)
    app.add_url_rule("/api/tracking/audit", "tracking_audit", api_audit, methods=["POST"])
    app.add_url_rule("/api/tracking/events", "tracking_events", api_events)
    app.add_url_rule("/api/tracking/findings", "tracking_findings", api_findings)
    app.add_url_rule("/api/tracking/funnel", "tracking_funnel", api_funnel)
    app.add_url_rule("/api/tracking/findings/<int:fid>/resolve", "tracking_f_resolve", api_finding_resolve, methods=["POST"])
    app.add_url_rule("/api/tracking/findings/<int:fid>/reopen", "tracking_f_reopen", api_finding_reopen, methods=["POST"])
    app.add_url_rule("/api/tracking/findings/<int:fid>/snooze", "tracking_f_snooze", api_finding_snooze, methods=["POST"])
