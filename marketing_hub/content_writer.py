"""Pipeline gen content cho 1 SP (v2026-05-08).

Flow:
1. Fetch info SP từ haravan_products (vendor, type, body_html cũ).
2. Pre-compute suggested internal links theo priority rules.
3. Gọi `ai_writer.generate_blog_post()` — AI tự dùng list link gợi ý + viết theo rules
   v2026-05-08 (output có analysis_md + body_md với format `[**a**](u)`).
4. Convert body_md → HTML qua `markdown` lib — `[**anchor**](url)` tự render thành
   `<a href="url"><strong>anchor</strong></a>`, không cần inject post-hoc.
5. Save full payload vào content_jobs.
"""
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import markdown as md_lib
from bs4 import BeautifulSoup

import ai_writer
import db
import internal_links
import image_processor
import haravan_client
import keyword_research


# ─────────────── SINTECH INLINE STYLE (giống Past.txt mẫu) ───────────────
# Tất cả font Arial, color đen body, link đỏ thương hiệu #e74c3c.

_STYLE_H2 = "font-family:Arial,sans-serif;font-size:16pt;font-weight:700;color:#000000;line-height:1.38;margin-top:24px;margin-bottom:16px"
_STYLE_H3 = "font-family:Arial,sans-serif;font-size:14pt;font-weight:700;color:#434343;line-height:1.38;margin-top:21px;margin-bottom:16px"
_STYLE_P_BASE = "font-family:Arial,sans-serif;font-size:11pt;color:#000000;line-height:1.38;margin-bottom:16px"
_STYLE_LIST = "font-family:Arial,sans-serif;font-size:11pt;color:#000000;line-height:1.38;margin-bottom:16px;padding-left:24px"
_STYLE_LINK = "color:#e74c3c;font-weight:700;text-decoration:underline"
_STYLE_LINK_INNER_STRONG = "color:#e74c3c;font-weight:700;text-decoration:underline"
_STYLE_STRONG = "font-weight:700"
_STYLE_TABLE = "border-collapse:collapse;width:100%;margin:14px 0;font-size:11pt;font-family:Arial,sans-serif"
_STYLE_TH = "border:1px solid #cccccc;padding:8px 10px;vertical-align:top;color:#000000;font-family:Arial,sans-serif;font-weight:700;background:#f4f4f4;text-align:left"
_STYLE_TD = "border:1px solid #cccccc;padding:8px 10px;vertical-align:top;color:#000000;font-family:Arial,sans-serif"


def validate_body_md(body_md: str) -> list:
    """Check rule violations trong body Markdown. Trả list warnings (text)."""
    warnings = []
    if not body_md:
        return ["Body trống"]
    lines = body_md.split("\n")
    # 1. Cấm H1
    if any(re.match(r"^#\s+", l) for l in lines):
        warnings.append("Có heading H1 (cấm)")
    # 2. Cấm dùng 'anh' trong public content
    if re.search(r"\banh\b", body_md, flags=re.IGNORECASE):
        warnings.append("Có dùng từ 'anh' (rule public dùng 'bạn')")
    # 3. Cấm `---` separator
    if re.search(r"^---+\s*$", body_md, flags=re.MULTILINE):
        warnings.append("Có separator `---`")
    # 4. Mỗi H2 phải có ≥2 câu dẫn trước H3 con
    h2_indices = [i for i, l in enumerate(lines) if re.match(r"^##\s+", l)]
    for idx, h2_line_idx in enumerate(h2_indices):
        # Tìm H3 đầu tiên sau H2 này (trước H2 kế)
        next_h2_idx = h2_indices[idx + 1] if idx + 1 < len(h2_indices) else len(lines)
        between = lines[h2_line_idx + 1:next_h2_idx]
        first_h3_in_block = next((i for i, l in enumerate(between) if re.match(r"^###\s+", l)), None)
        if first_h3_in_block is not None:
            intro_block = "\n".join(between[:first_h3_in_block]).strip()
            sentence_count = len(re.findall(r"[.!?]\s+|[.!?]$", intro_block))
            if sentence_count < 2:
                h2_title = lines[h2_line_idx].strip("# ").strip()[:60]
                warnings.append(f"H2 '{h2_title}' thiếu đoạn dẫn ≥2 câu trước H3 (chỉ có {sentence_count} câu)")
    # 5. Cấm H2 'Kết lại / Tổng kết / Lời kết' trước outro
    forbidden_outro_h2 = ["kết lại", "tổng kết", "lời kết", "nhận định cuối", "tóm lại"]
    for l in lines:
        m = re.match(r"^##\s+(.+)", l)
        if m:
            t = m.group(1).strip().lower()
            if any(f in t for f in forbidden_outro_h2):
                warnings.append(f"Có H2 outro thừa: '{m.group(1).strip()}' (cấm — outro phải là <p>)")
    # 6. Internal link sai format **[anchor](url)**
    if re.search(r"\*\*\[[^\]]+\]\([^)]+\)\*\*", body_md):
        warnings.append("Có link sai format `**[a](u)**` — phải là `[**a**](u)`")
    # 7. Câu nguyên văn Sintech policy
    if "Sintech hiện công bố chính sách bán hàng, kiểm hàng, vận chuyển và trả góp 0% qua thẻ tín dụng" not in body_md:
        warnings.append("Thiếu nguyên văn câu chính sách Sintech (Vì sao mua tại Sintech)")
    # 8. Outro cụm mở
    outro_starts = ["tóm lại,", "nói ngắn gọn,", "sau tất cả,", "kết lại,"]
    if not any(s in body_md.lower() for s in outro_starts):
        warnings.append("Outro thiếu cụm mở 'Tóm lại,/Nói ngắn gọn,/Sau tất cả,/Kết lại,'")
    # 9. Cảnh báo cộc lốc — đếm câu mở "Bạn"
    bao_open_count = len(re.findall(r"^\s*\*?Bạn\b", body_md, flags=re.MULTILINE | re.IGNORECASE))
    p_count = len(re.findall(r"^\S", body_md, flags=re.MULTILINE))
    if p_count > 0 and bao_open_count > p_count * 0.4:
        warnings.append(f"Quá nhiều câu mở bằng 'Bạn...' ({bao_open_count}/{p_count}) — đa dạng connector hơn")
    # 10. Author signature ở cuối bài (rule mới — tăng trust)
    if "team kỹ thuật Sintech" not in body_md or "0911 713 000" not in body_md:
        warnings.append("Thiếu author signature cuối bài: 'Tư vấn cấu hình bởi team kỹ thuật Sintech — Hotline 0911 713 000 · 457 Trần Xuân Soạn, Q7, TP.HCM.'")
    # 11. FAQ section: mỗi câu hỏi PHẢI là H3
    faq_h2_match = re.search(r"^##\s+.*[Cc]âu hỏi\s+thường\s+gặp.*$", body_md, flags=re.MULTILINE)
    if faq_h2_match:
        # Cắt từ FAQ H2 đến H2 kế tiếp
        faq_start = faq_h2_match.start()
        next_h2 = re.search(r"^##\s+", body_md[faq_h2_match.end():], flags=re.MULTILINE)
        faq_block = body_md[faq_h2_match.end():faq_h2_match.end() + (next_h2.start() if next_h2 else len(body_md))]
        h3_count = len(re.findall(r"^###\s+", faq_block, flags=re.MULTILINE))
        # Đếm câu hỏi paragraph (không phải H3) — kết thúc bằng "?"
        question_para_count = len(re.findall(r"^[^\s#].*\?\s*$", faq_block, flags=re.MULTILINE))
        if h3_count < 3:
            warnings.append(f"FAQ chỉ có {h3_count} H3 — mỗi câu hỏi PHẢI là H3 (### câu hỏi?), nên có 4-6 H3")
        if question_para_count > 1 and h3_count < question_para_count:
            warnings.append(f"FAQ có {question_para_count} câu hỏi paragraph thường (không phải H3) — sửa thành ### câu hỏi?")
    return warnings


