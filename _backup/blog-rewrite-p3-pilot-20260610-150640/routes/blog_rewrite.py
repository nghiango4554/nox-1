# -*- coding: utf-8 -*-
"""Routes — Blog Rewrite AI (P1: page + read-only API + import-scan local DB).

KHÔNG gọi AI, KHÔNG PUT Haravan, KHÔNG upload ảnh. import-scan chỉ ghi SQLite local.
Generate/Approve/Apply/Rollback = P2/P3+ (chưa làm).
"""
import csv, io, sys, subprocess
from pathlib import Path
from flask import render_template, request, jsonify, Response
import blog_rewrite as br

_WORKER = Path(__file__).parent.parent / "_scripts" / "run_blog_rewrite_worker.py"


def _spawn_worker(job_id):
    """Spawn worker mock detached qua sys.executable (KHÔNG block Flask)."""
    flags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([sys.executable, str(_WORKER), "--job", str(job_id)],
                     cwd=str(_WORKER.parent.parent), stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags, close_fds=True)


def _p5_blocked():
    return jsonify({"ok": False, "phase": "P5",
                    "error": "Chức năng chưa bật. Không có thay đổi nào được gửi lên Haravan."}), 501


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


# ─────────────── P2: selection ───────────────
def api_select(cid):
    payload = request.get_json(silent=True) or {}
    br.set_selected(int(cid), bool(payload.get("selected", True)))
    return jsonify({"ok": True})


def api_select_bulk():
    p = request.get_json(silent=True) or {}
    res = br.bulk_select(mode=p.get("mode", "top_priority"), limit=int(p.get("limit", 5)),
                         risk=p.get("risk", "high"), ids=p.get("ids"))
    return jsonify(res)


# ─────────────── P2: jobs (mock) ───────────────
def api_create_job():
    p = request.get_json(silent=True) or {}
    mode = p.get("mode", "selected")
    if mode == "top_priority":
        br.bulk_select("clear_all")
        br.bulk_select("top_priority", limit=int(p.get("limit", 5)), risk="high")
    ids = p.get("ids") or br.selected_ids()
    res = br.create_job(ids, mode=mode, explicit_confirm=bool(p.get("explicit_confirm")))
    if res.get("ok"):
        _spawn_worker(res["job_id"])
    code = 200 if res.get("ok") else (409 if res.get("needs_confirm") else 400)
    return jsonify(res), code


def api_jobs():
    br.recover_stale_jobs()
    return jsonify({"jobs": br.list_jobs()})


def api_job_detail(jid):
    j = br.get_job(int(jid))
    if not j:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "job": j})


def api_job_cancel(jid):
    return jsonify(br.cancel_job(int(jid)))


def api_job_retry(jid):
    res = br.retry_failed(int(jid))
    if res.get("ok"):
        _spawn_worker(res["job_id"])
    return jsonify(res), (200 if res.get("ok") else 400)


def api_draft(did):
    d = br.get_draft(int(did))
    if not d:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "draft": d})


def api_candidate_events(cid):
    return jsonify({"events": br.candidate_events(int(cid))})


def register(app):
    """Đăng ký route Blog Rewrite AI (P1 + P2 mock queue)."""
    # P1
    app.add_url_rule("/seo/blog-rewrite-ai", "seo_blog_rewrite_page", seo_blog_rewrite_page)
    app.add_url_rule("/api/blog-rewrite/status", "br_status", api_status)
    app.add_url_rule("/api/blog-rewrite/candidates", "br_candidates", api_candidates)
    app.add_url_rule("/api/blog-rewrite/candidates/<cid>", "br_candidate_detail", api_candidate_detail)
    app.add_url_rule("/api/blog-rewrite/import-scan", "br_import_scan", api_import_scan, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/export", "br_export", api_export)
    # P2 selection
    app.add_url_rule("/api/blog-rewrite/candidates/<cid>/select", "br_select", api_select, methods=["PATCH", "POST"])
    app.add_url_rule("/api/blog-rewrite/candidates/select-bulk", "br_select_bulk", api_select_bulk, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/candidates/<cid>/events", "br_candidate_events", api_candidate_events)
    # P2 jobs (mock)
    app.add_url_rule("/api/blog-rewrite/jobs", "br_create_job", api_create_job, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/jobs", "br_jobs", api_jobs)
    app.add_url_rule("/api/blog-rewrite/jobs/<jid>", "br_job_detail", api_job_detail)
    app.add_url_rule("/api/blog-rewrite/jobs/<jid>/cancel", "br_job_cancel", api_job_cancel, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/jobs/<jid>/retry-failed", "br_job_retry", api_job_retry, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/drafts/<did>", "br_draft", api_draft)
    # P5 placeholder — BLOCKED (501)
    for ep, path in [("approve", "approve"), ("reject", "reject"), ("apply", "apply"), ("rollback", "rollback")]:
        app.add_url_rule(f"/api/blog-rewrite/drafts/<did>/{path}", f"br_p5_{ep}",
                         lambda did=None: _p5_blocked(), methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/bulk-approve", "br_p5_bulk_approve",
                     lambda: _p5_blocked(), methods=["POST"])
