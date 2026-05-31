"""Routes: SEO Quality — 7 endpoint (duplicates + inlinks + indexability +
broken-links page + check-links + recheck-broken + link-check-status).

Tách từ app.py (Batch 5B refactor). Low risk — chỉ là read + bg check job.

Dep:
- seo as seo_mod (link_check_state, start_link_check_async, LINK_ERROR_LABELS)
- db.seo_* (find_duplicates, inlinks_summary, orphan_pages, top_inlinks,
  indexability_stats, list_non_indexable, broken_link_summary,
  broken_breakdown, count_broken_filtered, broken_links_filtered,
  get_broken_target_urls, reset_broken_links_for_recheck)
"""

from flask import (
    render_template, request, jsonify,
    redirect, url_for, flash,
)

import db
import seo as seo_mod


# ─────────────────────── DUPLICATES ──────────────────────────────

def seo_duplicates():
    field = request.args.get("field", "title")
    if field not in ("title", "meta_desc", "h1"):
        field = "title"
    dup_groups = db.seo_find_duplicates(field)
    counts = {
        "title": len(db.seo_find_duplicates("title")),
        "meta_desc": len(db.seo_find_duplicates("meta_desc")),
        "h1": len(db.seo_find_duplicates("h1")),
    }
    return render_template("seo_duplicates.html", field=field, groups=dup_groups, counts=counts)


# ─────────────────────── INLINKS / ORPHANS ───────────────────────

def seo_inlinks_page():
    view = request.args.get("view", "top")  # top | orphans
    url_type = request.args.get("type") or None
    summary = db.seo_inlinks_summary()
    if view == "orphans":
        items = db.seo_orphan_pages(url_type=url_type, limit=500)
    else:
        items = db.seo_top_inlinks(limit=100)
    return render_template(
        "seo_inlinks.html",
        summary=summary, items=items, view=view, url_type=url_type,
    )


# ─────────────────────── INDEXABILITY ────────────────────────────

def seo_indexability_page():
    reason = request.args.get("reason")
    stats = db.seo_indexability_stats()
    pages = db.seo_list_non_indexable(reason=reason, limit=500)
    return render_template(
        "seo_indexability.html",
        stats=stats, pages=pages, active_reason=reason,
    )


# ─────────────────────── BROKEN LINKS PAGE ───────────────────────

def seo_broken_links_page():
    summary = db.seo_broken_link_summary()
    state = seo_mod.link_check_state()
    breakdown = db.seo_broken_breakdown()

    kind = request.args.get("kind") or None
    if kind not in ("4xx", "5xx", "timeout"):
        kind = None
    try:
        status_code = int(request.args["status"]) if request.args.get("status") else None
    except (TypeError, ValueError):
        status_code = None
    error_kind = request.args.get("error_kind") or None
    internal_arg = request.args.get("internal")
    is_internal = None
    if internal_arg == "1":
        is_internal = True
    elif internal_arg == "0":
        is_internal = False
    search = (request.args.get("q") or "").strip() or None
    sort = request.args.get("sort") or "refs_desc"
    if sort not in ("refs_desc", "refs_asc", "url", "status"):
        sort = "refs_desc"
    try:
        page_num = max(1, int(request.args.get("page") or 1))
    except (TypeError, ValueError):
        page_num = 1
    per_page = 100

    filters = dict(kind=kind, status_code=status_code, error_kind=error_kind,
                   is_internal=is_internal, search=search)
    total_filtered = db.seo_count_broken_filtered(**filters)
    total_pages = max(1, (total_filtered + per_page - 1) // per_page)
    broken = db.seo_broken_links_filtered(
        **filters, sort=sort,
        limit=per_page, offset=(page_num - 1) * per_page,
    )

    return render_template(
        "seo_broken_links.html",
        summary=summary, state=state, broken=broken,
        breakdown=breakdown,
        error_labels=seo_mod.LINK_ERROR_LABELS,
        filters={
            "kind": kind, "status_code": status_code, "error_kind": error_kind,
            "internal": internal_arg, "q": search or "", "sort": sort,
        },
        page_num=page_num, total_pages=total_pages, total_filtered=total_filtered,
        per_page=per_page,
    )


# ─────────────────────── CHECK LINKS (bg job) ────────────────────

def seo_check_links():
    started = seo_mod.start_link_check_async()
    if started:
        flash("Đã bắt đầu check link gãy. Quá trình này có thể mất vài phút.", "success")
    else:
        flash("Đang check link — chờ xong rồi check tiếp.", "error")
    return redirect(url_for("seo_broken_links_page"))


def seo_recheck_broken():
    """Re-check ĐÚNG các link đang broken (4xx/5xx/timeout) — không quét toàn bộ
    pool external chưa check. Tiện cho việc phân loại error_kind chi tiết."""
    targets = db.seo_get_broken_target_urls()
    if not targets:
        flash("Không có link broken nào để re-check.", "error")
        return redirect(url_for("seo_broken_links_page"))
    n = db.seo_reset_broken_links_for_recheck()
    started = seo_mod.start_link_check_async(only_targets=targets)
    if started:
        flash(f"Đã reset {n} link và bắt đầu re-check ĐÚNG {len(targets)} target broken.", "success")
    else:
        flash(f"Đã reset {n} link nhưng đang có run khác — chờ xong rồi bấm lại.", "warning")
    return redirect(url_for("seo_broken_links_page"))


def seo_link_check_status():
    return jsonify({
        "state": seo_mod.link_check_state(),
        "summary": db.seo_broken_link_summary(),
    })


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 7 route SEO Quality."""
    app.add_url_rule("/seo/duplicates", "seo_duplicates", seo_duplicates)
    app.add_url_rule("/seo/inlinks", "seo_inlinks_page", seo_inlinks_page)
    app.add_url_rule("/seo/indexability", "seo_indexability_page", seo_indexability_page)
    app.add_url_rule("/seo/broken-links", "seo_broken_links_page", seo_broken_links_page)
    app.add_url_rule("/seo/check-links", "seo_check_links", seo_check_links, methods=["POST"])
    app.add_url_rule("/seo/recheck-broken", "seo_recheck_broken", seo_recheck_broken, methods=["POST"])
    app.add_url_rule("/api/seo/link-check-status", "seo_link_check_status", seo_link_check_status)
