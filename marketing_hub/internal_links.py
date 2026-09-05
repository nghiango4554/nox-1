"""Gợi ý internal link tự nhiên cho bài viết SEO sản phẩm Sintech (v2026-05-08).

Tuân theo priority order trong seo_writing_rules.md:
1. Link đúng category sản phẩm (cùng vendor + cùng product_type)
2. Link category liên quan trực tiếp (cùng product_type)
3. Link phụ kiện dùng kèm (heuristic theo product_type)
4. Link nhóm nhu cầu (PC Gaming / PC văn phòng / Gaming Gear)
5. Link trang chủ Sintech (cho CTA intro/outro — handled separately)

Output format mỗi item: {url, anchor, source, score}.
Anchor là cụm danh từ mô tả (vd "chuột gaming", "màn hình 2K") — KHÔNG dùng
"tại đây / xem thêm".
"""
import re
from urllib.parse import urlparse

import db


SITE_BASE = "https://sintech.vn"
SINTECH_HOME_LINK = {
    "url": SITE_BASE,
    "anchor": "Sintech",
    "source": "homepage",
    "score": 100,
}
MAX_SUGGESTIONS = 8

# Heuristic: với mỗi product_type, gợi ý 1-2 nhóm phụ kiện dùng kèm.
#
# ⚠️ 4/9/2026 — RÀ LẠI BẰNG HTTP THẬT trên sintech.vn. 6/18 slug cũ đã hỏng:
#     micro       → 404 CHẾT (bài tai nghe gợi ý link vào trang không tồn tại)
#     nguon       → 301 psu-nguon
#     ssd         → 301 ssd-m-2
#     lot-chuot   → 301 ban-di-chuot
#     ban-gaming  → 301 ban-phim-gaming   ⚠️ LỆCH NGHĨA: "bàn gaming" hoá "bàn phím"
#     ghe-gaming  → 301 ghe-van-phong     ⚠️ LỆCH NGHĨA: "ghế gaming" hoá "ghế văn phòng"
# Hai cái lệch nghĩa nguy hơn cả 404: anchor viết "bàn gaming" mà trỏ sang bàn phím.
# Link nội bộ nên trỏ THẲNG đích, đi qua 301 là mất một phần link equity.
# Kiểm lại khi đổi handle collection: `curl -o /dev/null -w '%{http_code} %{redirect_url}'`.
ACCESSORY_HINTS = {
    "MÀN HÌNH": ["man-hinh-may-tinh", "ban-phim-co", "chuot-gaming"],
    "LAPTOP": ["laptop", "chuot-gaming", "tai-nghe-gaming", "ban-di-chuot"],
    "CHUỘT": ["chuot-gaming", "ban-di-chuot", "ban-phim-co"],
    "BÀN PHÍM": ["ban-phim-co", "chuot-gaming", "ban-di-chuot"],
    "TAI NGHE": ["tai-nghe-gaming", "tai-nghe"],       # bỏ "micro" — 404
    "PC": ["pc-gaming", "man-hinh-may-tinh", "ban-phim-co"],
    "MAINBOARD": ["cpu", "ram", "vga"],
    "VGA": ["pc-gaming", "man-hinh-may-tinh", "psu-nguon"],
    "RAM": ["mainboard", "cpu", "ssd-m-2"],
    "SSD": ["ram", "mainboard"],
    "NGUỒN": ["case", "tan-nhiet", "vga"],
    "TẢN NHIỆT": ["case", "psu-nguon", "cpu"],
    "VỎ CASE": ["psu-nguon", "tan-nhiet", "mainboard"],
    "GHẾ GAMING": ["ghe", "ban-phim-co", "chuot-gaming"],
    "BÀN GAMING": ["ghe", "ban-phim-co"],
}

# Nhóm nhu cầu — match theo vendor / type chung.
DEMAND_GROUPS = [
    {"slug": "pc-gaming", "anchor": "PC gaming"},
    {"slug": "pc-van-phong", "anchor": "PC văn phòng"},
    {"slug": "laptop-gaming", "anchor": "laptop gaming"},
]


def _handle_from_url(url: str) -> str:
    p = urlparse(url).path
    m = re.match(r"^/products/([^/]+)/?$", p)
    return m.group(1) if m else ""


ANCHOR_MAX_LEN = 30  # Hard cap — anchor SEO best practice ≤30c, tránh ngắt câu


