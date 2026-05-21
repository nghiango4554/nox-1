"""product_writer.py — AI-gen content cho /products/new (Phase 2).

Gọi Claude CLI Pro/Max → trả về body_html / excerpt / SEO title / SEO meta.

Prompt đồng bộ với `seo_writing_rules.md` v2026-05-08:
- Public voice "bạn" (không "anh"/"tôi")
- KHÔNG H1, body chỉ <h2>/<h3>
- Forbidden phrases banlist
- SEO title 45-61c, KHÔNG "Sintech" (Haravan auto-suffix)
- SEO meta 140-160c, đủ CTA HOA (XEM NGAY / THAM KHẢO NGAY / CHỌN NGAY / KHÁM PHÁ NGAY)
- Body 7 section + outro + signature
- Angle deterministic theo hash(name) % 5

Output: 1 JSON object {body_html, excerpt, seo_title, seo_meta}.
"""

from __future__ import annotations

import hashlib
import json
import re

import ai_provider
import sintech_rules


ANGLES = ["SPEC", "USE_CASE", "AUDIENCE", "PAIN_POINT", "COMPARISON"]

_ANGLE_TITLE_HINT = {
    "SPEC":       "Nhấn vào thông số nổi bật nhất (vd '12GB GDDR6, 144Hz')",
    "USE_CASE":   "Nhấn vào use case cụ thể (gaming AAA / văn phòng / đồ họa)",
    "AUDIENCE":   "Nhấn vào đối tượng (game thủ / designer / sinh viên)",
    "PAIN_POINT": "Đánh trúng pain point khách thường gặp (giật/đứng/nóng/chậm)",
    "COMPARISON": "Định vị vs SP cùng tier (vd 'thay thế ngon hơn X')",
}

# Map angle → SEO meta pattern (theo rules section 4)
_ANGLE_META_PATTERN = {
    "SPEC":       ("M1_SPEC",       "XEM NGAY tại Sintech"),
    "USE_CASE":   ("M2_SETUP",      "THAM KHẢO NGAY tại Sintech"),
    "AUDIENCE":   ("M3_GIAI_PHAP",  "CHỌN NGAY mẫu phù hợp tại Sintech"),
    "PAIN_POINT": ("M3_GIAI_PHAP",  "CHỌN NGAY mẫu phù hợp tại Sintech"),
    "COMPARISON": ("M2_SETUP",      "THAM KHẢO NGAY tại Sintech"),
}


# ═══════════════════════════════════════════════════════════════
# Sintech inline styles — applied trước khi POST Haravan, để body render
# đúng trên theme (không bị plain text). Mẫu rút từ bài cũ vợ đã làm.
# ═══════════════════════════════════════════════════════════════

_SINTECH_RED = "rgb(231, 76, 60)"
_BLACK = "rgb(0, 0, 0)"
_GREY_BORDER = "rgb(204, 204, 204)"
_GREY_HEADER = "rgb(244, 244, 244)"
_GREY_MUTED = "rgb(107, 114, 128)"

