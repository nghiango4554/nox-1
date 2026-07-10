"""Routes: Products New + Blog Writer redirect — 6 endpoint.

/products/new flow (5 phase):
  - GET  /products/new                — form
  - POST /products/new/preview        — parse tên SP → suggest tag/loại/hãng
  - POST /products/new/organize-spec  — clean spec_raw qua Codex (Phase 5)
  - POST /products/new/generate       — gen body_html + excerpt + SEO meta
  - POST /products/new/create         — POST Haravan tạo SP thật (lift permission gate)

Legacy redirect:
  - GET  /blog-writer                 → /content-jobs (form 1-shot cũ đã xóa)

⚠️ /products/new/create là endpoint DUY NHẤT dùng `allow_blocked_operations` —
explicit UI flow tạo SP mới (default gate cấm POST products.json).

Dep:
- product_parser as pp, product_writer as pw, codex_provider as cp
- haravan_client (create_product, update_product [flat-field SEO], get_product)
"""

from datetime import datetime, timezone

from flask import render_template, request, jsonify, redirect, url_for

import product_parser as pp
import product_writer as pw
import codex_provider as cp
import haravan_client as hv_client


# ─────────────────────── LEGACY REDIRECT ─────────────────────────

def blog_writer_redirect():
    return redirect(url_for("content_jobs_list_page"))


# ─────────────────────── /products/new FLOW ──────────────────────

def products_new_form():
    return render_template("products_new.html")


def products_new_preview():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    warranty = (body.get("warranty_months") or "").strip()

    parsed = pp.parse(name)

    all_tags = []
    if warranty and warranty.isdigit() and 1 <= int(warranty) <= 120:
        all_tags.append(f"bh_{int(warranty):02d}_tháng")
    all_tags.extend(parsed.get("tags") or [])

    return jsonify({
        **parsed,
        "all_tags": all_tags,
        "warranty_months": warranty,
        "price": body.get("price"),
        "compare_price": body.get("compare_price"),
        "stock": body.get("stock"),
    })