def _normalize_anchor_from_collection_title(title: str) -> str:
    """Rút anchor descriptive NGẮN từ title collection.

    Vd 'PC AutoCAD cấu hình mạnh, thao tác nhanh | Chính hãng – Sintech'
    → 'PC AutoCAD'  (max 30c).
    """
    if not title:
        return ""
    # Tách bỏ phần sau dấu |, –, -, , và lấy 2-4 từ đầu
    t = re.split(r"\s*[|–\-,]\s*", title)[0]
    t = re.sub(r"\s+", " ", t).strip()
    # Bỏ các cụm "chính hãng / giá tốt / dễ nhìn" cuối → giữ keyword chính
    t = re.sub(r"\s+(chính hãng|giá tốt|giá rẻ|cao cấp|chuyên nghiệp).*$", "", t, flags=re.IGNORECASE)
    if len(t) > ANCHOR_MAX_LEN:
        # Cắt theo từ
        words = t.split()
        cut = ""
        for w in words:
            if len(cut) + len(w) + 1 > ANCHOR_MAX_LEN:
                break
            cut = (cut + " " + w).strip() if cut else w
        t = cut
    return t


def _normalize_anchor_from_product_title(title: str, max_len: int = ANCHOR_MAX_LEN) -> str:
    """Rút keyword chính từ tên SP (max 30c) — KHÔNG để full tên SP làm anchor.

    Vd 'Thẻ nhớ MicroSD 64G TEAMGROUP Box Class10 U1 100MB/s'
    → 'thẻ nhớ MicroSD 64GB'.
    """
    if not title:
        return ""
    t = re.sub(r"\s+", " ", title).strip()
    if len(t) <= max_len:
        return t
    # Cắt theo từ — ưu tiên giữ 2-4 từ đầu
    words = t.split()
    cut = ""
    for w in words:
        if len(cut) + len(w) + 1 > max_len:
            break
        cut = (cut + " " + w).strip() if cut else w
    return cut or t[:max_len]


def _tokenize(text: str) -> set:
    if not text:
        return set()
    words = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    return {w for w in words if len(w) >= 3}


# ─── Layer 1: Same vendor + same product_type ───
def _query_same_vendor_type(handle: str, vendor: str, product_type: str, limit: int = 3) -> list:
    if not vendor or not product_type:
        return []
    conn = db.get_conn()
    rows = conn.execute(
        """SELECT handle, title FROM haravan_products
           WHERE vendor = ? AND product_type = ? AND handle != ? AND status = 'active'
           ORDER BY inventory_total DESC, RANDOM()
           LIMIT ?""",
        (vendor, product_type, handle, limit),
    ).fetchall()
    conn.close()
    return [
        {
            "url": f"{SITE_BASE}/products/{r['handle']}",
            "anchor": _normalize_anchor_from_product_title(r["title"]),
            "source": f"category_exact:{vendor}+{product_type}",
            "score": 30,
        }
        for r in rows if r["handle"]
    ]


# Slug chính cho từng product_type — match exact slug trong /collections/<slug>
PRODUCT_TYPE_TO_SLUGS = {
    "MÀN HÌNH": ["man-hinh-may-tinh", "man-hinh-gaming"],
    "LAPTOP": ["laptop", "laptop-gaming", "laptop-van-phong"],
    "CHUỘT": ["chuot-gaming", "chuot-may-tinh"],
    "BÀN PHÍM": ["ban-phim-co", "ban-phim-may-tinh"],
    "TAI NGHE": ["tai-nghe-gaming", "tai-nghe-may-tinh"],
    "PC": ["pc-gaming", "may-tinh-bo"],
    "MAINBOARD": ["mainboard"],
    "VGA": ["vga", "card-do-hoa"],
    "RAM": ["ram"],
    "SSD": ["ssd", "o-cung-ssd"],
    "NGUỒN": ["nguon", "nguon-may-tinh"],
    "TẢN NHIỆT": ["tan-nhiet"],
    "VỎ CASE": ["case", "vo-case"],
    "GHẾ GAMING": ["ghe-gaming"],
    "BÀN GAMING": ["ban-gaming"],
    "MICRO": ["micro"],
    "WEBCAM": ["webcam"],
}