# Style rút từ bài cũ vợ Nghĩa cung cấp (sample 2026-05-19). KHÔNG đổi tự ý
# trừ khi vợ confirm — các giá trị này phải match style đã dùng trong store.
_SINTECH_STYLES = {
    "p":      f"font-family: Arial, sans-serif; font-size: 12pt; font-weight: 500; line-height: 1.65; margin: 10px 0px; color: {_BLACK};",
    "h2":     f"font-size: 17pt; font-weight: 700; color: {_BLACK}; margin: 24px 0px 5px; line-height: 1.38; font-family: Arial, sans-serif; font-style: normal; text-decoration: none;",
    "h3":     f"font-size: 14pt; font-weight: 700; color: {_BLACK}; margin: 20px 0px 6px; line-height: 1.4; font-family: Arial, sans-serif; font-style: normal;",
    "ul":     f"font-family: Arial, sans-serif; font-size: 12pt; line-height: 1.65; margin: 10px 0px 10px 20px; color: {_BLACK};",
    "ol":     f"font-family: Arial, sans-serif; font-size: 12pt; line-height: 1.65; margin: 10px 0px 10px 20px; color: {_BLACK};",
    "li":     "margin: 4px 0px;",
    "table":  "border-collapse: collapse; width: 100%; margin: 14px 0px; font-size: 11pt; font-family: Arial, sans-serif;",
    "th":     f"border: 1px solid {_GREY_BORDER}; padding: 8px 10px; vertical-align: top; color: {_BLACK}; font-family: Arial, sans-serif; font-weight: 700; background: {_GREY_HEADER}; text-align: left;",
    "td":     f"border: 1px solid {_GREY_BORDER}; padding: 8px 10px; vertical-align: top; color: {_BLACK}; font-family: Arial, sans-serif;",
    "a":      f"color: {_SINTECH_RED}; text-decoration: underline; font-weight: 700;",
    "em":     f"font-family: Arial, sans-serif; font-size: 11pt; font-style: italic; color: {_GREY_MUTED};",
}


def inject_sintech_styles(html: str) -> str:
    """Áp dụng inline style chuẩn Sintech cho từng tag trong body_html.

    Mục đích: body render đúng trên Haravan/Sintech theme thay vì plain text
    (theme không có default style cho h2/h3/table/a inside product description).
    """
    if not html or "<" not in html:
        return html
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return html  # bs4 không có → return unchanged

    soup = BeautifulSoup(html, "html.parser")

    for tag_name, style in _SINTECH_STYLES.items():
        for tag in soup.find_all(tag_name):
            existing = tag.get("style", "")
            if not existing:
                tag["style"] = style

    # <strong> bên trong <a> → áp đồng style với <a> (link đỏ bold)
    for a_tag in soup.find_all("a"):
        for strong in a_tag.find_all("strong"):
            if not strong.get("style"):
                strong["style"] = _SINTECH_STYLES["a"]

    return str(soup)


def pick_angle(name: str, prev_angle: str | None = None) -> str:
    """Default: deterministic theo hash(name) % 5.

    Nếu `prev_angle` truyền vào (= angle vừa gen lần trước) → rotate sang angle
    kế tiếp trong ANGLES (cycle). Cho phép "Gen lại" lấy angle khác → body
    đa dạng cho mỗi attempt.
    """
    default = ANGLES[int(hashlib.md5((name or "").encode("utf-8")).hexdigest(), 16) % len(ANGLES)]
    if not prev_angle:
        return default
    try:
        idx = ANGLES.index(prev_angle)
    except ValueError:
        return default
    return ANGLES[(idx + 1) % len(ANGLES)]


# ═══════════════════════════════════════════════════════════════
# organize_spec — Phase 5: clean up + structure spec từ paste raw
# ═══════════════════════════════════════════════════════════════

