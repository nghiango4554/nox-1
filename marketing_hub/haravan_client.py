"""Haravan Admin API wrapper. Reads token từ ../state/haravan_token.json.

Haravan API mimics Shopify Admin API:
- Endpoint: https://{shop}.myharavan.com/admin/{resource}.json
- Auth header: Authorization: Bearer {access_token}
"""

import json
import time
from pathlib import Path
from typing import Optional

import requests

TOKEN_PATH = Path(__file__).parent.parent / "state" / "haravan_token.json"
TIMEOUT = 30


class HaravanError(Exception):
    pass


def load_config() -> dict:
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _base_url() -> str:
    cfg = load_config()
    return f"https://{cfg['shop_domain']}/admin"


def _auth_headers() -> dict:
    cfg = load_config()
    return {
        "Authorization": f"Bearer {cfg['access_token']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


HARAVAN_PAUSE_FLAG = Path(__file__).parent / ".env" / "haravan_paused.flag"


def _check_paused():
    """Raise nếu Haravan đang bị pause (file .env/haravan_paused.flag exist)."""
    if HARAVAN_PAUSE_FLAG.exists():
        reason = HARAVAN_PAUSE_FLAG.read_text(encoding="utf-8").strip() or "manually paused"
        raise HaravanError(f"⏸️ Haravan PAUSED: {reason}")


# Permission gate (2026-05-12): chỉ cho phép quyền CHỈNH SỬA + upload ảnh vào SP existing.
# CẤM: tạo SP mới, xóa SP, tạo bài viết, xóa bài viết.
import re as _re_perm
_BLOCKED_OPERATIONS = [
    ("POST",   _re_perm.compile(r"^/products\.json"),                "Tạo sản phẩm mới"),
    ("POST",   _re_perm.compile(r"^/blogs/\d+/articles\.json"),      "Tạo bài viết blog mới"),
    ("DELETE", _re_perm.compile(r"^/products/\d+\.json$"),           "Xóa sản phẩm"),
    ("DELETE", _re_perm.compile(r"^/blogs/\d+/articles/\d+\.json$"), "Xóa bài viết blog"),
    ("DELETE", _re_perm.compile(r"^/articles/\d+\.json$"),           "Xóa bài viết"),
]


import contextlib
import threading

_permission_override = threading.local()


@contextlib.contextmanager
def allow_blocked_operations(reason: str):
    """Tạm thời lift permission gate cho block code cụ thể.

    Chỉ dùng cho explicit user-initiated action qua UI (vd /products/new).
    KHÔNG dùng cho automated script — gate cố ý chặn auto-create.

    Usage:
        with hv_client.allow_blocked_operations("ui_form:/products/new"):
            hv_client.create_product(fields)
    """
    prev = getattr(_permission_override, "active", None)
    _permission_override.active = reason
    try:
        yield
    finally:
        _permission_override.active = prev


def _check_permission(method: str, path: str):
    """Raise nếu method+path nằm trong blocklist (create/delete SP+bài viết).

    Bỏ qua nếu đang trong block `allow_blocked_operations(...)` — explicit override.
    """
    if getattr(_permission_override, "active", None):
        return  # explicit override active
    method_up = method.upper()
    for blocked_method, pattern, label in _BLOCKED_OPERATIONS:
        if method_up == blocked_method and pattern.match(path):
            raise HaravanError(
                f"🔒 PERMISSION DENIED: {method} {path} — thao tác '{label}' bị cấm. "
                f"Chỉ có quyền CHỈNH SỬA (PUT/PATCH) + upload ảnh vào SP existing. "
                f"Nếu cần override → wrap trong hv_client.allow_blocked_operations('reason')."
            )


def _summarize_payload(payload) -> str:
    """Tóm tắt GỌN payload đẩy lên Haravan (không lưu full content) cho audit log."""
    if not isinstance(payload, dict) or not payload:
        return ""
    inner = next(iter(payload.values()), None)
    if not isinstance(inner, dict):
        return ""
    parts = []
    for k, v in inner.items():
        if k == "id":
            continue
        if k == "body_html":
            parts.append(f"body_html: {len(v or '')}c")
        elif "title_tag" in k:
            parts.append(f"title: {str(v)[:55]}")
        elif "description_tag" in k:
            parts.append(f"meta: {str(v)[:55]}")
        elif k == "images":
            parts.append("images")
        elif isinstance(v, str):
            parts.append(f"{k}: {v[:35]}")
        else:
            parts.append(k)
    return " · ".join(parts)[:500]


def _audit(method: str, path: str, payload, ok: bool, status_code, error):
    """Ghi audit (best-effort) — TUYỆT ĐỐI không làm vỡ luồng sync."""
    try:
        import re as _re
        import db
        m = _re.search(r"/([a-z_]+)/(\d+)", path)
        rtype = (m.group(1).rstrip("s") if m else path.strip("/").split(".")[0])
        rid = m.group(2) if m else None
        db.haravan_audit_log(method=method, path=path, resource_type=rtype, resource_id=rid,
                             summary=_summarize_payload(payload), ok=ok,
                             status_code=status_code, error=(error[:300] if error else None))
    except Exception:
        pass


def _request(method: str, path: str, params: dict = None, payload: dict = None) -> dict:
    """Low-level request. Path = '/products.json' (relative to /admin).

    Bypass SSL verify (verify=False) — máy vợ đang có VPN/antivirus intercept
    HTTPS làm cert chain không verify được. Trade-off acceptable cho local dev.
    """
    _check_paused()
    _check_permission(method, path)
    url = f"{_base_url()}{path}"
    # Disable urllib3 InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    r = requests.request(
        method, url,
        headers=_auth_headers(),
        params=params,
        json=payload,
        timeout=TIMEOUT,
        verify=False,  # bypass SSL verify (VPN/antivirus intercept)
    )
    if r.status_code == 429:
        # rate-limited — wait + retry once
        time.sleep(2)
        r = requests.request(method, url, headers=_auth_headers(),
                              params=params, json=payload, timeout=TIMEOUT, verify=False)
    is_mut = method.upper() in ("PUT", "POST", "DELETE")
    if r.status_code >= 400:
        try:
            err = r.json()
        except (ValueError, TypeError):
            err = {"error": r.text[:300]}
        if is_mut:
            _audit(method, path, payload, False, r.status_code, str(err))
        raise HaravanError(f"HTTP {r.status_code} {method} {path}: {err}")
    if is_mut:
        _audit(method, path, payload, True, r.status_code, None)
    if not r.content:
        return {}
    try:
        return r.json()
    except (ValueError, TypeError):
        return {"_raw": r.text}


