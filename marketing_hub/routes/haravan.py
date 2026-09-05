"""Routes: Haravan — 10 endpoint (dashboard + sync + products + blogs + inline edit + AI rewrite).

⚠️ Permission gate: `api_haravan_product_edit` gọi `hv_client.update_product` KHÔNG dùng
`allow_blocked_operations` — cố ý dùng default gate trong haravan_client (PUT SEO meta cho phép,
POST/DELETE SP chặn).

Dep:
- haravan_client (PUT product field + update_product)
- haravan_sync (start_sync_async / start_sync_incremental_async / sync_state / HV_ISSUE_LABELS / hv_enrich_issue)
- db (hv_* + seo_get_page + activity_log)
- routes.blog_topics (classify_blog_topic + BLOG_TOPICS + BLOG_TOPIC_LABELS)
"""

import json
from datetime import datetime

from flask import render_template, request, jsonify, redirect, url_for, flash

import db
import haravan_client as hv_client
import haravan_sync as hv_sync
from routes.blog_topics import classify_blog_topic, BLOG_TOPICS, BLOG_TOPIC_LABELS


# ─────────────────────── CONSTANTS ───────────────────────────────

# Map field UI → field API Haravan + DB local
HV_FIELD_API_MAP = {
    "title": "title",
    "vendor": "vendor",
    "product_type": "product_type",
    "tags": "tags",
    "meta_title": "metafields_global_title_tag",
    "meta_description": "metafields_global_description_tag",
}
HV_FIELD_DB_MAP = {
    "title": "title",
    "vendor": "vendor",
    "product_type": "product_type",
    "tags": "tags",
    "meta_title": "meta_title",
    "meta_description": "meta_description",
}


# ─────────────────────── INLINE EDIT API ─────────────────────────

def api_haravan_product_edit(haravan_id):
    """Inline edit 1 field SP Haravan: push API + update DB local."""
    data = request.get_json(force=True) or {}
    field = (data.get("field") or "").strip()
    value = data.get("value")
    if field not in HV_FIELD_API_MAP:
        return jsonify({"error": f"field không hợp lệ: {field}"}), 400
    api_field = HV_FIELD_API_MAP[field]
    db_field = HV_FIELD_DB_MAP[field]

    try:
        # SEO flat field: PUT qua /products/{id}.json — theme đọc field flat (KHÔNG đọc
        # từ /products/{id}/metafields.json dù endpoint đó cũng nhận data). Verified 15/5.
        hv_client.update_product(haravan_id, {api_field: value})
    except Exception as e:
        return jsonify({"error": f"Haravan API error: {e.__class__.__name__}: {str(e)[:200]}"}), 502

    conn = db.get_conn()
    conn.execute(
        f"UPDATE haravan_products SET {db_field}=?, last_synced=? WHERE haravan_id=?",
        (value, datetime.now().isoformat(timespec="seconds"), haravan_id),
    )
    conn.commit()
    conn.close()

    db.activity_log(
        kind="hv_edit", icon="✏️",
        title=f"Sửa SP Haravan: {field}",
        description=f"Value: {(value or '')[:80]}",
        href=url_for("haravan_product_detail", haravan_id=haravan_id),
    )
    return jsonify({"ok": True, "field": field, "value": value})


# 🗑️ 6/8/2026 — ĐÃ GỠ `haravan_blog_ai_rewrite` + `PRODUCT_TYPES_FOR_BLOG`
# + template `blog_writer.html`.
# Cả cụm chết hẳn từ khi form blog 1-shot bị thay bằng /content-jobs: mở trang thì
# 500 (template gọi endpoint `blog_writer_page` đã xoá), mà gửi form thì 405 (route
# chỉ nhận GET). Nút "✨ AI rewrite" ở haravan_blogs.html cũng gỡ theo.
# Muốn viết lại blog cũ: dùng /content-jobs.


# ─────────────────────── HARAVAN BLOGS PAGE ──────────────────────

