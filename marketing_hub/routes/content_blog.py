"""Routes: Content Blog — 18 endpoint (page + detail + gen×2 + batch-gen SSE×4 +
gen-title/meta + save + sync×2 + gather-images + image serve + select + upload + url).

Helpers nội bộ:
- _blog_jobs_list/get/update (CRUD)
- _run_blog_gen, _run_blog_gen_full (1-pass + 2-pass gen)
- _push_blog_to_haravan, _apply_blog_push (sync)

State:
- _batch_streams (SSE stream registry, module-level)
- BLOG_ID_BY_TARGET (huong-dan + news blog_id Sintech)

Dep:
- db, job_sync, image_gather, blog_content_writer, haravan_blog,
  haravan_client, image_processor, cloudinary_upload, ai_provider (lazy)
- routes._shared.save_seo_job_edits
"""

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    render_template, request, jsonify,
    redirect, url_for, flash, send_from_directory,
    Response, stream_with_context,
)
from werkzeug.utils import secure_filename

import db
from routes._shared import save_seo_job_edits


# ─────────────────────── MODULE STATE ────────────────────────────

# SSE batch-gen streams: stream_id → {events, stop, done}
_batch_streams: dict = {}

# blog_id Sintech theo loại bài (Open API haravan_blog).
# huong-dan=Hướng dẫn · news=Tin tức.
BLOG_ID_BY_TARGET = {"huong-dan": 1000960873, "news": 1000906526}


# ─────────────────────── DB HELPERS ──────────────────────────────

def _blog_jobs_list(status: str = None, source: str = None, blog: str = None):
    conn = db.get_conn()
    sql = "SELECT * FROM blog_jobs WHERE 1=1"
    args = []
    if status == "not_gen":
        sql += " AND status IN ('pending','failed')"
    elif status == "generated":
        sql += " AND status IN ('draft','synced')"
    elif status:
        sql += " AND status = ?"
        args.append(status)
    if source:
        sql += " AND source = ?"
        args.append(source)
    if blog:
        sql += " AND target_blog = ?"
        args.append(blog)
    sql += " ORDER BY CASE WHEN pillar LIKE '%Autodesk%' THEN 0 ELSE 1 END ASC, COALESCE(pillar,'zzz') ASC, click DESC, id ASC"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _blog_jobs_get(job_id: int):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM blog_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _blog_jobs_update(job_id: int, **fields):
    if not fields:
        return
    if any(k in fields for k in ("edited_title", "edited_meta", "edited_body_html")):
        row = _blog_jobs_get(job_id) or {}
        title = fields.get("edited_title", row.get("edited_title")) or ""
        meta = fields.get("edited_meta", row.get("edited_meta")) or ""
        body = fields.get("edited_body_html", row.get("edited_body_html")) or ""
        if title or meta or body:
            try:
                import seo_quality
                rate = seo_quality.rate_content(title, meta, body, url_type="blog")
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
                import re as _re_wc
                text_only = _re_wc.sub(r"<[^>]+>", " ", body)
                fields["word_count"] = len([w for w in text_only.split() if w])
            except Exception as e:
                print(f"[blog quality_score] err: {e}")
    fields["updated_at"] = datetime.now().isoformat(timespec="seconds")
    keys = list(fields.keys())
    sets = ", ".join(f"{k}=?" for k in keys)
    db.execute_write(  # retry khi DB locked (vd đang crawl)
        f"UPDATE blog_jobs SET {sets} WHERE id=?",
        [*[fields[k] for k in keys], job_id])


def _blog_image_dir(job_id):
    return Path(__file__).parent.parent / "data" / "blog_images" / str(job_id)


# ─────────────────────── GEN ENGINES ─────────────────────────────