def validate_titles_metas(titles: list, metas: list) -> list:
    """Check length rules cho title (45-61c) + meta (140-160c)."""
    warnings = []
    for i, t in enumerate(titles or []):
        n = len(t)
        if n < 45:
            warnings.append(f"Title #{i+1} ngắn ({n}c, cần ≥45)")
        elif n > 61:
            warnings.append(f"Title #{i+1} dài ({n}c, max 61)")
    for i, m in enumerate(metas or []):
        n = len(m)
        if n < 140:
            warnings.append(f"Meta #{i+1} ngắn ({n}c, cần ≥140)")
        elif n > 160:
            warnings.append(f"Meta #{i+1} dài ({n}c, max 160)")
    return warnings


def apply_sintech_style(html: str) -> str:
    """Wrap inline style chuẩn Sintech (Arial + size pt + color + margin) cho mỗi
    heading / paragraph / list / link trong HTML output từ markdown lib.
    """
    if not html:
        return html
    soup = BeautifulSoup(html, "html.parser")

    for h2 in soup.find_all("h2"):
        h2["style"] = _STYLE_H2
    for h3 in soup.find_all("h3"):
        h3["style"] = _STYLE_H3
    for p in soup.find_all("p"):
        # Paragraph chỉ chứa <img> → center align
        has_only_img = bool(p.find("img")) and not p.get_text(strip=True)
        if has_only_img:
            p["style"] = f"{_STYLE_P_BASE};text-align:center"
            continue
        existing = (p.get("style") or "").strip()
        if "text-align" in existing:
            p["style"] = f"{_STYLE_P_BASE};{existing}"
        else:
            p["style"] = _STYLE_P_BASE
    for ul in soup.find_all(["ul", "ol"]):
        ul["style"] = _STYLE_LIST
    for li in soup.find_all("li"):
        li["style"] = "margin-bottom:6px"
    for a in soup.find_all("a"):
        a["style"] = _STYLE_LINK
        # Force màu đỏ + underline + bold cho <strong> bên trong link
        for inner_strong in a.find_all("strong"):
            inner_strong["style"] = _STYLE_LINK_INNER_STRONG
    # Strong ngoài link: bold default
    for strong in soup.find_all("strong"):
        if not strong.get("style"):
            strong["style"] = _STYLE_STRONG
    # Bảng trong mô tả: theme Haravan KHÔNG tự style → phải inline viền/padding
    for table in soup.find_all("table"):
        table["style"] = _STYLE_TABLE
    for th in soup.find_all("th"):
        th["style"] = _STYLE_TH
    for td in soup.find_all("td"):
        td["style"] = _STYLE_TD

    return str(soup)


def _get_product_image_urls(handle: str, max_count: int = 10) -> list:
    """Lấy URL ảnh SP từ haravan_products.images JSON. Trả max N url đầu (default 10)."""
    if not handle:
        return []
    conn = db.get_conn()
    row = conn.execute(
        "SELECT images FROM haravan_products WHERE handle = ?", (handle,),
    ).fetchone()
    conn.close()
    if not row or not row["images"]:
        return []
    try:
        imgs = json.loads(row["images"])
    except Exception:
        return []
    out = []
    for img in imgs[:max_count]:
        src = None
        if isinstance(img, dict):
            src = img.get("src") or img.get("url")
        elif isinstance(img, str):
            src = img
        if src:
            out.append(src)
    return out


def pick_target_image_count(num_available: int, num_h2_body: int) -> int:
    """Số ảnh cần chèn theo rule vợ chốt 2026-05-10:

    - SP có ≤ 4 ảnh → dùng HẾT (không bỏ ảnh nào)
    - SP có ≥ 5 ảnh → lấy 4-6 ảnh đầu, scale theo số H2 chính trong body:
        + ≤4 H2 → 4 ảnh
        + 5-6 H2 → 5 ảnh
        + ≥7 H2 → 6 ảnh

    `num_h2_body` là tổng số H2 trong body (anh đã trừ H2 'Vì sao Sintech' + 'Câu hỏi thường gặp'
    trước khi truyền vào, vì 2 section đó không insert ảnh chính).
    """
    if num_available <= 0:
        return 0
    if num_available <= 4:
        return num_available
    # ≥5 ảnh sẵn → cap 4-6 tùy heading
    if num_h2_body <= 4:
        return 4
    if num_h2_body <= 6:
        return 5
    return 6


