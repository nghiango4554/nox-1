"""Crawl sitemap của đối thủ → lưu URL + classify topic.
Mục đích: phát hiện content gap (đối thủ có nhiều bài, Sintech thiếu).
"""
import re
import threading
import time
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests

import db


USER_AGENT = "SintechHubCompetitorBot/1.0"
TIMEOUT = 20

# Đối thủ chính của Sintech
COMPETITORS = {
    "hacom": {
        "label": "HACOM",
        "domain": "hacom.vn",
        "sitemap": "https://hacom.vn/sitemap.xml",
    },
    "gearvn": {
        "label": "GearVN",
        "domain": "gearvn.com",
        "sitemap": "https://gearvn.com/sitemap.xml",
    },
    "phongvu": {
        "label": "Phong Vũ",
        "domain": "phongvu.vn",
        "sitemap": "https://phongvu.vn/sitemap.xml",
    },
    "minhtuanmobile": {
        "label": "Minh Tuấn Mobile",
        "domain": "minhtuanmobile.com",
        "sitemap": "https://minhtuanmobile.com/sitemap.xml",
    },
}


def classify_url_type(url: str) -> str:
    """Phân loại URL theo path đặc trưng e-commerce VN."""
    p = urlparse(url).path.lower()
    if any(x in p for x in ("/products/", "/product/", "/san-pham/", "/sp/")):
        return "product"
    if any(x in p for x in ("/blogs/", "/blog/", "/news/", "/tin-tuc/", "/bai-viet/", "/tu-van/")):
        return "blog"
    if any(x in p for x in ("/collections/", "/collection/", "/category/", "/danh-muc/", "/categories/")):
        return "collection"
    if p in ("/", "") or "/pages/" in p or "/page/" in p:
        return "page"
    return "other"


def classify_topic(title: str, url: str = "") -> str:
    """Detect topic — CHỈ theo title. Tham số `url` giữ lại cho tương thích, KHÔNG dùng.

    4/9/2026: BỎ bản sao luật riêng, gọi thẳng nguồn duy nhất ở routes/blog_topics.py.
    Bản sao cũ lệch cả thứ tự lẫn từ khoá so với thước dùng cho blog Sintech (service
    nằm cuối thay vì thứ 2, thiếu "tphcm"/"quận"), làm bảng "Topic gap" trừ hai vế đo
    bằng hai cây thước khác nhau — 11/266 blog Sintech ra 2 kết quả.

    Cũng bỏ luôn việc nhét url vào chuỗi phân loại: đường dẫn chứa nhiều từ trùng
    keyword (vd handle /news/ của blog Sintech) làm phân loại nhiễu nặng. Khi sitemap
    thiếu title đã có `_slug_to_title()` đoán title từ slug rồi.
    """
    from routes.blog_topics import classify_blog_topic
    return classify_blog_topic(title)


def _slug_to_title(url: str) -> str:
    """Đoán title từ slug URL — fallback khi sitemap không có title."""
    try:
        p = urlparse(url).path
        slug = p.rstrip("/").rsplit("/", 1)[-1]
        slug = re.sub(r"\.(html?|php)$", "", slug, flags=re.IGNORECASE)
        return slug.replace("-", " ").replace("_", " ").strip()
    except Exception:
        return ""


