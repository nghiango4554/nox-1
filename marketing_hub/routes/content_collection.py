"""Routes: Content Collection — 10 endpoint (list + detail + gen×3 (bg/status/stop) +
gen-job + gen-title-meta + save + sync + sync-all).

Tách từ app.py (Batch 6B). Med risk — bg worker `_gen_bg_worker_collection_loop`
dùng `_GEN_BG` ở routes/state (đã verify shared state qua re-import).

Move kèm helpers:
- _collection_jobs_list/get/update
- _build_tier_groups
- _gen_bg_worker_collection_loop, _enqueue_collection_gen
- _save_seo_job_edits (duplicate sang content_blog Batch 6C để tránh phụ thuộc chéo)

Dep:
- db
- routes.state (_GEN_BG, _GEN_BG_LOCK)
- collection_content_writer (lazy import)
- job_sync (apply_sync_result)
- seo_quality (auto compute quality score)
"""

import json
import os
import threading
import time
from datetime import datetime

from flask import (
    render_template, request, jsonify,
    redirect, url_for, flash,
)

import db
import job_sync
from routes.state import _GEN_BG, _GEN_BG_LOCK


# ─────────────────────── DB HELPERS ──────────────────────────────

def _collection_jobs_list(status: str = None):
    conn = db.get_conn()
    sql = "SELECT * FROM collection_jobs"
    args = []
    if status:
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY id ASC"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _collection_jobs_get(job_id: int):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM collection_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _collection_jobs_update(job_id: int, **fields):
    if not fields:
        return
    if any(k in fields for k in ("edited_title", "edited_meta", "edited_body_html")):
        row = _collection_jobs_get(job_id) or {}
        title = fields.get("edited_title", row.get("edited_title")) or ""
        meta = fields.get("edited_meta", row.get("edited_meta")) or ""
        body = fields.get("edited_body_html", row.get("edited_body_html")) or ""
        if title or meta or body:
            try:
                import seo_quality
                rate = seo_quality.rate_content(title, meta, body, url_type="collection")
                fields["quality_score"] = rate["score"]
                fields["readability_score"] = int(rate["readability"].get("score", 0))
                fields["quality_breakdown"] = json.dumps({
                    "breakdown": {k: {kk: vv for kk, vv in v.items() if kk in ("score", "max")}
                                   for k, v in rate["breakdown"].items()},
                    "issues_high": rate["issues_high"],
                    "issues_med": rate["issues_med"],
                    "issues_low": rate["issues_low"],
                    "tier": rate["tier"],
                }, ensure_ascii=False)
            except Exception as e:
                print(f"[quality_score] err: {e}")
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    keys = list(fields.keys())
    sets = ", ".join(f"{k}=?" for k in keys)
    conn = db.get_conn()
    conn.execute(f"UPDATE collection_jobs SET {sets} WHERE id=?",
                 [*[fields[k] for k in keys], job_id])
    conn.commit()
    conn.close()


def _build_tier_groups(all_jobs):
    """Group jobs by tier1 → tier2, maintaining nav order from taxonomy JSON."""
    tax_path = os.path.join(os.path.dirname(__file__), "..", "data", "collection_taxonomy.json")
    try:
        with open(tax_path, encoding="utf-8") as f:
            tax_data = json.load(f)
        t1_order = list(tax_data["taxonomy"].keys())
    except Exception:
        t1_order = []

    t1_map = {}
    for j in all_jobs:
        t1h = j.get("tier1_handle") or "uncategorized"
        t1n = j.get("tier1_name") or "Chưa phân loại"
        t2h = j.get("tier2_handle") or t1h
        t2n = j.get("tier2_name") or t1n
        if t1h not in t1_map:
            t1_map[t1h] = {"name": t1n, "handle": t1h, "t2_map": {}}
        t2_map = t1_map[t1h]["t2_map"]
        if t2h not in t2_map:
            t2_map[t2h] = {"name": t2n, "handle": t2h, "jobs": []}
        t2_map[t2h]["jobs"].append(j)

    def t1_sort_key(h):
        try:
            return t1_order.index(h)
        except ValueError:
            return 9999

    tier_groups = []
    for t1h in sorted(t1_map.keys(), key=t1_sort_key):
        t1v = t1_map[t1h]
        t2_groups = []
        for t2h, t2v in t1v["t2_map"].items():
            t2_stats = {}
            for s in ("pending", "draft", "synced", "failed", "existing", "drafting"):
                t2_stats[s] = sum(1 for j in t2v["jobs"] if j["status"] == s)
            t2_stats["total"] = len(t2v["jobs"])
            t2_stats["done"] = t2_stats["synced"] + t2_stats["existing"]
            t2_stats["active"] = t2_stats["draft"] + t2_stats["pending"] + t2_stats["failed"]
            t2_groups.append({**t2v, "stats": t2_stats})

        t1_stats = {}
        all_t1_jobs = [j for g in t2_groups for j in g["jobs"]]
        for s in ("pending", "draft", "synced", "failed", "existing", "drafting"):
            t1_stats[s] = sum(1 for j in all_t1_jobs if j["status"] == s)
        t1_stats["total"] = len(all_t1_jobs)
        t1_stats["done"] = t1_stats["synced"] + t1_stats["existing"]
        t1_stats["pct"] = round(t1_stats["done"] / t1_stats["total"] * 100) if t1_stats["total"] else 0

        tier_groups.append({
            "name": t1v["name"], "handle": t1h,
            "tier2_groups": t2_groups,
            "stats": t1_stats,
        })
    return tier_groups