# ─── Layer 2: Same product_type (different vendor) — link category collection ───
def _query_category_collection(product_type: str, limit: int = 3) -> list:
    """Tìm trang collection match exact slug của product_type."""
    if not product_type:
        return []
    key = product_type.upper().strip()
    slugs = PRODUCT_TYPE_TO_SLUGS.get(key, [])
    if not slugs:
        return []
    conn = db.get_conn()
    out = []
    for slug in slugs[:limit]:
        row = conn.execute(
            """SELECT url, title FROM seo_pages
               WHERE url LIKE ? AND title IS NOT NULL
                 AND (status_code IS NULL OR status_code < 400)
               LIMIT 1""",
            (f"%/collections/{slug}",),
        ).fetchone()
        if row:
            out.append({
                "url": row["url"],
                "anchor": _normalize_anchor_from_collection_title(row["title"]),
                "source": f"category_collection:{slug}",
                "score": 22,
            })
    conn.close()
    return out


# ─── Layer 3: Phụ kiện dùng kèm ───
def _query_accessory_collections(product_type: str, limit: int = 3) -> list:
    if not product_type:
        return []
    key = product_type.upper().strip()
    slugs = ACCESSORY_HINTS.get(key, [])
    if not slugs:
        return []
    conn = db.get_conn()
    out = []
    for slug in slugs[:limit]:
        row = conn.execute(
            "SELECT url, title FROM seo_pages WHERE url LIKE ? AND title IS NOT NULL LIMIT 1",
            (f"%/collections/{slug}",),
        ).fetchone()
        if row:
            out.append({
                "url": row["url"],
                "anchor": _normalize_anchor_from_collection_title(row["title"]),
                "source": f"accessory:{slug}",
                "score": 16,
            })
    conn.close()
    return out


# ─── Layer 4: Nhóm nhu cầu chung ───
def _query_demand_group_collections(limit: int = 2) -> list:
    conn = db.get_conn()
    out = []
    for grp in DEMAND_GROUPS[:limit]:
        row = conn.execute(
            "SELECT url, title FROM seo_pages WHERE url LIKE ? AND title IS NOT NULL LIMIT 1",
            (f"%/collections/{grp['slug']}",),
        ).fetchone()
        if row:
            out.append({
                "url": row["url"],
                "anchor": grp["anchor"],
                "source": f"demand:{grp['slug']}",
                "score": 10,
            })
    conn.close()
    return out


def suggest_internal_links(product_url: str, product_title: str = None,
                            vendor: str = None, product_type: str = None,
                            limit: int = MAX_SUGGESTIONS,
                            include_homepage_cta: bool = True) -> list:
    """Trả list link gợi ý theo priority (sort score giảm dần).

    Mỗi item: {url, anchor, source, score}.
    `include_homepage_cta=True` → luôn append Sintech homepage làm CTA intro/outro.
    """
    handle = _handle_from_url(product_url)
    if not handle:
        return ([SINTECH_HOME_LINK] if include_homepage_cta else [])
    if not vendor or not product_type or not product_title:
        conn = db.get_conn()
        row = conn.execute(
            "SELECT title, vendor, product_type FROM haravan_products WHERE handle = ?",
            (handle,),
        ).fetchone()
        conn.close()
        if row:
            product_title = product_title or row["title"]
            vendor = vendor or row["vendor"]
            product_type = product_type or row["product_type"]

    candidates = []
    candidates.extend(_query_same_vendor_type(handle, vendor or "", product_type or "", limit=3))
    candidates.extend(_query_category_collection(product_type or "", limit=3))
    candidates.extend(_query_accessory_collections(product_type or "", limit=3))
    candidates.extend(_query_demand_group_collections(limit=2))

    # Dedupe by url, giữ score cao nhất
    best = {}
    for c in candidates:
        if not c.get("url") or not c.get("anchor"):
            continue
        if c["url"] not in best or c["score"] > best[c["url"]]["score"]:
            best[c["url"]] = c
    out = sorted(best.values(), key=lambda x: -x["score"])[:limit]
    if include_homepage_cta:
        # Sintech homepage luôn có ở đầu (CTA intro/outro)
        out = [SINTECH_HOME_LINK] + [l for l in out if l["url"] != SINTECH_HOME_LINK["url"]]
    return out


def count_internal_links_in_html(html: str, site_base: str = SITE_BASE) -> int:
    """Đếm số <a href=...> trỏ về cùng site_base trong 1 đoạn HTML."""
    if not html:
        return 0
    base_host = urlparse(site_base).netloc
    count = 0
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
        href = m.group(1).strip()
        if href.startswith("#") or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        try:
            host = urlparse(href).netloc
        except Exception:
            continue
        if not host or host == base_host:
            count += 1
    return count
