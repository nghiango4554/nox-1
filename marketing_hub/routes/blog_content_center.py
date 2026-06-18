# -*- coding: utf-8 -*-
"""Routes — Blog SEO Command Center (/blog-content) + API.

Thay trang /blog-content cũ. Chỉ hiển thị 40 bài roadmap (source='roadmap').
Sync Haravan GATED (confirm phrase). Không tự publish, không sửa theme, không scheduler.
"""
import csv
import io
import sys
from pathlib import Path

from flask import request, jsonify, render_template, redirect, Response

sys.path.insert(0, str(Path(__file__).parent.parent))
import blog_content_center as bcc


def blog_content_page():
    bcc.ensure_schema()
    payload = bcc.ui_payload()
    return render_template("blog_content.html", shb=payload["SHB"], sh=payload["SH"])


def blog_content_edit_page(item_id):
    it = bcc.get_item(item_id)
    if not it:
        return redirect("/blog-content", code=302)
    import json as _json
    brief = {
        "secondary": _json.loads(it.get("secondary_keywords_json") or "[]"),
        "outline": _json.loads(it.get("outline_json") or "[]"),
        "internal": [(l.get("target") or l.get("anchor")) if isinstance(l, dict) else l
                     for l in _json.loads(it.get("internal_links_json") or "[]")],
    }
    return render_template("blog_content_edit.html", it=it, brief=brief)


def api_save_edit(item_id):
    d = request.get_json(silent=True) or {}
    try:
        bcc.save_edit(item_id, title=d.get("title"), meta=d.get("meta"),
                      h1=d.get("h1"), slug=d.get("slug"), body=d.get("body"))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ─────────── API ───────────
def api_status():
    return jsonify(bcc.status_summary())


def api_items():
    f = request.args
    items = bcc.list_items(
        cluster=f.get("cluster"), priority=f.get("priority"), status=f.get("status"),
        week=f.get("week"), owner_missing=(f.get("no_owner") == "1"),
        overdue=(f.get("overdue") == "1"), q=f.get("q"))
    return jsonify({"items": items, "count": len(items)})


def api_item(item_id):
    it = bcc.get_item(item_id)
    if not it:
        return jsonify({"error": "not found"}), 404
    return jsonify(it)


def api_set_status(item_id):
    status = (request.get_json(silent=True) or {}).get("status", "")
    try:
        return jsonify(bcc.set_status(item_id, status))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


def api_set_owner(item_id):
    owner = (request.get_json(silent=True) or {}).get("owner", "")
    return jsonify(bcc.set_field(item_id, "owner", owner, {"owner"}))


def api_set_deadline(item_id):
    data = request.get_json(silent=True) or {}
    field = data.get("field", "deadline_publish")
    val = data.get("value", "")
    try:
        return jsonify(bcc.set_field(item_id, field, val, {"deadline_draft", "deadline_publish"}))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


def api_import_roadmap():
    try:
        return jsonify(bcc.import_roadmap())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def api_kanban():
    return jsonify(bcc.kanban())


def api_calendar():
    return jsonify(bcc.calendar())


def api_kpi():
    return jsonify(bcc.kpi_monitor())


def api_generate_brief(item_id):
    try:
        return jsonify({"ok": True, "brief": bcc.build_brief(item_id)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def api_generate_draft(item_id):
    try:
        return jsonify(bcc.generate_draft(item_id))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def api_sync(item_id):
    data = request.get_json(silent=True) or {}
    res = bcc.sync_item(item_id, data.get("confirm", ""), publish=bool(data.get("publish")))
    code = 200 if res.get("ok") else 400
    return jsonify(res), code


def api_export():
    items = bcc.list_items()
    cols = ["roadmap_id", "cluster", "priority", "week", "phase", "title", "intent",
            "funnel", "seo_score", "impact", "status", "owner", "deadline_draft",
            "deadline_publish", "target_url", "main_keyword", "next_action"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for it in items:
        w.writerow([it.get(c, "") for c in cols])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=blog_content_roadmap.csv"})


def blog_rewrite_archived():
    """Trang AI Viết Lại Blog cũ đã archive -> chuyển về Command Center."""
    return redirect("/blog-content", code=302)


def register(app):
    app.add_url_rule("/blog-content", "blog_content_page", blog_content_page)
    app.add_url_rule("/blog-content/<int:item_id>/edit", "bcc_edit_page", blog_content_edit_page)
    app.add_url_rule("/blog-content/<int:item_id>/save-edit", "bcc_save_edit",
                     api_save_edit, methods=["POST"])
    app.add_url_rule("/api/blog-content/status", "bcc_status", api_status)
    app.add_url_rule("/api/blog-content/items", "bcc_items", api_items)
    app.add_url_rule("/api/blog-content/items/<int:item_id>", "bcc_item", api_item)
    app.add_url_rule("/api/blog-content/items/<int:item_id>/status", "bcc_set_status",
                     api_set_status, methods=["POST"])
    app.add_url_rule("/api/blog-content/items/<int:item_id>/owner", "bcc_set_owner",
                     api_set_owner, methods=["POST"])
    app.add_url_rule("/api/blog-content/items/<int:item_id>/deadline", "bcc_set_deadline",
                     api_set_deadline, methods=["POST"])
    app.add_url_rule("/api/blog-content/import-roadmap", "bcc_import",
                     api_import_roadmap, methods=["POST"])
    app.add_url_rule("/api/blog-content/export", "bcc_export", api_export)
    app.add_url_rule("/api/blog-content/kanban", "bcc_kanban", api_kanban)
    app.add_url_rule("/api/blog-content/calendar", "bcc_calendar", api_calendar)
    app.add_url_rule("/api/blog-content/kpi", "bcc_kpi", api_kpi)
    app.add_url_rule("/api/blog-content/items/<int:item_id>/generate-brief", "bcc_gen_brief",
                     api_generate_brief, methods=["POST"])
    app.add_url_rule("/api/blog-content/items/<int:item_id>/generate-draft", "bcc_gen_draft",
                     api_generate_draft, methods=["POST"])
    app.add_url_rule("/api/blog-content/items/<int:item_id>/sync", "bcc_sync",
                     api_sync, methods=["POST"])
    # archived blog-rewrite-ai -> redirect (route cũ không crash)
    app.add_url_rule("/seo/blog-rewrite-ai", "seo_blog_rewrite_page", blog_rewrite_archived)