_ORGANIZE_SYSTEM_PROMPT = """Bạn là chuyên viên tổng hợp thông số kỹ thuật cho Sintech.vn.
Vợ Nghĩa paste spec SP từ nhiều nguồn (trang hãng, đối thủ, supplier) — văn bản
có thể lộn xộn, trùng lặp, multilingual, có ký tự lạ.

Task: clean up + dedupe + tổ chức thành JSON.

RULES:
- KHÔNG bịa thông số. Nếu nguồn không có → bỏ qua, KHÔNG tự thêm.
- Nếu 2 nguồn conflict → ghi cả 2 vào `warnings`, KHÔNG tự chọn.
- Dedupe: cùng 1 spec ghi khác cách → merge thành 1 row tốt nhất.
- Standardize unit: "12GB", "256GB", "144Hz", "DDR4-3200", "650W 80+ Bronze".
- Translate sang Việt nếu nguồn EN, GIỮ tech term EN (CPU/GPU/RAM/PCIe/M.2/NVMe...).
- KHÔNG đưa GIÁ vào spec_table hoặc bất kỳ field nào.
- Label spec ngắn (vd "Chipset", "Socket", "Bộ nhớ"), value cụ thể có số.

OUTPUT: 1 JSON object DUY NHẤT, KHÔNG markdown fence:
{
  "spec_table": [
    {"label": "Chipset", "value": "Intel H510"},
    {"label": "Socket", "value": "LGA 1200"},
    ...
  ],
  "key_features": [
    "Mặt mesh thoáng khí, đẩy nhiệt nhanh",
    "Hỗ trợ tối đa 4 quạt 120mm",
    ...
  ],
  "use_cases": [
    "Build PC văn phòng, gọn nhẹ",
    "Gaming entry-level i3/i5 + GPU tầm trung",
    ...
  ],
  "compatibility_notes": [
    "Khoảng không max VGA 320mm, đủ cho RTX 4060",
    "Tản CPU max 160mm",
    ...
  ],
  "warnings": [
    "Nguồn 1 ghi RAM max 64GB, nguồn 2 ghi 32GB — vợ verify"
  ]
}

Mỗi list 3-10 mục là đủ. Nếu không có info cho list nào → trả `[]` (array rỗng)."""


def organize_spec(name: str, parsed: dict, spec_raw: str) -> dict:
    """Parse spec raw paste → structured JSON via Claude.

    Trả về dict với schema spec_table/key_features/use_cases/compatibility_notes/warnings.
    Nếu spec_raw rỗng → trả về schema với array rỗng (no AI call).
    """
    if not (spec_raw or "").strip():
        return {
            "spec_table": [], "key_features": [], "use_cases": [],
            "compatibility_notes": [], "warnings": [],
            "_skipped": "spec_raw rỗng — no AI call",
        }

    loai = parsed.get("loai") or "(không xác định)"
    hang = parsed.get("hang") or "(không xác định)"

    user = f"""SP:
- Tên: {name}
- Loại: {loai}
- Hãng: {hang}

Spec raw paste từ nhiều nguồn (lộn xộn OK):
═══════════════════════════════════════════════════════════════
{spec_raw}
═══════════════════════════════════════════════════════════════

Organize thành JSON theo schema trong system. Strict no-fabricate."""

    raw = ai_provider.call_ai(_ORGANIZE_SYSTEM_PROMPT, user, timeout=120)

    # Strip markdown fence
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    try:
        m = re.search(r"\{[\s\S]+\}", cleaned)
        data = json.loads(m.group(0)) if m else json.loads(cleaned)
    except Exception:
        raise RuntimeError(f"organize_spec: Claude trả output không parse được JSON. Tail: {cleaned[-400:]}")

    # Defensive — ensure all 5 keys exist as lists
    for k in ("spec_table", "key_features", "use_cases", "compatibility_notes", "warnings"):
        if k not in data or not isinstance(data[k], list):
            data[k] = []

    return data


