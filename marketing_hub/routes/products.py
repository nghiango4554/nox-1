"""Routes: Products New + Blog Writer redirect — 6 endpoint.

/products/new flow:
  - GET  /products/new                — form
  - POST /products/new/preview        — parse tên SP → suggest tag/loại/hãng
  - POST /products/new/check-dup      — quét SP trùng trong catalog (DB local, read-only)
  - POST /products/new/resize-images  — DRY-RUN resize 600×338, trả base64 preview
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

import base64
import io
import re
import unicodedata
from datetime import datetime, timezone

from flask import render_template, request, jsonify, redirect, url_for

import product_parser as pp
import product_writer as pw
import codex_provider as cp
import haravan_client as hv_client
import db


# ─────────────────────── LEGACY REDIRECT ─────────────────────────

def blog_writer_redirect():
    return redirect(url_for("content_jobs_list_page"))


# ─────────────────────── QUÉT TRÙNG SP ───────────────────────────

# token loại SP / form-factor / marketing — KHÔNG phải mã model, bỏ khi so trùng
_DUP_STOP = {
    "vo", "case", "mainboard", "main", "bo", "mach", "chu", "card", "man", "hinh",
    "o", "cung", "ssd", "hdd", "ram", "cpu", "gpu", "vga", "nguon", "tan", "nhiet",
    "loa", "tai", "nghe", "chuot", "ban", "phim", "co", "fan", "laptop", "pc",
    "cho", "va", "gb", "tb", "atx", "matx", "itx", "mesh", "den", "trang", "wifi",
    "bluetooth", "rgb", "argb", "led", "new", "fullbox", "nobox", "chinh", "hang",
    "fv", "ddr4", "ddr5", "ddr3", "pcie", "nvme", "m2", "sata", "gaming", "pro",
    "of", "the", "x4", "x16", "gen", "usb", "type",
}
_SPEC_RE = re.compile(r"^\d+(gb|tb|hz|w|mm|cm|mhz|ghz|wh|mah|nm|bit|k|p|inch|in)$")


def _dup_features(name: str):
    """Tách tên SP thành (raw, core, codes, nums) để so trùng."""
    s = (name or "").lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    raw = set(re.findall(r"[a-z0-9]+", s))
    codes = set()
    # mã model nối bằng - . / : gm-03, b760m-k, srs-xv500, n5070wf3oc-12gd
    for m in re.findall(r"[a-z0-9]+(?:[-./][a-z0-9]+)+", s):
        codes.add(re.sub(r"[-./]", "", m))
    # token đơn lẫn chữ+số: b760m, xv500, c920, a620m
    for t in raw:
        if any(c.isdigit() for c in t) and any(c.isalpha() for c in t):
            codes.add(t)
    codes = {c for c in codes if c not in _DUP_STOP and not _SPEC_RE.match(c)}
    nums = {t for t in raw if t.isdigit() and len(t) >= 3}          # 5070, 990, 12700
    core = {t for t in raw if t not in _DUP_STOP and len(t) >= 2 and not _SPEC_RE.match(t)}
    return raw, core, codes, nums


def _scan_duplicates_cache(name: str):
    """Quét SP trùng/giống trong CACHE local. Trả (list_match, số_row_đã_quét)."""
    _, qcore, qcodes, qnums = _dup_features(name)
    try:
        conn = db.get_conn()
        rows = conn.execute(
            "SELECT haravan_id, title, handle, status FROM haravan_products "
            "WHERE title IS NOT NULL AND TRIM(title)!=''").fetchall()
        conn.close()
    except Exception:
        rows = []
    out = []
    for r in rows:
        traw, tcore, tcodes, tnums = _dup_features(r["title"])
        if not traw:
            continue
        code_hit = qcodes & tcodes
        num_hit = qnums & tnums
        core_hit = qcore & tcore
        # containment: % token lõi của query nằm trong SP (subset-aware, không phạt tên ngắn)
        contain = len(core_hit) / max(1, len(qcore))
        if not (code_hit or (num_hit and contain >= 0.6) or contain >= 0.85):
            continue
        out.append({
            "title": r["title"], "handle": r["handle"],
            "haravan_id": r["haravan_id"], "status": r["status"],
            "score": round(len(code_hit) * 2.0 + len(num_hit) * 0.6 + contain * 1.5, 2),
            "match": (sorted(code_hit) or sorted(num_hit | core_hit))[:4],
            "source": "cache",
        })
    out.sort(key=lambda x: -x["score"])
    return out, len(rows)


def _live_dup_by_handle(name: str):
    """#3: soi Haravan LIVE theo handle (slug tên mới). Bắt cả SP mà cache còn thiếu
    (cache stale/vừa prune) → dedup không bị lỗ. Handle trùng = dup chắc (score cao)."""
    try:
        slug = (pp.parse(name).get("slug") or "").strip()
        if not slug:
            return []
        data = hv_client._request("GET", "/products.json",
                                  params={"handle": slug, "limit": 5})
        prods = data.get("products", []) if isinstance(data, dict) else []
        return [{
            "title": p.get("title"), "handle": p.get("handle"),
            "haravan_id": p.get("id"),
            "status": ("live" if p.get("published_at") else "hidden"),
            "score": 99.0, "match": ["handle trùng (live)"], "source": "live",
        } for p in prods if p.get("id")]
    except Exception:
        return []


def _find_duplicates(name: str):
    """Gộp cache + live, dedup theo haravan_id (ưu tiên bản 'live'). Trả list sort score."""
    cache, _ = _scan_duplicates_cache(name)
    merged = {}
    for d in cache + _live_dup_by_handle(name):
        i = d.get("haravan_id")
        if i is None:
            continue
        if i not in merged or d.get("source") == "live":
            merged[i] = d
    return sorted(merged.values(), key=lambda x: -x.get("score", 0))


def products_new_check_dup():
    """Quét SP trùng/giống trong catalog (cache local + Haravan live theo handle)."""
    name = ((request.get_json(silent=True) or {}).get("name") or "").strip()
    if not name:
        return jsonify({"ok": True, "matches": []})
    cache, checked = _scan_duplicates_cache(name)
    live = _live_dup_by_handle(name)
    merged = {}
    for d in cache + live:
        i = d.get("haravan_id")
        if i is None:
            continue
        if i not in merged or d.get("source") == "live":
            merged[i] = d
    out = sorted(merged.values(), key=lambda x: -x.get("score", 0))
    return jsonify({"ok": True, "matches": out[:10], "checked": checked,
                    "live_hits": len(live)})


# ─────────────────────── ẢNH (resize + nhúng body) ───────────────

def _b64_to_bytes(data_url: str) -> bytes:
    s = data_url or ""
    if "," in s:
        s = s.split(",", 1)[1]
    return base64.b64decode(s)


def _resize_600x338(img_bytes: bytes) -> bytes:
    """600×338: ngang dài (ratio≥1.4) → cover; vuông/đứng → contain nền trắng."""
    from PIL import Image
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = im.size
    if w / h >= 1.4:
        r = max(600 / w, 338 / h)
        nw, nh = max(1, int(w * r)), max(1, int(h * r))
        im = im.resize((nw, nh), Image.LANCZOS)
        x, y = (nw - 600) // 2, (nh - 338) // 2
        im = im.crop((x, y, x + 600, y + 338))
    else:
        r = min(600 / w, 338 / h)
        nw, nh = max(1, int(w * r)), max(1, int(h * r))
        cv = Image.new("RGB", (600, 338), (255, 255, 255))
        cv.paste(im.resize((nw, nh), Image.LANCZOS), ((600 - nw) // 2, (338 - nh) // 2))
        im = cv
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def _grande(src: str) -> str:
    """URL ảnh carousel SP -> bản _grande (~600px Haravan tự resize, giữ tỉ lệ)."""
    return re.sub(r"(\.(?:jpg|jpeg|png|webp))(\?|$)", r"_grande\1\2", src, flags=re.I)


def _img_count_for_body(body_html: str) -> int:
    """#8: số ảnh chèn body bám số H2 — bài dài nhiều ảnh, linh kiện lặt vặt ít ảnh.
    ≤2 H2 → 1 · 3-4 → 2 · 5-6 → 3 · ≥7 → 4."""
    n = len(re.findall(r"<h2", body_html or "", re.I))
    if n <= 2:
        return 1
    if n <= 4:
        return 2
    if n <= 6:
        return 3
    return 4


def _embed_images(body_html: str, urls: list, alt: str) -> str:
    """Nhúng ảnh giàn đều trước các H2 (bỏ H2 đầu = intro). Số ảnh = len(urls)."""
    pos = [m.start() for m in re.finditer(r"<h2", body_html or "", re.I)]
    if not pos or not urls:
        return body_html
    slots = pos[1:] if len(pos) > 1 else pos   # ưu tiên chèn từ H2 thứ 2 (sau intro)
    k = min(len(urls), len(slots))
    if k <= 0:
        return body_html
    if k == len(slots):
        chosen = slots
    elif k == 1:
        chosen = [slots[0]]
    else:
        step = (len(slots) - 1) / (k - 1)
        chosen = [slots[round(i * step)] for i in range(k)]

    def tag(u):
        return (f'<img src="{u}" alt="{alt}" style="display:block;max-width:600px;'
                f'width:100%;height:auto;margin:14px auto;border-radius:6px;">')

    ins = list(zip(chosen, urls[:k]))
    b = body_html
    for off, u in sorted(ins, key=lambda x: -x[0]):
        b = b[:off] + tag(u) + b[off:]
    return b


def products_new_resize_images():
    """DRY-RUN: nhận base64 ảnh gốc → resize 600×338 → trả base64 preview. KHÔNG up Haravan."""
    imgs = (request.get_json(silent=True) or {}).get("images") or []
    out = []
    for d in imgs[:12]:
        try:
            out.append("data:image/jpeg;base64,"
                       + base64.b64encode(_resize_600x338(_b64_to_bytes(d))).decode("ascii"))
        except Exception:
            out.append(None)
    return jsonify({"ok": True, "resized": out, "count": sum(1 for x in out if x)})


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

    # #2/#3: chặn trùng ở SERVER (không chỉ tin frontend). Match mạnh (handle live
    # trùng, hoặc score cache cao) → chặn, trừ khi user tick "vẫn tạo" (force_create).
    if not body.get("force_create"):
        dups = _find_duplicates(name)
        strong = [d for d in dups if d.get("source") == "live" or d.get("score", 0) >= 3.0]
        if strong:
            return jsonify({
                "ok": False, "error": "duplicate", "need_force": True,
                "message": "Có SP trùng/rất giống trong catalog. Tick 'Vẫn tạo' nếu chắc chắn tạo mới.",
                "duplicates": strong[:5],
            }), 409

    tags_list = []
    if warranty and str(warranty).isdigit() and 1 <= int(warranty) <= 120:
        # tag bảo hành chuẩn catalog = "bh_NN tháng" (DẤU CÁCH, không gạch dưới) —
        # smart collection/bộ lọc khớp format này; "bh_NN_tháng" bị bỏ sót.
        tags_list.append(f"bh_{int(warranty):02d} tháng")
    tags_list.extend(parsed.get("tags") or [])

    variant_title = f"Bảo hành {int(warranty)} tháng" if warranty and str(warranty).isdigit() else "Mặc định"
    variant = {
        "option1": variant_title,
        "requires_shipping": True,       # SP vật lý — bật ship
        "taxable": True,
        "inventory_management": "haravan",
        "inventory_policy": "continue",  # cho bán tiếp khi hết tồn (khớp catalog live)
    }
    # #4: bóc số từ ô tồn kho ("25 cái" → 25). Qty set được (test 17/7 SP ẩn: dính 25).
    stock_digits = re.sub(r"[^\d]", "", stock)
    if stock_digits:
        variant["inventory_quantity"] = int(stock_digits)
    price_val = None
    if price is not None and str(price).replace(".", "").strip().isdigit():
        price_val = float(price)
        variant["price"] = price_val
    # #6: giá so sánh — có thì dùng, KHÔNG để trống → mặc định = giá nhập
    if compare_price is not None and str(compare_price).replace(".", "").strip().isdigit():
        variant["compare_at_price"] = float(compare_price)
    elif price_val is not None:
        variant["compare_at_price"] = price_val

    product_fields = {
        "title": name,
        "body_html": body_html,
        "vendor": parsed.get("hang") or "",
        "product_type": parsed.get("loai") or "",
        "tags": ", ".join(tags_list),
        "published": False,  # #7: tạo ẨN trước, publish ở CUỐI khi build xong (tránh SP live dở)
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

        # ─── ẢNH: gốc → carousel SP; nhúng URL carousel (_grande) vào body ───
        # KHÔNG dùng theme asset cho ảnh body: Haravan dọn/mangle URL asset → ảnh chết
        # (bug 30/6). URL carousel SP luôn tồn tại, _grande để Haravan tự resize ~600px.
        img_report = {"carousel": 0, "embedded": 0}
        images = body.get("images") or []
        if images:
            slug = (created.get("handle") or str(product_id))[:42]
            for i, d in enumerate(images[:12]):
                try:
                    raw = _b64_to_bytes(d)
                    with hv_client.allow_blocked_operations("ui_form:/products/new"):
                        hv_client.add_product_image(
                            product_id, base64.b64encode(raw).decode("ascii"),
                            filename=f"{slug}-{i + 1}.jpg", alt=name)
                    img_report["carousel"] += 1
                except Exception as e:
                    errors.append(f"carousel ảnh {i + 1}: {e}")
            try:
                with hv_client.allow_blocked_operations("ui_form:/products/new"):
                    fresh = hv_client.get_product(product_id)
                car = sorted(fresh.get("images") or [], key=lambda x: x.get("position") or 0)
                want = _img_count_for_body(body_html)  # #8: số ảnh body bám số H2
                urls = [_grande(im["src"]) for im in car if im.get("src")][:want]
                if urls:
                    new_body = _embed_images(body_html, urls, name)
                    with hv_client.allow_blocked_operations("ui_form:/products/new"):
                        hv_client.update_product(product_id, {"body_html": new_body})
                    body_html = new_body
                    img_report["embedded"] = len(urls)
            except Exception as e:
                errors.append(f"nhúng ảnh body: {e}")

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

        # #7: PUBLISH ở CUỐI — chỉ khi body đã lưu OK (có content + H2). Lỗi giữa
        # chừng → SP GIỮ ẨN chờ vợ kiểm, không để 1 SP live dở dang.
        published_live = False
        body_ok = bool(body_check.get("stored_length")) and body_check.get("has_h2")
        if body_ok:
            try:
                with hv_client.allow_blocked_operations("ui_form:/products/new"):
                    hv_client.update_product(
                        product_id, {"id": product_id, "published": True, "published_scope": "web"})
                published_live = True
            except Exception as e:
                errors.append(f"publish fail (SP giữ ẩn): {e}")
        else:
            errors.append("Body chưa lưu đúng → SP GIỮ ẨN, kiểm tra rồi publish tay")

        handle = created.get("handle") or parsed.get("slug") or ""
        status_msg = ("✅ Đã tạo + publish LIVE" if published_live
                      else "⚠️ SP tạo ở trạng thái ẨN (có lỗi/body chưa đạt) — kiểm rồi publish tay")
        return jsonify({
            "ok": True,
            "product_id": product_id,
            "handle": handle,
            "published_live": published_live,
            "status_msg": status_msg,
            "admin_url": f"https://admin.haravan.com/admin/products/{product_id}",
            "live_url": (f"https://sintech.vn/products/{handle}" if (handle and published_live) else None),
            "body_check": body_check,
            "seo_check": seo_check,
            "img_report": img_report,
            "errors": errors,
        })
    except hv_client.HaravanError as e:
        return jsonify({"ok": False, "error": f"Haravan: {e}", "errors": errors}), 502
    except Exception as e:
        return jsonify({"ok": False, "error": f"Unexpected: {e}", "errors": errors}), 500


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 8 route Products + legacy redirect."""
    app.add_url_rule("/blog-writer", "blog_writer_redirect", blog_writer_redirect)
    app.add_url_rule("/products/new", "products_new_form", products_new_form)
    app.add_url_rule("/products/new/preview",
                     "products_new_preview", products_new_preview, methods=["POST"])
    app.add_url_rule("/products/new/check-dup",
                     "products_new_check_dup", products_new_check_dup, methods=["POST"])
    app.add_url_rule("/products/new/resize-images",
                     "products_new_resize_images", products_new_resize_images, methods=["POST"])
    app.add_url_rule("/products/new/organize-spec",
                     "products_new_organize_spec", products_new_organize_spec, methods=["POST"])
    app.add_url_rule("/products/new/generate",
                     "products_new_generate", products_new_generate, methods=["POST"])
    app.add_url_rule("/products/new/create",
                     "products_new_create", products_new_create, methods=["POST"])