_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _parse_sitemap(xml_text: str) -> tuple:
    """Trả (is_index, [items]). items = list of dict {loc, lastmod}."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False, []
    tag = root.tag.lower()
    is_index = "sitemapindex" in tag
    items = []
    elements = root.findall(".//sm:sitemap" if is_index else ".//sm:url", _SITEMAP_NS)
    if not elements:
        # Fallback no namespace
        elements = root.findall(".//sitemap" if is_index else ".//url")
    for el in elements:
        loc = el.find("sm:loc", _SITEMAP_NS)
        if loc is None:
            loc = el.find("loc")
        lastmod = el.find("sm:lastmod", _SITEMAP_NS)
        if lastmod is None:
            lastmod = el.find("lastmod")
        if loc is not None and loc.text:
            items.append({
                "loc": loc.text.strip(),
                "lastmod": lastmod.text.strip() if lastmod is not None and lastmod.text else None,
            })
    return is_index, items


def fetch_sitemap_urls(sitemap_url: str, max_urls: int = 5000) -> list:
    """Lấy tất cả URL từ sitemap (auto follow sitemap-index nested)."""
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(sitemap_url, headers=headers, timeout=TIMEOUT)
        if r.status_code >= 400:
            return []
    except requests.RequestException:
        return []

    is_index, items = _parse_sitemap(r.text)
    if not is_index:
        return items[:max_urls]

    # Nested: gom URL từ tất cả sitemap con
    all_items = []
    for sm in items:
        if len(all_items) >= max_urls:
            break
        try:
            sub_r = requests.get(sm["loc"], headers=headers, timeout=TIMEOUT)
            if sub_r.status_code >= 400:
                continue
            _, sub_items = _parse_sitemap(sub_r.text)
            all_items.extend(sub_items)
            time.sleep(0.3)
        except requests.RequestException:
            continue
    return all_items[:max_urls]


# In-memory state (giống pattern khác)
_state_lock = threading.Lock()
_state = {"running": False, "competitor": None, "fetched": 0, "total": 0,
          "message": "", "started_at": None}


def state_snapshot():
    with _state_lock:
        return dict(_state)


def _set_state(**kw):
    with _state_lock:
        _state.update(kw)


def crawl_competitor(competitor_key: str, max_urls: int = 5000) -> int:
    """Crawl sitemap 1 đối thủ → upsert DB. Trả số URL fetched."""
    info = COMPETITORS.get(competitor_key)
    if not info:
        return 0
    items = fetch_sitemap_urls(info["sitemap"], max_urls=max_urls)
    now = datetime.now().isoformat(timespec="seconds")
    rows = []
    for it in items:
        url = it["loc"]
        url_type = classify_url_type(url)
        title = _slug_to_title(url)
        topic = classify_topic(title, url)
        rows.append({
            "competitor": competitor_key,
            "url": url,
            "url_type": url_type,
            "title": title,
            "topic": topic,
            "keywords": None,
            "lastmod": it.get("lastmod"),
            "last_seen": now,
        })
    db.competitor_upsert(rows)
    return len(rows)


def run_crawl_all(max_per_competitor: int = 5000):
    """Crawl tất cả đối thủ — chạy trong thread."""
    keys = list(COMPETITORS.keys())
    _set_state(running=True, fetched=0, total=0,
               started_at=datetime.now().isoformat(timespec="seconds"),
               message="Bắt đầu crawl đối thủ...")
    total_fetched = 0
    try:
        for k in keys:
            info = COMPETITORS[k]
            _set_state(competitor=k, message=f"Crawl {info['label']}...")
            try:
                n = crawl_competitor(k, max_urls=max_per_competitor)
                total_fetched += n
                _set_state(fetched=total_fetched,
                           message=f"Xong {info['label']}: {n} URL")
            except Exception as e:
                _set_state(message=f"Lỗi {info['label']}: {e.__class__.__name__}")
        _set_state(running=False, competitor=None,
                   message=f"Xong: {total_fetched} URL từ {len(keys)} đối thủ.")
        # Notify
        try:
            import notifier
            stats = db.competitor_stats()
            msg_parts = [f"✅ <b>Crawl đối thủ xong</b>", f"📊 {total_fetched} URL"]
            for k, n in stats.get("by_competitor", {}).items():
                msg_parts.append(f"  • {COMPETITORS.get(k, {}).get('label', k)}: {n}")
            msg_parts.append(f"🔗 http://127.0.0.1:5055/competitors")
            notifier.send_telegram("\n".join(msg_parts))
        except Exception:
            pass
    except Exception as e:
        _set_state(running=False, message=f"Lỗi: {e.__class__.__name__}: {str(e)[:200]}")


def start_crawl_all_async() -> bool:
    snap = state_snapshot()
    if snap["running"]:
        return False
    t = threading.Thread(target=run_crawl_all, daemon=True)
    t.start()
    return True