def _run_blog_gen(job_id, gather_images=True):
    """Gen 1 bài blog. ai_pillar → brief-mode (viết mới); seo_seed → scrape-mode (cào URL cũ)."""
    job = _blog_jobs_get(job_id)
    if not job:
        return {"ok": False, "error": "Job không tồn tại"}
    import blog_content_writer as bcw
    _blog_jobs_update(job_id, status="drafting", error=None)
    try:
        if job.get("source") == "ai_pillar":
            gen = bcw.gen_blog_content_from_brief(job)
        else:
            ctx = bcw.fetch_blog_context(job["blog_url"])
            if not ctx.get("ok"):
                _blog_jobs_update(job_id, status="failed", error=f"Fetch ctx: {ctx.get('error')}")
                return {"ok": False, "error": ctx.get("error")}
            gen = bcw.gen_blog_content(
                job["blog_url"], job["article_title"] or ctx.get("h1", ""),
                page_title=ctx.get("page_title", ""), existing_meta=ctx.get("existing_meta", ""),
                body_snippet=ctx.get("body_snippet", ""))
        if not gen.get("ok"):
            _blog_jobs_update(job_id, status="failed", error=gen.get("error"))
            return gen
        body_html = gen["body_html"]
        if gather_images:
            try:
                import image_gather
                q = gen["title"] or job.get("article_title") or ""
                handles = [job["handle"]] if (job.get("source") != "ai_pillar" and job.get("handle")) else []
                res_img = image_gather.gather(job_id, q, product_handles=handles, max_n=10)
                picked = image_gather.auto_pick(res_img.get("items", []), n=3)
                if picked:
                    body_html, used = image_gather.insert_into_body(gen["body_html"], picked)
                    image_gather.mark_selected(job_id, [u["idx"] for u in used])
            except Exception as e:
                print(f"[blog gen auto-image] #{job_id}: {e}")
        _blog_jobs_update(
            job_id, edited_title=gen["title"], edited_meta=gen["meta"],
            edited_body_html=body_html, status="draft",
            ai_generated_at=datetime.now().isoformat(timespec="seconds"), error=None)
        gen["body_html"] = body_html
        return {"ok": True, **gen}
    except Exception as e:
        _blog_jobs_update(job_id, status="failed", error=str(e)[:300])
        return {"ok": False, "error": str(e)}


def _run_blog_gen_full(job_id: int) -> dict:
    """2-pass gen full: outline → content → auto-image."""
    job = _blog_jobs_get(job_id)
    if not job:
        return {"ok": False, "error": "Job không tồn tại"}
    import blog_content_writer as bcw
    _blog_jobs_update(job_id, status="drafting", error=None)
    try:
        outline_res = bcw.gen_outline(
            article_title=job.get("article_title") or job.get("handle") or "",
            keyword=job.get("keyword") or "",
            intent=job.get("intent") or "",
            unique_angle=job.get("unique_angle") or "",
        )
        if not outline_res.get("ok"):
            _blog_jobs_update(job_id, status="failed", error=f"Outline: {outline_res.get('error')}")
            return {"ok": False, "error": outline_res.get("error")}
        outline_text = outline_res["outline_text"]
        _blog_jobs_update(job_id, outline=outline_text)

        gen = bcw.gen_blog_with_outline(job, outline_text)
        if not gen.get("ok"):
            _blog_jobs_update(job_id, status="failed", error=gen.get("error"))
            return {"ok": False, "error": gen.get("error")}

        body_html = gen["body_html"]
        try:
            import image_gather
            q = gen["title"] or job.get("article_title") or ""
            handles = [job["handle"]] if (job.get("source") != "ai_pillar" and job.get("handle")) else []
            res_img = image_gather.gather(job_id, q, product_handles=handles, max_n=10)
            picked = image_gather.auto_pick(res_img.get("items", []), n=3)
            if picked:
                body_html, used = image_gather.insert_into_body(gen["body_html"], picked)
                image_gather.mark_selected(job_id, [u["idx"] for u in used])
        except Exception as e:
            print(f"[gen-full auto-image] #{job_id}: {e}")

        _blog_jobs_update(
            job_id, edited_title=gen["title"], edited_meta=gen["meta"],
            edited_body_html=body_html, status="draft",
            ai_generated_at=datetime.now().isoformat(timespec="seconds"), error=None)

        return {"ok": True, "title": gen["title"], "meta_len": len(gen["meta"]),
                "h2_count": len(outline_res.get("outline_json") or [])}
    except Exception as e:
        _blog_jobs_update(job_id, status="failed", error=str(e)[:300])
        return {"ok": False, "error": str(e)}


