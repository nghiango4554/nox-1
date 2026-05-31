"""Routes: Content Jobs SP — 15 endpoint (list + push + detail + generate
+ queue worker + save + toggle-money + approve/unapprove + delete + sync + stats).

Tách từ app.py (Batch 6A refactor). Med risk — bg worker `content_writer.start_worker_async()`
phải giữ state qua re-import.

Dep:
- db.content_job(s)_* (CRUD jobs)
- content_writer (start_worker_async, stop_worker, queue_state, upload_local_images_in_body_to_haravan)
- job_sync (SEO_TITLE_FIELD, SEO_DESC_FIELD)
- seo as seo_mod (EMPTY_DESC_THRESHOLD)
- haravan_client (lazy, sync)
- ai_writer + codex_provider (lazy, provider check)
"""

import json
from datetime import datetime

from flask import (
    render_template, request, jsonify,
    redirect, url_for, flash, make_response,
)

import db
import job_sync
import content_writer
import seo as seo_mod


# ─────────────────────── LIST + PUSH ─────────────────────────────

def content_jobs_list_page():
    status = request.args.get("status") or None
    cate = request.args.get("cate") or None
    valid_statuses = ("pending", "drafting", "text_done", "draft", "approved", "synced", "failed")
    if status and status not in valid_statuses:
        status = None
    jobs = db.content_jobs_list(status=status, cate=cate, limit=500)
    stats = db.content_jobs_stats()
    categories = db.content_jobs_categories()
    for j in jobs:
        try:
            j["internal_links_list"] = json.loads(j["internal_links_json"]) if j.get("internal_links_json") else []
        except Exception:
            j["internal_links_list"] = []
    resp = make_response(render_template(
        "content_jobs_list.html",
        jobs=jobs, stats=stats, active_status=status,
        categories=categories, active_cate=cate,
    ))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def content_jobs_push_from_empty_desc():
    """Đẩy SP thiếu mô tả/ngắn từ /seo/empty-desc vào content_jobs."""
    try:
        threshold = int(request.form.get("threshold") or seo_mod.EMPTY_DESC_THRESHOLD)
    except ValueError:
        threshold = seo_mod.EMPTY_DESC_THRESHOLD
    items = db.seo_empty_desc_list(
        url_type="product", threshold=threshold,
        only_empty=True, limit=2000,
    )
    SKIP_STATUSES_PUSH = ("drafting", "text_done", "draft", "approved", "synced")
    pushed = 0
    skipped = 0
    for it in items:
        existing = db.content_job_get_by_url(it["url"])
        if existing and existing["status"] in SKIP_STATUSES_PUSH:
            skipped += 1
            continue
        wc = it.get("desc_word_count") or 0
        reason = "empty_desc" if wc == 0 else "short_desc"
        db.content_job_upsert(
            it["url"],
            product_title=it.get("title"),
            current_word_count=wc,
            reason=reason,
            status="pending" if not existing else existing["status"],
        )
        pushed += 1
    flash(
        f"📤 Đã đẩy {pushed} SP vào hàng đợi viết AI "
        f"({skipped} SP đã có content AI — bỏ qua, không overwrite).",
        "success",
    )
    return redirect(url_for("content_jobs_list_page"))


def content_jobs_push_one():
    """Đẩy 1 URL cụ thể vào jobs (dùng từ tab /seo/empty-desc cho từng SP)."""
    url = (request.form.get("url") or "").strip()
    reason = (request.form.get("reason") or "manual").strip()
    if not url:
        flash("Thiếu URL", "error")
        return redirect(request.referrer or url_for("content_jobs_list_page"))
    existing = db.content_job_get_by_url(url)
    if existing:
        flash(f"⏳ SP đã có trong hàng đợi (status: {existing['status']}). Mở để xem.", "info")
        return redirect(url_for("content_jobs_detail_page", job_id=existing["id"]))
    job_id = db.content_job_upsert(url, reason=reason, status="pending")
    flash("✅ Đã đẩy SP vào hàng đợi viết AI.", "success")
    return redirect(url_for("content_jobs_detail_page", job_id=job_id))