# ─────────────────────── BG WORKER ───────────────────────────────

def _gen_bg_worker_collection_loop():
    """Background worker — consume hàng đợi ĐỘNG: pop job từ _GEN_BG['queue'] cho tới khi cạn."""
    import collection_content_writer as ccw
    while True:
        with _GEN_BG_LOCK:
            if _GEN_BG["stopped"]:
                _GEN_BG["queue"] = []
                _GEN_BG["running"] = False
                _GEN_BG["finished_at"] = datetime.now().isoformat(timespec="seconds")
                _GEN_BG["current_id"] = None
                _GEN_BG["current_name"] = None
                _GEN_BG["job_started_at"] = None
                break
            if not _GEN_BG["queue"]:
                _GEN_BG["running"] = False
                _GEN_BG["finished_at"] = datetime.now().isoformat(timespec="seconds")
                _GEN_BG["current_id"] = None
                _GEN_BG["current_name"] = None
                _GEN_BG["job_started_at"] = None
                break
            jid = _GEN_BG["queue"][0]
            job = _collection_jobs_get(jid)
            if not job:
                _GEN_BG["fail"] += 1
                _GEN_BG["done"] += 1
                _GEN_BG["errors"].append(f"#{jid}: Job not found")
                _GEN_BG["queue"] = [x for x in _GEN_BG["queue"] if x != jid]
                continue
            _GEN_BG["current_id"] = jid
            _GEN_BG["current_name"] = job.get("collection_title") or job.get("handle") or f"#{jid}"
            _GEN_BG["job_started_at"] = datetime.now().isoformat(timespec="seconds")

        t0 = time.time()
        _collection_jobs_update(jid, status="drafting", error=None)
        try:
            ctx = ccw.fetch_collection_context(job["collection_url"])
            if not ctx.get("ok"):
                _collection_jobs_update(jid, status="failed", error=f"Fetch ctx: {ctx.get('error')}")
                with _GEN_BG_LOCK:
                    _GEN_BG["fail"] += 1
                    _GEN_BG["errors"].append(f"#{jid}: fetch ctx: {str(ctx.get('error',''))[:80]}")
            else:
                gen = ccw.gen_collection_content(
                    job["collection_url"],
                    job["collection_title"] or ctx.get("h1", ""),
                    page_title=ctx.get("page_title", ""),
                    admin_desc=ctx.get("admin_desc", ""),
                    sp_names=ctx.get("sp_names", []),
                    haravan_id=job.get("haravan_id"),
                )
                if not gen.get("ok"):
                    _collection_jobs_update(jid, status="failed", error=gen.get("error"))
                    with _GEN_BG_LOCK:
                        _GEN_BG["fail"] += 1
                        _GEN_BG["errors"].append(f"#{jid}: {str(gen.get('error',''))[:80]}")
                else:
                    _collection_jobs_update(
                        jid,
                        edited_title=gen["title"], edited_meta=gen["meta"],
                        edited_body_html=gen["body_html"],
                        status="draft",
                        ai_generated_at=datetime.now().isoformat(timespec="seconds"),
                        error=None,
                    )
                    with _GEN_BG_LOCK:
                        _GEN_BG["ok"] += 1
        except Exception as e:
            _collection_jobs_update(jid, status="failed", error=str(e)[:300])
            with _GEN_BG_LOCK:
                _GEN_BG["fail"] += 1
                _GEN_BG["errors"].append(f"#{jid}: {str(e)[:80]}")
        with _GEN_BG_LOCK:
            _GEN_BG["done"] += 1
            _GEN_BG["completed_durations"].append(round(time.time() - t0, 1))
            _GEN_BG["queue"] = [x for x in _GEN_BG["queue"] if x != jid]
            _GEN_BG["current_id"] = None
            _GEN_BG["current_name"] = None
            _GEN_BG["job_started_at"] = None
            if len(_GEN_BG["errors"]) > 20:
                _GEN_BG["errors"] = _GEN_BG["errors"][-20:]
        time.sleep(1)