# ─────────────────────────── PRODUCTS ───────────────────────────

def list_products(page: int = 1, limit: int = 50, fields: str = None,
                  updated_at_min: str = None) -> list:
    params = {"page": page, "limit": min(limit, 250)}
    if fields:
        params["fields"] = fields
    if updated_at_min:
        params["updated_at_min"] = updated_at_min
    data = _request("GET", "/products.json", params=params)
    return data.get("products", [])


def count_products(updated_at_min: str = None) -> int:
    params = {}
    if updated_at_min:
        params["updated_at_min"] = updated_at_min
    data = _request("GET", "/products/count.json", params=params or None)
    return data.get("count", 0)


def get_product(product_id: int) -> dict:
    data = _request("GET", f"/products/{product_id}.json")
    return data.get("product", {})


def get_product_id_by_handle(handle: str):
    """Resolve product handle → haravan_id qua admin API. None nếu SP không tồn tại.
    Dùng khi cache local miss (SP mới chưa sync / race gen⨯sync)."""
    data = _request("GET", "/products.json",
                    params={"handle": handle, "fields": "id,handle"})
    prods = data.get("products", [])
    return prods[0]["id"] if prods else None


PAGE_SIZE = 50  # Haravan chặn cứng 50/trang dù gửi limit=250


def list_products_in_collection(collection_id: int, fields: str = "id,handle,title",
                                max_pages: int = 60) -> list:
    """Tất cả SP thuộc 1 collection (custom hoặc smart) qua /products.json?collection_id=.
    Read-only (GET)."""
    out = []
    page = 1
    while page <= max_pages:
        params = {"collection_id": collection_id, "limit": PAGE_SIZE, "page": page}
        if fields:
            params["fields"] = fields
        data = _request("GET", "/products.json", params=params)
        batch = data.get("products", [])
        if not batch:
            break
        out.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        page += 1
    return out