def haravan_blogs():
    """Quản lý blog/news của sintech.vn — data từ seo_pages (đã crawl).

    Khi nào Haravan API blogs/articles fix lỗi 502, có thể swap source sang sync trực tiếp.
    """
    # limit 5000: trang này lọc/phân trang trong Python nên phải nạp đủ, cắt ở 500
    # là âm thầm giấu bớt bài khi kho blog vượt mốc đó (hiện 268).
    all_blogs = db.seo_list_pages(url_type="blog", limit=5000, sort="url")

    for b in all_blogs:
        b["topic"] = classify_blog_topic(b.get("title") or "")
        try:
            b["issue_count"] = len(json.loads(b.get("issues") or "[]"))
        except (ValueError, TypeError):
            b["issue_count"] = 0

    topic_counts = {}
    for b in all_blogs:
        topic_counts[b["topic"]] = topic_counts.get(b["topic"], 0) + 1
    topic_breakdown = []
    for code, label, color, _kw in BLOG_TOPICS:
        topic_breakdown.append({
            "code": code, "label": label, "color": color,
            "count": topic_counts.get(code, 0),
        })
    if topic_counts.get("other", 0):
        topic_breakdown.append({
            "code": "other", "label": "❓ Khác",
            "color": "rgba(120,120,140,0.15)",
            "count": topic_counts["other"],
        })

    f_topic = request.args.get("topic") or None
    f_band = request.args.get("band") or None
    f_search = (request.args.get("q") or "").strip().lower() or None
    f_sort = request.args.get("sort") or "score_asc"

    filtered = list(all_blogs)
    if f_topic:
        filtered = [b for b in filtered if b["topic"] == f_topic]
    # 4/9/2026: dùng chung db.score_band thay vì tự đặt 80/60. Ngưỡng cũ ở đây lệch
    # hẳn với dashboard (65/50) — đo trên 268 blog thì 131 bài (48,9%) bị hai trang
    # xếp hạng ngược nhau, cùng một cột điểm.
    if f_band in ("good", "ok", "bad"):
        filtered = [b for b in filtered if db.score_band(b.get("score")) == f_band]
    if f_search:
        filtered = [b for b in filtered if f_search in (b.get("title") or "").lower()
                    or f_search in (b.get("url") or "").lower()]

    sort_keys = {
        "score_asc":  lambda b: (b.get("score") or 0, -(b.get("id") or 0)),
        "score_desc": lambda b: (-(b.get("score") or 0), -(b.get("id") or 0)),
        "title":      lambda b: (b.get("title") or "").lower(),
        "wc_desc":    lambda b: -(b.get("word_count") or 0),
        "wc_asc":     lambda b: (b.get("word_count") or 0),
        "issues_desc": lambda b: -b["issue_count"],
        "recent":     lambda b: -(b.get("id") or 0),
    }
    filtered.sort(key=sort_keys.get(f_sort, sort_keys["score_asc"]))

    thr_good, thr_ok = db.score_thresholds()
    scores = [b.get("score") for b in all_blogs if b.get("score") is not None]
    stats = {
        "total": len(all_blogs),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "good": sum(1 for s in scores if db.score_band(s) == "good"),
        "ok":   sum(1 for s in scores if db.score_band(s) == "ok"),
        "bad":  sum(1 for s in scores if db.score_band(s) == "bad"),
    }

    try:
        page_num = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page_num = 1
    per_page = 50
    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page_items = filtered[(page_num - 1) * per_page : page_num * per_page]

    return render_template(
        "haravan_blogs.html",
        blogs=page_items, stats=stats,
        topic_breakdown=topic_breakdown,
        topic_labels=BLOG_TOPIC_LABELS,
        thr_good=thr_good, thr_ok=thr_ok,   # nhãn band hiện đúng ngưỡng đang hiệu lực
        filters={"topic": f_topic, "band": f_band, "q": f_search or "", "sort": f_sort},
        page_num=page_num, total_pages=total_pages, total=total, per_page=per_page,
        active="hv_blogs",
    )


# ─────────────────────── HARAVAN DASHBOARD + SYNC ────────────────

def haravan_dashboard():
    stats = db.hv_stats()
    state = hv_sync.sync_state()
    latest = db.hv_latest_sync()
    top_issues = db.hv_top_issues(limit=10)
    enriched_top = []
    for it in top_issues:
        icon, label, _fix = hv_sync.HV_ISSUE_LABELS.get(it["code"], ("⚪", it["code"], ""))
        enriched_top.append({**it, "icon": icon, "label": label})
    return render_template(
        "haravan.html",
        stats=stats, state=state, latest=latest, top_issues=enriched_top, active="hv_home",
    )


def haravan_sync_start():
    try:
        limit_pages = int(request.form.get("limit_pages") or 0) or None
    except (TypeError, ValueError):
        limit_pages = None
    started = hv_sync.start_sync_async(limit_pages=limit_pages)
    if started:
        flash(f"Đã bắt đầu sync Haravan {'(' + str(limit_pages) + ' page test)' if limit_pages else '(toàn bộ)'}.", "success")
    else:
        flash("Đang sync — chờ xong rồi sync tiếp.", "error")
    return redirect(url_for("haravan_dashboard"))


def haravan_sync_incremental_start():
    """Incremental sync — chỉ pull SP thay đổi/mới kể từ last_synced."""
    ok = hv_sync.start_sync_incremental_async()
    if ok:
        return jsonify({"ok": True, "message": "Incremental sync đã bắt đầu"})
    return jsonify({"ok": False, "message": "Đang sync — chờ xong"}), 409


def haravan_prune_stale():
    """Dọn SP 'chết' trong cache (đã xóa trên Haravan nhưng còn trong DB local)."""
    dry = (request.args.get("dry") or request.form.get("dry") or "").lower() in ("1", "true", "yes")
    try:
        res = hv_sync.prune_stale_products(dry_run=dry)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500
    msg = (f"Đã dọn {res['deleted']} SP chết" if not dry
           else f"(thử) Có {res['stale']} SP chết") + \
          f" · cache {res['cache_before']}→{res['cache_before'] - res['deleted']} · live {res['live']}"
    return jsonify({"ok": True, "message": msg, **res})