def products_new_organize_spec():
    """Phase 5 — clean up + structure spec_raw qua Codex."""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    spec_raw = (body.get("spec_raw") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Thiếu tên SP"}), 400
    if not spec_raw:
        return jsonify({"ok": False, "error": "Spec_raw rỗng — paste spec trước"}), 400

    parsed = pp.parse(name)
    if not parsed.get("loai"):
        return jsonify({"ok": False, "error": parsed.get("note") or "Tên SP không hợp lệ"}), 400

    try:
        organized = pw.organize_spec(name=name, parsed=parsed, spec_raw=spec_raw)
        return jsonify({"ok": True, **organized})
    except cp.CodexRateLimitError as e:
        return jsonify({"ok": False, "error": f"Codex quota hết. ({e})"}), 503
    except Exception as e:
        return jsonify({"ok": False, "error": f"Organize fail: {e}"}), 500


def products_new_generate():
    """Phase 2 — gen body_html + excerpt + SEO title + SEO meta."""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Thiếu tên SP"}), 400
    parsed = pp.parse(name)
    if not parsed.get("loai"):
        return jsonify({"ok": False, "error": parsed.get("note") or "Tên SP không hợp lệ"}), 400

    organized_spec = body.get("organized_spec")
    if isinstance(organized_spec, dict) and not any(organized_spec.get(k) for k in ("spec_table", "key_features", "use_cases", "compatibility_notes")):
        organized_spec = None

    try:
        gen = pw.generate(
            name=name,
            parsed=parsed,
            price=(body.get("price") or "").strip(),
            warranty_months=(body.get("warranty_months") or "").strip(),
            organized_spec=organized_spec,
            prev_angle=(body.get("prev_angle") or None),
        )
        return jsonify({"ok": True, **gen})
    except cp.CodexRateLimitError as e:
        return jsonify({"ok": False, "error": f"Codex quota hết — đợi reset rồi thử lại. ({e})"}), 503
    except Exception as e:
        return jsonify({"ok": False, "error": f"Gen fail: {e}"}), 500


def products_new_create():
    """Phase 3 — POST Haravan tạo SP thật. Lift permission gate cho route này."""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Thiếu tên SP"}), 400

    parsed = pp.parse(name)
    if not parsed.get("loai"):
        return jsonify({"ok": False, "error": parsed.get("note") or "Tên SP không hợp lệ"}), 400

    warranty = (body.get("warranty_months") or "").strip()
    price = body.get("price")
    compare_price = body.get("compare_price")
    stock = str(body.get("stock") or "").strip()
    body_html = (body.get("body_html") or "").strip()
    excerpt = (body.get("excerpt") or "").strip()
    seo_title = (body.get("seo_title") or "").strip()
    seo_meta = (body.get("seo_meta") or "").strip()

    if not body_html:
        return jsonify({"ok": False, "error": "Body HTML rỗng — chạy AI gen trước"}), 400

    tags_list = []
    if warranty and str(warranty).isdigit() and 1 <= int(warranty) <= 120:
        tags_list.append(f"bh_{int(warranty):02d}_tháng")
    tags_list.extend(parsed.get("tags") or [])

    variant_title = f"Bảo hành {int(warranty)} tháng" if warranty and str(warranty).isdigit() else "Mặc định"
    variant = {
        "option1": variant_title,
        "requires_shipping": True,       # SP vật lý — bật ship
        "taxable": True,
        "inventory_management": "haravan",
        "inventory_policy": "continue",  # cho bán tiếp khi hết tồn (khớp catalog live)
    }
    if stock.isdigit():
        variant["inventory_quantity"] = int(stock)
    if price and str(price).replace(".", "").isdigit():
        variant["price"] = float(price)
    if compare_price and str(compare_price).replace(".", "").isdigit():
        variant["compare_at_price"] = float(compare_price)

    product_fields = {
        "title": name,
        "body_html": body_html,
        "vendor": parsed.get("hang") or "",
        "product_type": parsed.get("loai") or "",
        "tags": ", ".join(tags_list),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "published_scope": "web",  # chỉ lên web store, KHÔNG tick Haravan POS (vợ dặn 23/6)
        "summary_html": excerpt,
        "options": [{"name": "Bảo hành", "values": [variant_title]}],
        "variants": [variant],
    }

    errors = []

    try:
        with hv_client.allow_blocked_operations("ui_form:/products/new"):
            created = hv_client.create_product(product_fields)
        product_id = created.get("id")
        if not product_id:
            return jsonify({"ok": False, "error": "Tạo SP OK nhưng không có id trả về", "raw": created}), 500

        # SEO title/meta — theme Sintech CHỈ đọc flat-field metafields_global_*
        # set qua PUT product. /metafields endpoint theme KHÔNG đọc (chỉ tạo
        # metafield rác), nên bỏ hẳn. Verify bằng <title> trang live.
        seo_sent = {"title": None, "description": None}
        if seo_title or seo_meta:
            flat = {"id": product_id}
            if seo_title:
                flat["metafields_global_title_tag"] = seo_title
                seo_sent["title"] = seo_title
            if seo_meta:
                flat["metafields_global_description_tag"] = seo_meta
                seo_sent["description"] = seo_meta
            try:
                with hv_client.allow_blocked_operations("ui_form:/products/new"):
                    hv_client.update_product(product_id, flat)
            except Exception as e:
                errors.append(f"flat SEO PUT fail: {e}")

        body_check = {}
        try:
            with hv_client.allow_blocked_operations("ui_form:/products/new"):
                verified = hv_client.get_product(product_id)
            stored_body = verified.get("body_html") or ""
            body_check = {
                "stored_length": len(stored_body),
                "sent_length": len(body_html),
                "has_h2": "<h2" in stored_body,
                "has_h3": "<h3" in stored_body,
                "has_table": "<table" in stored_body,
                "has_ul": "<ul" in stored_body,
                "has_link": "<a " in stored_body,
                "first_200": stored_body[:200],
                "haravan_published_at": verified.get("published_at"),
            }
        except Exception as e:
            errors.append(f"verify body fail: {e}")

        seo_check = {
            "title_sent": seo_sent.get("title"),
            "description_sent": (seo_sent.get("description") or "")[:160] or None,
            "note": "SEO set qua flat-field metafields_global_* (PUT product). Verify <title> trang live sau ~vài phút CDN.",
        }

        handle = created.get("handle") or parsed.get("slug") or ""
        return jsonify({
            "ok": True,
            "product_id": product_id,
            "handle": handle,
            "admin_url": f"https://admin.haravan.com/admin/products/{product_id}",
            "live_url": f"https://sintech.vn/products/{handle}" if handle else None,
            "body_check": body_check,
            "seo_check": seo_check,
            "errors": errors,
        })
    except hv_client.HaravanError as e:
        return jsonify({"ok": False, "error": f"Haravan: {e}", "errors": errors}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": f"Unexpected: {e}", "errors": errors}), 500


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 6 route Products + legacy redirect."""
    app.add_url_rule("/blog-writer", "blog_writer_redirect", blog_writer_redirect)
    app.add_url_rule("/products/new", "products_new_form", products_new_form)
    app.add_url_rule("/products/new/preview",
                     "products_new_preview", products_new_preview, methods=["POST"])
    app.add_url_rule("/products/new/organize-spec",
                     "products_new_organize_spec", products_new_organize_spec, methods=["POST"])
    app.add_url_rule("/products/new/generate",
                     "products_new_generate", products_new_generate, methods=["POST"])
    app.add_url_rule("/products/new/create",
                     "products_new_create", products_new_create, methods=["POST"])