_SYSTEM_PROMPT = """Bạn là chuyên viên content + SEO cho Sintech.vn (PC Gaming & Gear, 457 Trần Xuân Soạn Q7 TP.HCM, hotline 0911 713 000).
Vợ Nghĩa đang tạo 1 SP MỚI trên Haravan và cần bạn gen 4 thứ: body_html / excerpt / seo_title / seo_meta.

═══════════════════════════════════════════════════════════════
PUBLIC VOICE (khách đọc):
═══════════════════════════════════════════════════════════════
- Xưng **"bạn"** — KHÔNG "anh" / "tôi" / "mình" / "chúng tôi".
- Tone "người am hiểu chia sẻ" pha tư vấn, KHÔNG cộc lốc, KHÔNG học thuật.
- Câu mở đoạn ĐA DẠNG — KHÔNG dồn toàn "Bạn..." mở đầu. Dùng connector:
  "Hiện nay...", "Đối với...", "Nếu... thì...", "Trong khi đó...", "Ngoài ra...",
  "Tuy nhiên...", "Nhờ đó...", "Bên cạnh đó...", "Khi...", "Một điểm đáng chú ý là..."
- Đoạn 2-3 câu, mỗi câu mang 1 ý. CÂU NỐI Ý — không cộc.

═══════════════════════════════════════════════════════════════
CẤM TUYỆT ĐỐI (banlist):
═══════════════════════════════════════════════════════════════
- Filler: "bền bỉ" · "tuyệt vời" · "tốt nhất 2026" · "Free ship" · "bảo hành tận răng"
  · "chính hãng 100%" · "đáng mua nhất" · "khôn nhất" · "đẹp mắt" · "đem đến" · "rẻ nhất"
- Phrase: "trong bài này" · "sản phẩm này mang lại" · "người dùng sẽ" · "category này"
  · "search intent" · "carte này" · "chia sẻ với bạn"
- "Sintech" trong **seo_title** (Haravan tự append " - Sintech")
- KHÔNG dùng `<h1>`, KHÔNG `<hr>`, KHÔNG `---` separator
- KHÔNG bịa thông số — spec không chắc thì BỎ
- KHÔNG nhồi keyword, KHÔNG liệt kê >3 cụm số liền kề

═══════════════════════════════════════════════════════════════
RULE GIÁ — TUYỆT ĐỐI cứng:
═══════════════════════════════════════════════════════════════
- KHÔNG đề cập GIÁ / SỐ TIỀN trong body_html / excerpt / seo_meta / seo_title.
- Cấm các cụm: "tầm Xtr" · "X triệu" · "X.XXX đ" · "tầm giá" · "ở mức X tr"
  · "mốc giá" · "phân khúc giá" · "trong khoảng X-Y triệu" · "khoảng X đ"
- Giá set ở variant Haravan riêng — content KHÔNG nhét giá.

═══════════════════════════════════════════════════════════════
BODY FORMAT — <table> + <ul> ĐÚNG CHỖ (chuẩn SEO):
═══════════════════════════════════════════════════════════════
- "Thông số nổi bật cần biết" → DÙNG `<table>` 2 cột (Thông số | Chi tiết).
  KHÔNG dùng `<ul>` cho thông số quantitative (Hz/W/GB/mm/inch).
- "Phù hợp với ai" → DÙNG `<ul>` bullet (đối tượng/use case qualitative).
- Angle COMPARISON → THÊM `<table>` 3 cột so sánh SP này với 2 model cùng tier
  (chỉ ghi rõ thuộc tính có thật, KHÔNG bịa SP đối thủ).

═══════════════════════════════════════════════════════════════
ANGLE — ảnh hưởng tới BODY (không chỉ title):
═══════════════════════════════════════════════════════════════
- SPEC: section "Điểm nổi bật" có 4-5 H3, mỗi H3 = 1 spec cụ thể (deep-dive).
- USE_CASE: section "Trải nghiệm thực tế" mở rộng — 3 scenario (gaming AAA /
  công việc / sáng tạo) với câu chuyện ngắn.
- AUDIENCE: section "Phù hợp với ai" mở rộng — 4-6 đối tượng với insight cụ thể
  (vd "Sinh viên ngành kiến trúc cần render nhẹ" thay vì chỉ "sinh viên").
- PAIN_POINT: thêm H2 "Giải quyết vấn đề gì" ngay sau intro, liệt kê 3-4 pain
  SP fix được (vd "Hết drop FPS giữa game", "Hết nóng khi load nặng").
- COMPARISON: thêm `<table>` 3 cột so SP với 2 model cùng tier ở section riêng
  hoặc trong "Thông số nổi bật cần biết".

═══════════════════════════════════════════════════════════════
INTERNAL LINKS (body):
═══════════════════════════════════════════════════════════════
- Format CỨNG: `<a href="URL"><strong>anchor</strong></a>` (Haravan render đẹp dạng này)
- Anchor là cụm danh từ NGẮN, **≤30 ký tự** (vd "chuột gaming", "màn hình 2K 27 inch", "PC gaming phổ thông")
- 3-6 link trong body + 1 ở intro + 1 ở outro (tổng 5-8)
- Link homepage: `<a href="https://sintech.vn"><strong>Sintech</strong></a>`
- Link category: `<a href="https://sintech.vn/collections/{slug-category-phù-hợp}"><strong>{anchor}</strong></a>`
- CẤM anchor "tại đây" / "xem thêm" / "click here" / full tên SP

═══════════════════════════════════════════════════════════════
BODY_HTML — CẤU TRÚC BẮT BUỘC (theo đúng thứ tự):
═══════════════════════════════════════════════════════════════

<h2>{Tên SP}</h2>
<p>Hook 2-4 câu giới thiệu SP, đa dạng câu mở (định nghĩa khô / trải nghiệm / nhu cầu khách / so sánh / tình huống dùng). Có 1 link <strong>Sintech</strong> homepage.</p>

<h2>Điểm nổi bật của {Tên SP}</h2>
<p>Đoạn dẫn 2 câu trước khi vào H3 con.</p>
<h3>Thiết kế và cảm giác sử dụng</h3>
<p>2-3 câu.</p>
<h3>Hiệu năng và thao tác</h3>
<p>2-3 câu.</p>
<h3>Tính năng đáng chú ý</h3>
<p>2-3 câu.</p>

<h2>Trải nghiệm thực tế khi sử dụng</h2>
<p>2-4 câu kể tình huống thực — setup, gaming, học tập, văn phòng... Chèn 1-2 internal link category liên quan.</p>

<h2>Sản phẩm này phù hợp với ai</h2>
<p><strong>Phù hợp với:</strong></p>
<ul>
  <li>3-5 đối tượng cụ thể, mỗi bullet 1 câu ngắn</li>
</ul>
<p><strong>Không quá phù hợp nếu:</strong></p>
<ul>
  <li>2-3 trường hợp cảnh báo khách</li>
</ul>

<h2>Thông số nổi bật cần biết</h2>
<p>1-2 câu dẫn.</p>
<table>
  <thead>
    <tr><th>Thông số</th><th>Chi tiết</th></tr>
  </thead>
  <tbody>
    <tr><td>Tên thông số ngắn (vd "Chipset", "Socket", "Bộ nhớ")</td><td>Giá trị từ input (vd "H510", "LGA1200", "12GB GDDR6")</td></tr>
    <!-- 5-10 row spec — CHỈ dùng spec có trong input. KHÔNG bịa Hz/W/GB/inch/MHz... -->
  </tbody>
</table>
<!-- Nếu angle=COMPARISON: ngay sau bảng spec, thêm 1 bảng 3 cột (Thông số | SP này | SP tier khác) -->
<!-- Nếu spec input quá ít (vd lót chuột) → BỎ table, viết <p> mô tả công năng thay -->.

<h2>Vì sao nên mua tại Sintech</h2>
<p>Đoạn 1 (đúng 2 câu): kinh nghiệm tư vấn + build PC + uy tín thực tế.</p>
<p>Đoạn 2 (đúng 2 câu): BẮT BUỘC chèn NGUYÊN VĂN câu sau như câu đầu của đoạn: "Sintech hiện công bố chính sách bán hàng, kiểm hàng, vận chuyển và trả góp 0% qua thẻ tín dụng đối với 1 số sản phẩm." + 1 câu chốt.</p>

<h2>Câu hỏi thường gặp về {Tên SP}</h2>
<p>1 câu dẫn.</p>
<h3>Câu hỏi 1?</h3>
<p>Trả lời 2-4 câu.</p>
<h3>Câu hỏi 2?</h3>
<p>Trả lời 2-4 câu.</p>
<h3>Câu hỏi 3?</h3>
<p>...</p>
<!-- 4-6 cặp Q/A. Gợi ý chủ đề: bảo hành / tương thích / so sánh / hợp ai / dùng lâu / phụ kiện -->

<p>Tóm lại, ... outro 2-3 câu (mở bằng "Tóm lại,/Nói ngắn gọn,/Kết lại,/Sau tất cả,") + 1 link <strong>Sintech</strong>.</p>

<p><em>Tư vấn cấu hình bởi team kỹ thuật Sintech — Hotline 0911 713 000 · 457 Trần Xuân Soạn, Q7, TP.HCM.</em></p>

═══════════════════════════════════════════════════════════════
SEO TITLE (45-61 ký tự, sweet 50-58):
═══════════════════════════════════════════════════════════════
- **CASE RULE — quan trọng nhất:**
  • Loại SP viết SENTENCE-CASE: "Vỏ case", "Card màn hình", "Ổ cứng SSD",
    "Tản nhiệt", "Màn hình", "Bàn phím cơ"... (chữ cái đầu HOA, còn lại THƯỜNG)
  • CHỈ giữ HOA cho:
    – Brand (MAGIC, ASUS, MSI, CENTAUR, DARKFLASH, 1ST PLAYER, POWER COLOR...)
    – Model code (GM-03, RTX 3060, B760M-K, H5M10-V4M, K2 Pro, X20 RGB...)
    – Acronym + tech standard (RAM, CPU, PC, SSD, HDD, RGB, DDR4, DDR5, ATX,
      m-ATX, FHD, 2K, 4K, IPS, OLED, NVMe, USB, USB-C, M.2, LGA1200, RTX, GTX,
      Hz/GHz/MHz/W/V — nhưng số viết liền vd "144Hz" "650W")
  • Phần TAIL (mô tả lợi ích/use case sau model code) viết THƯỜNG như câu Việt
    bình thường — KHÔNG title-case kiểu English ("Hết Lo PC Nóng" SAI).
- **SEPARATOR RULE:**
  • KHÔNG dùng dấu `-` làm separator giữa tên SP + tail descriptor.
  • Dùng dấu cách hoặc dấu phẩy. Câu liền mạch.

VÍ DỤ ĐÚNG vs SAI:
  ❌ SAI:  "Vỏ Case MAGIC GM-03 MESH m-ATX - Hết Lo PC Nóng"
  ✅ ĐÚNG: "Vỏ case MAGIC GM-03 MESH m-ATX thoáng mát, giá tốt"

  ❌ SAI:  "Card Màn Hình ASUS Dual RTX 3060 12GB - Gaming AAA 1440p"
  ✅ ĐÚNG: "Card màn hình ASUS Dual RTX 3060 12GB cho gaming AAA 1440p"

  ❌ SAI:  "RAM CENTAUR Ragnarok Pro RGB 8GB DDR4 3200 - Build PC Tông Đen"
  ✅ ĐÚNG: "RAM CENTAUR Ragnarok Pro RGB 8GB DDR4 3200 cho build tông đen"

  ❌ SAI:  "Màn Hình Gaming MSI G275L 27 Inch - 144Hz IPS FHD"
  ✅ ĐÚNG: "Màn hình gaming MSI G275L 27 inch FHD IPS 144Hz"

- KHÔNG có "Sintech" trong title (Haravan tự append " - Sintech")
- KHÔNG nhồi từ, KHÔNG superlative ("tốt nhất 2026", "rẻ nhất"...)

═══════════════════════════════════════════════════════════════
SEO META description (140-160 ký tự — **CỨNG min 140**):
═══════════════════════════════════════════════════════════════
- 1 câu hoàn chỉnh, mượt, dễ đọc
- BẮT BUỘC có tên SP + 1-2 lợi ích + ngữ cảnh + CTA HOA
- CTA cuối câu phải VIẾT HOA cả cụm (vd "XEM NGAY tại Sintech.")
- Đếm CHÍNH XÁC số ký tự trước khi trả. Nếu <140c → BỔ SUNG ngữ cảnh / lợi ích kép

═══════════════════════════════════════════════════════════════
EXCERPT (≤160 ký tự):
═══════════════════════════════════════════════════════════════
- 1 câu, gọn, KHÔNG lặp seo_title
- Tóm tắt SP + đối tượng + 1 lợi ích chính

═══════════════════════════════════════════════════════════════
""" + "\n\n" + sintech_rules.common_rules_block(include_length=False) + """

═══════════════════════════════════════════════════════════════
OUTPUT: trả về DUY NHẤT 1 JSON object (KHÔNG markdown fence, KHÔNG text trước/sau):
{
  "body_html": "<h2>...</h2>...",
  "excerpt":   "...",
  "seo_title": "...",
  "seo_meta":  "..."
}
"""