def _enqueue_collection_gen(ids):
    """Thêm job_ids vào hàng đợi gen nền; khởi động worker nếu đang idle."""
    try:
        ids = [int(x) for x in ids]
    except Exception:
        ids = []
    start_worker = False
    with _GEN_BG_LOCK:
        if not _GEN_BG.get("running"):
            _GEN_BG.update({
                "running": True, "stopped": False, "kind": "collection",
                "queue": [], "total": 0,
                "current_id": None, "current_name": None, "job_started_at": None,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "finished_at": None,
                "ok": 0, "fail": 0, "done": 0,
                "completed_durations": [], "errors": [],
            })
            start_worker = True
        for jid in ids:
            if jid == _GEN_BG.get("current_id") or jid in _GEN_BG["queue"]:
                continue
            _GEN_BG["queue"].append(jid)
            _GEN_BG["total"] += 1
        snapshot = dict(_GEN_BG)
    if start_worker:
        t = threading.Thread(target=_gen_bg_worker_collection_loop, daemon=True)
        t.start()
    return snapshot


def _save_seo_job_edits(update_fn, job_id):
    """Lưu edit title/meta/body từ form detail (CHUNG cho collection + blog).

    update_fn tự lo recompute quality/readability khi có edited_*.
    """
    payload = request.get_json(silent=True) or request.form
    update_fn(job_id,
              edited_title=(payload.get("title") or "").strip(),
              edited_meta=(payload.get("meta") or "").strip(),
              edited_body_html=(payload.get("body") or "").strip())
    return jsonify({"ok": True})


# ─────────────────────── ROUTES ──────────────────────────────────

def collection_content_page():
    status_filter = request.args.get("status") or None
    view = request.args.get("view") or ("tier" if not status_filter else "flat")
    jobs = _collection_jobs_list(status=status_filter)
    conn = db.get_conn()
    stats = {}
    for s in ("pending", "draft", "synced", "failed", "existing"):
        stats[s] = conn.execute("SELECT COUNT(*) FROM collection_jobs WHERE status=?", (s,)).fetchone()[0]
    stats["total"] = conn.execute("SELECT COUNT(*) FROM collection_jobs").fetchone()[0]
    conn.close()
    tier_groups = _build_tier_groups(jobs) if view == "tier" else []
    return render_template("collection_content.html", jobs=jobs, stats=stats,
                           active_status=status_filter, view=view, tier_groups=tier_groups)


def collection_content_detail_page(job_id):
    job = _collection_jobs_get(job_id)
    if not job:
        flash("Job không tồn tại.", "error")
        return redirect(url_for("collection_content_page"))
    return render_template("collection_content_detail.html", job=job)


def collection_content_gen_bg():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids") or []
    try:
        ids = [int(x) for x in ids]
    except Exception:
        return jsonify({"ok": False, "error": "ids phải là list int"}), 400
    if not ids:
        return jsonify({"ok": False, "error": "Thiếu list ids"}), 400
    state = _enqueue_collection_gen(ids)
    return jsonify({"ok": True, "state": state})


def collection_content_gen_status():
    return jsonify(dict(_GEN_BG))


def collection_content_gen_stop():
    with _GEN_BG_LOCK:
        _GEN_BG["stopped"] = True
    return jsonify({"ok": True, "state": dict(_GEN_BG)})


def collection_content_gen(job_id):
    """Gen lẻ / gen lại 1 collection — KHÔNG chạy đồng bộ nữa mà ĐẨY VÀO HÀNG ĐỢI nền."""
    job = _collection_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    state = _enqueue_collection_gen([job_id])
    queue = state.get("queue", [])
    if state.get("current_id") == job_id:
        position = 0
    elif job_id in queue:
        position = queue.index(job_id) + 1
    else:
        position = 0
    return jsonify({
        "ok": True, "queued": True,
        "position": position,
        "queue_len": len(queue),
        "running": state.get("running", False),
        "state": state,
    })


