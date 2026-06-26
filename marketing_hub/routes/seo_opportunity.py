"""Routes: SEO Opportunity + SERP Brief Engine.

Trang:
  /seo/opportunities  — Keyword Opportunity table (import CSV + sync GSC + scoring)
  /seo/serp-briefs    — SERP Brief Builder (manual URLs, provider-ready stub)

AN TOÀN: KHÔNG publish, KHÔNG PUT Haravan, KHÔNG gọi API SERP trả phí.
"send to blog" chỉ đánh dấu trạng thái (draft/queue), KHÔNG tạo content job live.
"""
import io

from flask import render_template, request, jsonify, Response

import seo_opportunity as opp


# ───────────── pages ─────────────

def seo_opportunities_page():
    opp.ensure_schema()
    return render_template(
        "seo_opportunities.html",
        active="opp",
        page_types=opp.PAGE_TYPES,
        statuses=opp.STATUSES,
        intents=opp.INTENTS,
        stats=opp.keyword_stats(),
    )


def seo_serp_briefs_page():
    opp.ensure_schema()
    return render_template(
        "seo_serp_briefs.html",
        active="serp",
        briefs=opp.list_briefs(limit=100),
    )


# ───────────── keyword opportunity API ─────────────

def api_opp_list():
    args = request.args
    rows = opp.list_keywords(
        source=args.get("source") or None,
        intent=args.get("intent") or None,
        status=args.get("status") or None,
        priority=args.get("priority") or None,
        page_type=args.get("page_type") or None,
        q=args.get("q") or None,
        sort=args.get("sort") or "score",
        limit=int(args.get("limit") or 500),
    )
    return jsonify({"ok": True, "rows": rows, "count": len(rows)})


def api_opp_import_csv():
    """Import CSV: multipart file 'file' HOẶC field 'text' (paste)."""
    source = (request.form.get("source") or request.args.get("source") or "csv").strip()
    country = (request.form.get("country") or opp.DEFAULT_COUNTRY).strip()
    language = (request.form.get("language") or opp.DEFAULT_LANGUAGE).strip()
    text = ""
    filename = ""
    f = request.files.get("file")
    if f and f.filename:
        filename = f.filename
        raw = f.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")
    else:
        text = request.form.get("text") or ""
    if not text.strip():
        return jsonify({"ok": False, "error": "Chưa có nội dung CSV (file hoặc text)"}), 400
    res = opp.import_csv(text, source=source, filename=filename, country=country, language=language)
    code = 200 if res.get("ok") else 400
    return jsonify(res), code


def api_opp_sync_gsc():
    days = int(request.form.get("days") or request.args.get("days") or 90)
    min_imp = int(request.form.get("min_impressions") or 30)
    res = opp.sync_from_gsc(days=days, min_impressions=min_imp)
    code = 200 if res.get("ok") else 400
    return jsonify(res), code


def api_opp_update(kid):
    payload = request.get_json(silent=True) or request.form
    fields = {k: payload.get(k) for k in
              ("status", "priority", "suggested_page_type", "topic_cluster", "notes", "intent")
              if payload.get(k) is not None}
    ok = opp.update_keyword_fields(int(kid), **fields)
    return jsonify({"ok": ok})


def api_opp_score_detail(kid):
    """Trả breakdown score để giải thích (transparent)."""
    row = opp.get_keyword(int(kid))
    if not row:
        return jsonify({"ok": False, "error": "not found"}), 404
    score, bd = opp.compute_score(row)
    return jsonify({"ok": True, "score": score, "breakdown": bd})


def api_opp_send_to_blog(kid):
    """SAFE: chỉ đánh dấu keyword 'approved' + note — KHÔNG tạo content job live,
    KHÔNG publish. Người vận hành tự kéo sang /blog-content khi muốn viết thật."""
    row = opp.get_keyword(int(kid))
    if not row:
        return jsonify({"ok": False, "error": "not found"}), 404
    note = (row.get("notes") or "")
    if "→ blog queue" not in note:
        note = (note + " | → blog queue (draft)").strip(" |")
    opp.update_keyword_fields(int(kid), status="approved", notes=note)
    return jsonify({"ok": True, "message": "Đã đánh dấu approved + queue draft (chưa tạo bài live)"})