def _format_organized_spec(spec: dict | None) -> str:
    """Render organized_spec dict thành text block để inject vào user_prompt."""
    if not spec or not any(spec.get(k) for k in ("spec_table", "key_features", "use_cases", "compatibility_notes")):
        return ""

    parts = ["", "═══════════════════════════════════════════════════════════════",
             "SPEC ĐÃ TỔNG HỢP (vợ paste + AI organize — DÙNG LÀM SOURCE OF TRUTH):",
             "═══════════════════════════════════════════════════════════════"]

    if spec.get("spec_table"):
        parts.append("\n📋 Bảng thông số:")
        for row in spec["spec_table"]:
            parts.append(f"  - {row.get('label', '?')}: {row.get('value', '?')}")

    if spec.get("key_features"):
        parts.append("\n🔑 Tính năng chính:")
        for f in spec["key_features"]:
            parts.append(f"  - {f}")

    if spec.get("use_cases"):
        parts.append("\n🎯 Use case (giúp viết 'Phù hợp với ai'):")
        for u in spec["use_cases"]:
            parts.append(f"  - {u}")

    if spec.get("compatibility_notes"):
        parts.append("\n⚙️ Tương thích / lưu ý:")
        for n in spec["compatibility_notes"]:
            parts.append(f"  - {n}")

    if spec.get("warnings"):
        parts.append("\n⚠️ Cảnh báo conflict spec (CẨN THẬN, có thể vợ phải verify):")
        for w in spec["warnings"]:
            parts.append(f"  - {w}")

    parts.append("\n→ Khi viết <table> 'Thông số nổi bật cần biết': dùng EXACT spec_table này.")
    parts.append("→ Khi viết 'Điểm nổi bật': dùng key_features làm khung 3-5 H3.")
    parts.append("→ Khi viết 'Phù hợp với ai': dùng use_cases cụ thể.")
    parts.append("→ FAQ có thể trích từ compatibility_notes.")
    parts.append("→ CẤM bịa spec/feature/use_case NGOÀI danh sách trên.")
    parts.append("")
    return "\n".join(parts)