def collection_content_gen_title_meta(job_id):
    """Gen LẠI title HOẶC meta HOẶC cả 2 — payload {field: 'title'|'meta'|'both'}."""
    job = _collection_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    payload = request.get_json(silent=True) or {}
    field = payload.get("field", "both")
    if field not in ("title", "meta", "both"):
        field = "both"
    import collection_content_writer as ccw
    try:
        ctx = ccw.fetch_collection_context(job["collection_url"])
        gen = ccw.gen_title_meta_only(
            job["collection_url"],
            job["collection_title"] or (ctx.get("h1") if ctx.get("ok") else ""),
            page_title=ctx.get("page_title", "") if ctx.get("ok") else "",
            admin_desc=ctx.get("admin_desc", "") if ctx.get("ok") else "",
            sp_names=ctx.get("sp_names", []) if ctx.get("ok") else [],
            existing_title=job.get("edited_title") or "",
            existing_meta=job.get("edited_meta") or "",
            field=field,
        )
        if not gen.get("ok"):
            return jsonify(gen), 500
        update_kwargs = {"ai_generated_at": datetime.now().isoformat(timespec="seconds")}
        if "title" in gen:
            update_kwargs["edited_title"] = gen["title"]
        if "meta" in gen:
            update_kwargs["edited_meta"] = gen["meta"]
        _collection_jobs_update(job_id, **update_kwargs)
        return jsonify({"ok": True, **gen})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def collection_content_save(job_id):
    return _save_seo_job_edits(_collection_jobs_update, job_id)


def collection_content_sync(job_id):
    job = _collection_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    if not job.get("haravan_id"):
        return jsonify({"ok": False, "error": "Thiếu haravan_id (collection chưa tồn tại trên Haravan)"}), 400
    if not job.get("edited_title") or not job.get("edited_body_html"):
        return jsonify({"ok": False, "error": "Chưa có title/body — gen AI trước"}), 400
    import collection_content_writer as ccw
    res = ccw.sync_collection_to_haravan(
        int(job["haravan_id"]),
        job["edited_title"],
        job.get("edited_meta") or "",
        job["edited_body_html"],
    )
    if job_sync.apply_sync_result(_collection_jobs_update, job_id, res):
        return jsonify({"ok": True})
    return jsonify(res), 500


def collection_content_sync_all():
    jobs = _collection_jobs_list(status="draft")
    ok = fail = 0
    errors = []
    import collection_content_writer as ccw
    for job in jobs:
        if not job.get("haravan_id") or not job.get("edited_title") or not job.get("edited_body_html"):
            fail += 1
            errors.append(f"#{job['id']}: thiếu data")
            continue
        try:
            res = ccw.sync_collection_to_haravan(
                int(job["haravan_id"]),
                job["edited_title"], job.get("edited_meta") or "",
                job["edited_body_html"],
            )
            if job_sync.apply_sync_result(_collection_jobs_update, job["id"], res):
                ok += 1
            else:
                fail += 1
                errors.append(f"#{job['id']}: {res.get('error', '')[:80]}")
        except Exception as e:
            fail += 1
            errors.append(f"#{job['id']}: {str(e)[:80]}")
        time.sleep(0.8)
    flash(f"🚀 Sync xong: {ok} OK, {fail} fail." + (f" Sample lỗi: {errors[0]}" if errors else ""),
          "success" if ok else "error")
    return redirect(url_for("collection_content_page"))


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 10 route Collection Content."""
    app.add_url_rule("/collection-content", "collection_content_page", collection_content_page)
    app.add_url_rule("/collection-content/<int:job_id>",
                     "collection_content_detail_page", collection_content_detail_page)
    app.add_url_rule("/collection-content/gen-bg",
                     "collection_content_gen_bg", collection_content_gen_bg, methods=["POST"])
    app.add_url_rule("/collection-content/gen-status",
                     "collection_content_gen_status", collection_content_gen_status)
    app.add_url_rule("/collection-content/gen-stop",
                     "collection_content_gen_stop", collection_content_gen_stop, methods=["POST"])
    app.add_url_rule("/collection-content/<int:job_id>/gen",
                     "collection_content_gen", collection_content_gen, methods=["POST"])
    app.add_url_rule("/collection-content/<int:job_id>/gen-title-meta",
                     "collection_content_gen_title_meta", collection_content_gen_title_meta, methods=["POST"])
    app.add_url_rule("/collection-content/<int:job_id>/save",
                     "collection_content_save", collection_content_save, methods=["POST"])
    app.add_url_rule("/collection-content/<int:job_id>/sync",
                     "collection_content_sync", collection_content_sync, methods=["POST"])
    app.add_url_rule("/collection-content/sync-all",
                     "collection_content_sync_all", collection_content_sync_all, methods=["POST"])