def haravan_sync_status_api():
    return jsonify(hv_sync.sync_state())


def haravan_status_api():
    return jsonify({
        "state": hv_sync.sync_state(),
        "stats": db.hv_stats(),
    })


# ─────────────────────── HARAVAN PRODUCTS PAGES ──────────────────

def haravan_products_page():
    filters = {
        "vendor": request.args.get("vendor") or None,
        "product_type": request.args.get("type") or None,
        "status": request.args.get("status") or None,
        "issue_code": request.args.get("issue") or None,
        "search": request.args.get("q") or None,
        "sort": request.args.get("sort") or "score_asc",
    }
    band = request.args.get("band")
    score_filter = {}
    if band == "good":
        score_filter = {"min_score": 80}
    elif band == "ok":
        score_filter = {"min_score": 60, "max_score": 79}
    elif band == "bad":
        score_filter = {"max_score": 59}

    # 4/9/2026: thêm try — /haravan/products?page=abc trả 500. Hai hàm anh em trong
    # cùng file (haravan_blogs dòng ~163, haravan_audit dòng ~314) đã bọc, riêng đây sót.
    try:
        page_num = max(1, int(request.args.get("page", 1) or 1))
    except (TypeError, ValueError):
        page_num = 1
    per_page = 50
    total = db.hv_count_products(**filters)
    total_pages = max(1, (total + per_page - 1) // per_page)
    products = db.hv_list_products(
        **filters, limit=per_page, offset=(page_num - 1) * per_page,
    )
    stats = db.hv_stats()
    top_issues = db.hv_top_issues(limit=12)
    enriched_top = []
    for it in top_issues:
        icon, label, _fix = hv_sync.HV_ISSUE_LABELS.get(it["code"], ("⚪", it["code"], ""))
        enriched_top.append({**it, "icon": icon, "label": label})
    return render_template(
        "haravan_products.html",
        products=products, stats=stats, top_issues=enriched_top,
        filters=filters, band=band,
        page_num=page_num, total_pages=total_pages, total=total, active="hv_products",
    )


def haravan_product_detail(haravan_id):
    p = db.hv_get_product(haravan_id)
    if not p:
        flash("Không tìm thấy sản phẩm trong DB. Sync lại có thể giúp.", "error")
        return redirect(url_for("haravan_products_page"))
    raw_issues = []
    if p.get("audit_issues"):
        try:
            raw_issues = json.loads(p["audit_issues"])
        except (ValueError, TypeError):
            raw_issues = []
    issues = [hv_sync.hv_enrich_issue(it) for it in raw_issues]
    images = []
    if p.get("images"):
        try:
            images = json.loads(p["images"])
        except (ValueError, TypeError):
            images = []
    return render_template(
        "haravan_product_detail.html",
        p=p, issues=issues, images=images,
    )


def haravan_audit_page():
    """Audit log — mọi thay đổi (PUT/POST/DELETE) đẩy lên Haravan."""
    only_fail = request.args.get("fail") == "1"
    try:
        page = max(1, int(request.args.get("page", 1) or 1))
    except ValueError:
        page = 1
    PAGE = 100
    rows = db.haravan_audit_list(limit=PAGE, offset=(page - 1) * PAGE, only_fail=only_fail)
    stats = db.haravan_audit_stats()
    return render_template("haravan_audit.html", rows=rows, stats=stats,
                           page=page, only_fail=only_fail, page_size=PAGE, active="hv_audit")


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 9 route Haravan — giữ nguyên endpoint name."""
    app.add_url_rule("/haravan/audit", "haravan_audit_page", haravan_audit_page)
    app.add_url_rule("/api/haravan/products/<int:haravan_id>/edit",
                     "api_haravan_product_edit", api_haravan_product_edit, methods=["POST"])
    app.add_url_rule("/haravan/blogs", "haravan_blogs", haravan_blogs)
    app.add_url_rule("/haravan", "haravan_dashboard", haravan_dashboard)
    app.add_url_rule("/haravan/sync", "haravan_sync_start", haravan_sync_start, methods=["POST"])
    app.add_url_rule("/api/haravan/sync-incremental/start",
                     "haravan_sync_incremental_start", haravan_sync_incremental_start, methods=["POST"])
    app.add_url_rule("/api/haravan/prune-stale", "haravan_prune_stale", haravan_prune_stale, methods=["POST"])
    app.add_url_rule("/api/haravan/sync/status", "haravan_sync_status_api", haravan_sync_status_api)
    app.add_url_rule("/api/haravan/status", "haravan_status_api", haravan_status_api)
    app.add_url_rule("/haravan/products", "haravan_products_page", haravan_products_page)
    app.add_url_rule("/haravan/products/<int:haravan_id>",
                     "haravan_product_detail", haravan_product_detail)