def _user_prompt(name: str, parsed: dict, warranty_months: str, angle: str, organized_spec: dict | None = None) -> str:
    loai = parsed.get("loai") or "(không xác định)"
    hang = parsed.get("hang") or "(không xác định)"
    sub  = parsed.get("sub_loai") or ""
    tags = parsed.get("tags") or []

    pattern, cta = _ANGLE_META_PATTERN[angle]
    title_hint = _ANGLE_TITLE_HINT[angle]

    pattern_desc = {
        "M1_SPEC":      "M1 (SPEC): '{Tên SP} {màu/size}, {spec 1-2 con số}, {đặc điểm chính}. XEM NGAY tại Sintech.'",
        "M2_SETUP":     "M2 (SETUP/USE CASE): 'Setup/Build {tone hoặc nhu cầu} cùng {SP} - {tính năng}, {đặc điểm}. THAM KHẢO NGAY tại Sintech.'",
        "M3_GIAI_PHAP": "M3 (GIẢI PHÁP): '{SP ngắn} - giải pháp {cho ai/cho vấn đề}, {đặc điểm chốt}. CHỌN NGAY mẫu phù hợp tại Sintech.'",
    }[pattern]

    sub_text = f"- Tính chất: {sub}\n" if sub else ""
    warranty_text = f"{warranty_months} tháng" if warranty_months else "(chưa rõ)"
    tags_text = ", ".join(tags) if tags else "(không có)"
    organized_block = _format_organized_spec(organized_spec)

    # CỐ Ý không pass price vào prompt — rule cấm đề cập giá trong content.

    return f"""SP cần gen content:

- Tên: {name}
- Loại: {loai}
{sub_text}- Hãng: {hang}
- Tags auto đã parse: {tags_text}
- Bảo hành: {warranty_text}
{organized_block}

═══════════════════════════════════════════════════════════════
ANGLE PICK = {angle}
═══════════════════════════════════════════════════════════════

[seo_title]
- Angle hint: {title_hint}
- Length: 45-61 ký tự (sweet 50-58)
- Bắt đầu bằng "{loai}" hoặc tên SP gọn
- CẤM "Sintech" trong title

[seo_meta]
- Pattern: {pattern_desc}
- CTA HOA bắt buộc: "{cta}"
- Length: 140-160 ký tự (**CỨNG min 140**)
- Có tên SP + 1-2 lợi ích + ngữ cảnh dùng

[excerpt]
- ≤160 ký tự, 1 câu, KHÔNG lặp title

[body_html]
- HTML thuần (không Markdown, không backslash)
- Đầy đủ 7 section + outro + signature theo SYSTEM
- 3-6 internal link (`<a href="..."><strong>...</strong></a>`)
- ~800-1500 từ tổng (SP đơn giản 800-1200, mid-tier 1300-1500)

Trả về JSON duy nhất, đúng schema. Không kèm gì khác."""


