"""Routes: ALT Manager — 14 endpoint (P1-P5 audit/edit/bulk ALT text).

Đăng ký qua `register(app)` (manual add_url_rule — giữ flat endpoint name).

Dep:
- alt_manager (module chính: summarize/list/save)
- haravan_client (PUT ALT ảnh + update_product body_html)
- content_writer._gen_alt_for_position (AI gen 1 ảnh SP)
"""

import csv
import io
from flask import render_template, request, jsonify, Response

import alt_manager
import alt_issue_import
import haravan_client as hv_client


# ─────────────────────── LIST / EDITOR PAGES ─────────────────────

def alt_manager_page():
    """P2 — trang list SP với ALT coverage badge, KPI + filter + paginate."""
    page = max(1, int(request.args.get("page", 1) or 1))
    only_missing = request.args.get("missing", "1") != "0"
    filter_type = (request.args.get("type") or "").strip() or None
    filter_vendor = (request.args.get("vendor") or "").strip() or None
    search = (request.args.get("q") or "").strip() or None
    sort = request.args.get("sort", "missing_desc")
    if sort not in ("missing_desc", "total_desc", "handle_asc"):
        sort = "missing_desc"

    summary = alt_manager.summarize_alt_coverage()
    page_data = alt_manager.list_products_paginated(
        page=page, page_size=50,
        only_missing=only_missing,
        filter_type=filter_type, filter_vendor=filter_vendor,
        search=search, sort=sort,
    )
    options = alt_manager.list_filter_options()
    try:
        issue_counts = alt_issue_import.counts()
    except Exception:
        issue_counts = {"total": 0, "by_type": {}, "by_context": {}, "by_status": {}}
    return render_template(
        "alt_manager.html",
        summary=summary, page_data=page_data, options=options,
        only_missing=only_missing,
        filter_type=filter_type, filter_vendor=filter_vendor,
        search=search, sort=sort,
        issue_counts=issue_counts,
    )


# ─────────────────── IMAGE ISSUE QUEUE (import LibreCrawl/crawler) ───────────────────

def api_alt_issues():
    """List queue image issue + counts. Filter type/context/status, sort priority."""
    rows = alt_issue_import.list_issues(
        issue_type=(request.args.get("type") or "").strip() or None,
        context=(request.args.get("context") or "").strip() or None,
        status=(request.args.get("status") or "").strip() or None,
        limit=int(request.args.get("limit", 200) or 200),
        offset=int(request.args.get("offset", 0) or 0),
    )
    return jsonify({"counts": alt_issue_import.counts(), "items": rows})


def api_alt_issues_mark():
    """Mark 1 issue reviewed/ignored/pending. KHÔNG đụng live ảnh."""
    data = request.get_json(silent=True) or {}
    ok = alt_issue_import.mark(data.get("id"), (data.get("status") or "").strip())
    return jsonify({"success": ok})


def api_alt_issues_export():
    """Export toàn bộ queue ra CSV."""
    rows = alt_issue_import.export_rows()
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=alt_image_issues.csv"})


def alt_manager_product_page(product_id):
    """P3 — editor inline ALT text cho 1 SP."""
    from content_writer import _gen_alt_for_position  # noqa: F401 — confirm importable
    product = alt_manager.get_product_for_editor(product_id)
    if not product:
        return "Không tìm thấy SP", 404
    return render_template("alt_manager_product.html", product=product)


# ─────────────────────── PRODUCT-IMAGE ALT API ───────────────────

def alt_manager_gen_alt(product_id):
    """P3 — AI gen ALT text cho 1 image."""
    from content_writer import _gen_alt_for_position
    data = request.get_json(force=True) or {}
    position = int(data.get("position", 1))
    total = int(data.get("total", 1))
    product = alt_manager.get_product_for_editor(product_id)
    if not product:
        return jsonify({"error": "SP not found"}), 404
    name_clean = (product.get("title") or product.get("handle") or "").strip()
    alt = _gen_alt_for_position(name_clean, position, total)
    return jsonify({"alt": alt})


def alt_manager_save_alts(product_id):
    """P3 — bulk save ALT: PUT Haravan API + update local DB."""
    data = request.get_json(force=True) or {}
    updates = data.get("updates", [])  # [{image_id, alt}, ...]
    if not updates:
        return jsonify({"ok": True, "saved": 0, "errors": []})
    errors = []
    saved = 0
    for item in updates:
        image_id = item.get("image_id")
        new_alt = (item.get("alt") or "").strip()
        if not image_id:
            continue
        result = hv_client.put_image_alt(product_id, image_id, new_alt)
        if result.get("ok"):
            alt_manager.update_image_alt_local(product_id, image_id, new_alt)
            saved += 1
        else:
            errors.append({"image_id": image_id, "error": result.get("error", "unknown")})
    return jsonify({"ok": len(errors) == 0, "saved": saved, "errors": errors})