# ─────────────────────── DETAIL ──────────────────────────────────

def content_jobs_detail_page(job_id):
    job = db.content_job_get(job_id)
    if not job:
        flash("Không tìm thấy job.", "error")
        return redirect(url_for("content_jobs_list_page"))
    for k in ("ai_titles_json", "ai_metas_json", "ai_outline",
               "internal_links_json", "ai_stats_json"):
        try:
            job[k.replace("_json", "_list" if "links" in k or "titles" in k or "metas" in k else "_data")] = (
                json.loads(job[k]) if job.get(k) else []
            )
        except Exception:
            pass
    titles = []
    metas = []
    try:
        titles = json.loads(job["ai_titles_json"]) if job.get("ai_titles_json") else []
    except Exception:
        pass
    try:
        metas = json.loads(job["ai_metas_json"]) if job.get("ai_metas_json") else []
    except Exception:
        pass
    try:
        internal_link_list = json.loads(job["internal_links_json"]) if job.get("internal_links_json") else []
    except Exception:
        internal_link_list = []
    try:
        outline = json.loads(job["ai_outline"]) if job.get("ai_outline") else []
    except Exception:
        outline = []
    try:
        ai_stats = json.loads(job["ai_stats_json"]) if job.get("ai_stats_json") else {}
    except Exception:
        ai_stats = {}
    return render_template(
        "content_jobs_detail.html",
        job=job,
        titles=titles, metas=metas,
        internal_link_list=internal_link_list,
        outline=outline,
        ai_stats=ai_stats,
    )


# ─────────────────────── GENERATE + QUEUE ────────────────────────

def content_jobs_generate(job_id):
    """Đẩy 1 job vào queue → worker tự gen ngầm (return ngay, không đợi)."""
    job = db.content_job_get(job_id)
    if not job:
        flash("Job không tồn tại.", "error")
        return redirect(url_for("content_jobs_list_page"))
    import ai_writer
    import codex_provider
    has_provider = (
        codex_provider.is_codex_available()
        or ai_writer._load_openai_key()
        or ai_writer._load_anthropic_key()
    )
    if not has_provider:
        flash("⚠️ Chưa có AI provider. Cài Codex CLI (`npm install -g @openai/codex`).", "error")
        return redirect(url_for("content_jobs_detail_page", job_id=job_id))
    if job["status"] in ("failed", "draft", "drafting"):
        db.content_job_update(job_id, status="pending", error=None)
    started = content_writer.start_worker_async()
    msg = f"📥 Đã đẩy job #{job_id} vào queue."
    msg += " Worker đã start." if started else " Worker đang chạy sẽ pickup."
    msg += " Em làm việc khác đi, anh báo khi xong."
    flash(msg, "success")
    return redirect(url_for("content_jobs_detail_page", job_id=job_id))


def content_jobs_queue_start_all():
    """Reset tất cả job draft/failed về pending + start worker (gen tất cả pending)."""
    started = content_writer.start_worker_async()
    if started:
        flash("🚀 Worker đã start — sẽ gen lần lượt tất cả job pending. Em làm việc khác, anh báo tiến độ.", "success")
    else:
        flash("⏳ Worker đang chạy sẵn — không cần start lại.", "info")
    return redirect(url_for("content_jobs_list_page"))


def content_jobs_queue_stop():
    stopped = content_writer.stop_worker()
    if stopped:
        flash("🛑 Đã gửi signal dừng — worker sẽ stop sau khi xong job hiện tại.", "info")
    else:
        flash("Worker không đang chạy.", "info")
    return redirect(url_for("content_jobs_list_page"))


def content_jobs_queue_status_api():
    return jsonify(content_writer.queue_state())


# ─────────────────────── SAVE + MONEY + APPROVE/UNAPPROVE/DEL ──