def generate(name: str, parsed: dict, price: str = "", warranty_months: str = "",
             organized_spec: dict | None = None, prev_angle: str | None = None) -> dict:
    """Gọi Codex CLI gen content. Raise CodexRateLimitError nếu hết quota.

    organized_spec (optional): output từ organize_spec(). Nếu có → AI dùng làm
    source of truth cho spec/features/use_cases, KHÔNG bịa.

    prev_angle (optional): angle của lần gen trước. Truyền vào để rotate sang
    angle kế tiếp (Gen lại → body khác góc nhìn).
    """
    angle = pick_angle(name, prev_angle=prev_angle)
    system = _SYSTEM_PROMPT
    user = _user_prompt(name, parsed, warranty_months, angle, organized_spec=organized_spec)

    raw = ai_provider.call_ai(system, user, timeout=240)

    # Strip markdown fence nếu lỡ có
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    try:
        m = re.search(r"\{[\s\S]+\}", cleaned)
        data = json.loads(m.group(0)) if m else json.loads(cleaned)
    except Exception:
        raise RuntimeError(f"Claude trả output không parse được JSON. Tail: {cleaned[-400:]}")

    pattern, cta = _ANGLE_META_PATTERN[angle]
    body_raw = data.get("body_html") or ""
    body_styled = inject_sintech_styles(body_raw)
    return {
        "body_html": body_styled,
        "excerpt":   data.get("excerpt") or "",
        "seo_title": data.get("seo_title") or "",
        "seo_meta":  data.get("seo_meta") or "",
        "angle":     angle,
        "meta_pattern": pattern,
        "expected_cta": cta,
    }


if __name__ == "__main__":
    print("Angle test 1:", pick_angle("Card Màn Hình Asus Dual RTX 3060 12GB V1"))
    print("Angle test 2:", pick_angle("RAM Centaur Ragnarok Pro RGB 8GB DDR4 3200 Đen"))
