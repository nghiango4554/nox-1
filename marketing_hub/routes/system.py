"""Routes: System level — Competitors + Canva + Global search.

8 endpoint hoàn toàn độc lập, không đụng background state hay job worker.
Đăng ký vào app qua `register(app)` (manual add_url_rule pattern để
giữ nguyên endpoint name → KHÔNG vỡ 12+ chỗ url_for ở templates).
"""

import secrets

from flask import (
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    session,
)

import db
import competitors as competitors_mod

from routes.blog_topics import classify_blog_topic, BLOG_TOPIC_LABELS


# ─────────────────────── GLOBAL SEARCH ──────────────────────

def api_global_search():
    """Fuzzy search trên posts + Haravan products + SEO pages + competitors."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    limit_each = 5
    like = f"%{q}%"
    results = []
    conn = db.get_conn()

    # Posts
    rows = conn.execute(
        "SELECT id, code, caption, scheduled_date FROM posts "
        "WHERE code LIKE ? OR caption LIKE ? ORDER BY id DESC LIMIT ?",
        (like, like, limit_each),
    ).fetchall()
    for r in rows:
        results.append({
            "kind": "post", "icon": "📝",
            "title": (r["code"] or f"Post #{r['id']}"),
            "snippet": (r["caption"] or "")[:80],
            "href": url_for("post_detail", post_id=r["id"]),
            "tag": r["scheduled_date"] or "",
        })

    # Haravan products
    rows = conn.execute(
        "SELECT haravan_id, title, handle, vendor, audit_score FROM haravan_products "
        "WHERE title LIKE ? OR handle LIKE ? OR vendor LIKE ? "
        "ORDER BY audit_score ASC LIMIT ?",
        (like, like, like, limit_each),
    ).fetchall()
    for r in rows:
        results.append({
            "kind": "haravan", "icon": "🛒",
            "title": r["title"] or "(no title)",
            "snippet": f"{r['vendor'] or ''} · /{r['handle']}",
            "href": url_for("haravan_product_detail", haravan_id=r["haravan_id"]),
            "tag": f"score {r['audit_score']}" if r["audit_score"] is not None else "",
        })

    # SEO pages (chỉ match URL/title nhanh)
    rows = conn.execute(
        "SELECT id, url, title, url_type, score FROM seo_pages "
        "WHERE title LIKE ? OR url LIKE ? "
        "ORDER BY score ASC LIMIT ?",
        (like, like, limit_each),
    ).fetchall()
    for r in rows:
        results.append({
            "kind": "seo", "icon": "🔍",
            "title": r["title"] or r["url"],
            "snippet": r["url"],
            "href": url_for("seo_url_detail", page_id=r["id"]),
            "tag": f"{r['url_type'] or ''} · {r['score']}đ" if r["score"] is not None else (r["url_type"] or ""),
        })

    # Competitors
    rows = conn.execute(
        "SELECT id, competitor, url, title FROM competitor_urls "
        "WHERE title LIKE ? OR url LIKE ? LIMIT ?",
        (like, like, limit_each),
    ).fetchall()
    for r in rows:
        results.append({
            "kind": "competitor", "icon": "🥷",
            "title": r["title"] or "(no title)",
            "snippet": r["url"],
            "href": r["url"],
            "tag": r["competitor"],
        })

    conn.close()
    return jsonify({"results": results, "total": len(results)})


# ─────────────────────── COMPETITORS ────────────────────────

def competitors_page():
    stats = db.competitor_stats()
    state = competitors_mod.state_snapshot()
    topic_gap = db.competitor_topic_gap(min_competitor_count=3)

    # Cross-reference với Sintech (seo_pages) để tính gap thật
    sintech_topic_count = {}
    sintech_blogs = db.seo_list_pages(url_type="blog", limit=1000, sort="url")
    for b in sintech_blogs:
        topic = classify_blog_topic(b.get("title") or "")
        sintech_topic_count[topic] = sintech_topic_count.get(topic, 0) + 1

    for it in topic_gap:
        it["sintech_count"] = sintech_topic_count.get(it["topic"], 0)
        it["gap"] = it["competitor_count"] - it["sintech_count"]
        label, color = BLOG_TOPIC_LABELS.get(it["topic"], (it["topic"], "rgba(120,120,140,0.15)"))
        it["label"] = label
        it["color"] = color

    # Filter & paginate URL list
    f_competitor = request.args.get("competitor") or None
    f_topic = request.args.get("topic") or None
    f_search = (request.args.get("q") or "").strip() or None
    f_sort = request.args.get("sort") or "recent"
    try:
        page_num = max(1, int(request.args.get("page") or 1))
    except (TypeError, ValueError):
        page_num = 1
    per_page = 50

    filters = dict(competitor=f_competitor, topic=f_topic, search=f_search)
    total = db.competitor_count(**filters)
    total_pages = max(1, (total + per_page - 1) // per_page)
    items = db.competitor_list(
        **filters, sort=f_sort,
        limit=per_page, offset=(page_num - 1) * per_page,
    )

    return render_template(
        "competitors.html",
        stats=stats, state=state,
        topic_gap=topic_gap,
        items=items,
        competitors_meta=competitors_mod.COMPETITORS,
        topic_labels=BLOG_TOPIC_LABELS,
        filters={"competitor": f_competitor, "topic": f_topic,
                 "q": f_search or "", "sort": f_sort},
        page_num=page_num, total_pages=total_pages, total=total,
        per_page=per_page, active="competitors",
    )


def competitors_crawl():
    started = competitors_mod.start_crawl_all_async()
    if started:
        flash("Đã bắt đầu crawl 4 đối thủ. Có thể mất 1-3 phút.", "success")
    else:
        flash("Đang crawl — chờ xong rồi crawl tiếp.", "error")
    return redirect(url_for("competitors_page"))


def api_competitors_status():
    return jsonify({
        "state": competitors_mod.state_snapshot(),
        "stats": db.competitor_stats(),
    })


# ─────────────────────── CANVA ──────────────────────────────

def canva_status_page():
    import canva_client
    connected = canva_client.is_connected()
    profile = None
    templates = []
    err = None
    if connected:
        try:
            profile = canva_client.get_user_profile().get("profile", {})
            templates = canva_client.list_brand_templates(limit=50)
        except Exception as e:
            err = str(e)[:300]
    return render_template("canva.html",
                           connected=connected,
                           profile=profile,
                           templates=templates,
                           err=err)


def canva_connect():
    import canva_client
    state = secrets.token_urlsafe(24)
    auth_url, verifier = canva_client.build_auth_url(state)
    session["canva_oauth_state"] = state
    session["canva_code_verifier"] = verifier
    return redirect(auth_url)


def canva_callback():
    import canva_client
    code = request.args.get("code")
    state = request.args.get("state")
    err = request.args.get("error")
    if err:
        flash(f"Canva OAuth lỗi: {err} ({request.args.get('error_description','')})", "error")
        return redirect(url_for("canva_status_page"))
    if not code or state != session.get("canva_oauth_state"):
        flash("Canva OAuth state không khớp (CSRF guard). Bấm Connect lại.", "error")
        return redirect(url_for("canva_status_page"))
    verifier = session.pop("canva_code_verifier", None)
    session.pop("canva_oauth_state", None)
    if not verifier:
        flash("Mất code_verifier (session expired). Connect lại.", "error")
        return redirect(url_for("canva_status_page"))
    try:
        canva_client.exchange_code(code, verifier)
        flash("✅ Kết nối Canva thành công!", "success")
    except Exception as e:
        flash(f"❌ Exchange token lỗi: {str(e)[:300]}", "error")
    return redirect(url_for("canva_status_page"))


def canva_disconnect():
    import canva_client
    canva_client.clear_tokens()
    flash("Đã ngắt kết nối Canva.", "success")
    return redirect(url_for("canva_status_page"))


# ─────────────────────── REGISTRATION ───────────────────────

def register(app):
    """Đăng ký 8 route vào Flask app — giữ nguyên endpoint name (không Blueprint prefix)."""
    app.add_url_rule("/api/search", "api_global_search", api_global_search)
    app.add_url_rule("/competitors", "competitors_page", competitors_page)
    app.add_url_rule("/competitors/crawl", "competitors_crawl", competitors_crawl, methods=["POST"])
    app.add_url_rule("/api/competitors/status", "api_competitors_status", api_competitors_status)
    app.add_url_rule("/canva", "canva_status_page", canva_status_page)
    app.add_url_rule("/canva/connect", "canva_connect", canva_connect)
    app.add_url_rule("/canva/callback", "canva_callback", canva_callback)
    app.add_url_rule("/canva/disconnect", "canva_disconnect", canva_disconnect, methods=["POST"])
