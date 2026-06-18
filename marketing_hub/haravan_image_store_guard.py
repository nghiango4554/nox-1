# -*- coding: utf-8 -*-
"""Haravan image upload — STORE GUARD + ROUTING BY USAGE CONTEXT.

Nguyên tắc: KHÔNG phải mọi ảnh đều cần Files Manager `/file/`.
Routing đúng theo VỊ TRÍ sử dụng (context):

  product_main_image        -> haravan_product_image          (product.hstatic.net/...)
  product_gallery           -> haravan_product_image
  blog_hero                 -> haravan_article_image          (article/hero workflow)
  product_description_inline-> haravan_files_manager_admin_session  (BẮT BUỘC /file/)
  blog_body_inline          -> haravan_files_manager_admin_session  (editor-style /file/)

Ảnh INLINE trong mô tả sản phẩm (và blog body editor-style) — RULE (Cách 1, 2026-06-16):
chấp nhận ảnh Sintech KHO ĐÚNG (200000860097) ở 2 dạng:
    cdn.hstatic.net/products/200000860097/<name>      (Product image — bài SP cũ vẫn dùng)
    file.hstatic.net/200000860097/file/<name>   |  cdn.hstatic.net/files/200000860097/file/<name>
CHẶN: theme asset, article image, store khác, external.
(Trước đây bắt buộc /file/ — đã nới vì bài SP cũ vốn chèn link /products/ và hiển thị tốt.)

KHÔNG upload trong file này. Chỉ: classify URL · route adapter · gate apply.

An toàn (hard rules): không log cookie/token, không upload hàng loạt,
không sửa article/product/theme, không commit/push.
"""

import re

EXPECTED_STORE_ID = "200000860097"          # Sintech (xác nhận qua theme asset public_url)
SINTECH_THEME_ID = "1001494160"  # theme live hiện tại (role=main); chỉ tham chiếu, classify dùng store id
SHOP_DOMAIN = "sintech.myharavan.com"

# ─────────────────────────── Classification labels ───────────────────────────
SINTECH_FILES = "SINTECH_FILES"
SINTECH_PRODUCT_IMAGE = "SINTECH_PRODUCT_IMAGE"
SINTECH_ARTICLE_IMAGE = "SINTECH_ARTICLE_IMAGE"
SINTECH_THEME_ASSET = "SINTECH_THEME_ASSET"
HARAVAN_OTHER_STORE = "HARAVAN_OTHER_STORE"
EXTERNAL = "EXTERNAL"
INVALID = "INVALID"

_HSTATIC_HOSTS = ("cdn.hstatic.net", "file.hstatic.net", "product.hstatic.net",
                  "theme.hstatic.net")


