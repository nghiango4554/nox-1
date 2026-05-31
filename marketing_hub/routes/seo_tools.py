"""Routes: SEO Tools — 33 endpoint (h1-in-desc + title-meta + GSC + CWV + schema + empty-desc).

Tách từ app.py (Batch 5C refactor). Med-High risk — nhiều background worker
(_GEN_BG/_PILLAR_BG ở routes.state đã được verify giữ state qua re-import).

Move kèm:
- `_load_psi_key()` helper (chỉ dùng nội bộ CWV)
- `GITHUB_RAW_BASE` constant (sync-github)

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
    if sync_filter not in ("synced", "unsynced"):
        sync_filter = None
    items = seo_mod.list_title_meta_pages(
        url_type=url_type, issue_filter=issue_filter, sort=sort, limit=2000,
        sync_filter=sync_filter,
    )
    summary = seo_mod.title_meta_summary()
    fix_state = seo_mod.title_meta_fix_state()
    return render_template(
        "seo_title_meta.html",
        items=items, summary=summary, fix_state=fix_state,
        url_type=url_type, issue_filter=issue_filter, sort=sort,
        sync_filter=sync_filter,
        issue_labels=seo_mod.TITLE_META_LABELS,
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
    if sync_filter not in ("synced", "unsynced"):
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


def seo_title_meta_fix_all_status():
    return jsonify(seo_mod.title_meta_fix_state())


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

    return render_template(
        "seo_cwv.html",
        rows=rows, stats=stats, state=state,
        strategy=strategy, sort=sort, order=order,
        page_num=page_num, total_pages=total_pages, total=total,
        psi_key=_load_psi_key(),
        progress=progress,
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
    return jsonify(cwv_mod.state_snapshot())


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
    """Quét All Batch — chain 8 phase: mobile×(product→collection→blog→page) → desktop×(...)."""
    body = request.get_json(silent=True) or {}
    api_key = body.get("api_key", "").strip() or _load_psi_key()
    ok = cwv_mod.start_chain_async(api_key=api_key)
    return jsonify({"ok": ok, "message": "Đã bắt đầu Quét All Batch" if ok else "Đang có scan chạy rồi"})


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
    app.add_url_rule("/seo/title-meta/regen", "seo_title_meta_regen", seo_title_meta_regen, methods=["POST"])
    app.add_url_rule("/seo/title-meta/fix-all/start", "seo_title_meta_fix_all_start", seo_title_meta_fix_all_start, methods=["POST"])
    app.add_url_rule("/seo/title-meta/fix-all/stop", "seo_title_meta_fix_all_stop", seo_title_meta_fix_all_stop, methods=["POST"])
    app.add_url_rule("/api/seo/title-meta/fix-all/status", "seo_title_meta_fix_all_status", seo_title_meta_fix_all_status)
    app.add_url_rule("/api/seo/title-meta/gen-map", "seo_title_meta_gen_map", seo_title_meta_gen_map)

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