def update_product(product_id: int, fields: dict) -> dict:
    payload = {"product": fields}
    data = _request("PUT", f"/products/{product_id}.json", payload=payload)
    return data.get("product", {})


def put_image_alt(product_id: int, image_id: int, alt: str) -> dict:
    """PUT ALT text cho 1 image của SP. Trả {"ok": True} hoặc {"ok": False, "error": msg}."""
    try:
        _request("PUT", f"/products/{product_id}/images/{image_id}.json",
                 payload={"image": {"id": image_id, "alt": alt}})
        return {"ok": True}
    except HaravanError as e:
        return {"ok": False, "error": str(e)}


def create_product(fields: dict) -> dict:
    payload = {"product": fields}
    data = _request("POST", "/products.json", payload=payload)
    return data.get("product", {})


# ─────────────────────────── COLLECTIONS ───────────────────────────

def list_custom_collections(page: int = 1, limit: int = 50) -> list:
    data = _request("GET", "/custom_collections.json", params={"page": page, "limit": limit})
    return data.get("custom_collections", [])


def list_smart_collections(page: int = 1, limit: int = 50) -> list:
    data = _request("GET", "/smart_collections.json", params={"page": page, "limit": limit})
    return data.get("smart_collections", [])


def count_custom_collections() -> int:
    data = _request("GET", "/custom_collections/count.json")
    return data.get("count", 0)


def count_smart_collections() -> int:
    data = _request("GET", "/smart_collections/count.json")
    return data.get("count", 0)


# ─────────────────────────── BLOGS / ARTICLES ───────────────────────────

def list_blogs() -> list:
    data = _request("GET", "/blogs.json")
    return data.get("blogs", [])


def list_articles(blog_id: int, page: int = 1, limit: int = 50) -> list:
    data = _request("GET", f"/blogs/{blog_id}/articles.json", params={"page": page, "limit": limit})
    return data.get("articles", [])


def get_article(blog_id: int, article_id: int) -> dict:
    data = _request("GET", f"/blogs/{blog_id}/articles/{article_id}.json")
    return data.get("article", {})


def update_article(blog_id: int, article_id: int, fields: dict) -> dict:
    payload = {"article": fields}
    data = _request("PUT", f"/blogs/{blog_id}/articles/{article_id}.json", payload=payload)
    return data.get("article", {})


# ─────────────────────────── METAFIELDS (SEO title/description) ───────────────────────────
# QUAN TRỌNG: Haravan KHÔNG lưu SEO title/description qua flat field
# `metafields_global_title_tag` / `metafields_global_description_tag` trên smart_collection,
# custom_collection và article. Trên product cũng KHÔNG persist. Phải dùng explicit metafields
# endpoint với namespace=global, key=title_tag/description_tag.

_METAFIELDS_PATH = {
    "products":           lambda rid: f"/products/{rid}/metafields.json",
    "smart_collections":  lambda rid: f"/smart_collections/{rid}/metafields.json",
    "custom_collections": lambda rid: f"/custom_collections/{rid}/metafields.json",
    # Articles dùng /articles/{id}/metafields.json (KHÔNG /blogs/.../articles/.../metafields)
    "articles":           lambda rid: f"/articles/{rid}/metafields.json",
}