def api_opp_export():
    csv_text = opp.export_keywords_csv()
    return Response(csv_text, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=seo_keyword_opportunities.csv"})


# ───────────── SERP brief API ─────────────

def api_brief_create():
    """Mode A — Manual URLs. payload: keyword, urls (list hoặc text nhiều dòng), keyword_id?"""
    payload = request.get_json(silent=True) or request.form
    keyword = (payload.get("keyword") or "").strip()
    kid = payload.get("keyword_id")
    raw_urls = payload.get("urls")
    if isinstance(raw_urls, str):
        urls = [u.strip() for u in raw_urls.replace(",", "\n").splitlines() if u.strip()]
    elif isinstance(raw_urls, list):
        urls = [str(u).strip() for u in raw_urls if str(u).strip()]
    else:
        urls = []
    if not keyword:
        return jsonify({"ok": False, "error": "Thiếu keyword"}), 400
    if not urls:
        return jsonify({"ok": False, "error": "Cần ít nhất 1 URL top SERP (tối đa 5)"}), 400
    res = opp.analyze_serp(keyword, urls, source_mode="manual",
                           keyword_id=int(kid) if kid else None)
    code = 200 if res.get("ok") else 400
    return jsonify(res), code


def api_brief_provider():
    """Mode B — Provider-ready stub. CHƯA có credential → từ chối, KHÔNG gọi API trả phí."""
    return jsonify({
        "ok": False,
        "provider_ready": False,
        "error": "API key required — DataForSEO/SerpAPI chưa cấu hình & chưa được duyệt. "
                 "Dùng Mode A (nhập URL thủ công).",
    }), 400


def api_brief_get(bid):
    b = opp.get_brief(int(bid))
    if not b:
        return jsonify({"ok": False, "error": "not found"}), 404
    return jsonify({"ok": True, "brief": b})


def api_brief_list():
    return jsonify({"ok": True, "briefs": opp.list_briefs(limit=int(request.args.get("limit") or 100))})


def api_brief_ai(bid):
    res = opp.ai_enhance_brief(int(bid))
    code = 200 if res.get("ok") else 400
    return jsonify(res), code


def api_brief_export(bid):
    md = opp.brief_to_markdown(int(bid))
    return Response(md, mimetype="text/markdown",
                    headers={"Content-Disposition": f"attachment; filename=content_brief_{bid}.md"})


# ───────────── register ─────────────

def register(app):
    app.add_url_rule("/seo/opportunities", "seo_opportunities_page", seo_opportunities_page)
    app.add_url_rule("/seo/serp-briefs", "seo_serp_briefs_page", seo_serp_briefs_page)

    app.add_url_rule("/api/seo/opportunities", "api_opp_list", api_opp_list)
    app.add_url_rule("/api/seo/opportunities/import-csv", "api_opp_import_csv",
                     api_opp_import_csv, methods=["POST"])
    app.add_url_rule("/api/seo/opportunities/sync-gsc", "api_opp_sync_gsc",
                     api_opp_sync_gsc, methods=["POST"])
    app.add_url_rule("/api/seo/opportunities/<int:kid>/update", "api_opp_update",
                     api_opp_update, methods=["POST"])
    app.add_url_rule("/api/seo/opportunities/<int:kid>/score", "api_opp_score_detail",
                     api_opp_score_detail)
    app.add_url_rule("/api/seo/opportunities/<int:kid>/send-to-blog", "api_opp_send_to_blog",
                     api_opp_send_to_blog, methods=["POST"])
    app.add_url_rule("/api/seo/opportunities/export.csv", "api_opp_export", api_opp_export)

    app.add_url_rule("/api/seo/serp-briefs", "api_brief_list", api_brief_list)
    app.add_url_rule("/api/seo/serp-briefs/create", "api_brief_create",
                     api_brief_create, methods=["POST"])
    app.add_url_rule("/api/seo/serp-briefs/provider", "api_brief_provider",
                     api_brief_provider, methods=["POST"])
    app.add_url_rule("/api/seo/serp-briefs/<int:bid>", "api_brief_get", api_brief_get)
    app.add_url_rule("/api/seo/serp-briefs/<int:bid>/ai-enhance", "api_brief_ai",
                     api_brief_ai, methods=["POST"])
    app.add_url_rule("/api/seo/serp-briefs/<int:bid>/export.md", "api_brief_export",
                     api_brief_export)
