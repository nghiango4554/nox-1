"""Routes: GSC direct API — /api/gsc/status + /api/gsc/refresh (LIVE-1A core sync).

Refresh = background thread + lock (409 already_running). Render KHÔNG gọi GSC API.
Route Sheets cũ /seo/gsc/refresh GIỮ NGUYÊN (fallback), không đụng.
"""
from flask import jsonify, request

from services import gsc_api_client as gsc
from services import gsc_sync_service as gsync


def api_gsc_status():
    gsync.reconcile_stale_runs()
    probe = request.args.get("probe", "0") in ("1", "true", "yes")
    return jsonify(gsync.get_status(probe=probe))


def api_gsc_refresh():
    st = gsc.config_state()
    if not st["configured"]:
        return jsonify({"ok": False, "error": "not_configured"}), 400
    if not gsc.token_present():
        return jsonify({"ok": False, "error": "token_missing"}), 400
    sync_type = request.args.get("type")
    if not sync_type and request.is_json:
        sync_type = (request.json or {}).get("type")
    sync_type = sync_type if sync_type in ("incremental", "backfill") else "incremental"
    gsync.reconcile_stale_runs()
    res = gsync.start_sync_async(sync_type)
    if not res.get("started"):
        return jsonify({"ok": False, "status": "already_running",
                        "started_at": res.get("started_at"), "sync_type": res.get("sync_type")}), 409
    return jsonify({"ok": True, **res})


def register(app):
    app.add_url_rule("/api/gsc/status", "api_gsc_status", api_gsc_status)
    app.add_url_rule("/api/gsc/refresh", "api_gsc_refresh", api_gsc_refresh, methods=["POST"])