def _clean_product_name(name: str, max_len: int = 70) -> str:
    """Rút gọn tên SP cho ALT: bỏ ký tự đặc biệt, normalize space, truncate."""
    if not name:
        return ""
    # Bỏ phần trong ngoặc đơn cuối tên (thường chứa spec dài)
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    # Replace ký tự đặc biệt
    cleaned = re.sub(r"[/'\"\\|]", " ", cleaned)
    cleaned = re.sub(r"[(){}\[\]]", " ", cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Truncate
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rsplit(" ", 1)[0]
    return cleaned


# ALT templates theo vị trí ảnh trong bài (rules section 18)
_ALT_TEMPLATES = {
    1: "{name}",  # hero shot
    2: "{name} cận cảnh chi tiết",
    3: "{name} trên setup PC gọn",
    4: "{name} cổng kết nối và spec",
    5: "{name} cho dân build PC gaming",
    6: "{name} chính hãng tại Sintech",
}


def _gen_alt_for_position(product_name_clean: str, position: int, total: int) -> str:
    """Gen alt cho ảnh vị trí thứ N (1-indexed). Tổng ảnh = total.

    Position 1 = hero, Position cuối = closing Sintech (nếu total ≥ 2).
    Length 50-125c — truncate nếu dài, pad nếu ngắn.
    """
    if not product_name_clean:
        return f"Sản phẩm tại Sintech ảnh {position}"
    # Closing image luôn có "chính hãng tại Sintech" (vị trí cuối)
    if position == total and total >= 2:
        tpl = _ALT_TEMPLATES[6]
    elif position in _ALT_TEMPLATES:
        tpl = _ALT_TEMPLATES[position]
    else:
        # Fallback cho vị trí > 6 (hiếm gặp)
        tpl = "{name} chi tiết " + str(position)

    alt = tpl.format(name=product_name_clean)
    # Length guards: max 125c
    if len(alt) > 125:
        alt = alt[:125].rsplit(" ", 1)[0]
    return alt


IMAGES_LOCAL_DIR = Path(__file__).parent / "data" / "images"


def upload_local_images_in_body_to_haravan(body_html: str) -> str:
    """Scan body_html tìm URL `/local-images/<handle>/<file>` → upload Haravan asset_storage → replace URL CDN.

    Gọi NGAY TRƯỚC khi sync 1 bài lên Haravan. Sequential upload (KHÔNG parallel)
    → tránh race condition tạo SP rác.

    Returns: body_html mới với URL CDN Haravan thay cho /local-images/...
    """
    if not body_html:
        return body_html

    # Match cả relative URL và absolute URL chứa /local-images/
    pattern = re.compile(r'(https?://[^/]+)?(/local-images/([^/"\'\s>]+)/([^"\'\s>?]+))')
    matches = list(pattern.finditer(body_html))
    if not matches:
        return body_html

    # Build map: local_url → cdn_url (chỉ upload 1 lần / URL)
    url_map = {}
    for m in matches:
        local_url = m.group(2)  # /local-images/<handle>/<file>
        if local_url in url_map:
            continue
        handle = m.group(3)
        filename = m.group(4)
        local_path = IMAGES_LOCAL_DIR / handle / filename
        if not local_path.exists():
            print(f"[sync-img] SKIP {local_url}: file local không tồn tại")
            continue
        try:
            img_bytes = local_path.read_bytes()
            # ALT từ filename (img_N.jpg → vị trí N)
            alt = f"{handle} {filename}"
            cdn_url = haravan_client.upload_to_asset_storage(
                img_bytes, filename=f"{handle[:60]}_{filename}", alt=alt,
            )
            url_map[local_url] = cdn_url
            print(f"[sync-img] {local_url} → {cdn_url[:60]}...")
        except Exception as e:
            print(f"[sync-img] FAIL {local_url}: {e}")
            # Không replace → giữ local URL (sẽ broken trên website nhưng KHÔNG fail sync)

    # Replace tất cả occurrences trong body_html
    out = body_html
    for local_url, cdn_url in url_map.items():
        # Replace cả relative và absolute (vd `http://127.0.0.1:5055/local-images/...`)
        out = out.replace(local_url, cdn_url)
    return out


def _to_grande_url(src: str) -> str:
    """Haravan CDN: foo.png → foo_grande.png (size 600x600).
    Chỉ áp dụng cho .jpg/.jpeg/.png/.webp/.gif (CDN support resize).
    Các extension khác (.jfif/.bmp/.tiff...) giữ nguyên URL gốc — inline CSS
    600x388 vẫn ép kích thước hiển thị trong body.
    """
    return re.sub(
        r"\.(jpg|jpeg|png|webp|gif)(\?.*)?$",
        r"_grande.\1\2",
        src, count=1, flags=re.IGNORECASE,
    )


def process_and_upload_images(handle: str, product_title: str, max_count: int = 2) -> list:
    """REFACTOR 2026-05-13: dùng URL ảnh CDN GỐC của SP + suffix _grande.

    Bỏ download/resize/upload storage hoàn toàn. Lấy URL có sẵn từ
    haravan_products.images JSON → transform thành size _grande (600x600).
    Inline CSS 600x388 (object-fit:contain + white bg) apply trong
    insert_images_into_body_md để khớp spec Sintech.

    Lợi ích:
      - 0 slot storage SP tốn (trước ~4 ảnh/SP)
      - Skip download + resize + upload → nhanh hơn 10x
      - Tận dụng CDN Haravan có sẵn

    ALT theo template rule mục 18 — đa dạng theo vị trí ảnh.
    """
    src_urls = _get_product_image_urls(handle, max_count=max_count)
    if not src_urls:
        return []

    name_clean = _clean_product_name(product_title)
    total = len(src_urls)
    out = []
    for i, src in enumerate(src_urls, 1):
        grande_url = _to_grande_url(src)
        alt = _gen_alt_for_position(name_clean, i, total)
        out.append({"url_cdn": grande_url, "alt": alt})
    return out


_SKIP_H2_PATTERNS = [
    re.compile(r"v[ìi].*sao.*sintech", re.IGNORECASE),
    re.compile(r"câu\s*h[ỏo]i.*th[ưuờơ]ng\s*g[ặa]p", re.IGNORECASE),
    re.compile(r"\bFAQ\b", re.IGNORECASE),
    re.compile(r"^\s*c[âa]u\s*h[ỏo]i", re.IGNORECASE),
]


def _is_main_h2(heading_text: str) -> bool:
    """H2 'chính' (được phép chèn ảnh): KHÔNG phải 'Vì sao Sintech' / 'FAQ' / 'Câu hỏi thường gặp'."""
    txt = heading_text.strip()
    for pat in _SKIP_H2_PATTERNS:
        if pat.search(txt):
            return False
    return True


def count_main_h2(body_md: str) -> int:
    """Đếm số H2 'chính' trong body (trừ H2 đầu tên SP, 'Vì sao Sintech', FAQ)."""
    if not body_md:
        return 0
    h2_lines = re.findall(r"^##\s+(.+)$", body_md, flags=re.MULTILINE)
    if len(h2_lines) <= 1:
        return 0
    # H2 đầu là tên SP — skip. Các H2 còn lại lọc theo _is_main_h2.
    return sum(1 for h in h2_lines[1:] if _is_main_h2(h))


_IMG_INLINE_STYLE = (
    "width:100%;max-width:600px;height:388px;object-fit:contain;"
    "background:#fff;display:block;margin:16px auto"
)

_STRIP_IMG_PATTERNS = [
    re.compile(r"!\[[^\]]*\]\([^)]+\)\s*"),                     # Markdown ![alt](url)
    re.compile(r"<img\s+[^>]*?/?>\s*", re.IGNORECASE),           # HTML <img ... />
    re.compile(r"<p[^>]*>\s*(?:&nbsp;|\s)*</p>", re.IGNORECASE), # empty <p> sau khi strip img
]


def _strip_existing_images(body_md: str) -> str:
    """Xóa hết ảnh có sẵn trong body_md (Markdown + HTML img tags) trước khi insert ảnh mới.
    Tránh trùng ảnh khi re-process pattern khác nhau.
    """
    out = body_md
    for pat in _STRIP_IMG_PATTERNS:
        out = pat.sub("", out)
    # Dọn dòng trống dư
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def insert_images_into_body_md(body_md: str, images: list) -> str:
    """Chèn N ảnh vào body_md, phân bổ qua nhiều H2 chính.

    Logic (v2026-05-10):
      - Ảnh 1: sau intro paragraph (sau H2 đầu = tên SP)
      - Ảnh 2..N-1: phân bổ đều sau các H2 chính (KHÔNG sau 'Vì sao Sintech', 'FAQ')
      - Ảnh cuối (nếu còn): sau H2 'Vì sao Sintech' (giữ behavior cũ — closing visual)

    REFACTOR 2026-05-13: output HTML <img> với inline CSS 600x388
    (object-fit:contain + white bg) thay vì Markdown — để ép kích thước
    đồng nhất khớp spec Sintech mà KHÔNG cần upload/resize.

    FIX 2026-05-13: STRIP ảnh cũ trong body_md trước khi insert — tránh
    trùng ảnh khi re-process (ai_body_md có thể chứa ![alt](url) từ Codex gen).
    """
    if not body_md or not images:
        return body_md

    # Xóa ảnh có sẵn trong body_md trước
    body_md = _strip_existing_images(body_md)

    img_strings = [
        f'<img src="{img["url_cdn"]}" alt="{img["alt"]}" style="{_IMG_INLINE_STYLE}" />'
        for img in images
    ]
    n_img = len(img_strings)
    if n_img == 0:
        return body_md

    # Tách body theo H2 sections để tìm vị trí chèn
    # Mỗi section bắt đầu bằng "## " và kết thúc trước "## " kế hoặc EOF
    h2_re = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    h2_matches = list(h2_re.finditer(body_md))
    if not h2_matches:
        return body_md  # không có H2 → không biết chèn vào đâu

    # Phân loại H2:
    #   index 0 = H2 đầu (tên SP) → ảnh đầu chèn vào intro của section này
    #   index 1..N = các H2 còn lại → main_h2 hoặc skip_h2
    main_h2_indices = []  # H2 chính được phép chèn ảnh
    sintech_h2_idx = None  # 'Vì sao Sintech' → ảnh closing
    for idx, m in enumerate(h2_matches):
        if idx == 0:
            continue
        title = m.group(1).strip()
        if re.search(r"v[ìi].*sao.*sintech", title, re.IGNORECASE):
            sintech_h2_idx = idx
        elif _is_main_h2(title):
            main_h2_indices.append(idx)

    # Chia số ảnh:
    #   1 ảnh: chỉ intro
    #   2 ảnh: intro + sintech (giống behavior cũ)
    #   3+ ảnh: intro + N-2 ảnh phân bổ qua main H2 + 1 ảnh sintech (nếu có)
    insert_at_h2_idx = []  # list (h2_index_to_insert_AFTER, img_idx)
    img_pos = 0

    # Ảnh 1: intro (sau H2 đầu, chèn cuối intro paragraph)
    insert_at_intro = (n_img >= 1)
    if insert_at_intro:
        img_pos = 1

    # Ảnh cuối: sintech (chỉ nếu có ≥2 ảnh và có Sintech H2)
    has_sintech_img = (n_img >= 2 and sintech_h2_idx is not None)
    n_middle = n_img - (1 if insert_at_intro else 0) - (1 if has_sintech_img else 0)

    # Phân bổ ảnh giữa cho các main H2 — SKIP H2 đầu tiên sau intro để tránh ảnh sát ảnh intro
    candidate_h2 = main_h2_indices[1:] if len(main_h2_indices) > 1 else main_h2_indices
    if n_middle > 0 and candidate_h2:
        if n_middle >= len(candidate_h2):
            for h2_i in candidate_h2[:n_middle]:
                insert_at_h2_idx.append((h2_i, img_pos))
                img_pos += 1
        else:
            step = len(candidate_h2) / n_middle
            for k in range(n_middle):
                h2_i = candidate_h2[int(k * step)]
                insert_at_h2_idx.append((h2_i, img_pos))
                img_pos += 1

    # Build offset list
    inserts = []

    # Intro img: cuối paragraph intro (sau H2 đầu, trước H2 thứ 2)
    if insert_at_intro:
        h2_first = h2_matches[0]
        section_end = h2_matches[1].start() if len(h2_matches) > 1 else len(body_md)
        section_text = body_md[h2_first.end():section_end]
        # Skip leading whitespace
        para_start_offset = 0
        for line in section_text.split("\n"):
            if line.strip():
                break
            para_start_offset += len(line) + 1
        # Scan đến dòng trống / heading
        rest = section_text[para_start_offset:]
        para_end_offset = para_start_offset
        for line in rest.split("\n"):
            if not line.strip() or line.lstrip().startswith("#"):
                break
            para_end_offset += len(line) + 1
        insert_pos = h2_first.end() + para_end_offset
        inserts.append((insert_pos, 0))

    # Middle imgs: chèn CUỐI SECTION của H2 chính đó (trước H2 kế tiếp = cuối content section)
    for h2_i, img_idx in insert_at_h2_idx:
        # Vị trí cuối section = start của H2 kế tiếp (hoặc EOF)
        if h2_i + 1 < len(h2_matches):
            section_end = h2_matches[h2_i + 1].start()
        else:
            section_end = len(body_md)
        inserts.append((section_end, img_idx))

    # Closing img: cuối section "Vì sao Sintech"
    if has_sintech_img:
        section_end = (
            h2_matches[sintech_h2_idx + 1].start()
            if sintech_h2_idx + 1 < len(h2_matches)
            else len(body_md)
        )
        inserts.append((section_end, n_img - 1))

    # Apply inserts theo thứ tự offset giảm dần để không lệch
    inserts.sort(key=lambda x: -x[0])
    out = body_md
    for pos, img_idx in inserts:
        before = out[:pos].rstrip()
        after = out[pos:].lstrip()
        out = before + "\n\n" + img_strings[img_idx] + "\n\n" + after
    return out


def _fetch_product_info(product_url: str) -> dict:
    handle = internal_links._handle_from_url(product_url)
    if not handle:
        return {}
    conn = db.get_conn()
    row = conn.execute(
        """SELECT haravan_id, handle, title, vendor, product_type, body_html
           FROM haravan_products WHERE handle = ?""",
        (handle,),
    ).fetchone()
    conn.close()
    return dict(row) if row else {}


def _strip_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def build_spec_block_for_specs(product_name: str, web_specs: list, vendor: str = "",
                               body_text: str = "") -> str:
    """Tạo khối <blockquote> thông số kỹ thuật từ web_specs. Rỗng nếu fail.
    KHÔNG đưa Tình trạng/Bảo hành vào bảng (đã bỏ theo yêu cầu)."""
    try:
        import spec_block
        if not web_specs:
            return ""
        return spec_block.build_spec_blockquote(product_name, web_specs, brand=vendor)
    except Exception as e:
        print(f"[spec_block skip] {e}")
        return ""


def md_to_html(text: str) -> str:
    """Convert Markdown body → HTML cho Haravan body_html.

    Markdown lib tự render `[**anchor**](url)` thành
    `<a href="url"><strong>anchor</strong></a>` — đúng format Sintech yêu cầu.
    """
    if not text:
        return ""
    return md_lib.markdown(
        text,
        extensions=["extra", "sane_lists", "tables", "nl2br"],
        output_format="html5",
    )


def gen_text_phase(job_id: int) -> dict:
    """Phase 1 — chỉ AI gen text (không process ảnh). Save status=text_done.

    Phase này tốn thời gian dài (~90s) do gọi Codex CLI. Sau khi xong, image worker
    sẽ pickup job ở status `text_done` để xử lý ảnh.

    Special return: nếu rate limit hit → trả {"ok": False, "rate_limit": True} để
    worker pause; job được reset về `pending` (không phải `failed`) để retry sau.
    """
    import codex_provider
    job = db.content_job_get(job_id)
    if not job:
        return {"ok": False, "error": "Job không tồn tại"}

    db.content_job_update(job_id, status="drafting", error=None)

    try:
        info = _fetch_product_info(job["product_url"])
        product_name = info.get("title") or job.get("product_title") or ""
        if not product_name:
            raise RuntimeError("Không tìm thấy thông tin sản phẩm — handle không match haravan_products.")
        product_type = info.get("product_type") or job.get("product_type") or ""
        vendor = info.get("vendor") or job.get("vendor") or ""
        existing_text = _strip_html(info.get("body_html") or "")[:2000]

        # Pre-compute suggested links
        suggestions = internal_links.suggest_internal_links(
            job["product_url"],
            product_title=product_name,
            vendor=vendor,
            product_type=product_type,
            limit=8,
            include_homepage_cta=True,
        )

        # Pick template round-robin (fallback nếu research fail)
        template_id = ai_writer.pick_template(job_id)

        # 🔍 Phase 2: Real keyword research từ Google Suggest VN
        kr_data = {}
        try:
            kr_data = keyword_research.research_keyword_for_product(
                product_name, vendor, product_type,
            )
        except Exception as e:
            print(f"[keyword research skip] {e}")

        # Money product detection: ưu tiên flag DB nếu vợ tick, fallback auto-detect
        is_money_db = bool(job.get("is_money_product"))
        is_money_auto = ai_writer.detect_money_product(product_name, product_type, vendor)
        is_money = is_money_db or is_money_auto
        # Persist auto-detect flag nếu DB chưa tick — vợ thấy được auto đoán
        if is_money_auto and not is_money_db:
            db.content_job_update(job_id, is_money_product=1)

        # 🔧 Web spec research (Serper) — bổ sung THÔNG SỐ THẬT để AI gen chuẩn spec/chức năng.
        # Gộp body_html gốc (ưu tiên) + spec cào từ web. Lỗi/không key → bỏ qua, job vẫn chạy.
        web_spec_text = ""
        web_spec_source = ""
        web_raw_specs = []
        spec_conflicts = []
        try:
            import serper_search
            if serper_search.is_serper_available():
                _sp = serper_search.fetch_product_specs(f"{product_name} thông số")
                if _sp.get("ok"):
                    web_spec_text = _sp.get("specs_text", "")
                    web_spec_source = _sp.get("source_url", "")
                    web_raw_specs = _sp.get("specs", [])
                    # So spec gốc (mô tả Haravan) vs spec web → flag lệch cho vợ verify
                    if web_raw_specs and existing_text:
                        spec_conflicts = serper_search.detect_spec_conflicts(existing_text, web_raw_specs)
        except Exception as e:
            print(f"[web spec research skip] {e}")

        _spec_parts = []
        if existing_text:
            _spec_parts.append(existing_text)
        if web_spec_text:
            _spec_parts.append(f"[Thông số tra cứu từ web — {web_spec_source}]:\n{web_spec_text}")
        combined_specs = "\n\n".join(_spec_parts).strip()

        # 🔍 Research ĐỐI THỦ (SERP) — cào heading top results để hiểu nhu cầu khách
        # + tìm khoảng trống nội dung. CHỈ để tham khảo, prompt cấm copy cấu trúc/câu chữ.
        competitor_headings = ""
        try:
            import serper_search
            if serper_search.is_serper_available():
                _rc = serper_search.research_competitor_headings(product_name, max_urls=3)
                if _rc.get("ok"):
                    competitor_headings = _rc.get("competitor_headings_text", "")
        except Exception as e:
            print(f"[competitor research skip] {e}")

        product_info = {
            "product_name": product_name,
            "product_type": product_type,
            "vendor": vendor,
            "specs": combined_specs or "(SP chưa có mô tả — viết dựa trên tên SP)",
            "suggested_links": suggestions,
            "template_id": template_id,
            "keyword_research": kr_data,
            "competitor_headings": competitor_headings,
            "is_money_product": is_money,
        }
        ai_result = ai_writer.generate_blog_post(product_info)

        # Auto-fix meta sai length (140-160c) — quick suffix + AI regen tối đa 2 lần
        fixed_metas, fix_info = ai_writer.auto_fix_metas(product_info, ai_result["metas"], max_retries=2)
        ai_result["metas"] = fixed_metas
        if fix_info.get("fixed_by"):
            print(f"[auto_fix_metas job {job_id}] {fix_info}")

        # Validate text-only (chưa có ảnh)
        warnings = validate_body_md(ai_result["body_markdown"])
        warnings.extend(validate_titles_metas(ai_result["titles"], ai_result["metas"]))

        # Convert MD → HTML preview (chưa inject ảnh — ảnh worker thêm sau)
        body_html_preview = apply_sintech_style(md_to_html(ai_result["body_markdown"]))

        # 🔖 Khối thông số kỹ thuật <blockquote> cuối bài — theme Sintech tự render thành BẢNG.
        # Dùng web_raw_specs (đã cào) + dữ liệu xác minh; raw (không style) để theme tự xử lý.
        _spec_bq = build_spec_block_for_specs(product_name, web_raw_specs, vendor=vendor,
                                              body_text=existing_text)
        if _spec_bq:
            body_html_preview = body_html_preview.rstrip() + "\n" + _spec_bq

        db.content_job_update(
            job_id,
            haravan_id=info.get("haravan_id"),
            handle=info.get("handle"),
            product_title=product_name,
            vendor=vendor,
            product_type=product_type,
            ai_analysis_md=ai_result.get("analysis_md") or "",
            ai_titles_json=json.dumps(ai_result["titles"], ensure_ascii=False),
            ai_metas_json=json.dumps(ai_result["metas"], ensure_ascii=False),
            ai_keywords=ai_result["keywords"],
            ai_outline=ai_result.get("outline_md") or "",
            ai_body_md=ai_result["body_markdown"],
            ai_body_html=body_html_preview,
            internal_links_json=json.dumps(suggestions, ensure_ascii=False),
            ai_stats_json=json.dumps({
                **ai_result["stats"],
                "web_spec_source": web_spec_source or None,
                "spec_conflicts": spec_conflicts or None,
                "keyword_research": {
                    "core_keywords": kr_data.get("core_keywords", []),
                    "raw_count": len(kr_data.get("raw_suggestions", [])),
                    "top_questions": kr_data.get("top_questions", [])[:8],
                    "intent_summary": {k: len(v) for k, v in (kr_data.get("by_intent") or {}).items() if v},
                } if kr_data else None,
            }, ensure_ascii=False),
            spec_conflict_json=(json.dumps(spec_conflicts, ensure_ascii=False) if spec_conflicts else None),
            ai_generated_at=datetime.now().isoformat(timespec="seconds"),
            selected_title_idx=0,
            selected_meta_idx=0,
            edited_title=(ai_result["titles"][0] if ai_result["titles"] else ""),
            edited_meta=(ai_result["metas"][0] if ai_result["metas"] else ""),
            edited_body_html=body_html_preview,
            status="text_done",
            error=(" / ".join(warnings))[:500] if warnings else None,
        )
        return {"ok": True}
    except codex_provider.CodexRateLimitError as e:
        # Rate limit → reset job về pending (không phải failed) để retry sau khi quota reset
        db.content_job_update(job_id, status="pending", error=None)
        return {"ok": False, "rate_limit": True, "error": str(e)[:500]}
    except Exception as e:
        # Detect rate-limit: AIQuotaError (mọi provider cạn) hoặc substring
        msg = str(e)
        try:
            import ai_provider
            _is_quota = isinstance(e, ai_provider.AIQuotaError)
        except Exception:
            _is_quota = False
        if _is_quota or codex_provider._is_rate_limit_message(msg):
            db.content_job_update(job_id, status="pending", error=None)
            return {"ok": False, "rate_limit": True, "error": msg[:500]}
        db.content_job_update(job_id, status="failed", error=f"text_phase {e.__class__.__name__}: {e}"[:500])
        return {"ok": False, "error": str(e)[:500]}


def process_images_phase(job_id: int) -> dict:
    """Phase 2 — fetch + process + upload 2 ảnh, inject vào body. Status=draft.

    Pickup job đang ở status `text_done`. Nếu không có handle hoặc không có ảnh,
    vẫn complete với status=draft (chỉ thiếu ảnh).
    """
    job = db.content_job_get(job_id)
    if not job:
        return {"ok": False, "error": "Job không tồn tại"}

    db.content_job_update(job_id, status="drafting")  # đánh dấu image worker đang xử lý

    try:
        body_md_orig = job.get("ai_body_md") or ""
        handle = job.get("handle") or ""
        product_name = job.get("product_title") or ""

        images_uploaded = []
        try:
            # Dynamic image count: ≤4 ảnh → lấy hết; ≥5 ảnh → 4-6 tùy số H2
            available_urls = _get_product_image_urls(handle, max_count=10)
            num_main_h2 = count_main_h2(body_md_orig)
            target_count = pick_target_image_count(len(available_urls), num_main_h2)
            print(f"[image phase job {job_id}] avail={len(available_urls)} main_h2={num_main_h2} target={target_count}")
            if target_count > 0:
                images_uploaded = process_and_upload_images(handle, product_name, max_count=target_count)
        except Exception as e:
            print(f"[image phase skip] {e}")

        body_md_with_images = insert_images_into_body_md(body_md_orig, images_uploaded)
        body_html = apply_sintech_style(md_to_html(body_md_with_images))

        # Update ai_stats_json gộp images_uploaded
        try:
            stats = json.loads(job.get("ai_stats_json") or "{}")
        except Exception:
            stats = {}
        stats["images_uploaded"] = images_uploaded

        db.content_job_update(
            job_id,
            # KHÔNG update ai_body_md (giữ raw text không ảnh để re-run image phase chuẩn)
            ai_body_html=body_html,
            edited_body_html=body_html,
            ai_stats_json=json.dumps(stats, ensure_ascii=False),
            status="draft",
            # Không reset error — giữ warnings từ phase 1
        )
        return {"ok": True, "images_count": len(images_uploaded)}
    except Exception as e:
        db.content_job_update(job_id, status="failed", error=f"image_phase {e.__class__.__name__}: {e}"[:500])
        return {"ok": False, "error": str(e)[:500]}


# Backward compat: gọi đầy đủ 2 phase tuần tự (chỉ dùng cho debug/manual)
def generate_content_for_job(job_id: int) -> dict:
    res1 = gen_text_phase(job_id)
    if not res1["ok"]:
        return {"ok": False, "error": res1["error"], "payload": None}
    res2 = process_images_phase(job_id)
    if not res2["ok"]:
        return {"ok": False, "error": res2["error"], "payload": None}
    return {"ok": True, "error": None, "payload": db.content_job_get(job_id)}


# ─────────────────────────── DUAL WORKER QUEUE (parallel pipeline) ───────────────────────────
#
# 2 worker thread chạy song song để tăng throughput:
#   - Text Worker: pop status=pending → gen_text_phase → status=text_done
#   - Image Worker: pop status=text_done → process_images_phase → status=draft
#
# Pipeline:
#   T=0   T=90  T=120  T=180  T=210
#   Bài 1: [text_____][img__]
#   Bài 2:            [text_____][img__]
# → throughput tăng từ ~1 bài/150s → 1 bài/90s (+67%).
#
# State machine:
#   pending → drafting (text_worker) → text_done → drafting (image_worker) → draft
#   (Status `drafting` dùng chung cho cả 2 phase — phân biệt qua DB query.)

_text_state = {
    "running": False, "should_stop": False,
    "current_job_id": None, "current_job_url": "",
    "current_started_at": None,
    "completed": 0, "failed": 0,
    "started_at": None, "last_message": "",
}
_image_state = {
    "running": False, "should_stop": False,
    "current_job_id": None, "current_job_url": "",
    "current_started_at": None,
    "completed": 0, "failed": 0,
    "started_at": None, "last_message": "",
}
_text_lock = threading.Lock()
_image_lock = threading.Lock()
WORKER_SLEEP_BETWEEN = 3


def queue_state() -> dict:
    """Snapshot state cả 2 worker + count pending/text_done jobs."""
    with _text_lock:
        text_snap = dict(_text_state)
    with _image_lock:
        image_snap = dict(_image_state)
    pending = len(db.content_jobs_list(status="pending", limit=10000))
    text_done = len(db.content_jobs_list(status="text_done", limit=10000))
    with _prewarmer_lock:
        prewarmer_snap = dict(_prewarmer_state)
    return {
        # Backward-compat fields
        "running": text_snap["running"] or image_snap["running"],
        "should_stop": text_snap["should_stop"] and image_snap["should_stop"],
        "current_job_id": text_snap["current_job_id"] or image_snap["current_job_id"],
        "current_job_url": text_snap["current_job_url"] or image_snap["current_job_url"],
        "current_started_at": text_snap["current_started_at"] or image_snap["current_started_at"],
        "completed": text_snap["completed"] + image_snap["completed"],
        "failed": text_snap["failed"] + image_snap["failed"],
        "started_at": text_snap["started_at"] or image_snap["started_at"],
        "last_message": text_snap["last_message"] or image_snap["last_message"],
        # Detailed
        "text_worker": text_snap,
        "image_worker": image_snap,
        "prewarmer": prewarmer_snap,
        "pending_in_db": pending,
        "text_done_in_db": text_done,
    }


def _set_text_state(**kw):
    with _text_lock:
        _text_state.update(kw)


def _set_image_state(**kw):
    with _image_lock:
        _image_state.update(kw)


def _next_job_by_status(status: str):
    rows = db.content_jobs_list(status=status, limit=1)
    return rows[0]["id"] if rows else None


def _text_worker_loop():
    """Pop status=pending → gen text phase → status=text_done."""
    _set_text_state(
        running=True, should_stop=False, completed=0, failed=0,
        started_at=datetime.now().isoformat(timespec="seconds"),
        last_message="Text worker started.",
    )
    try:
        while True:
            with _text_lock:
                if _text_state["should_stop"]:
                    _set_text_state(last_message="Text worker dừng theo lệnh.")
                    break
            job_id = _next_job_by_status("pending")
            if not job_id:
                # Idle — đợi 10s xem có job mới đẩy vào không
                _set_text_state(last_message="Idle — chờ pending mới...", current_job_id=None)
                time.sleep(10)
                # Check again
                if not _next_job_by_status("pending"):
                    _set_text_state(last_message="Hết pending — text worker stop.")
                    break
                continue
            job = db.content_job_get(job_id)
            url = (job.get("product_url") if job else "") or ""
            _set_text_state(
                current_job_id=job_id, current_job_url=url,
                current_started_at=datetime.now().isoformat(timespec="seconds"),
                last_message=f"Gen text job #{job_id}: {url[:80]}",
            )
            try:
                res = gen_text_phase(job_id)
                with _text_lock:
                    if res["ok"]:
                        _text_state["completed"] += 1
                    elif res.get("rate_limit"):
                        # Rate limit hit — pause worker, đợi quota reset
                        _text_state["last_message"] = (
                            f"⏸️ RATE LIMIT! Quota Codex Plus hết. Worker auto-pause. "
                            f"Job #{job_id} → reset về pending. Bấm Stop và đợi reset."
                        )
                        _text_state["should_stop"] = True
                    else:
                        _text_state["failed"] += 1
            except Exception as e:
                with _text_lock:
                    _text_state["failed"] += 1
                    _text_state["last_message"] = f"Job #{job_id} crashed: {e}"
            _set_text_state(current_job_id=None, current_job_url="", current_started_at=None)
            time.sleep(WORKER_SLEEP_BETWEEN)
    finally:
        _set_text_state(running=False, should_stop=False, current_job_id=None, current_job_url="")


def _image_worker_loop():
    """Pop status=text_done → process images phase → status=draft."""
    _set_image_state(
        running=True, should_stop=False, completed=0, failed=0,
        started_at=datetime.now().isoformat(timespec="seconds"),
        last_message="Image worker started.",
    )
    try:
        while True:
            with _image_lock:
                if _image_state["should_stop"]:
                    _set_image_state(last_message="Image worker dừng theo lệnh.")
                    break
            job_id = _next_job_by_status("text_done")
            if not job_id:
                # Idle — đợi 10s xem có text_done mới không (text worker có thể đang gen)
                _set_image_state(last_message="Idle — chờ text_done mới...", current_job_id=None)
                # Nếu cả text worker đã stop và không còn text_done → cũng dừng image worker
                with _text_lock:
                    text_running = _text_state["running"]
                if not text_running:
                    if not _next_job_by_status("text_done"):
                        _set_image_state(last_message="Text worker stop + hết text_done — image worker stop.")
                        break
                time.sleep(10)
                continue
            job = db.content_job_get(job_id)
            url = (job.get("product_url") if job else "") or ""
            _set_image_state(
                current_job_id=job_id, current_job_url=url,
                current_started_at=datetime.now().isoformat(timespec="seconds"),
                last_message=f"Process images job #{job_id}: {url[:80]}",
            )
            try:
                res = process_images_phase(job_id)
                with _image_lock:
                    if res["ok"]:
                        _image_state["completed"] += 1
                    else:
                        _image_state["failed"] += 1
            except Exception as e:
                with _image_lock:
                    _image_state["failed"] += 1
                    _image_state["last_message"] = f"Job #{job_id} crashed: {e}"
            _set_image_state(current_job_id=None, current_job_url="", current_started_at=None)
            time.sleep(1)  # Image worker cooldown ngắn (mỗi bài chỉ ~25-30s)
    finally:
        _set_image_state(running=False, should_stop=False, current_job_id=None, current_job_url="")


def _recover_orphan_drafting():
    """Khi worker start, các job đang `drafting` từ session cũ (Flask đã restart)
    sẽ orphan. Reset về phase phù hợp:
      - Có ai_body_md → text_done (image worker pickup)
      - Không có ai_body_md → pending (text worker pickup lại)
    """
    drafting_jobs = db.content_jobs_list(status="drafting", limit=1000)
    recovered = 0
    for j in drafting_jobs:
        new_status = "text_done" if (j.get("ai_body_md") or "").strip() else "pending"
        db.content_job_update(j["id"], status=new_status, error=None)
        recovered += 1
    return recovered


def start_worker_async() -> bool:
    """Spawn 3 thread song song: text worker + image worker + pre-warmer."""
    _recover_orphan_drafting()
    started_any = False
    with _text_lock:
        if not _text_state["running"]:
            _text_state["should_stop"] = False
            t = threading.Thread(target=_text_worker_loop, daemon=True)
            t.start()
            started_any = True
    with _image_lock:
        if not _image_state["running"]:
            _image_state["should_stop"] = False
            t = threading.Thread(target=_image_worker_loop, daemon=True)
            t.start()
            started_any = True
    # Start prewarmer (best-effort, không tính vào started_any)
    start_prewarmer_async()
    return started_any


def stop_worker() -> bool:
    """Signal cả 2 worker (+ prewarmer) dừng sau khi xong job hiện tại."""
    stopped = False
    with _text_lock:
        if _text_state["running"]:
            _text_state["should_stop"] = True
            stopped = True
    with _image_lock:
        if _image_state["running"]:
            _image_state["should_stop"] = True
            stopped = True
    with _prewarmer_lock:
        if _prewarmer_state["running"]:
            _prewarmer_state["should_stop"] = True
            stopped = True
    return stopped


# ─────────────────────────── PRE-WARMER (Task 3) ───────────────────────────
#
# Chạy ngầm song song với 2 worker chính. Pre-process ảnh các SP đang ở status
# `pending` HOẶC `text_done` (chưa qua image phase) → save vào local cache.
# Khi image worker pickup, đọc cache là xong → save 10-15s/bài.
#
# Chạy chậm (1 SP / 4s) để không spam Haravan CDN + tránh tốn RAM.

_prewarmer_state = {
    "running": False, "should_stop": False,
    "preheated": 0, "skipped": 0, "failed": 0,
    "current_handle": "",
    "started_at": None, "last_message": "",
}
_prewarmer_lock = threading.Lock()
PREWARMER_INTERVAL = 4  # giây giữa mỗi SP


def _set_prewarmer_state(**kw):
    with _prewarmer_lock:
        _prewarmer_state.update(kw)


def _prewarmer_loop():
    """Iterate qua jobs cần image, pre-process + cache ảnh."""
    _set_prewarmer_state(
        running=True, should_stop=False,
        preheated=0, skipped=0, failed=0,
        started_at=datetime.now().isoformat(timespec="seconds"),
        last_message="Pre-warmer started.",
    )
    try:
        while True:
            with _prewarmer_lock:
                if _prewarmer_state["should_stop"]:
                    _set_prewarmer_state(last_message="Pre-warmer dừng theo lệnh.")
                    break
            # Lấy 1 job pending hoặc text_done có handle, ảnh chưa cache
            jobs = (
                db.content_jobs_list(status="pending", limit=200)
                + db.content_jobs_list(status="text_done", limit=200)
            )
            target = None
            for j in jobs:
                handle = j.get("handle")
                # Nếu chưa có handle, fetch từ haravan_products
                if not handle:
                    info = _fetch_product_info(j["product_url"])
                    handle = info.get("handle")
                if not handle:
                    continue
                # Skip nếu đã cache đủ 2 ảnh
                if image_processor.cache_exists(handle, 1) and image_processor.cache_exists(handle, 2):
                    continue
                target = (j, handle)
                break

            if not target:
                # Hết SP cần preheat, idle 30s
                _set_prewarmer_state(last_message="Idle — không có SP nào cần pre-process.")
                # Nếu cả 2 worker chính đã stop → cũng dừng prewarmer
                with _text_lock:
                    text_running = _text_state["running"]
                with _image_lock:
                    image_running = _image_state["running"]
                if not text_running and not image_running:
                    _set_prewarmer_state(last_message="Cả 2 worker stop — pre-warmer cũng stop.")
                    break
                time.sleep(30)
                continue

            j, handle = target
            _set_prewarmer_state(
                current_handle=handle,
                last_message=f"Pre-process {handle[:60]}",
            )
            try:
                src_urls = _get_product_image_urls(handle, max_count=2)
                for i, src in enumerate(src_urls, 1):
                    if image_processor.cache_exists(handle, i):
                        continue
                    try:
                        bts = image_processor.process_haravan_image(src)
                        image_processor.cache_save(handle, i, bts)
                    except Exception as e:
                        with _prewarmer_lock:
                            _prewarmer_state["failed"] += 1
                        print(f"[prewarmer skip] {src}: {e}")
                with _prewarmer_lock:
                    _prewarmer_state["preheated"] += 1
            except Exception as e:
                with _prewarmer_lock:
                    _prewarmer_state["failed"] += 1
                    _prewarmer_state["last_message"] = f"Pre-warmer crash: {e}"
            time.sleep(PREWARMER_INTERVAL)
    finally:
        _set_prewarmer_state(running=False, should_stop=False, current_handle="")


def start_prewarmer_async() -> bool:
    with _prewarmer_lock:
        if _prewarmer_state["running"]:
            return False
        _prewarmer_state["should_stop"] = False
    t = threading.Thread(target=_prewarmer_loop, daemon=True)
    t.start()
    return True