# ─────────────────────── SUMMARY / WORST ─────────────────────────

def alt_manager_summary():
    """P1 — coverage stats toàn shop, parse JSON images đã có trong DB."""
    return jsonify(alt_manager.summarize_alt_coverage())


def alt_manager_worst():
    """P1 — top SP có nhiều ảnh thiếu/yếu ALT nhất."""
    limit = max(1, min(int(request.args.get("limit", 50)), 500))
    only_missing = request.args.get("all", "").lower() not in ("1", "true", "yes")
    return jsonify({
        "items": alt_manager.worst_products(limit=limit, only_with_missing=only_missing),
        "limit": limit,
    })


# ─────────────────────── DESC-IMAGE ALT API (P5) ─────────────────

def alt_manager_desc_images(product_id):
    """P5 — fetch body_html LIVE từ Haravan, parse img tags."""
    try:
        imgs, _ = alt_manager.get_product_desc_images(product_id)
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500
    product = alt_manager.get_product_for_editor(product_id)
    return jsonify({"images": imgs, "title": (product or {}).get("title", "")})


def alt_manager_gen_alt_desc(product_id):
    """P5 — gen ALT cho 1 ảnh mô tả."""
    data = request.get_json(force=True) or {}
    idx = int(data.get("index", 0))
    product = alt_manager.get_product_for_editor(product_id)
    if not product:
        return jsonify({"error": "SP not found"}), 404
    name = (product.get("title") or product.get("handle") or "").strip()
    alt = alt_manager.gen_alt_for_desc_image(name, idx)
    return jsonify({"alt": alt})


