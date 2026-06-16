# -*- coding: utf-8 -*-
"""Routes — Blog Rewrite AI (P1: page + read-only API + import-scan local DB).

KHÔNG gọi AI, KHÔNG PUT Haravan, KHÔNG upload ảnh. import-scan chỉ ghi SQLite local.
Generate/Approve/Apply/Rollback = P2/P3+ (chưa làm).
"""
import csv, io, sys, subprocess
from pathlib import Path
from flask import render_template, request, jsonify, Response
import blog_rewrite as br
import blog_rewrite_apply as ap
import blog_rewrite_remediate as rem

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
    return jsonify({"ok": False, "phase": "P5B",
                    "error": "Live apply chưa bật. Không có thay đổi nào được gửi lên Haravan."}), 501


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
    provider = p.get("provider", "mock")
    res = br.create_job(ids, mode=mode, explicit_confirm=bool(p.get("explicit_confirm")), provider=provider)
    if res.get("ok"):
        _spawn_worker(res["job_id"])
    code = 200 if res.get("ok") else (409 if res.get("needs_confirm") else 400)
    return jsonify(res), code


def api_provider_health():
    import blog_rewrite_gen as gen
    return jsonify(gen.provider_health(request.args.get("provider", "claude")))


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


def api_candidate_draft(cid):
    d = br.latest_draft_for_candidate(int(cid))
    if not d:
        return jsonify({"ok": False, "error": "chưa có draft"}), 404
    return jsonify({"ok": True, "draft": d})


# ─────────────── P4: review studio (local) ───────────────
def api_edit_draft(did):
    return jsonify(br.edit_draft(int(did), request.get_json(silent=True) or {}))


def api_candidate_drafts(cid):
    return jsonify({"drafts": br.list_drafts(int(cid))})


def api_clone_version(did):
    return jsonify(br.clone_version(int(did)))


def api_regenerate_single(cid):
    p = request.get_json(silent=True) or {}
    if not p.get("explicit_confirm"):
        return jsonify({"ok": False, "error": "regenerate-single cần explicit_confirm=true"}), 400
    res = br.create_job([int(cid)], mode="single", provider=p.get("provider", "claude"))
    if res.get("ok"):
        _spawn_worker(res["job_id"])
    return jsonify(res), (200 if res.get("ok") else 400)


def api_approve_local(did):
    return jsonify(br.approve_local(int(did)))


def api_reject_local(did):
    return jsonify(br.reject_local(int(did), (request.get_json(silent=True) or {}).get("reason", "")))


def api_image_plan(did):
    return jsonify(ap.build_image_rehost_plan(int(did), refresh=False))


def api_image_plan_refresh(did):
    return jsonify(ap.build_image_rehost_plan(int(did), refresh=True))


def api_batch_results():
    return jsonify({"results": br.batch_results()})


# ─────────────── P5E: image remediation queue (local) ───────────────
def api_image_summary():
    return jsonify(rem.image_summary())


def api_image_items():
    a = request.args
    return jsonify(rem.list_items(candidate_id=a.get("candidate_id"), source_class=a.get("source_class"),
        availability=a.get("availability"), selected_action=a.get("selected_action"),
        review_status=a.get("review_status"), q=a.get("q"),
        limit=min(int(a.get("limit", 200)), 1000), offset=int(a.get("offset", 0))))


def api_image_set_action(iid):
    p = request.get_json(silent=True) or {}
    return jsonify(rem.set_action(int(iid), p.get("action", ""), p.get("note")))


def api_image_bulk_dead():
    p = request.get_json(silent=True) or {}
    return jsonify(rem.bulk_dead_local(p.get("confirm_phrase", "")))


def api_image_remediate(cid):
    p = request.get_json(silent=True) or {}
    return jsonify(rem.build_remediated_draft_local(int(cid), p.get("source_draft_id")))


def api_image_gate(cid):
    return jsonify({"candidate_id": int(cid), "apply_gate": rem.article_gate(int(cid))})


def api_image_export():
    return jsonify(rem.export_workload())


# ─────────────── P5A: apply preview (dry-run, KHÔNG PUT) ───────────────
def api_apply_preview(did):
    return jsonify(ap.apply_preview(int(did)))


def api_backup_preview(did):
    return jsonify(ap.backup_preview(int(did)))