def list_metafields(resource_type: str, resource_id: int) -> list:
    path_fn = _METAFIELDS_PATH.get(resource_type)
    if not path_fn:
        raise HaravanError(f"Unsupported metafield resource_type: {resource_type}")
    data = _request("GET", path_fn(resource_id))
    return data.get("metafields", [])


def upsert_metafield(resource_type: str, resource_id: int,
                     namespace: str, key: str, value: str) -> dict:
    """Tạo mới hoặc update metafield namespace/key cho 1 resource.

    Empty value → xóa metafield (nếu tồn tại) thay vì POST chuỗi rỗng.
    """
    path_fn = _METAFIELDS_PATH.get(resource_type)
    if not path_fn:
        raise HaravanError(f"Unsupported metafield resource_type: {resource_type}")

    existing = list_metafields(resource_type, resource_id)
    match = next((m for m in existing
                  if m.get("namespace") == namespace and m.get("key") == key), None)

    value_str = (value or "").strip()

    if not value_str:
        if match:
            _request("DELETE", f"/metafields/{match['id']}.json")
            return {"deleted": True, "id": match["id"]}
        return {"skipped": True, "reason": "empty value, no existing metafield"}

    if match:
        payload = {"metafield": {"id": match["id"], "value": value_str, "value_type": "string"}}
        data = _request("PUT", f"/metafields/{match['id']}.json", payload=payload)
        return data.get("metafield", {})

    payload = {"metafield": {
        "namespace": namespace, "key": key, "value": value_str, "value_type": "string",
    }}
    data = _request("POST", path_fn(resource_id), payload=payload)
    return data.get("metafield", {})


def upsert_seo_metafields(resource_type: str, resource_id: int,
                          title: str = None, description: str = None) -> dict:
    """Convenience: upsert cả 2 metafield SEO title_tag + description_tag."""
    out = {}
    if title is not None:
        out["title"] = upsert_metafield(resource_type, resource_id, "global", "title_tag", title)
    if description is not None:
        out["description"] = upsert_metafield(resource_type, resource_id, "global", "description_tag", description)
    return out


# ─────────────────────────── PAGES ───────────────────────────

def list_pages(page: int = 1, limit: int = 50) -> list:
    data = _request("GET", "/pages.json", params={"page": page, "limit": limit})
    return data.get("pages", [])


def get_page(page_id: int) -> dict:
    data = _request("GET", f"/pages/{page_id}.json")
    return data.get("page", {})


def count_pages() -> int:
    data = _request("GET", "/pages/count.json")
    return data.get("count", 0)


# ─────────────────────────── PRODUCT IMAGES ───────────────────────────

def add_product_image(product_id: int, attachment_b64: str,
                      filename: str = "image.jpg", alt: str = "") -> dict:
    """Upload ảnh (base64) vào product images carousel. Trả image dict
    có `src` = URL CDN public (`https://cdn.hstatic.net/products/...`).
    """
    payload = {
        "image": {
            "attachment": attachment_b64,
            "filename": filename,
            "alt": alt,
        }
    }
    data = _request("POST", f"/products/{product_id}/images.json", payload=payload)
    return data.get("image", {})


# ─────────────────────────── ASSET STORAGE (internal) ───────────────────────────
#
# Để chèn ảnh inline vào body_html của các SP khác, app upload ảnh đã process
# vào 1 SP "asset_storage" hidden (status=draft). URL CDN trả về dùng được public
# trong body_html mà không hiển thị ảnh trên trang SP đích.

ASSET_STORAGE_CFG = Path(__file__).parent.parent / "state" / "asset_storage_product.json"
ASSET_STORAGE_MAX = 90  # Haravan limit per product


