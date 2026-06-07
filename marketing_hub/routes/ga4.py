"""Routes: GA4 Analytics — tab /seo/ga4 + /api/ga4/* (Batch 2: status + refresh skeleton).

Trang render CHỈ đọc config (fs) + sync log (DB) — KHÔNG gọi GA4 API.
API probe (validate property/token) chỉ chạy ở /api/ga4/status?probe=1.
Full dashboard report UI, SEO join, task center: batch sau.
"""
from flask import render_template, jsonify, request

from services import ga4_config, ga4_client, ga4_sync_service
from services import ga4_report_service as rpt


def ga4_page():
    state = ga4_config.config_state()
    last_sync = ga4_sync_service.latest_sync()
    return render_template(
        "seo_ga4.html",
        state=state,
        token_present=ga4_client.token_present(),
        last_sync=last_sync,
        is_running=ga4_sync_service.is_running(),
    )


def api_ga4_status():
    ga4_sync_service.reconcile_stale_runs()       # dọn run treo do app restart
    probe = request.args.get("probe", "1") not in ("0", "false", "no")
    data = ga4_client.status(probe=probe)
    data["last_sync"] = ga4_sync_service.latest_sync()
    data.update(ga4_sync_service.running_info())
    return jsonify(data)


def api_ga4_refresh():
    sync_type = request.args.get("type")
    if not sync_type and request.is_json:
        sync_type = (request.json or {}).get("type")
    sync_type = sync_type or "incremental"
    if sync_type not in ("incremental", "backfill"):
        sync_type = "incremental"
    st = ga4_config.config_state()
    if not st["configured"]:
        return jsonify({"ok": False, "error": "not_configured"}), 400
    if not ga4_client.token_present():
        return jsonify({"ok": False, "error": "token_missing"}), 400

    ga4_sync_service.reconcile_stale_runs()
    result = ga4_sync_service.start_sync_async(sync_type)
    if not result.get("started"):
        return jsonify({
            "ok": False, "status": "already_running",
            "started_at": result.get("started_at"),
            "sync_type": result.get("sync_type"),
        }), 409
    return jsonify({"ok": True, **result})


# ─────────────── Report endpoints (Batch 3 — đọc SQLite, KHÔNG gọi GA4 API) ───────────────
def api_ga4_overview():
    return jsonify(rpt.overview(request.args))


def api_ga4_channels():
    return jsonify(rpt.channels(request.args))


def api_ga4_landing_pages():
    return jsonify(rpt.landing_pages(request.args))


def api_ga4_devices():
    return jsonify(rpt.devices(request.args))


def api_ga4_events():
    return jsonify(rpt.events(request.args))


def api_ga4_ecommerce():
    return jsonify(rpt.ecommerce(request.args))


def api_ga4_realtime():
    force = request.args.get("force") in ("1", "true", "yes")
    return jsonify(rpt.realtime(request.args, force=force))


def register(app):
    app.add_url_rule("/seo/ga4", "ga4_page", ga4_page)
    app.add_url_rule("/api/ga4/status", "api_ga4_status", api_ga4_status)
    app.add_url_rule("/api/ga4/refresh", "api_ga4_refresh", api_ga4_refresh, methods=["POST"])
    # report (GET, read-only SQLite)
    app.add_url_rule("/api/ga4/overview", "api_ga4_overview", api_ga4_overview)
    app.add_url_rule("/api/ga4/channels", "api_ga4_channels", api_ga4_channels)
    app.add_url_rule("/api/ga4/landing-pages", "api_ga4_landing_pages", api_ga4_landing_pages)
    app.add_url_rule("/api/ga4/devices", "api_ga4_devices", api_ga4_devices)
    app.add_url_rule("/api/ga4/events", "api_ga4_events", api_ga4_events)
    app.add_url_rule("/api/ga4/ecommerce", "api_ga4_ecommerce", api_ga4_ecommerce)
    app.add_url_rule("/api/ga4/realtime", "api_ga4_realtime", api_ga4_realtime)
