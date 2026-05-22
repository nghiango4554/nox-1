"""Haravan Open API — Blog/Article (apis.haravan.com/web/blogs/*).

KHÁC `haravan_client.py` (admin API {shop}.myharavan.com/admin → product/theme/customer/order).
Blog nằm ở Open API `apis.haravan.com/web` với token scope RIÊNG (`blog_access_token`).
Dùng token product/theme ở đây sẽ 401 (sai scope). Config ở ../state/haravan_token.json.

⚠️ QUIRK QUAN TRỌNG: POST tạo article KHÔNG tôn trọng `published:false` — nó vẫn set
`published_at` (quá khứ) → bài LÊN LIVE. Để tạo bài ẨN phải: POST xong → PUT `published_at=null`.
Hàm create_article(hidden=True) đã xử lý 2 bước này.

Blog IDs Sintech: 1000960873 = "Hướng dẫn" (handle huong-dan) · 1000906526 = "Tin tức công nghệ" (handle news).

FIELD MAP article (verified 22/5/2026):
  title, author, body_html, tags (chuỗi phẩy), handle, image={"src": url} (Haravan re-host về cdn.hstatic.net),
  page_title = SEO title, meta_description = SEO meta description.
  KHÔNG có field excerpt riêng (summary_html / excerpt bị bỏ qua; meta_description auto-sinh từ body nếu không set).
  KHÔNG dùng metafields_global_* (đó là của admin product API).
"""
import json
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN_PATH = Path(__file__).parent.parent / "state" / "haravan_token.json"
TIMEOUT = 30


class HaravanBlogError(Exception):
    pass


def _cfg() -> dict:
    return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))


def _base() -> str:
    return _cfg().get("open_api_base", "https://apis.haravan.com/web").rstrip("/")


def _headers() -> dict:
    tok = _cfg().get("blog_access_token")
    if not tok:
        raise HaravanBlogError("Thiếu 'blog_access_token' trong state/haravan_token.json (scope web/blogs).")
    return {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _req(method: str, path: str, payload: dict = None, params: dict = None) -> dict:
    # verify=False: máy vợ có VPN/antivirus intercept HTTPS (giống haravan_client).
    r = requests.request(method, _base() + path, headers=_headers(),
                         json=payload, params=params, timeout=TIMEOUT, verify=False)
    if r.status_code >= 400:
        raise HaravanBlogError(f"HTTP {r.status_code} {method} {path}: {r.text[:300]}")
    return r.json() if r.text else {}


def list_blogs() -> list:
    return _req("GET", "/blogs.json").get("blogs", [])


def list_articles(blog_id: int, limit: int = 50, page: int = 1) -> list:
    return _req("GET", f"/blogs/{blog_id}/articles.json",
                params={"limit": limit, "page": page}).get("articles", [])


def get_article(blog_id: int, article_id: int) -> dict:
    return _req("GET", f"/blogs/{blog_id}/articles/{article_id}.json").get("article", {})


def update_article(blog_id: int, article_id: int, fields: dict) -> dict:
    body = {"article": {"id": article_id, **fields}}
    return _req("PUT", f"/blogs/{blog_id}/articles/{article_id}.json", payload=body).get("article", {})


def delete_article(blog_id: int, article_id: int) -> bool:
    _req("DELETE", f"/blogs/{blog_id}/articles/{article_id}.json")
    return True


def create_article(blog_id: int, fields: dict, hidden: bool = True) -> dict:
    """Tạo article trong blog_id. fields: title, author, body_html, tags, ...

    hidden=True (mặc định) → bài ẨN (draft): POST rồi PUT published_at=null,
    vì Open API bỏ qua published:false lúc POST (vẫn publish). Trả về article dict.
    """
    payload = {"article": {**fields}}
    payload["article"]["published"] = not hidden
    art = _req("POST", f"/blogs/{blog_id}/articles.json", payload=payload).get("article", {})
    aid = art.get("id")
    # POST lỡ publish dù hidden → ép ẩn bằng published_at=null (cách duy nhất ăn).
    if hidden and aid and (art.get("published") or art.get("published_at")):
        art = update_article(blog_id, aid, {"published": False, "published_at": None})
    return art