def _extract_store_id(url: str):
    """Lấy store id (account id 10+ chữ số) trong path hstatic.

    Các pattern thật gặp:
      file.hstatic.net/<id>/file/...        (Files Manager)
      product.hstatic.net/<id>/product/...  (product image cũ)
      cdn.hstatic.net/products/<id>/...     (product image THẬT khi POST images.json)
      cdn.hstatic.net/themes/<id>/...       (theme asset)
    """
    if not url:
        return None
    for pat in (
        r"hstatic\.net/(\d{10,})/",           # id ngay sau host (file./product.)
        r"hstatic\.net/products/(\d{10,})/",  # cdn.hstatic.net/products/<id>/
        r"hstatic\.net/themes/(\d{10,})/",    # cdn.hstatic.net/themes/<id>/
        r"/files?/(\d{10,})/file/",           # /files/<id>/file/
    ):
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def classify_haravan_image_url(url: str) -> str:
    """Phân loại 1 URL ảnh → 1 label.

    file.hstatic.net/200000860097/file/   | /files/200000860097/file/ -> SINTECH_FILES
    product.hstatic.net/200000860097/                                 -> SINTECH_PRODUCT_IMAGE
    *.hstatic.net/200000860097/.../article/ (path article)            -> SINTECH_ARTICLE_IMAGE
    cdn.hstatic.net/themes/200000860097/                              -> SINTECH_THEME_ASSET
    *.hstatic.net/<store khác>/                                       -> HARAVAN_OTHER_STORE
    domain khác                                                        -> EXTERNAL
    rỗng / không phải URL                                              -> INVALID
    """
    if not url or not isinstance(url, str):
        return INVALID
    u = url.strip()

    # pattern không scheme: "/files/<id>/file/..."
    if not re.match(r"^https?://", u) and not u.startswith("//"):
        m = re.search(r"/files?/(\d{10,})/file/", u)
        if m:
            return SINTECH_FILES if m.group(1) == EXPECTED_STORE_ID else HARAVAN_OTHER_STORE
        return INVALID

    host_m = re.search(r"^(?:https?:)?//([^/]+)/", u)
    host = host_m.group(1).lower() if host_m else ""
    if not any(h in host for h in _HSTATIC_HOSTS):
        return EXTERNAL

    sid = _extract_store_id(u)

    # Files manager — 2 dạng host đều là Files:
    #   file.hstatic.net/<id>/file/...        | cdn.hstatic.net/files/<id>/file/... (+_grande)
    mfile = re.search(r"/files?/(\d{10,})/file/", u)
    if not mfile and "file.hstatic.net" in host:
        mfile = re.search(r"/(\d{10,})/file/", u)
    if mfile:
        return SINTECH_FILES if mfile.group(1) == EXPECTED_STORE_ID else HARAVAN_OTHER_STORE
    # Product image: product.hstatic.net/<id>/...  HOẶC  cdn.hstatic.net/products/<id>/...
    if "product.hstatic.net" in host or ("cdn.hstatic.net" in host and "/products/" in u):
        return SINTECH_PRODUCT_IMAGE if sid == EXPECTED_STORE_ID else HARAVAN_OTHER_STORE
    # Article image (best-effort: path chứa /article)
    if re.search(r"/articles?/", u):
        return SINTECH_ARTICLE_IMAGE if sid == EXPECTED_STORE_ID else HARAVAN_OTHER_STORE
    # Theme asset
    if "cdn.hstatic.net" in host and "/themes/" in u:
        return SINTECH_THEME_ASSET if sid == EXPECTED_STORE_ID else HARAVAN_OTHER_STORE
    # hstatic khác pattern
    if sid:
        return HARAVAN_OTHER_STORE if sid != EXPECTED_STORE_ID else SINTECH_THEME_ASSET
    return EXTERNAL


# ─────────────────────────── Routing by context ───────────────────────────
CONTEXTS = (
    "product_main_image", "product_gallery", "blog_hero",
    "product_description_inline", "blog_body_inline",
)

# Context inline (mô tả SP / blog body editor-style)
INLINE_CONTEXTS = {"product_description_inline", "blog_body_inline"}

# Classification được chấp nhận theo từng context.
# Cách 1 (2026-06-16): inline chấp nhận ảnh Sintech kho đúng dạng PRODUCT hoặc FILES.
CONTEXT_ACCEPTED = {
    "product_main_image": {SINTECH_PRODUCT_IMAGE},
    "product_gallery": {SINTECH_PRODUCT_IMAGE},
    "blog_hero": {SINTECH_ARTICLE_IMAGE, SINTECH_FILES, SINTECH_PRODUCT_IMAGE},
    "product_description_inline": {SINTECH_FILES, SINTECH_PRODUCT_IMAGE},
    "blog_body_inline": {SINTECH_FILES, SINTECH_PRODUCT_IMAGE},
}


def choose_image_upload_adapter(context: str) -> str:
    if context == "product_main_image":
        return "haravan_product_image"
    if context == "product_gallery":
        return "haravan_product_image"
    if context == "blog_hero":
        return "haravan_article_image"
    if context == "product_description_inline":
        return "haravan_files_manager_admin_session"
    if context == "blog_body_inline":
        return "haravan_files_manager_admin_session"
    return "disabled"


def files_manager_session_status() -> str:
    """Trạng thái admin session cho Files Manager.

    Máy này KHÔNG có browser/admin session, cookie, hay MCP browser cho Haravan
    → luôn FILES_MANAGER_SESSION_REQUIRED cho tới khi user tự đăng nhập + bật flag.
    KHÔNG dò cookie người dùng, KHÔNG đoán endpoint.
    """
    return "FILES_MANAGER_SESSION_REQUIRED"