def alt_manager_save_desc(product_id):
    """P5 — fetch live body_html → inject ALT → PUT lên Haravan."""
    data = request.get_json(force=True) or {}
    updates = data.get("updates", [])
    if not updates:
        return jsonify({"ok": True, "saved": 0})
    try:
        _, live_html = alt_manager.get_product_desc_images(product_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Fetch Haravan thất bại: {e}"}), 500
    if not live_html:
        return jsonify({"ok": False, "error": "body_html trống"}), 400
    new_html = alt_manager.save_desc_image_alts(product_id, updates, live_html)
    try:
        hv_client.update_product(product_id, {"body_html": new_html})
        alt_manager.db.mark_alt_synced(product_id)  # cột "Ngày sync"
        return jsonify({"ok": True, "saved": len(updates)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 500


# ─────────────────────── BULK GEN BACKGROUND JOB ─────────────────

def alt_manager_bulk_gen_start():
    """P4 — khởi chạy bulk gen ALT background job."""
    ok = alt_manager.start_bulk_gen_async()
    if not ok:
        return jsonify({"ok": False, "error": "Job đang chạy rồi"}), 409
    return jsonify({"ok": True, "message": "Đã bắt đầu bulk gen"})


def alt_manager_bulk_gen_start_dual():
    """Bulk gen ALT bằng AI, chạy song song Codex×N + Claude×N (workers mỗi provider)."""
    try:
        workers = int(request.args.get("workers") or (request.get_json(silent=True) or {}).get("workers") or 3)
    except Exception:
        workers = 3
    ok = alt_manager.start_bulk_gen_dual_async(workers)
    if not ok:
        return jsonify({"ok": False, "error": "Job đang chạy rồi"}), 409
    return jsonify({"ok": True, "message": f"Đã bắt đầu Dual AI (Codex×{workers} + Claude×{workers})"})


def alt_manager_bulk_gen_start_desc():
    """Bulk gen chỉ ảnh mô tả (body_html) — API image ALT không hỗ trợ."""
    ok = alt_manager.start_bulk_gen_async(desc_only=True)
    if not ok:
        return jsonify({"ok": False, "error": "Job đang chạy rồi"}), 409
    return jsonify({"ok": True})


def alt_manager_bulk_gen_stop():
    """P4 — gửi tín hiệu dừng bulk gen job."""
    stopped = alt_manager.stop_bulk_gen()
    return jsonify({"ok": stopped, "message": "Đang dừng..." if stopped else "Job không chạy"})


def alt_manager_fetch_status():
    """Stub: hệ gen mới tự build worklist trong job, không cần bước fetch riêng."""
    return jsonify({"running": False, "found_products": 0, "found_images": 0, "message": ""})


def alt_manager_fetch_stop():
    return jsonify({"ok": True})


def alt_manager_fetch_start():
    return jsonify({"ok": False, "error": "Không cần Fetch — bấm 'Dual AI (Codex+Claude)' để gen trực tiếp."})


def alt_manager_bulk_gen_status():
    """P4 — polling endpoint trả trạng thái bulk gen job."""
    return jsonify(alt_manager.bulk_gen_job_state())


def alt_manager_gen_save_all(product_id):
    """Gen + save ALT cho tất cả ảnh (product + desc) của 1 SP."""
    try:
        result = alt_manager.gen_and_save_all_alts(product_id)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500
    return jsonify(result)


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 14 route ALT Manager — giữ nguyên endpoint name."""
    app.add_url_rule("/alt-manager", "alt_manager_page", alt_manager_page)
    app.add_url_rule("/alt-manager/<int:product_id>", "alt_manager_product_page", alt_manager_product_page)

    app.add_url_rule("/api/alt-manager/<int:product_id>/gen-alt",
                     "alt_manager_gen_alt", alt_manager_gen_alt, methods=["POST"])
    app.add_url_rule("/api/alt-manager/<int:product_id>/save",
                     "alt_manager_save_alts", alt_manager_save_alts, methods=["POST"])

    app.add_url_rule("/api/alt-manager/summary", "alt_manager_summary", alt_manager_summary)
    app.add_url_rule("/api/alt-manager/worst", "alt_manager_worst", alt_manager_worst)

    app.add_url_rule("/api/alt-manager/<int:product_id>/desc-images",
                     "alt_manager_desc_images", alt_manager_desc_images)
    app.add_url_rule("/api/alt-manager/<int:product_id>/gen-alt-desc",
                     "alt_manager_gen_alt_desc", alt_manager_gen_alt_desc, methods=["POST"])
    app.add_url_rule("/api/alt-manager/<int:product_id>/save-desc",
                     "alt_manager_save_desc", alt_manager_save_desc, methods=["POST"])

    app.add_url_rule("/api/alt-manager/bulk-gen/start",
                     "alt_manager_bulk_gen_start", alt_manager_bulk_gen_start, methods=["POST"])
    app.add_url_rule("/api/alt-manager/bulk-gen/start-dual",
                     "alt_manager_bulk_gen_start_dual", alt_manager_bulk_gen_start_dual, methods=["POST"])
    # Alias khớp UI template (alt-gen/*) + stub fetch/*
    app.add_url_rule("/api/alt-manager/alt-gen/start",
                     "alt_gen_start", alt_manager_bulk_gen_start, methods=["POST"])
    app.add_url_rule("/api/alt-manager/alt-gen/start-dual",
                     "alt_gen_start_dual", alt_manager_bulk_gen_start_dual, methods=["POST"])
    app.add_url_rule("/api/alt-manager/alt-gen/status", "alt_gen_status", alt_manager_bulk_gen_status)
    app.add_url_rule("/api/alt-manager/alt-gen/stop",
                     "alt_gen_stop", alt_manager_bulk_gen_stop, methods=["POST"])
    app.add_url_rule("/api/alt-manager/fetch/status", "alt_fetch_status", alt_manager_fetch_status)
    app.add_url_rule("/api/alt-manager/fetch/stop",
                     "alt_fetch_stop", alt_manager_fetch_stop, methods=["POST"])
    app.add_url_rule("/api/alt-manager/fetch/start",
                     "alt_fetch_start", alt_manager_fetch_start, methods=["POST"])
    app.add_url_rule("/api/alt-manager/bulk-gen/start-desc",
                     "alt_manager_bulk_gen_start_desc", alt_manager_bulk_gen_start_desc, methods=["POST"])
    app.add_url_rule("/api/alt-manager/bulk-gen/stop",
                     "alt_manager_bulk_gen_stop", alt_manager_bulk_gen_stop, methods=["POST"])
    app.add_url_rule("/api/alt-manager/bulk-gen/status",
                     "alt_manager_bulk_gen_status", alt_manager_bulk_gen_status)

    app.add_url_rule("/api/alt-manager/<int:product_id>/gen-save-all",
                     "alt_manager_gen_save_all", alt_manager_gen_save_all, methods=["POST"])

    # Image issue queue (import LibreCrawl/crawler — review only, no live apply)
    app.add_url_rule("/api/alt-manager/issues", "api_alt_issues", api_alt_issues)
    app.add_url_rule("/api/alt-manager/issues/mark", "api_alt_issues_mark",
                     api_alt_issues_mark, methods=["POST"])
    app.add_url_rule("/api/alt-manager/issues/export.csv", "api_alt_issues_export",
                     api_alt_issues_export)