# ─────────────────────── HARAVAN SYNC ────────────────────────────

def _push_blog_to_haravan(job, publish=True):
    """Đẩy 1 bài blog lên Haravan qua Open API."""
    import haravan_blog
    import blog_content_writer as bcw
    title = (job.get("edited_title") or "").strip()
    body = job.get("edited_body_html") or ""
    if not title or not body:
        return {"ok": False, "error": "Chưa có title/body — gen AI trước."}
    body_html = bcw.compress_html(bcw.sanitize_pasted_html(body))
    # FAQ schema: gan comment FAQJSON -> theme article.liquid in ra JSON-LD FAQPage.
    # (Haravan strip <script> khoi body nen phai di duong comment.) Bai khong co khoi FAQ -> bo qua.
    try:
        import faq_schema
        body_html, _n_faq = faq_schema.attach(body_html)
    except Exception:
        pass
    blog_id = job.get("haravan_blog_id") or BLOG_ID_BY_TARGET.get(
        (job.get("target_blog") or "news").strip(), 1000906526)
    meta = (job.get("edited_meta") or "").strip()
    fields = {
        "title": title,
        "author": "Trọng Nghĩa",
        "body_html": body_html,
        "summary_html": meta,
        "page_title": title,
        "meta_description": meta,
    }
    if job.get("handle"):
        fields["handle"] = job["handle"]
    if job.get("keyword"):
        fields["tags"] = job["keyword"]
    try:
        import image_gather
        _items = image_gather.load_meta(job["id"]).get("items", [])
        _hero = next((it for it in _items if it.get("is_hero") and it.get("origin_url")), None)
        _sel = [it for it in _items if it.get("selected") and it.get("origin_url")]
        _chosen = _hero or (_sel[0] if _sel else None)
        if _chosen:
            fields["image"] = {"src": _chosen["origin_url"]}
    except Exception:
        pass
    try:
        import haravan_client as _hc
        aid = job.get("haravan_article_id")
        if aid:
            haravan_blog.update_article(int(blog_id), int(aid), fields)
            try:
                _hc.upsert_seo_metafields("articles", int(aid), title=title, description=meta)
            except Exception:
                pass
            return {"ok": True, "article_id": int(aid), "blog_id": int(blog_id), "created": False}
        art = haravan_blog.create_article(int(blog_id), fields, hidden=not publish)
        new_aid = art.get("id")
        if new_aid:
            try:
                _hc.upsert_seo_metafields("articles", int(new_aid), title=title, description=meta)
            except Exception:
                pass
        return {"ok": True, "article_id": new_aid, "blog_id": int(blog_id), "created": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _apply_blog_push(job_id, res):
    """Map kết quả push → cập nhật blog_jobs."""
    if not res.get("ok"):
        _blog_jobs_update(job_id, status="failed", error=(res.get("error") or "")[:500])
        return False
    upd = {"status": "synced", "synced_at": datetime.now().isoformat(timespec="seconds"), "error": None}
    if res.get("created"):
        upd["haravan_article_id"] = res.get("article_id")
        upd["haravan_blog_id"] = res.get("blog_id")
    _blog_jobs_update(job_id, **upd)
    return True


# ─────────────────────── ROUTES ──────────────────────────────────

def blog_content_page():
    status_filter = request.args.get("status") or None
    source_filter = request.args.get("source") or None
    blog_filter = request.args.get("blog") or None
    jobs = _blog_jobs_list(status=status_filter, source=source_filter, blog=blog_filter)
    import image_gather
    for j in jobs:
        items = image_gather.load_meta(j["id"]).get("items", [])
        j["img_count"] = len(items)
        j["img_selected"] = sum(1 for it in items if it.get("selected"))
    conn = db.get_conn()
    stats = {}
    for s in ("pending", "draft", "synced", "failed"):
        stats[s] = conn.execute("SELECT COUNT(*) FROM blog_jobs WHERE status=?", (s,)).fetchone()[0]
    stats["total"] = conn.execute("SELECT COUNT(*) FROM blog_jobs").fetchone()[0]
    blog_counts = {r[0]: r[1] for r in conn.execute(
        "SELECT target_blog, COUNT(*) FROM blog_jobs GROUP BY target_blog").fetchall()}
    conn.close()
    return render_template("blog_content.html", jobs=jobs, stats=stats,
                           active_status=status_filter, active_blog=blog_filter,
                           blog_counts=blog_counts, shop="sintech.myharavan.com")


def blog_content_detail_page(job_id):
    job = _blog_jobs_get(job_id)
    if not job:
        flash("Bài không tồn tại.", "error")
        return redirect(url_for("blog_content_page"))
    import image_gather
    meta = image_gather.load_meta(job_id)
    images = meta.get("items", []) if meta else []
    for it in images:
        it["thumb_url"] = url_for("blog_content_image", job_id=job_id, filename=it["file"])
    return render_template("blog_content_detail.html", job=job, images=images)


def blog_content_gen(job_id):
    if not _blog_jobs_get(job_id):
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    res = _run_blog_gen(job_id)
    return jsonify(res) if res.get("ok") else (jsonify(res), 500)


def blog_content_gen_full(job_id):
    if not _blog_jobs_get(job_id):
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    res = _run_blog_gen_full(job_id)
    return jsonify(res) if res.get("ok") else (jsonify(res), 500)


def blog_content_batch_gen():
    """Khởi động batch gen liên tục. Trả stream_id để client lắng nghe SSE."""
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "full")
    status_filter = data.get("status", "not_gen")
    jobs = _blog_jobs_list(status=status_filter)
    if not jobs:
        return jsonify({"ok": False, "error": "Không có bài nào trong filter này."})
    job_ids = [j["id"] for j in jobs]
    titles = {j["id"]: (j.get("article_title") or j.get("handle") or f"#{j['id']}")[:60] for j in jobs}

    stream_id = uuid.uuid4().hex[:10]
    entry = {"events": [], "stop": {"stop": False}, "done": False}
    _batch_streams[stream_id] = entry

    def push(msg):
        entry["events"].append(msg)

    def runner():
        import time as _t
        total = len(job_ids)
        done = 0
        for idx, jid in enumerate(job_ids):
            if entry["stop"]["stop"]:
                push({"type": "stopped", "done": done, "total": total})
                break
            title = titles.get(jid, f"#{jid}")
            push({"type": "start", "id": jid, "title": title, "idx": idx + 1, "total": total})
            try:
                res = _run_blog_gen_full(jid) if mode == "full" else _run_blog_gen(jid)
                if res.get("ok"):
                    done += 1
                    push({"type": "done", "id": jid, "title": title, "idx": idx + 1, "total": total})
                else:
                    push({"type": "error", "id": jid, "title": title,
                          "error": (res.get("error") or "?")[:120], "idx": idx + 1, "total": total})
            except Exception as e:
                push({"type": "error", "id": jid, "title": title,
                      "error": str(e)[:120], "idx": idx + 1, "total": total})
        else:
            push({"type": "finish", "done": done, "total": total})
        entry["done"] = True
        _t.sleep(1800)
        _batch_streams.pop(stream_id, None)

    threading.Thread(target=runner, daemon=True).start()
    return jsonify({"ok": True, "stream_id": stream_id, "total": len(job_ids)})