def url_accepted_for_context(url: str, context: str) -> dict:
    """Verdict 1 URL trong 1 context cụ thể."""
    cls = classify_haravan_image_url(url)
    accepted = CONTEXT_ACCEPTED.get(context, set())
    ok = cls in accepted
    reason = None
    if not ok:
        if cls == HARAVAN_OTHER_STORE:
            reason = "UPLOAD_WRONG_STORE"
        elif cls == EXTERNAL:
            reason = "EXTERNAL_IMAGE_BLOCKED"
        elif cls == INVALID:
            reason = "INVALID_IMAGE"
        elif context in INLINE_CONTEXTS:
            # Sintech-owned nhưng sai dạng cho inline (vd theme asset / article image)
            reason = "BLOCKED_INLINE_IMAGE_WRONG_TYPE"
        else:
            reason = "WRONG_CLASSIFICATION_FOR_CONTEXT"
    return {
        "ok": ok,
        "classification": cls,
        "context": context,
        "reason": reason,
        "expected_store_id": EXPECTED_STORE_ID,
        "actual_store_id": _extract_store_id(url),
        "url": url,
    }


# ─────────────────────────── Apply gate (inline images) ───────────────────────────
_IMG_SRC_RE = re.compile(r'<img\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\']', re.I)


def scan_inline_images(body_html: str, context: str = "product_description_inline") -> dict:
    """Scan mọi <img src> trong body_html theo context.

    Inline (product_description_inline / blog_body_inline) — Cách 1:
      mọi ảnh PHẢI là Sintech kho đúng dạng PRODUCT hoặc FILES; sai -> blocked + lý do.
    Trả dict: ok, total, images[], blocking_reasons{}, gate_status.
    """
    srcs = _IMG_SRC_RE.findall(body_html or "")
    images = []
    reasons = {}
    for src in srcs:
        v = url_accepted_for_context(src, context)
        images.append(v)
        if not v["ok"]:
            reasons[v["reason"]] = reasons.get(v["reason"], 0) + 1

    ok = all(i["ok"] for i in images) if images else True
    gate_status = "OK_INLINE_ALL_SINTECH" if ok else "BLOCKED"
    return {
        "ok": ok,
        "context": context,
        "total": len(images),
        "blocking_reasons": reasons,
        "gate_status": gate_status,
        # Cách 1: ảnh /products/ + /files/ Sintech đều OK -> KHÔNG bắt buộc Files Manager session
        "needs_files_manager_session": False,
        "images": images,
    }


# ─────────────────────────── Adapter registry ───────────────────────────
ADAPTERS = {
    "haravan_files_manager_admin_session": {
        "enabled": False,          # OFF — chưa có admin session/cookie hợp lệ
        "proven": False,
        "session_status": "FILES_MANAGER_SESSION_REQUIRED",
        "method": "Admin browser session (cookie) -> Files Manager upload",
        "url_pattern": "file.hstatic.net/200000860097/file/<name>",
        "contexts": ["product_description_inline", "blog_body_inline"],
        "fallback_allowed": False,
    },
    "haravan_product_image": {
        "enabled": True,           # ON — cho product main/gallery
        "proven": True,
        "method": "POST /products/<id>/images.json (base64)",
        "url_pattern": "product.hstatic.net/200000860097/product/<name>",
        "contexts": ["product_main_image", "product_gallery"],
        "fallback_allowed": True,
    },
    "haravan_article_image": {
        "enabled": True,           # ON — cho blog hero/thumbnail
        "proven": False,           # workflow hero tuỳ hệ thống (blog API hay 502)
        "method": "Article image / hero workflow",
        "url_pattern": "hstatic.net/200000860097/.../article/<name> (tuỳ workflow)",
        "contexts": ["blog_hero"],
        "fallback_allowed": True,
    },
    "haravan_theme_asset": {
        "enabled": True,           # ON nhưng KHÔNG cho 2 context inline
        "proven": True,
        "method": "PUT apis.haravan.com/web/themes/<theme>/assets.json (base64)",
        "url_pattern": "cdn.hstatic.net/themes/200000860097/assets/<name>",
        "contexts": ["collection_content", "page_content", "blog_legacy_fallback"],
        "fallback_allowed": True,
    },
}


