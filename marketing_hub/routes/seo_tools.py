"""Routes: SEO Tools — 33 endpoint (h1-in-desc + title-meta + GSC + CWV + schema + empty-desc).

Background worker (_GEN_BG/_PILLAR_BG) ở routes.state dùng chung 1 ref —
state KHÔNG reset khi module re-import.

Helper nội bộ:
- `_load_psi_key()` (CWV)
- `GITHUB_RAW_BASE` const (sync-github)

Dep:
- seo as seo_mod
- cwv as cwv_mod
- db
- requests, json, datetime, pathlib.Path
- schema_scanner (lazy import inside route)
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

import requests

from flask import (
    render_template, request, jsonify,
    redirect, url_for, flash,
)

import db
import seo as seo_mod
import cwv as cwv_mod


ROOT = Path(__file__).parent.parent  # marketing_hub/

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/nghiango4554/nox-1/master"


# ─────────────────────── HELPERS ─────────────────────────────────

def _load_psi_key() -> str:
    try:
        cfg = json.loads((ROOT.parent / "state" / "psi_config.json").read_text())
        return cfg.get("psi_api_key", "")
    except Exception:
        return ""


# ─────────────────────── H1 IN DESC (7 route) ────────────────────

_COVERAGE_FILE = Path(__file__).parent.parent / "data" / "collection_coverage.json"


def scan_collection_coverage():
    """Fetch live collection từ Haravan + đo độ dài mô tả → lưu cache JSON.
    Cross-ref status trong collection_jobs để biết bài nào đã gen sẵn (chỉ cần sync)."""
    import re as _re
    import haravan_client as hv

    def fetch_all(fn, kind):
        out, page = [], 1
        while True:
            try:
                batch = fn(page=page, limit=50)
            except Exception:
                break
            if not batch:
                break
            for c in batch:
                text = _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", c.get("body_html") or "")).strip()
                out.append({"handle": c.get("handle"), "title": c.get("title"), "kind": kind, "len": len(text)})
            if len(batch) < 50:
                break
            page += 1
        return out

    allc = fetch_all(hv.list_custom_collections, "custom") + fetch_all(hv.list_smart_collections, "smart")
    missing = [c for c in allc if c["len"] < 200]
    conn = db.get_conn()
    jobs = {r["handle"]: (r["status"], r["blen"]) for r in conn.execute(
        "SELECT handle, status, length(COALESCE(edited_body_html,'')) blen FROM collection_jobs")}
    conn.close()
    for c in missing:
        st = jobs.get(c["handle"])
        c["job_status"] = st[0] if st else None
        c["gen_len"] = st[1] if st else 0
    data = {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(allc), "ok": len(allc) - len(missing), "missing": missing,
    }
    try:
        _COVERAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _COVERAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[coverage] write err: {e}")
    return data


def seo_coverage_page():
    """Coverage tổng sức khỏe nội dung: SP/collection thiếu mô tả + author/schema."""
    try:
        sp_empty = db.seo_empty_desc_list(url_type="product", only_empty=True, limit=5000)
    except Exception:
        sp_empty = []
    coll = None
    try:
        if _COVERAGE_FILE.exists():
            coll = json.loads(_COVERAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        coll = None
    conn = db.get_conn()

    def one(sql):
        r = conn.execute(sql).fetchone()
        return (r[0] if r else 0) or 0
    blog_jobs_total = one("SELECT COUNT(*) FROM blog_jobs WHERE edited_body_html IS NOT NULL AND edited_body_html!=''")
    blog_jobs_author = one("SELECT COUNT(*) FROM blog_jobs WHERE edited_body_html LIKE '%data-author-box%'")
    blog_audited = one("SELECT COUNT(*) FROM seo_pages WHERE url_type='blog' AND schema_scanned_at IS NOT NULL")
    blog_faq = one("SELECT COUNT(*) FROM seo_pages WHERE url_type='blog' AND schema_has_faq=1")
    conn.close()
    return render_template(
        "seo_coverage.html",
        sp_empty_count=len(sp_empty), sp_empty_sample=sp_empty[:12],
        coll=coll,
        blog_jobs_total=blog_jobs_total, blog_jobs_author=blog_jobs_author,
        blog_audited=blog_audited, blog_faq=blog_faq,
    )


def seo_coverage_scan_collections():
    try:
        data = scan_collection_coverage()
        return jsonify({"ok": True, "missing": len(data["missing"]), "total": data["total"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def seo_eeat_page():
    """Bảng audit E-E-A-T — gom tín hiệu sẵn có trong DB thành checklist gap."""
    import author_block
    conn = db.get_conn()

    def one(sql, args=()):
        r = conn.execute(sql, args).fetchone()
        return (r[0] if r else 0) or 0

    # 1. Trang pháp lý / trust (TRUST checklist)
    trust_defs = [
        ("Giới thiệu / About", ["gioi-thieu", "ve-chung-toi", "about"]),
        ("Liên hệ", ["lien-he", "contact"]),
        ("Chính sách bảo mật", ["bao-mat", "privacy"]),
        ("Điều khoản & điều kiện", ["dieu-khoan", "dieu-kien", "terms"]),
        ("Đổi trả / Hoàn tiền / Bảo hành", ["doi-tra", "hoan-tien", "tra-hang", "bao-hanh", "return"]),
        ("Chính sách vận chuyển", ["van-chuyen", "giao-hang", "shipping"]),
    ]
    trust = []
    for label, slugs in trust_defs:
        found = None
        for s in slugs:
            r = conn.execute(
                "SELECT url FROM seo_pages WHERE url LIKE ? "
                "AND (status_code=200 OR status_code IS NULL) LIMIT 1", (f"%{s}%",)
            ).fetchone()
            if r:
                found = r["url"]
                break
        trust.append({"label": label, "ok": bool(found), "url": found})

    # 2. 404 / broken
    broken_pages = one("SELECT COUNT(*) FROM seo_pages WHERE status_code >= 400")
    try:
        broken_links = one("SELECT COUNT(*) FROM seo_links WHERE status_code >= 400 OR status_code = 0")
    except Exception:
        broken_links = 0

    # 3. Organization schema homepage
    home = conn.execute(
        "SELECT schema_types FROM seo_pages WHERE url IN "
        "('https://sintech.vn/','https://sintech.vn','https://www.sintech.vn/') LIMIT 1"
    ).fetchone()
    home_org = bool(home and home[0] and "Organization" in home[0])

    # 4. Schema blog (Article / FAQ) — từ audit schema sẵn có
    blog_audited = one("SELECT COUNT(*) FROM seo_pages WHERE url_type='blog' AND schema_scanned_at IS NOT NULL")
    blog_article = one("SELECT COUNT(*) FROM seo_pages WHERE url_type='blog' AND schema_has_article=1")
    blog_faq = one("SELECT COUNT(*) FROM seo_pages WHERE url_type='blog' AND schema_has_faq=1")

    # 5. Author box coverage (trên blog_jobs ta quản lý)
    try:
        blog_jobs_total = one("SELECT COUNT(*) FROM blog_jobs WHERE edited_body_html IS NOT NULL AND edited_body_html != ''")
        blog_jobs_author = one("SELECT COUNT(*) FROM blog_jobs WHERE edited_body_html LIKE '%data-author-box%'")
    except Exception:
        blog_jobs_total = blog_jobs_author = 0
    conn.close()

    return render_template(
        "seo_eeat.html",
        trust=trust, broken_pages=broken_pages, broken_links=broken_links,
        home_org=home_org, blog_audited=blog_audited, blog_article=blog_article, blog_faq=blog_faq,
        blog_jobs_total=blog_jobs_total, blog_jobs_author=blog_jobs_author,
        author=author_block.AUTHOR,
    )


def seo_h1_in_desc_page():
    url_type = request.args.get("type") or None
    show_all = request.args.get("all") == "1"
    items = db.seo_h1_in_desc_list(
        url_type=url_type,
        only_violations=not show_all,
        limit=2000,
    )
    summary = db.seo_h1_in_desc_summary()
    state = seo_mod.desc_h1_state()
    for it in items:
        try:
            it["desc_h1_list"] = json.loads(it["desc_h1_text"]) if it.get("desc_h1_text") else []
        except Exception:
            it["desc_h1_list"] = []
        sa = it.get("desc_h1_fixed_at")  # cột "Ngày sync"
        try:
            it["synced_at_disp"] = datetime.fromisoformat(sa).strftime("%d/%m %H:%M") if sa else ""
        except Exception:
            it["synced_at_disp"] = (sa or "")[:16]
    return render_template(
        "seo_h1_in_desc.html",
        items=items, summary=summary, state=state,
        url_type=url_type, show_all=show_all,
    )


def seo_h1_in_desc_scan():
    types_raw = request.form.getlist("types")
    valid = {"product", "collection", "blog", "page"}
    url_types = [t for t in types_raw if t in valid] or None
    try:
        limit = int(request.form.get("limit") or 0) or None
    except ValueError:
        limit = None
    started = seo_mod.start_desc_h1_scan_async(url_types=url_types, limit=limit)
    if started:
        scope = ", ".join(url_types) if url_types else "tất cả loại"
        flash(f"🔎 Đã bắt đầu quét H1 trong mô tả ({scope}). Tự refresh để xem tiến độ.", "success")
    else:
        flash("⏳ Đang có lượt quét chạy — chờ xong mới chạy lượt mới.", "info")
    return redirect(url_for("seo_h1_in_desc_page"))


def seo_h1_in_desc_status():
    return jsonify({
        "state": seo_mod.desc_h1_state(),
        "summary": db.seo_h1_in_desc_summary(),
    })


def seo_h1_in_desc_fix():
    payload = request.get_json(silent=True) or request.form
    url = (payload.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Thiếu url"}), 400
    try:
        result = seo_mod.fix_h1_in_desc_for_url(url)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


def seo_h1_fix_all_start():
    payload = request.get_json(silent=True) or request.form
    url_type = (payload.get("type") or "").strip() or None
    if url_type and url_type not in ("product", "collection", "blog", "page"):
        url_type = None
    started = seo_mod.start_h1_fix_all_async(url_type=url_type)
    if started:
        return jsonify({"ok": True, "message": "Đã start job fix-all."})
    return jsonify({"ok": False, "error": "Job đang chạy rồi — đợi xong hoặc bấm dừng."}), 409


def seo_h1_fix_all_stop():
    stopped = seo_mod.stop_h1_fix_all()
    if stopped:
        return jsonify({"ok": True, "message": "Đã gửi yêu cầu dừng."})
    return jsonify({"ok": False, "error": "Không có job đang chạy."}), 400


def seo_h1_fix_all_status():
    return jsonify(seo_mod.h1_fix_all_state())


# ─────────────────────── TITLE/META HUB (7 route) ────────────────

def seo_title_meta_page():
    url_type = request.args.get("type") or None
    issue_filter = request.args.get("issue") or None
    sort = request.args.get("sort") or "score_asc"
    sync_filter = request.args.get("sync") or None
    if url_type and url_type not in ("product", "collection", "blog", "page"):
        url_type = None
    if issue_filter and issue_filter not in seo_mod.ALL_TITLE_META_CODES:
        issue_filter = None
    if sort not in ("score_asc", "n_issues_desc", "url"):
        sort = "score_asc"
    if sync_filter not in ("synced", "unsynced", "error"):
        sync_filter = None
    items = seo_mod.list_title_meta_pages(
        url_type=url_type, issue_filter=issue_filter, sort=sort, limit=2000,
        sync_filter=sync_filter,
    )
    summary = seo_mod.title_meta_summary()
    fix_state = seo_mod.title_meta_fix_state()
    tiers = seo_mod.load_tiers()
    return render_template(
        "seo_title_meta.html",
        items=items, summary=summary, fix_state=fix_state,
        url_type=url_type, issue_filter=issue_filter, sort=sort,
        sync_filter=sync_filter,
        issue_labels=seo_mod.TITLE_META_LABELS,
        tiers=tiers,
        recrawl=seo_mod.tm_recrawl_state(),
    )


def seo_title_meta_fix():
    payload = request.get_json(silent=True) or request.form
    url = (payload.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Thiếu url"}), 400
    force_title = (payload.get("title") or "").strip() or None
    force_meta = (payload.get("meta") or "").strip() or None
    try:
        result = seo_mod.fix_title_meta_for_url(url,
            force_title=force_title, force_meta=force_meta)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify(result), 200 if result.get("ok") else 400


def seo_title_meta_preview():
    """Gen 3 title + 3 meta cho 1 URL (KHÔNG PUT) → frontend cho vợ click chọn 1/3 + 1/3."""
    payload = request.get_json(silent=True) or request.form
    url = (payload.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Thiếu url"}), 400
    try:
        result = seo_mod.preview_title_meta_for_url(url)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify(result), 200 if result.get("ok") else 400


def seo_title_meta_regen():
    """Đẩy 1 SP vào hàng chờ gen+sync lại — chạy ngầm, frontend poll realtime."""
    payload = request.get_json(silent=True) or request.form
    url = (payload.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "Thiếu url"}), 400
    try:
        result = seo_mod.enqueue_title_meta_regen(url)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify(result), 200 if result.get("ok") else 409


def seo_title_meta_fix_all_start():
    payload = request.get_json(silent=True) or request.form
    url_type = (payload.get("type") or "").strip() or None
    issue_filter = (payload.get("issue") or "").strip() or None
    sync_filter = (payload.get("sync") or "").strip() or None
    if url_type and url_type not in ("product", "collection", "blog", "page"):
        url_type = None
    if issue_filter and issue_filter not in seo_mod.ALL_TITLE_META_CODES:
        issue_filter = None
    if sync_filter not in ("synced", "unsynced", "error"):
        sync_filter = None
    started = seo_mod.start_title_meta_fix_all_async(
        url_type=url_type, issue_filter=issue_filter, sync_filter=sync_filter)
    if started:
        return jsonify({"ok": True, "message": "Đã start job."})
    return jsonify({"ok": False, "error": "Job đang chạy rồi."}), 409


def seo_title_meta_fix_all_stop():
    stopped = seo_mod.stop_title_meta_fix()
    if stopped:
        return jsonify({"ok": True, "message": "Đã gửi yêu cầu dừng."})
    return jsonify({"ok": False, "error": "Không có job đang chạy."}), 400


# ─── Re-crawl RIÊNG trang title-meta — qua HÀNG ĐỢI JOB (worker process riêng) ───
def seo_title_meta_recrawl_start():
    payload = request.get_json(silent=True) or request.form
    scope = (payload.get("scope") or "issues").strip()
    if db.job_active("tm_recrawl"):
        return jsonify({"ok": False, "error": "Đang chạy re-crawl rồi."}), 409
    jid = db.job_enqueue("tm_recrawl", {"scope": scope, "workers": payload.get("workers")})
    return jsonify({"ok": True, "job_id": jid, "scope": scope})


def seo_title_meta_recrawl_stop():
    job = db.job_active("tm_recrawl")
    if not job:
        return jsonify({"ok": False, "error": "Không có re-crawl đang chạy."}), 400
    db.job_request_stop(job["id"])
    return jsonify({"ok": True, "message": "Đã gửi yêu cầu dừng."})


def seo_title_meta_recrawl_status():
    job = db.job_active("tm_recrawl") or db.job_latest("tm_recrawl")
    if not job:
        return jsonify({"running": False, "total": 0, "done": 0, "success": 0,
                        "failed": 0, "scope": "", "workers": 0, "message": ""})
    try:
        prog = json.loads(job.get("progress") or "{}")
    except Exception:
        prog = {}
    running = job["status"] in ("queued", "running")
    msg = prog.get("message", "")
    if job["status"] == "queued" and not msg:
        msg = "⏳ Đang chờ worker nhặt job..."
    return jsonify({
        "running": running,
        "total": prog.get("total", 0), "done": prog.get("done", 0),
        "success": prog.get("success", 0), "failed": prog.get("failed", 0),
        "scope": prog.get("scope", ""), "workers": prog.get("workers", 0),
        "message": msg, "job_status": job["status"],
    })


def seo_title_meta_fix_all_status():
    return jsonify(seo_mod.title_meta_fix_state())


def seo_title_meta_tier_products():
    """Lấy SP theo tầng (collection handles) cho bảng phân tầng.
    Body: {handles:[...], mode:'issues'|'all'}."""
    payload = request.get_json(silent=True) or {}
    handles = payload.get("handles") or []
    if isinstance(handles, str):
        handles = [h.strip() for h in handles.split(",") if h.strip()]
    handles = [h for h in handles if isinstance(h, str) and h]
    mode = (payload.get("mode") or "issues").strip()
    if mode not in ("issues", "all"):
        mode = "issues"
    if not handles:
        return jsonify({"ok": False, "error": "Thiếu handles"}), 400
    try:
        items = seo_mod.list_tier_products(handles, mode=mode)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify({"ok": True, "items": items, "count": len(items), "mode": mode})


def seo_title_meta_regen_all():
    """Gen lại TẤT CẢ SP product có lỗi title/meta — GỒM cả SP đã sync (không skip).
    Áp prompt spec-inject mới cho toàn bộ. Tự dừng khi hết quota AI."""
    try:
        pages = seo_mod.list_title_meta_pages(url_type="product", limit=100000)
        urls = [p["url"] for p in pages]
        res = seo_mod.start_title_meta_fix_urls_async(urls)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify(res), 200 if res.get("ok") else 409


def seo_title_meta_regen_remaining():
    """Gen TIẾP các SP product lỗi CHƯA gen lần nào (url không nằm trong synced set).
    Dùng để tiếp tục sau khi quota dừng — không gen lại SP đã xong."""
    try:
        pages = seo_mod.list_title_meta_pages(url_type="product", limit=100000)
        synced = seo_mod.synced_title_meta_urls()
        urls = [p["url"] for p in pages if p["url"] not in synced]
        res = seo_mod.start_title_meta_fix_urls_async(urls)
        res.setdefault("remaining", len(urls))
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify(res), 200 if res.get("ok") else 409


def seo_title_meta_regen_dual():
    """Dual-AI: gen SP product lỗi CHƯA gen (unsynced) bằng Codex + Claude SONG SONG.
    Chỉ chạy khi cả 2 provider khả dụng (guard trong seo_mod)."""
    try:
        pages = seo_mod.list_title_meta_pages(url_type="product", limit=100000)
        synced = seo_mod.synced_title_meta_urls()
        urls = [p["url"] for p in pages if p["url"] not in synced]
        res = seo_mod.start_title_meta_fix_dual_async(urls)
        res.setdefault("remaining", len(urls))
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify(res), 200 if res.get("ok") else 409


def seo_title_meta_tier_progress():
    """Tiến độ fix title/meta theo từng tầng (cho badge % trên ô tầng)."""
    try:
        return jsonify({"ok": True, **seo_mod.tier_progress()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200], "tiers": []}), 500


def seo_title_meta_fix_filtered():
    """Gen+Sync thẳng Haravan cho tập SP đã lọc (phân tầng). Không duyệt.
    Body: {urls:[...]}."""
    payload = request.get_json(silent=True) or {}
    urls = payload.get("urls") or []
    if not isinstance(urls, list):
        return jsonify({"ok": False, "error": "urls phải là list"}), 400
    urls = [u for u in urls if isinstance(u, str) and u]
    if len(urls) > 800:
        return jsonify({"ok": False, "error": f"Quá nhiều SP ({len(urls)}), giới hạn 800/lần."}), 400
    try:
        res = seo_mod.start_title_meta_fix_urls_async(urls)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Lỗi server: {e}"}), 500
    return jsonify(res), 200 if res.get("ok") else 409


def seo_title_meta_gen_map():
    """Set URL đã gen (đã có đề xuất F/G trong Sheet) — cho cột Trạng thái + skip gen lại."""
    try:
        import sheet_writer
        done = sorted(sheet_writer.list_urls_with_proposal())
        return jsonify({"ok": True, "done": done, "count": len(done)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200], "done": []})


# ─────────────────────── GSC INSIGHTS (3 route) ──────────────────

def seo_gsc_page():
    cache = seo_mod.gsc_load_cache()
    if not cache:
        return render_template("seo_gsc.html", cache=None, tasks=[], summary=None)
    tasks = seo_mod.gsc_build_tasks(cache)
    return render_template(
        "seo_gsc.html",
        cache=cache, tasks=tasks,
        summary=cache.get("summary", {}),
        fetched_at=cache.get("fetched_at"),
        performance=cache.get("performance", {}),
        coverage=cache.get("coverage", {}),
    )


def seo_gsc_task_page(task_id):
    task = seo_mod.gsc_get_task(task_id)
    if not task:
        flash("Task không tồn tại trong cache.", "error")
        return redirect(url_for("seo_gsc_page"))
    return render_template("seo_gsc_task.html", task=task)


def seo_gsc_refresh():
    """Re-fetch data từ 2 Google Sheet GSC export."""
    script = ROOT / "_fetch_gsc_cache.py"
    try:
        r = subprocess.run(
            ["python", str(script)],
            capture_output=True, text=True, timeout=120, encoding="utf-8",
        )
        if r.returncode == 0:
            flash("✅ Refresh cache GSC xong.", "success")
        else:
            flash(f"❌ Refresh fail: {r.stderr[:300]}", "error")
    except Exception as e:
        flash(f"❌ Refresh error: {e}", "error")
    return redirect(url_for("seo_gsc_page"))


# ─────────────────────── CORE WEB VITALS (10 route) ──────────────

def seo_cwv_page():
    strategy = request.args.get("strategy", "mobile")
    sort = request.args.get("sort", "performance_score")
    order = request.args.get("order", "asc")
    page_num = max(1, int(request.args.get("page", 1)))
    per_page = 50
    offset = (page_num - 1) * per_page

    total = db.cwv_count(strategy)
    rows = db.cwv_list(strategy=strategy, limit=per_page, offset=offset, sort=sort, order=order)
    stats = db.cwv_stats(strategy)
    state = cwv_mod.state_snapshot()
    total_pages = max(1, (total + per_page - 1) // per_page)
    progress = db.cwv_progress(strategy)

    # Overall performance CẢ 2 thiết bị (để header hiện song song Mobile + Desktop)
    stats_mobile = db.cwv_stats("mobile")
    stats_desktop = db.cwv_stats("desktop")
    total_mobile = db.cwv_count("mobile")
    total_desktop = db.cwv_count("desktop")

    # ── Bảng "Top URL LCP tệ nhất" (P0B) — READ-ONLY, đọc từ seo_cwv_lcp, KHÔNG gọi PSI ──
    # (schema migration đã chạy lúc startup trong db.init_db → route chỉ đọc)
    lcp_strategy = request.args.get("lcp_strategy", strategy)
    if lcp_strategy not in ("mobile", "desktop"):
        lcp_strategy = "mobile"
    lcp_pt = request.args.get("lcp_pt") or None
    lcp_scope = request.args.get("lcp_scope") or None
    lcp_opp = request.args.get("lcp_opp") or None
    lcp_rows = db.cwv_lcp_list(strategy=lcp_strategy, page_type=lcp_pt,
                               field_scope=lcp_scope, opportunity=lcp_opp)
    lcp_filters = db.cwv_lcp_filters(strategy=lcp_strategy)
    lcp_summary = db.cwv_lcp_summary(strategy=lcp_strategy)

    return render_template(
        "seo_cwv.html",
        rows=rows, stats=stats, state=state,
        strategy=strategy, sort=sort, order=order,
        page_num=page_num, total_pages=total_pages, total=total,
        psi_key=_load_psi_key(),
        progress=progress,
        stats_mobile=stats_mobile, stats_desktop=stats_desktop,
        total_mobile=total_mobile, total_desktop=total_desktop,
        lcp_rows=lcp_rows, lcp_strategy=lcp_strategy, lcp_filters=lcp_filters,
        lcp_summary=lcp_summary, lcp_pt=lcp_pt, lcp_scope=lcp_scope, lcp_opp=lcp_opp,
    )


def seo_cwv_diff_page():
    diff_path = ROOT / "data" / "cwv_weekly_diff.json"
    diff = None
    error = None
    if diff_path.exists():
        try:
            diff = json.loads(diff_path.read_text(encoding="utf-8"))
        except Exception as e:
            error = f"Không đọc được {diff_path.name}: {e}"
    else:
        error = (
            "Chưa có file `data/cwv_weekly_diff.json`. "
            "Cần snapshot ≥2 tuần (`_scripts/weekly_cwv_snapshot.py`) rồi chạy "
            "`_scripts/weekly_cwv_diff.py` để generate."
        )
    return render_template("seo_cwv_diff.html", diff=diff, error=error)


def api_cwv_status():
    st = cwv_mod.state_snapshot()
    pass_start = cwv_mod.current_pass()
    stats = db.cwv_pass_stats(pass_start)
    st["pass"] = {
        "active": bool(pass_start),                 # có đợt đang dở (đã dừng giữa chừng)
        "remaining": stats["remaining"],            # số lần quét (url×strategy) còn lại của đợt
        "total": stats["total"],
        "scanned": stats["scanned"],
    }
    return jsonify(st)


def api_cwv_progress():
    strategy = request.args.get("strategy", "mobile")
    return jsonify({"progress": db.cwv_progress(strategy)})


def api_cwv_scan_start():
    body = request.get_json(silent=True) or {}
    strategy = body.get("strategy", "mobile")
    api_key = body.get("api_key", "").strip() or _load_psi_key()
    mode = body.get("mode", "top")
    url_type = body.get("url_type", "product")
    limit = min(int(body.get("limit", 30)), 200)

    skip_scanned = bool(body.get("skip_scanned", False))
    if mode == "custom":
        urls = [u.strip() for u in body.get("urls", []) if u.strip()]
    else:
        urls = cwv_mod.get_top_urls(limit=limit, url_type=url_type, skip_scanned=skip_scanned, strategy=strategy)

    if not urls:
        return jsonify({"ok": False, "error": "Không có URL nào để scan"})

    ok = cwv_mod.start_scan_async(urls, api_key=api_key, strategy=strategy)
    return jsonify({"ok": ok, "total": len(urls),
                    "message": "Đã bắt đầu scan" if ok else "Đang có scan chạy rồi"})


def api_cwv_scan_start_all():
    """Quét toàn bộ 1 đợt: mobile×(product→collection→blog→page) → desktop×(...).
    Tự resume nếu có đợt dở, hoặc bắt đầu đợt mới (quét lại tất cả) nếu đợt cũ đã xong."""
    body = request.get_json(silent=True) or {}
    api_key = body.get("api_key", "").strip() or _load_psi_key()
    res = cwv_mod.start_full_scan_async(api_key=api_key)
    msg = {"new": "Đã bắt đầu quét đợt mới (toàn bộ)",
           "resume": "Đã quét tiếp đợt đang dở",
           "running": "Đang quét rồi"}.get(res.get("mode"), "")
    return jsonify({"ok": res.get("ok", False), "mode": res.get("mode"), "message": msg})


def api_cwv_scan_stop():
    cwv_mod.stop_scan()
    return jsonify({"ok": True})


def api_cwv_clear():
    strategy = (request.get_json(silent=True) or {}).get("strategy")
    db.cwv_clear(strategy)
    return jsonify({"ok": True})


def api_cwv_sync_github():
    """Pull JSON kết quả CWV scan mới nhất từ GitHub Actions → upsert vào seo_cwv local.

    Đọc data/cwv_results/_latest.json → fetch từng file con → upsert.
    """
    try:
        r = requests.get(f"{GITHUB_RAW_BASE}/data/cwv_results/_latest.json", timeout=15)
        if r.status_code != 200:
            return jsonify({"ok": False, "error": f"_latest.json HTTP {r.status_code}"}), 502
        latest = r.json()
        latest_date = latest.get("latest_date")
        files = latest.get("files") or []
        if not latest_date or not files:
            return jsonify({"ok": False, "error": "latest pointer thiếu date/files"}), 502

        total_upserted = 0
        total_failed = 0
        per_file = []
        for fname in files:
            url = f"{GITHUB_RAW_BASE}/data/cwv_results/{latest_date}/{fname}"
            try:
                fr = requests.get(url, timeout=30)
                if fr.status_code != 200:
                    per_file.append({"file": fname, "ok": False, "error": f"HTTP {fr.status_code}"})
                    total_failed += 1
                    continue
                payload = fr.json()
                results = payload.get("results") or []
                upserted = 0
                for res in results:
                    if res.get("ok"):
                        db.cwv_upsert(res)
                        upserted += 1
                per_file.append({"file": fname, "ok": True, "upserted": upserted, "total": len(results)})
                total_upserted += upserted
            except Exception as e:
                per_file.append({"file": fname, "ok": False, "error": str(e)[:200]})
                total_failed += 1

        try:
            sync_state_path = ROOT / "data" / "cwv_last_sync.json"
            sync_state_path.parent.mkdir(parents=True, exist_ok=True)
            sync_state_path.write_text(json.dumps({
                "synced_at": datetime.now().isoformat(timespec="seconds"),
                "from_date": latest_date,
                "upserted": total_upserted,
                "failed_files": total_failed,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

        return jsonify({
            "ok": True,
            "latest_date": latest_date,
            "files_processed": len(files),
            "upserted": total_upserted,
            "failed_files": total_failed,
            "detail": per_file,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 500


def api_cwv_sync_status():
    """Trạng thái sync GitHub gần nhất + có scan mới hơn local không."""
    info = {"last_sync": None, "remote_latest": None, "has_new": False}
    try:
        sync_state_path = ROOT / "data" / "cwv_last_sync.json"
        if sync_state_path.exists():
            info["last_sync"] = json.loads(sync_state_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    try:
        r = requests.get(f"{GITHUB_RAW_BASE}/data/cwv_results/_latest.json", timeout=10)
        if r.status_code == 200:
            remote = r.json()
            info["remote_latest"] = remote
            local_date = (info["last_sync"] or {}).get("from_date") if info["last_sync"] else None
            if remote.get("latest_date") and remote["latest_date"] != local_date:
                info["has_new"] = True
    except Exception as e:
        info["remote_error"] = str(e)[:200]
    return jsonify(info)


# ─────────────────────── SCHEMA (3 route) ────────────────────────

def seo_schema_page():
    url_type = request.args.get("url_type") or None
    missing = request.args.get("missing") or None
    page_num = max(1, int(request.args.get("page", 1)))
    per_page = 50
    offset = (page_num - 1) * per_page

    stats_all = db.seo_schema_stats()
    stats_by_type = {
        ut: db.seo_schema_stats(url_type=ut)
        for ut in ("product", "blog", "collection", "page")
    }
    total = db.seo_schema_count(url_type=url_type, missing=missing)
    rows = db.seo_schema_list(url_type=url_type, missing=missing,
                              limit=per_page, offset=offset)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "seo_schema.html",
        stats_all=stats_all, stats_by_type=stats_by_type,
        rows=rows, total=total, total_pages=total_pages,
        page_num=page_num, url_type=url_type, missing=missing,
    )


def seo_schema_rescan(page_id):
    conn = db.get_conn()
    row = conn.execute("SELECT url FROM seo_pages WHERE id=?", (page_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"ok": False, "error": "Page not found"}), 404
    import schema_scanner
    try:
        data = schema_scanner.update_page_schema(row["url"])
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500
    types = []
    if data.get("schema_types"):
        try:
            types = json.loads(data["schema_types"])
        except Exception:
            types = []
    return jsonify({
        "ok": True,
        "url": row["url"],
        "types": types,
        "schema_count": data.get("schema_count", 0),
        "has_product": bool(data.get("has_product")),
        "has_faq": bool(data.get("has_faq")),
        "has_article": bool(data.get("has_article")),
        "fetch_error": data.get("fetch_error"),
        "scanned_at": data.get("scanned_at"),
    })


def seo_schema_detail(page_id):
    conn = db.get_conn()
    row = conn.execute("SELECT url, url_type, title FROM seo_pages WHERE id=?", (page_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"ok": False, "error": "Page not found"}), 404
    import schema_scanner
    headers = {"User-Agent": schema_scanner.USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    try:
        r = requests.get(row["url"], headers=headers, timeout=12, allow_redirects=True)
        if r.status_code != 200:
            return jsonify({"ok": False, "error": f"HTTP {r.status_code}", "url": row["url"]}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}", "url": row["url"]}), 200
    parsed = schema_scanner.extract_jsonld_from_html(r.text)
    return jsonify({
        "ok": True,
        "url": row["url"],
        "url_type": row["url_type"],
        "title": row["title"],
        "blocks": parsed["blocks"],
        "all_types": parsed["all_types"],
        "errors": parsed["errors"],
    })


# ─────────────────────── EMPTY DESC (3 route) ────────────────────

def seo_empty_desc_page():
    try:
        threshold = int(request.args.get("threshold") or seo_mod.EMPTY_DESC_THRESHOLD)
    except ValueError:
        threshold = seo_mod.EMPTY_DESC_THRESHOLD
    threshold = max(0, min(threshold, 1000))
    show_all = request.args.get("all") == "1"
    items = db.seo_empty_desc_list(
        url_type="product",
        threshold=threshold,
        only_empty=not show_all,
        limit=2000,
    )
    summary = db.seo_empty_desc_summary(threshold=threshold)
    state = seo_mod.empty_desc_state()
    return render_template(
        "seo_empty_desc.html",
        items=items, summary=summary, state=state,
        threshold=threshold, show_all=show_all,
    )


def seo_empty_desc_scan():
    try:
        threshold = int(request.form.get("threshold") or seo_mod.EMPTY_DESC_THRESHOLD)
    except ValueError:
        threshold = seo_mod.EMPTY_DESC_THRESHOLD
    threshold = max(0, min(threshold, 1000))
    try:
        limit = int(request.form.get("limit") or 0) or None
    except ValueError:
        limit = None
    started = seo_mod.start_empty_desc_scan_async(threshold=threshold, limit=limit)
    if started:
        flash(f"📭 Đã bắt đầu quét SP thiếu mô tả (ngưỡng {threshold} từ).", "success")
    else:
        flash("⏳ Đang có lượt quét chạy — chờ xong mới chạy lượt mới.", "info")
    return redirect(url_for("seo_empty_desc_page", threshold=threshold))


def seo_empty_desc_status():
    return jsonify({
        "state": seo_mod.empty_desc_state(),
        "summary": db.seo_empty_desc_summary(),
    })


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 33 route SEO Tools."""
    # H1 in desc (7)
    app.add_url_rule("/seo/coverage", "seo_coverage_page", seo_coverage_page)
    app.add_url_rule("/seo/coverage/scan-collections", "seo_coverage_scan_collections", seo_coverage_scan_collections, methods=["POST"])
    app.add_url_rule("/seo/eeat", "seo_eeat_page", seo_eeat_page)
    app.add_url_rule("/seo/h1-in-desc", "seo_h1_in_desc_page", seo_h1_in_desc_page)
    app.add_url_rule("/seo/h1-in-desc/scan", "seo_h1_in_desc_scan", seo_h1_in_desc_scan, methods=["POST"])
    app.add_url_rule("/api/seo/h1-in-desc/status", "seo_h1_in_desc_status", seo_h1_in_desc_status)
    app.add_url_rule("/seo/h1-in-desc/fix", "seo_h1_in_desc_fix", seo_h1_in_desc_fix, methods=["POST"])
    app.add_url_rule("/seo/h1-in-desc/fix-all/start", "seo_h1_fix_all_start", seo_h1_fix_all_start, methods=["POST"])
    app.add_url_rule("/seo/h1-in-desc/fix-all/stop", "seo_h1_fix_all_stop", seo_h1_fix_all_stop, methods=["POST"])
    app.add_url_rule("/api/seo/h1-in-desc/fix-all/status", "seo_h1_fix_all_status", seo_h1_fix_all_status)

    # Title/Meta (7)
    app.add_url_rule("/seo/title-meta", "seo_title_meta_page", seo_title_meta_page)
    app.add_url_rule("/seo/title-meta/fix", "seo_title_meta_fix", seo_title_meta_fix, methods=["POST"])
    app.add_url_rule("/seo/title-meta/preview", "seo_title_meta_preview", seo_title_meta_preview, methods=["POST"])
    app.add_url_rule("/seo/title-meta/regen", "seo_title_meta_regen", seo_title_meta_regen, methods=["POST"])
    app.add_url_rule("/seo/title-meta/fix-all/start", "seo_title_meta_fix_all_start", seo_title_meta_fix_all_start, methods=["POST"])
    app.add_url_rule("/seo/title-meta/fix-all/stop", "seo_title_meta_fix_all_stop", seo_title_meta_fix_all_stop, methods=["POST"])
    app.add_url_rule("/api/seo/title-meta/fix-all/status", "seo_title_meta_fix_all_status", seo_title_meta_fix_all_status)
    app.add_url_rule("/seo/title-meta/recrawl/start", "seo_title_meta_recrawl_start", seo_title_meta_recrawl_start, methods=["POST"])
    app.add_url_rule("/seo/title-meta/recrawl/stop", "seo_title_meta_recrawl_stop", seo_title_meta_recrawl_stop, methods=["POST"])
    app.add_url_rule("/api/seo/title-meta/recrawl/status", "seo_title_meta_recrawl_status", seo_title_meta_recrawl_status)
    app.add_url_rule("/api/seo/title-meta/gen-map", "seo_title_meta_gen_map", seo_title_meta_gen_map)
    app.add_url_rule("/seo/title-meta/tier-products", "seo_title_meta_tier_products", seo_title_meta_tier_products, methods=["POST"])
    app.add_url_rule("/api/seo/title-meta/tier-progress", "seo_title_meta_tier_progress", seo_title_meta_tier_progress)
    app.add_url_rule("/seo/title-meta/regen-all", "seo_title_meta_regen_all", seo_title_meta_regen_all, methods=["POST"])
    app.add_url_rule("/seo/title-meta/regen-remaining", "seo_title_meta_regen_remaining", seo_title_meta_regen_remaining, methods=["POST"])
    app.add_url_rule("/seo/title-meta/regen-dual", "seo_title_meta_regen_dual", seo_title_meta_regen_dual, methods=["POST"])
    app.add_url_rule("/seo/title-meta/fix-filtered", "seo_title_meta_fix_filtered", seo_title_meta_fix_filtered, methods=["POST"])

    # GSC (3)
    app.add_url_rule("/seo/gsc", "seo_gsc_page", seo_gsc_page)
    app.add_url_rule("/seo/gsc/task/<task_id>", "seo_gsc_task_page", seo_gsc_task_page)
    app.add_url_rule("/seo/gsc/refresh", "seo_gsc_refresh", seo_gsc_refresh, methods=["POST"])

    # CWV (10)
    app.add_url_rule("/seo/cwv", "seo_cwv_page", seo_cwv_page)
    app.add_url_rule("/seo/cwv/diff", "seo_cwv_diff_page", seo_cwv_diff_page)
    app.add_url_rule("/api/seo/cwv/status", "api_cwv_status", api_cwv_status)
    app.add_url_rule("/api/seo/cwv/progress", "api_cwv_progress", api_cwv_progress)
    app.add_url_rule("/api/seo/cwv/scan/start", "api_cwv_scan_start", api_cwv_scan_start, methods=["POST"])
    app.add_url_rule("/api/seo/cwv/scan/start-all", "api_cwv_scan_start_all", api_cwv_scan_start_all, methods=["POST"])
    app.add_url_rule("/api/seo/cwv/scan/stop", "api_cwv_scan_stop", api_cwv_scan_stop, methods=["POST"])
    app.add_url_rule("/api/seo/cwv/clear", "api_cwv_clear", api_cwv_clear, methods=["POST"])
    app.add_url_rule("/api/seo/cwv/sync-github", "api_cwv_sync_github", api_cwv_sync_github, methods=["POST"])
    app.add_url_rule("/api/seo/cwv/sync-status", "api_cwv_sync_status", api_cwv_sync_status)

    # Schema (3)
    app.add_url_rule("/seo/schema", "seo_schema_page", seo_schema_page)
    app.add_url_rule("/seo/schema/rescan/<int:page_id>", "seo_schema_rescan", seo_schema_rescan, methods=["POST"])
    app.add_url_rule("/seo/schema/detail/<int:page_id>", "seo_schema_detail", seo_schema_detail)

    # Empty desc (3)
    app.add_url_rule("/seo/empty-desc", "seo_empty_desc_page", seo_empty_desc_page)
    app.add_url_rule("/seo/empty-desc/scan", "seo_empty_desc_scan", seo_empty_desc_scan, methods=["POST"])
    app.add_url_rule("/api/seo/empty-desc/status", "seo_empty_desc_status", seo_empty_desc_status)