def blog_content_batch_gen_stop(stream_id):
    entry = _batch_streams.get(stream_id)
    if entry:
        entry["stop"]["stop"] = True
    return jsonify({"ok": True})


def blog_content_batch_gen_status(stream_id):
    """Client hỏi stream còn active không (dùng khi reconnect)."""
    entry = _batch_streams.get(stream_id)
    if not entry:
        return jsonify({"active": False})
    return jsonify({"active": True, "done": entry["done"], "total_events": len(entry["events"])})


def blog_content_batch_gen_stream(stream_id):
    """SSE stream — client có thể reconnect bất kỳ lúc nào, nhận lại toàn bộ events từ offset."""
    entry = _batch_streams.get(stream_id)
    if not entry:
        return jsonify({"error": "Stream không tồn tại hoặc đã hết."}), 404
    start_idx = max(0, request.args.get("from", 0, type=int))

    import time as _t

    @stream_with_context
    def generate():
        yield "retry: 3000\n\n"
        idx = start_idx
        while True:
            events = entry["events"]
            while idx < len(events):
                yield f"data: {json.dumps(events[idx], ensure_ascii=False)}\n\n"
                idx += 1
            if entry["done"]:
                break
            _t.sleep(0.4)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def blog_content_gen_title(job_id):
    """Gen lại title 45-61c từ title/keyword hiện tại của job."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    current_title = job.get("edited_title") or job.get("article_title") or job.get("handle") or ""
    keyword = job.get("keyword") or ""
    body_snippet = ""
    if job.get("edited_body_html"):
        import re as _re
        body_snippet = _re.sub(r"<[^>]+>", " ", job["edited_body_html"])[:800]
    try:
        import ai_provider
        sys_p = "Bạn là SEO copywriter cho Sintech.vn (shop PC/laptop/gaming gear). Viết title SEO tiếng Việt."
        usr_p = (f"Tiêu đề hiện tại: {current_title}\nKeyword: {keyword or '(suy ra từ tiêu đề)'}\n"
                 f"Snippet nội dung: {body_snippet or '(chưa có)'}\n\n"
                 f"Viết lại title 45-61 ký tự, bám keyword, KHÔNG chứa 'Sintech', tự nhiên buyer-facing. "
                 f"Chỉ trả text thuần, không dấu ngoặc kép.")
        raw = ai_provider.call_ai(sys_p, usr_p, timeout=60).strip()
        raw = raw.strip('"\'')
        if not (20 <= len(raw) <= 80):
            return jsonify({"ok": False, "error": f"AI trả title bất thường ({len(raw)}c): {raw[:80]}"})
        return jsonify({"ok": True, "title": raw, "len": len(raw)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def blog_content_gen_meta(job_id):
    """Gen lại meta description 140-160c từ title + body hiện tại."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    title = job.get("edited_title") or job.get("article_title") or ""
    body_snippet = ""
    if job.get("edited_body_html"):
        import re as _re
        body_snippet = _re.sub(r"<[^>]+>", " ", job["edited_body_html"])[:1200]
    try:
        import ai_provider
        sys_p = "Bạn là SEO copywriter cho Sintech.vn (shop PC/laptop/gaming gear). Viết meta description chuẩn SEO tiếng Việt."
        usr_p = (f"Title bài: {title}\nNội dung (snippet): {body_snippet or '(chưa có)'}\n\n"
                 f"Viết meta description 140-160 ký tự: tóm tắt giá trị bài, có keyword, kết thúc bằng CTA HOA "
                 f"(XEM NGAY / KHÁM PHÁ NGAY / TÌM HIỂU NGAY / THAM KHẢO NGAY). "
                 f"Chỉ trả text thuần, không dấu ngoặc kép.")
        raw = ai_provider.call_ai(sys_p, usr_p, timeout=60).strip()
        raw = raw.strip('"\'')
        if not (100 <= len(raw) <= 200):
            return jsonify({"ok": False, "error": f"AI trả meta bất thường ({len(raw)}c): {raw[:100]}"})
        return jsonify({"ok": True, "meta": raw, "len": len(raw)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def blog_content_save(job_id):
    return save_seo_job_edits(_blog_jobs_update, job_id)


def blog_content_add_author(job_id):
    """E-E-A-T: chèn hộp tác giả + Person schema vào CUỐI bài (idempotent)."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    body = job.get("edited_body_html") or ""
    if not body:
        return jsonify({"ok": False, "error": "Bài chưa có nội dung — gen trước."}), 400
    import author_block
    if author_block.has_author_box(body):
        return jsonify({"ok": True, "already": True, "message": "Bài đã có hộp tác giả rồi."})
    _blog_jobs_update(job_id, edited_body_html=author_block.ensure_author_box(body))
    return jsonify({"ok": True, "message": f"Đã chèn hộp tác giả {author_block.AUTHOR['name']}."})


def blog_content_sync(job_id):
    """Vợ đã duyệt tay → sync thẳng lên Haravan, PUBLISH hiện (Google index được)."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    try:
        res = _push_blog_to_haravan(job, publish=True)
        if _apply_blog_push(job_id, res):
            return jsonify({"ok": True, "article_id": res.get("article_id"),
                            "created": res.get("created"), "published": True})
        return jsonify(res), 500
    except Exception as e:
        # Luôn trả JSON (không để Flask trả HTML 500 → frontend báo 'Unexpected token <').
        return jsonify({"ok": False, "error": f"Lỗi server khi sync: {e}"}), 500


def blog_content_sync_all():
    jobs = _blog_jobs_list(status="draft")
    ok = fail = 0
    errors = []
    import time as _t
    for job in jobs:
        res = _push_blog_to_haravan(job, publish=True)
        if _apply_blog_push(job["id"], res):
            ok += 1
        else:
            fail += 1
            errors.append(f"#{job['id']}: {res.get('error', '')[:80]}")
        _t.sleep(0.8)
    flash(f"🚀 Sync xong: {ok} OK, {fail} fail." + (f" Sample lỗi: {errors[0]}" if errors else ""),
          "success" if ok else "error")
    return redirect(url_for("blog_content_page"))


# ─────────────────────── IMAGE GATHER + SERVE + UPLOAD ───────────

def blog_content_gather_images(job_id):
    """Gom ảnh ứng viên về local cho job (T1)."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    import image_gather
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or job.get("edited_title") or job.get("article_title") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "Thiếu query (chưa có title) — gen AI hoặc nhập title trước."}), 400
    handles = data.get("product_handles")
    if handles is None:
        handles = [job["handle"]] if job.get("handle") else []
    try:
        max_n = max(1, min(int(data.get("max_n") or 10), 20))
    except (TypeError, ValueError):
        max_n = 10
    try:
        res = image_gather.gather(job_id, query, product_handles=handles, max_n=max_n)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 500
    for it in res.get("items", []):
        it["thumb_url"] = url_for("blog_content_image", job_id=job_id, filename=it["file"])
    return jsonify(res)


def blog_content_image(job_id, filename):
    """Serve ảnh ứng viên local: data/blog_images/<job_id>/<filename>."""
    folder = _blog_image_dir(job_id)
    safe = secure_filename(filename)
    if not folder.exists() or not (folder / safe).is_file():
        return "Not found", 404
    return send_from_directory(folder, safe)


def blog_content_images_select(job_id):
    """Đánh dấu ảnh đã chọn (selected=true) trong meta.json."""
    import image_gather
    meta = image_gather.load_meta(job_id)
    if not meta:
        return jsonify({"ok": False, "error": "Chưa gom ảnh cho job này."}), 400
    data = request.get_json(silent=True) or {}
    try:
        selected = {int(i) for i in (data.get("selected") or [])}
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "selected phải là list số idx."}), 400
    for it in meta.get("items", []):
        it["selected"] = it["idx"] in selected
    (_blog_image_dir(job_id) / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"ok": True, "selected": sorted(selected)})


def blog_content_image_upload(job_id):
    """Tải 1 ảnh AI (gen ngoài bằng ChatGPT/Canva) từ máy → auto-scale 1200px →
    host lên Haravan asset_storage (URL CDN public) → trả src để chèn vào bài."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Chưa chọn file ảnh."}), 400
    target = (request.form.get("target") or "body").strip()
    alt = (request.form.get("alt") or job.get("edited_title") or "").strip()[:180]
    try:
        raw = f.read()
        if not raw:
            return jsonify({"ok": False, "error": "File ảnh rỗng."}), 400
        import image_processor
        scaled = image_processor.process_blog_image(raw, max_w=1200)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Xử lý ảnh lỗi: {str(e)[:200]}"}), 400
    try:
        import cloudinary_upload
        fname = secure_filename(f.filename) or "ai_image.jpg"
        if not fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            fname += ".jpg"
        src = cloudinary_upload.upload(scaled, filename=fname)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Host ảnh lên Cloudinary lỗi: {str(e)[:240]}"}), 500
    is_hero = target == "hero"
    if is_hero:
        try:
            import image_gather
            image_gather.set_ai_hero(job_id, src, alt=alt)
        except Exception as e:
            print(f"[image-upload hero meta] #{job_id}: {e}")
    return jsonify({"ok": True, "src": src, "alt": alt, "target": target,
                    "is_hero": is_hero, "bytes": len(scaled)})