# ─────────────── P5B-1: armed apply (feature flag OFF → 423) ───────────────
def api_apply_live(did):
    p = request.get_json(silent=True) or {}
    res, code = ap.apply_draft_body_only(
        int(did), confirm_phrase=p.get("confirm_phrase", ""), fields=p.get("fields"),
        confirm_reviewed_draft=bool(p.get("confirm_reviewed_draft")),
        confirm_reviewed_images=bool(p.get("confirm_reviewed_images")))
    return jsonify(res), code


def api_rollback_live(did):
    p = request.get_json(silent=True) or {}
    res, code = ap.rollback_draft_apply(int(did), confirm_phrase=p.get("confirm_phrase", ""))
    return jsonify(res), code


def api_apply_status(did):
    return jsonify(ap.apply_status(int(did)))


def api_bulk_apply():
    return jsonify({"ok": False, "locked": True, "error": "Bulk apply chưa được hỗ trợ."}), 501


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
    app.add_url_rule("/api/blog-rewrite/candidates/<cid>/draft", "br_candidate_draft", api_candidate_draft)
    # P4 review studio (local — KHÔNG PUT)
    app.add_url_rule("/api/blog-rewrite/drafts/<did>", "br_edit_draft", api_edit_draft, methods=["PATCH"])
    app.add_url_rule("/api/blog-rewrite/candidates/<cid>/drafts", "br_candidate_drafts", api_candidate_drafts)
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/clone-version", "br_clone_version", api_clone_version, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/candidates/<cid>/regenerate-single", "br_regen_single", api_regenerate_single, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/approve-local", "br_approve_local", api_approve_local, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/reject-local", "br_reject_local", api_reject_local, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/image-plan", "br_image_plan", api_image_plan)
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/image-plan/refresh", "br_image_plan_refresh", api_image_plan_refresh, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/batch-results", "br_batch_results", api_batch_results)
    # P5E image remediation queue (local — KHÔNG upload/PUT)
    app.add_url_rule("/api/blog-rewrite/image-summary", "br_image_summary", api_image_summary)
    app.add_url_rule("/api/blog-rewrite/image-items", "br_image_items", api_image_items)
    app.add_url_rule("/api/blog-rewrite/image-items/<iid>/action", "br_image_set_action", api_image_set_action, methods=["POST", "PATCH"])
    app.add_url_rule("/api/blog-rewrite/image-bulk-dead", "br_image_bulk_dead", api_image_bulk_dead, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/candidates/<cid>/remediate-images", "br_image_remediate", api_image_remediate, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/candidates/<cid>/image-gate", "br_image_gate", api_image_gate)
    app.add_url_rule("/api/blog-rewrite/image-export", "br_image_export", api_image_export)
    # P5A apply preview (dry-run — KHÔNG PUT/upload)
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/apply-preview", "br_apply_preview", api_apply_preview, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/backup-preview", "br_backup_preview", api_backup_preview, methods=["POST"])
    # P5B-1 armed apply (flag OFF → 423 Locked)
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/apply-live", "br_apply_live", api_apply_live, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/rollback-live", "br_rollback_live", api_rollback_live, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/drafts/<did>/apply-status", "br_apply_status", api_apply_status)
    app.add_url_rule("/api/blog-rewrite/bulk-apply", "br_bulk_apply", api_bulk_apply, methods=["POST"])
    # P2 jobs (mock)
    app.add_url_rule("/api/blog-rewrite/jobs", "br_create_job", api_create_job, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/jobs", "br_jobs", api_jobs)
    app.add_url_rule("/api/blog-rewrite/jobs/<jid>", "br_job_detail", api_job_detail)
    app.add_url_rule("/api/blog-rewrite/jobs/<jid>/cancel", "br_job_cancel", api_job_cancel, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/jobs/<jid>/retry-failed", "br_job_retry", api_job_retry, methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/drafts/<did>", "br_draft", api_draft)
    app.add_url_rule("/api/blog-rewrite/provider-health", "br_provider_health", api_provider_health)
    # P5 placeholder — BLOCKED (501)
    for ep, path in [("approve", "approve"), ("reject", "reject"), ("apply", "apply"), ("rollback", "rollback")]:
        app.add_url_rule(f"/api/blog-rewrite/drafts/<did>/{path}", f"br_p5_{ep}",
                         lambda did=None: _p5_blocked(), methods=["POST"])
    app.add_url_rule("/api/blog-rewrite/bulk-approve", "br_p5_bulk_approve",
                     lambda: _p5_blocked(), methods=["POST"])
