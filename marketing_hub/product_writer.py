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

import claude_provider as cp


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


def pick_angle(name: str) -> str:
    h = int(hashlib.md5((name or "").encode("utf-8")).hexdigest(), 16)
    return ANGLES[h % len(ANGLES)]


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
OUTPUT: trả về DUY NHẤT 1 JSON object (KHÔNG markdown fence, KHÔNG text trước/sau):
{
  "body_html": "<h2>...</h2>...",
  "excerpt":   "...",
  "seo_title": "...",
  "seo_meta":  "..."
}
"""


def _user_prompt(name: str, parsed: dict, price: str, warranty_months: str, angle: str) -> str:
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

    # CỐ Ý không pass price vào prompt — rule cấm đề cập giá trong content.
    # Giá set ở variant Haravan ngoài route /create, không cần AI biết.

    return f"""SP cần gen content:

- Tên: {name}
- Loại: {loai}
{sub_text}- Hãng: {hang}
- Tags auto đã parse: {tags_text}
- Bảo hành: {warranty_text}

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


def generate(name: str, parsed: dict, price: str = "", warranty_months: str = "") -> dict:
    """Gọi Claude CLI gen content. Raise ClaudeRateLimitError nếu hết quota."""
    angle = pick_angle(name)
    system = _SYSTEM_PROMPT
    user = _user_prompt(name, parsed, price, warranty_months, angle)

    raw = cp.call_claude(system, user, timeout=240)

    # Strip markdown fence nếu lỡ có
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)

    try:
        m = re.search(r"\{[\s\S]+\}", cleaned)
        data = json.loads(m.group(0)) if m else json.loads(cleaned)
    except Exception:
        raise RuntimeError(f"Claude trả output không parse được JSON. Tail: {cleaned[-400:]}")

    pattern, cta = _ANGLE_META_PATTERN[angle]
    return {
        "body_html": data.get("body_html") or "",
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