def content_jobs_save(job_id):
    """Save edits từ form detail (title chosen + meta chosen + body edited + sync flags)."""
    job = db.content_job_get(job_id)
    if not job:
        flash("Job không tồn tại.", "error")
        return redirect(url_for("content_jobs_list_page"))
    try:
        sel_title_idx = int(request.form.get("selected_title_idx") or 0)
    except ValueError:
        sel_title_idx = 0
    try:
        sel_meta_idx = int(request.form.get("selected_meta_idx") or 0)
    except ValueError:
        sel_meta_idx = 0
    edited_title = (request.form.get("edited_title") or "").strip()
    edited_meta = (request.form.get("edited_meta") or "").strip()
    edited_body_html = request.form.get("edited_body_html") or ""
    is_money = 1 if request.form.get("is_money_product") else 0
    db.content_job_update(
        job_id,
        selected_title_idx=sel_title_idx,
        selected_meta_idx=sel_meta_idx,
        edited_title=edited_title,
        edited_meta=edited_meta,
        edited_body_html=edited_body_html,
        is_money_product=is_money,
        sync_body=1,
        sync_meta_title=1,
        sync_meta_desc=1,
    )
    flash("💾 Đã lưu chỉnh sửa.", "success")
    return redirect(url_for("content_jobs_detail_page", job_id=job_id))


def content_jobs_toggle_money(job_id):
    """Toggle is_money_product flag — endpoint riêng cho nút nhanh trên list."""
    job = db.content_job_get(job_id)
    if not job:
        return {"ok": False, "error": "not found"}, 404
    new_val = 0 if job.get("is_money_product") else 1
    db.content_job_update(job_id, is_money_product=new_val)
    return {"ok": True, "is_money_product": new_val}


def content_jobs_approve(job_id):
    """Đổi status job sang 'approved' — sẵn sàng sync."""
    job = db.content_job_get(job_id)
    if not job:
        flash("Job không tồn tại.", "error")
        return redirect(url_for("content_jobs_list_page"))
    if job["status"] != "draft":
        flash(f"Chỉ duyệt được job ở trạng thái 'draft' (hiện: {job['status']}).", "info")
        return redirect(url_for("content_jobs_detail_page", job_id=job_id))
    if not (job.get("edited_body_html") or "").strip():
        flash("⚠️ Body trống — không duyệt được.", "error")
        return redirect(url_for("content_jobs_detail_page", job_id=job_id))
    db.content_job_update(
        job_id,
        status="approved",
        approved_at=datetime.now().isoformat(timespec="seconds"),
    )
    flash("✅ Đã duyệt — chờ Sync ngoài bảng list.", "success")
    return redirect(url_for("content_jobs_list_page"))


def content_jobs_unapprove(job_id):
    db.content_job_update(job_id, status="draft", approved_at=None)
    flash("↩️ Đã chuyển về draft để chỉnh tiếp.", "info")
    return redirect(url_for("content_jobs_detail_page", job_id=job_id))


def content_jobs_delete(job_id):
    db.content_job_delete(job_id)
    flash("🗑️ Đã xoá job.", "info")
    return redirect(url_for("content_jobs_list_page"))


# ─────────────────────── SYNC HARAVAN ────────────────────────────