def blog_content_image_url(job_id):
    """Gắn ảnh từ 1 URL công khai có sẵn vào bài — KHÔNG upload, KHÔNG scale."""
    job = _blog_jobs_get(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Job không tồn tại"}), 404
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    target = (data.get("target") or "body").strip()
    alt = (data.get("alt") or job.get("edited_title") or "").strip()[:180]
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"ok": False, "error": "URL phải bắt đầu bằng http(s)://"}), 400
    is_hero = target == "hero"
    if is_hero:
        try:
            import image_gather
            image_gather.set_ai_hero(job_id, url, alt=alt)
        except Exception as e:
            print(f"[image-url hero meta] #{job_id}: {e}")
    return jsonify({"ok": True, "src": url, "alt": alt, "target": target, "is_hero": is_hero})


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký route Blog Content (legacy). Trang chính /blog-content do
    blog_content_center (Command Center) đảm nhận — dòng dưới đã archive.
    Các sub-route (detail/gen/sync/add-author...) GIỮ để blog_pillars + bài cũ không vỡ."""
    # ARCHIVED 2026-06-16: /blog-content main page -> Blog SEO Command Center (blog_content_center)
    # app.add_url_rule("/blog-content", "blog_content_page", blog_content_page)
    app.add_url_rule("/blog-content/<int:job_id>",
                     "blog_content_detail_page", blog_content_detail_page)
    app.add_url_rule("/blog-content/<int:job_id>/gen",
                     "blog_content_gen", blog_content_gen, methods=["POST"])
    app.add_url_rule("/blog-content/<int:job_id>/gen-full",
                     "blog_content_gen_full", blog_content_gen_full, methods=["POST"])
    app.add_url_rule("/blog-content/batch-gen",
                     "blog_content_batch_gen", blog_content_batch_gen, methods=["POST"])
    app.add_url_rule("/blog-content/batch-gen/stop/<stream_id>",
                     "blog_content_batch_gen_stop", blog_content_batch_gen_stop, methods=["POST"])
    app.add_url_rule("/blog-content/batch-gen/status/<stream_id>",
                     "blog_content_batch_gen_status", blog_content_batch_gen_status)
    app.add_url_rule("/blog-content/batch-gen/stream/<stream_id>",
                     "blog_content_batch_gen_stream", blog_content_batch_gen_stream)
    app.add_url_rule("/blog-content/<int:job_id>/gen-title",
                     "blog_content_gen_title", blog_content_gen_title, methods=["POST"])
    app.add_url_rule("/blog-content/<int:job_id>/gen-meta",
                     "blog_content_gen_meta", blog_content_gen_meta, methods=["POST"])
    app.add_url_rule("/blog-content/<int:job_id>/add-author",
                     "blog_content_add_author", blog_content_add_author, methods=["POST"])
    app.add_url_rule("/blog-content/<int:job_id>/save",
                     "blog_content_save", blog_content_save, methods=["POST"])
    app.add_url_rule("/blog-content/<int:job_id>/sync",
                     "blog_content_sync", blog_content_sync, methods=["POST"])
    app.add_url_rule("/blog-content/sync-all",
                     "blog_content_sync_all", blog_content_sync_all, methods=["POST"])
    app.add_url_rule("/blog-content/<int:job_id>/gather-images",
                     "blog_content_gather_images", blog_content_gather_images, methods=["POST"])
    app.add_url_rule("/blog-content/<int:job_id>/image/<path:filename>",
                     "blog_content_image", blog_content_image)
    app.add_url_rule("/blog-content/<int:job_id>/images/select",
                     "blog_content_images_select", blog_content_images_select, methods=["POST"])
    app.add_url_rule("/blog-content/<int:job_id>/image-upload",
                     "blog_content_image_upload", blog_content_image_upload, methods=["POST"])
    app.add_url_rule("/blog-content/<int:job_id>/image-url",
                     "blog_content_image_url", blog_content_image_url, methods=["POST"])