def _load_asset_storage_ids() -> list:
    """Trả list haravan_id của các SP asset storage đang dùng (multi-storage)."""
    if not ASSET_STORAGE_CFG.exists():
        raise HaravanError(
            f"Chưa có asset_storage product. File: {ASSET_STORAGE_CFG}"
        )
    cfg = json.loads(ASSET_STORAGE_CFG.read_text(encoding="utf-8"))
    # Backward-compat: old format {"haravan_id": N} → wrap to list
    if "storages" in cfg:
        return [s["haravan_id"] for s in cfg["storages"]]
    if "haravan_id" in cfg:
        return [cfg["haravan_id"]]
    return []


def _save_asset_storage_ids(ids: list):
    """Save list storage IDs back to config (multi-storage format)."""
    import datetime
    cfg = {
        "storages": [
            {"haravan_id": i, "added_at": datetime.datetime.now().isoformat(timespec="seconds")}
            for i in ids
        ],
    }
    ASSET_STORAGE_CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _create_new_asset_storage() -> int:
    """Tạo SP asset storage mới — CHỈ DÙNG THỦ CÔNG khi cần thêm slot.

    DEPRECATED auto-call: trước đó upload_to_asset_storage() tự gọi khi storage
    đầy, gây race condition tạo SP rác hàng loạt (incident 2026-05-10).
    Từ 2026-05-12: chỉ gọi MANUAL khi vợ chủ động muốn tạo storage mới.
    """
    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "product": {
            "title": f"_Sintech_Marketing_Hub_Asset_Storage_{ts}_",
            "vendor": "Sintech",
            "product_type": "ASSET_STORAGE",
            "published": False,
            "tags": "asset_storage,internal,hidden",
        }
    }
    data = _request("POST", "/products.json", payload=payload)
    pid = data.get("product", {}).get("id")
    if not pid:
        raise HaravanError(f"Tạo asset storage thất bại: {data}")
    print(f"[asset_storage] Created new storage product id={pid}")
    return pid


def _count_storage_images(storage_id: int) -> int:
    """Đếm số ảnh hiện có trong 1 storage SP."""
    try:
        prod = get_product(storage_id)
        return len(prod.get("images", []))
    except Exception:
        return 0


def upload_to_asset_storage(img_bytes: bytes, filename: str, alt: str = "") -> str:
    """Upload ảnh vào internal asset_storage product, multi-storage fallback.

    Logic SAFE (2026-05-12 — sau incident race condition tạo SP rác):
      1. Iterate qua list storages, thử upload vào storage đầu chưa đầy
      2. Storage đầy (HTTP 422) → switch storage tiếp theo
      3. Hết storage → RAISE LỖI (KHÔNG tự tạo SP mới — tránh tạo rác)

    Để thêm storage mới: tạo SP thủ công trên Haravan admin + thêm haravan_id
    vào file `state/asset_storage_product.json` field `storages`.
    """
    import base64
    b64 = base64.b64encode(img_bytes).decode()
    storage_ids = _load_asset_storage_ids()

    last_err = None
    for storage_id in storage_ids:
        try:
            img = add_product_image(storage_id, b64, filename=filename, alt=alt)
            src = img.get("src") or ""
            if not src:
                raise HaravanError(f"Upload OK nhưng không có src trả về: {img}")
            return src
        except HaravanError as e:
            msg = str(e)
            last_err = e
            if "vượt quá 90" in msg or "HTTP 422" in msg:
                print(f"[asset_storage] Storage {storage_id} đầy, thử storage tiếp...")
                continue
            raise

    # Tất cả storage đầy — RAISE rõ ràng, KHÔNG tự tạo SP nữa
    raise HaravanError(
        f"⚠️ Tất cả {len(storage_ids)} asset storage đầy (90/90). "
        f"Tạo SP storage mới thủ công trên Haravan admin + thêm haravan_id vào "
        f"`state/asset_storage_product.json`. KHÔNG tự tạo để tránh tạo SP rác."
    )


# ─────────────────────────── HEALTH ───────────────────────────

def shop_info() -> dict:
    """Test endpoint — trả info shop để xác nhận token hoạt động."""
    data = _request("GET", "/shop.json")
    return data.get("shop", {})