if __name__ == "__main__":
    passed = True

    def check(label, got, exp):
        global passed
        flag = "OK" if got == exp else "FAIL"
        if got != exp:
            passed = False
        print(f"[{flag}] {label}: {got}")

    # 10. Routing tests
    check("product_main_image", choose_image_upload_adapter("product_main_image"), "haravan_product_image")
    check("product_gallery", choose_image_upload_adapter("product_gallery"), "haravan_product_image")
    check("blog_hero", choose_image_upload_adapter("blog_hero"), "haravan_article_image")
    check("product_description_inline", choose_image_upload_adapter("product_description_inline"), "haravan_files_manager_admin_session")
    check("blog_body_inline", choose_image_upload_adapter("blog_body_inline"), "haravan_files_manager_admin_session")
    check("unknown_ctx", choose_image_upload_adapter("xxx"), "disabled")

    # URL acceptance in product_description_inline (Cách 1: products + files đều OK)
    PDI = "product_description_inline"
    check("files sintech accepted", url_accepted_for_context("https://file.hstatic.net/200000860097/file/a.jpg", PDI)["ok"], True)
    check("files cdn variant accepted", url_accepted_for_context("//cdn.hstatic.net/files/200000860097/file/x_grande.jpg", PDI)["ok"], True)
    check("files other store rejected", url_accepted_for_context("https://file.hstatic.net/200000420363/file/b.jpg", PDI)["reason"], "UPLOAD_WRONG_STORE")
    check("product img ACCEPTED inline (old)", url_accepted_for_context("https://product.hstatic.net/200000860097/product/p.png", PDI)["ok"], True)
    # URL ảnh sản phẩm THẬT (POST images.json trả cdn.hstatic.net/products/<id>/...) -> ACCEPTED
    check("real product img classify", classify_haravan_image_url("https://cdn.hstatic.net/products/200000860097/sintech_probe_x.jpg"), SINTECH_PRODUCT_IMAGE)
    check("real product img ACCEPTED inline", url_accepted_for_context("https://cdn.hstatic.net/products/200000860097/x.jpg", PDI)["ok"], True)
    # theme asset / external / wrong store vẫn bị chặn
    check("theme rejected inline", url_accepted_for_context("https://cdn.hstatic.net/themes/200000860097/assets/x.jpg", PDI)["reason"], "BLOCKED_INLINE_IMAGE_WRONG_TYPE")
    check("external rejected inline", url_accepted_for_context("https://example.com/x.jpg", PDI)["reason"], "EXTERNAL_IMAGE_BLOCKED")
    check("other store rejected inline", url_accepted_for_context("https://cdn.hstatic.net/products/200000420363/x.jpg", PDI)["reason"], "UPLOAD_WRONG_STORE")

    # Accept set inline = products + files
    check("inline accepts product", (SINTECH_PRODUCT_IMAGE in CONTEXT_ACCEPTED[PDI]), True)
    check("inline accepts files", (SINTECH_FILES in CONTEXT_ACCEPTED[PDI]), True)
    check("inline rejects theme", (SINTECH_THEME_ASSET in CONTEXT_ACCEPTED[PDI]), False)

    # Gate scan: product image + theme (theme bị chặn, product ok)
    body = ('<p><img src="https://cdn.hstatic.net/products/200000860097/ok.jpg"></p>'
            '<p><img src="https://cdn.hstatic.net/themes/200000860097/assets/bad.jpg"></p>')
    g = scan_inline_images(body, PDI)
    check("gate blocked mixed", g["gate_status"], "BLOCKED")
    check("gate flags wrong-type", "BLOCKED_INLINE_IMAGE_WRONG_TYPE" in g["blocking_reasons"], True)
    # Gate all product images -> OK
    g2 = scan_inline_images('<img src="https://cdn.hstatic.net/products/200000860097/a.jpg">', PDI)
    check("gate ok all product", g2["gate_status"], "OK_INLINE_ALL_SINTECH")

    print("\nALL PASS" if passed else "\nSOME FAILED")