def content_jobs_sync():
    """Bulk sync các job 'approved' lên Haravan (update body_html + optional meta)."""
    import haravan_client
    job_ids_raw = request.form.getlist("job_ids")
    if not job_ids_raw:
        flash("⚠️ Chưa chọn job nào để sync.", "error")
        return redirect(url_for("content_jobs_list_page"))
    job_ids = []
    for s in job_ids_raw:
        try:
            job_ids.append(int(s))
        except ValueError:
            continue
    ok, fail = 0, 0
    errors = []
    for jid in job_ids:
        job = db.content_job_get(jid)
        if not job or job["status"] != "approved":
            continue
        if not job.get("haravan_id"):
            db.content_job_update(jid, status="failed", error="Thiếu haravan_id — không sync được.")
            fail += 1
            errors.append(f"#{jid}: thiếu haravan_id")
            continue
        payload = {}
        if job.get("sync_body"):
            try:
                from content_writer import upload_local_images_in_body_to_haravan
                body_with_cdn = upload_local_images_in_body_to_haravan(job.get("edited_body_html") or "")
                payload["body_html"] = body_with_cdn
                if body_with_cdn != (job.get("edited_body_html") or ""):
                    db.content_job_update(jid, edited_body_html=body_with_cdn)
            except Exception as e:
                db.content_job_update(jid, status="failed", error=f"Upload local images fail: {str(e)[:200]}")
                fail += 1
                errors.append(f"#{jid}: upload img fail")
                continue
        sync_title = job.get("sync_meta_title")
        sync_desc = job.get("sync_meta_desc")
        if not payload and not sync_title and not sync_desc:
            db.content_job_update(jid, status="failed", error="Không tick field nào để sync.")
            fail += 1
            errors.append(f"#{jid}: chưa tick field nào")
            continue
        if sync_title:
            payload[job_sync.SEO_TITLE_FIELD] = (job.get("edited_title") or "").strip()
        if sync_desc:
            payload[job_sync.SEO_DESC_FIELD] = (job.get("edited_meta") or "").strip()
        try:
            haravan_client.update_product(int(job["haravan_id"]), payload)
            db.content_job_update(
                jid, status="synced",
                synced_at=datetime.now().isoformat(timespec="seconds"),
                error=None,
            )
            ok += 1
        except Exception as e:
            db.content_job_update(jid, status="failed", error=f"Sync: {e.__class__.__name__}: {str(e)[:200]}")
            fail += 1
            errors.append(f"#{jid}: {e.__class__.__name__}")
    if ok:
        db.activity_log(
            kind="content_jobs_sync", icon="🚀",
            title=f"Sync {ok} bài lên Haravan",
            description=f"Lỗi: {fail}",
            href=url_for("content_jobs_list_page"),
        )
    flash(f"🚀 Sync xong: {ok} OK, {fail} lỗi." + (f" Lỗi: {', '.join(errors[:5])}" if errors else ""),
          "success" if ok else "error")
    return redirect(url_for("content_jobs_list_page", status="synced" if ok else None))


def content_jobs_stats_api():
    return jsonify(db.content_jobs_stats())


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 15 route Content Product Jobs."""
    app.add_url_rule("/content-jobs", "content_jobs_list_page", content_jobs_list_page)
    app.add_url_rule("/content-jobs/push-from-empty-desc",
                     "content_jobs_push_from_empty_desc", content_jobs_push_from_empty_desc, methods=["POST"])
    app.add_url_rule("/content-jobs/push-one",
                     "content_jobs_push_one", content_jobs_push_one, methods=["POST"])
    app.add_url_rule("/content-jobs/<int:job_id>",
                     "content_jobs_detail_page", content_jobs_detail_page)
    app.add_url_rule("/content-jobs/<int:job_id>/generate",
                     "content_jobs_generate", content_jobs_generate, methods=["POST"])
    app.add_url_rule("/content-jobs/queue/start-all",
                     "content_jobs_queue_start_all", content_jobs_queue_start_all, methods=["POST"])
    app.add_url_rule("/content-jobs/queue/stop",
                     "content_jobs_queue_stop", content_jobs_queue_stop, methods=["POST"])
    app.add_url_rule("/api/content-jobs/queue-status",
                     "content_jobs_queue_status_api", content_jobs_queue_status_api)
    app.add_url_rule("/content-jobs/<int:job_id>/save",
                     "content_jobs_save", content_jobs_save, methods=["POST"])
    app.add_url_rule("/content-jobs/<int:job_id>/toggle-money",
                     "content_jobs_toggle_money", content_jobs_toggle_money, methods=["POST"])
    app.add_url_rule("/content-jobs/<int:job_id>/approve",
                     "content_jobs_approve", content_jobs_approve, methods=["POST"])
    app.add_url_rule("/content-jobs/<int:job_id>/unapprove",
                     "content_jobs_unapprove", content_jobs_unapprove, methods=["POST"])
    app.add_url_rule("/content-jobs/<int:job_id>/delete",
                     "content_jobs_delete", content_jobs_delete, methods=["POST"])
    app.add_url_rule("/content-jobs/sync", "content_jobs_sync", content_jobs_sync, methods=["POST"])
    app.add_url_rule("/api/content-jobs/stats", "content_jobs_stats_api", content_jobs_stats_api)
