# -*- coding: utf-8 -*-
"""Routes — Blog Rewrite AI (P1: page + read-only API + import-scan local DB).

KHÔNG gọi AI, KHÔNG PUT Haravan, KHÔNG upload ảnh. import-scan chỉ ghi SQLite local.
Generate/Approve/Apply/Rollback = P2/P3+ (chưa làm).
"""
import csv, io
from flask import render_template, request, jsonify, Response
import blog_rewrite as br


def seo_blog_rewrite_page():
    return render_template("blog_rewrite_ai.html", summary=br.status_summary())


def api_status():
    return jsonify(br.status_summary())


def api_candidates():
    a = request.args
    res = br.list_candidates(
        risk=a.get("risk") or None, status=a.get("status") or None,
        source_host=a.get("source_host") or None, traffic=a.get("traffic") or None,
        q=a.get("q") or None, only_selected=(a.get("only_selected") == "1"),
        sort=a.get("sort", "priority_score"), direction=a.get("direction", "desc"),
        limit=min(int(a.get("limit", 100)), 500), offset=int(a.get("offset", 0)))
    return jsonify(res)


def api_candidate_detail(cid):
    d = br.get_candidate(int(cid))
    if not d:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "candidate": d})


def api_import_scan():
    """POST: import scan vào DB local. dry_run mặc định True (chỉ preview).
    KHÔNG ghi Haravan, KHÔNG gọi AI. apply=true mới ghi DB."""
    payload = request.get_json(silent=True) or {}
    dry = not (payload.get("apply") is True or request.args.get("apply") == "1")
    try:
        res = br.build_candidates(dry_run=dry)
        return jsonify({"ok": True, "dry_run": dry, **res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


def api_export():
    res = br.list_candidates(limit=500, offset=0)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["article_url", "title", "author", "published_year", "risk_level",
                "source_group_primary", "priority_score", "gsc_clicks_28d",
                "gsc_impressions_28d", "ga4_organic_sessions_28d", "traffic_data_status",
                "status", "selected"])
    for r in res["items"]:
        w.writerow([r["article_url"], r["title"], r["author"], r["published_year"],
                    r["risk_level"], r["source_group_primary"], r["priority_score"],
                    r["gsc_clicks_28d"], r["gsc_impressions_28d"], r["ga4_organic_sessions_28d"],
                    r["traffic_data_status"], r["status"], r["selected"]])
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=blog_rewrite_candidates.csv"})


def register(app):
    """Đăng ký route Blog Rewrite AI (P1)."""
    app.add_url_rule("/seo/blog-rewrite-ai", "seo_blog_rewrite_page", seo_blog_rewrite_page)
    app.add_url_rule("/api/blog-rewrite/status", "br_status", api_status)
    app.add_url_rule("/api/blog-rewrite/candidates", "br_candidates", api_candidates)
    app.add_url_rule("/api/blog-rewrite/candidates/<cid>", "br_candidate_detail", api_candidate_detail)
    app.add_url_rule("/api/blog-rewrite/import-scan", "br_import_scan", api_import_scan, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/export", "br_export", api_export)
