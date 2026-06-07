"""Routes: Analytics Ops — /ops/analytics + orchestration status/run. Lock 409."""
from flask import render_template, jsonify, request

from services import analytics_daily_service as ops


def ops_page():
    return render_template("ops_analytics.html", status=ops.get_status())


def api_status():
    return jsonify(ops.get_status())


def api_run():
    res = ops.start_async("manual")
    if not res.get("started"):
        return jsonify({"ok": False, "status": "already_running", "started_at": res.get("started_at")}), 409
    return jsonify({"ok": True, **res})


def api_alert_preview():
    return jsonify(ops.alert_preview(mock=True))


def register(app):
    app.add_url_rule("/ops/analytics", "ops_page", ops_page)
    app.add_url_rule("/api/ops/analytics-daily/status", "ops_status", api_status)
    app.add_url_rule("/api/ops/analytics-daily/run", "ops_run", api_run, methods=["POST"])
    app.add_url_rule("/api/ops/analytics-daily/alert-preview", "ops_alert_preview", api_alert_preview)
