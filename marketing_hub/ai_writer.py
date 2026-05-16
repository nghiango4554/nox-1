"""AI writer cho bài SEO sản phẩm Sintech (v2026-05-08).

Tuân thủ rules trong seo_writing_rules.md.
Output có 2 phase: "## Phân tích" + "## Bài viết hoàn chỉnh".
Body Markdown dùng format link `[**anchor**](url)`.

Provider:
- Default: OpenAI (gpt-4o-mini) — vợ Nghĩa đang dùng key OpenAI cá nhân
- Fallback: Anthropic (claude-haiku-4-5) nếu set env AI_PROVIDER=anthropic
- Key OpenAI tự load từ env OPENAI_API_KEY hoặc file .env/key_openai.txt
"""
import json
import os
import re
from pathlib import Path

CLAUDE_MODEL = "claude-haiku-4-5"
OPENAI_MODEL = "gpt-4o-mini"
RULES_PATH = Path(__file__).parent / "seo_writing_rules.md"
ENV_DIR = Path(__file__).parent / ".env"

# Hybrid reasoning effort theo loại SP — SP đơn giản dùng low (~50% nhanh hơn),
# SP phức tạp dùng medium để giữ chất lượng văn phong + spec accuracy.
SIMPLE_PRODUCT_KEYWORDS = [
    "cable", "cáp", "lót", "sạc", "dây", "ốp", "túi", "phụ kiện",
    "chuyển đổi", "đầu chuyển", "adapter", "hub usb", "bao", "ba lô",
]
COMPLEX_PRODUCT_KEYWORDS = [
    "laptop", "pc gaming", "máy tính", "vga", "cpu", "mainboard", "main",
    "màn hình", "monitor", "ghế gaming", "ssd", "ram",
]


def pick_reasoning_effort(product_type: str = "", product_name: str = "") -> str:
    """Pick reasoning effort theo loại SP. Default medium nếu không match keyword."""
    text = (str(product_type or "") + " " + str(product_name or "")).lower()
    for kw in SIMPLE_PRODUCT_KEYWORDS:
        if kw in text:
            return "low"
    for kw in COMPLEX_PRODUCT_KEYWORDS:
        if kw in text:
            return "medium"
    return "low"  # default low cho speed; medium chỉ khi keyword cụ thể match


# ─────────── MONEY PRODUCT DETECTION ───────────
MONEY_PRODUCT_KEYWORDS = [
    # Tấm nền/màn cao cấp
    "qd-oled", "qd oled", "240hz", "360hz", "4k uhd", "5k", "8k", "miniled", "mini-led",
    # CPU/GPU cao cấp
    "rtx 4070", "rtx 4080", "rtx 4090", "rtx 5070", "rtx 5080", "rtx 5090",
    "rx 7800", "rx 7900", "rx 9070", "rx 9080",
    "i7-14", "i7-15", "i9-13", "i9-14", "i9-15",
    "ryzen 7 9", "ryzen 9 7", "ryzen 9 9",
    # Brand laptop/PC cao cấp
    "macbook", "iphone", "ipad pro",
    "asus rog", "rog strix", "rog zephyrus", "rog ally",
    "msi raider", "msi titan", "msi stealth",
    "razer blade", "alienware",
    "lenovo legion 9", "lenovo legion pro", "thinkpad x1",
    "predator helios", "acer predator triton",
    # SSD enthusiast
    "wd black sn8", "wd black sn7", "samsung 990 pro", "kingston fury",
    # Case / tản nước flagship
    "lian li o11", "lian li dynamic", "corsair icue 7000",
    "nzxt h9", "fractal north",
    # Tai nghe / chuột flagship
    "logitech g pro x", "razer viper v3", "razer deathadder v3 pro",
    "steelseries arctis nova pro",
]


def detect_money_product(product_name: str = "", product_type: str = "", vendor: str = "") -> bool:
    """Auto-detect SP money product theo keyword match.

    Vợ có thể override bằng checkbox trong web UI (`is_money_product` column).
    """
    text = (str(product_name or "") + " " + str(product_type or "") + " " + str(vendor or "")).lower()
    for kw in MONEY_PRODUCT_KEYWORDS:
        if kw in text:
            return True
    return False


# ─────────── 4 TEMPLATES XOAY VÒNG (10 bài/template) ───────────
TEMPLATE_NAMES = ["A", "B", "C", "D"]
TEMPLATE_DESCRIPTIONS = {
    "A": "STANDARD — Điểm nổi bật + Trải nghiệm + Phù hợp với ai + Thông số + Ưu điểm",
    "B": "TRẢI NGHIỆM-FIRST — Cảm giác mở hộp + Trên bàn / setup + Khi dùng hằng ngày + Cần check trước mua",
    "C": "SO SÁNH-FIRST — Giải quyết vấn đề gì + So với mặt bằng tầm giá + Khi nào nên/không phù hợp",
    "D": "HƯỚNG DẪN-FIRST — Dành cho cấu hình nào + Cách chọn không sai bước (3 bước) + Lưu ý lắp đặt",
}
TEMPLATE_BLOCKS = {
    "A": """H2: [Tên SP]
  Intro 2-4 câu + [**Sintech**](https://sintech.vn).
H2: Điểm nổi bật của [tên SP]
  (Đoạn dẫn ≥2 câu)
  H3: Thiết kế & cảm giác sử dụng
  H3: Hiệu năng / cảm giác thao tác
  H3: Tính năng đáng chú ý
H2: Trải nghiệm thực tế khi sử dụng
H2: Sản phẩm này phù hợp với ai
H2: Thông số nổi bật cần biết
H2: Ưu điểm khi chọn [tên SP]
H2: Vì sao nên mua tại Sintech (đúng 2 đoạn × 2 câu)
H2: Câu hỏi thường gặp về [tên SP] (mỗi câu hỏi là H3, 4-6 câu)
[Outro] [Author signature] [Outline table]""",
    "B": """H2: [Tên SP]
  Intro 2-4 câu + [**Sintech**](https://sintech.vn).
H2: Cảm giác đầu tiên khi mở hộp
H2: Trên bàn làm việc / setup gaming
  (Đoạn dẫn ≥2 câu)
  H3: Bố trí gọn gàng
  H3: Hợp tone setup nào
H2: Khi dùng hằng ngày
  (Đoạn dẫn ≥2 câu)
  H3: Tình huống học tập / văn phòng
  H3: Tình huống chơi game / giải trí
H2: Cần kiểm tra gì trước khi mua
H2: Thông số đáng chú ý
H2: Vì sao nên mua tại Sintech (đúng 2 đoạn × 2 câu)
H2: Câu hỏi thường gặp về [tên SP] (mỗi câu hỏi là H3, 4-6 câu)
[Outro] [Author signature] [Outline table]""",
    "C": """H2: [Tên SP]
  Intro 2-4 câu + [**Sintech**](https://sintech.vn).
H2: [Tên SP] giải quyết vấn đề gì
H2: So với mặt bằng chung trong tầm giá
  (Đoạn dẫn ≥2 câu)
  H3: Điểm nổi trội
  H3: Điểm cần cân nhắc
H2: Khi nào nên chọn [tên SP]
H2: Khi nào không phù hợp
H2: Thông số nổi bật cần biết
H2: Vì sao nên mua tại Sintech (đúng 2 đoạn × 2 câu)
H2: Câu hỏi thường gặp về [tên SP] (mỗi câu hỏi là H3, 4-6 câu)
[Outro] [Author signature] [Outline table]""",
    "D": """H2: [Tên SP]
  Intro 2-4 câu + [**Sintech**](https://sintech.vn).
H2: [Tên SP] dành cho cấu hình nào
H2: Cách chọn [loại SP] không sai bước
  (Đoạn dẫn ≥2 câu)
  H3: Bước 1: xác định nhu cầu
  H3: Bước 2: kiểm tra tương thích
  H3: Bước 3: chọn theo ngân sách
H2: Lưu ý khi lắp đặt / sử dụng
H2: Thông số kỹ thuật cần biết
H2: Vì sao nên mua tại Sintech (đúng 2 đoạn × 2 câu)
H2: Câu hỏi thường gặp về [tên SP] (mỗi câu hỏi là H3, 4-6 câu)
[Outro] [Author signature] [Outline table]""",
}


def pick_template(job_id: int) -> str:
    """Round-robin 4 templates, mỗi template 10 bài liên tiếp.

    Job 1-10 → A, 11-20 → B, 21-30 → C, 31-40 → D, 41-50 → A...
    """
    if not job_id or job_id < 1:
        return "A"
    cycle = (job_id - 1) // 10
    return TEMPLATE_NAMES[cycle % len(TEMPLATE_NAMES)]


def _load_rules() -> str:
    if RULES_PATH.exists():
        return RULES_PATH.read_text(encoding="utf-8")
    return ""


def _load_openai_key() -> str:
    """Tìm key OpenAI theo thứ tự: env var → .env/key_openai.txt."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip()
    f = ENV_DIR / "key_openai.txt"
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    return ""


def _load_anthropic_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def _resolve_provider() -> str:
    """Pick provider — env AI_PROVIDER override, else priority codex > openai > anthropic.

    `codex` ưu tiên cao nhất vì dùng quota ChatGPT login (KHÔNG tốn API credit).
    """
    explicit = os.environ.get("AI_PROVIDER", "").lower().strip()
    if explicit in ("codex", "openai", "anthropic"):
        return explicit
    try:
        import codex_provider
        if codex_provider.is_codex_available():
            return "codex"
    except Exception:
        pass
    if _load_openai_key():
        return "openai"
    if _load_anthropic_key():
        return "anthropic"
    return "codex"  # default — sẽ raise nếu chưa có gì


SYSTEM_PROMPT_TEMPLATE = """Bạn là chuyên viên content SEO cho Sintech.vn — chuỗi cửa hàng PC/laptop/linh kiện gaming.
Nhiệm vụ: viết bài SEO sản phẩm cho website Haravan của Sintech, tuân thủ NGHIÊM NGẶT bộ rules dưới đây.

═══════════ RULES SEO SINTECH ═══════════

{rules}

═══════════ FORMAT OUTPUT BẮT BUỘC ═══════════

Trả về **1 JSON object duy nhất** với schema chính xác:

{{
  "analysis_md": "Nội dung phần Phân tích viết Markdown — gồm: keyword chính, keyword phụ, search intent, đối tượng khách hàng, hướng viết unique, ghi chú nguồn (nếu có), CTA cố định, BẢNG kế hoạch internal link (5 cột: Vị trí | Anchor text | URL | Loại link | Lý do).",
  "titles": ["title 1 (45-61 ký tự, KHÔNG 'Sintech')", "title 2", "title 3"],
  "metas": ["meta 1 (140-160 ký tự, có CTA HOA)", "meta 2", "meta 3"],
  "keywords": "keyword chính, keyword phụ 1, keyword phụ 2, ...",
  "outline_md": "Bảng Markdown 2 cột (| Cấp heading | Nội dung |) chỉ liệt kê H2/H3 đã dùng trong body.",
  "body_md": "TOÀN BỘ bài viết Markdown — KHÔNG H1, chỉ H2 và H3. H2 đầu tiên là TÊN SẢN PHẨM, nằm TRÊN intro. Intro 2-4 câu sau H2 đầu, có CTA [**Sintech**](https://sintech.vn). Body có đủ 3-6 internal link dạng [**anchor**](url) — KHÔNG dùng **[anchor](url)**. Section 'Vì sao nên mua tại Sintech' đúng 2 đoạn × 2 câu, BẮT BUỘC chèn nguyên văn câu chính sách. Outro 2-3 câu mở bằng 'Tóm lại,/Nói ngắn gọn,/Sau tất cả,/Kết lại,' + có [**Sintech**](https://sintech.vn). Bài tổng 800-2700 từ. Public dùng 'bạn', KHÔNG dùng 'anh'."
}}

QUAN TRỌNG:
- Chỉ trả 1 JSON object, KHÔNG bọc markdown code fence (```), KHÔNG bình luận thêm.
- `analysis_md`, `outline_md`, `body_md` là chuỗi Markdown thuần — preserve newlines (\\n).
- Internal link **bắt buộc** format `[**anchor text**](URL)` — TUYỆT ĐỐI không dùng `**[anchor](URL)**`.
- Cấm các cụm SEOer/học thuật đã liệt kê trong rules."""


def _build_user_prompt(product_info: dict) -> str:
    template_id = product_info.get("template_id", "A")
    template_desc = TEMPLATE_DESCRIPTIONS.get(template_id, "")
    template_block = TEMPLATE_BLOCKS.get(template_id, "")

    user_prompt = (
        "Viết bài SEO cho sản phẩm sau, tuân thủ ĐẦY ĐỦ rules:\n\n"
        f"**Tên sản phẩm:** {product_info['product_name']}\n"
    )
    if product_info.get("product_type"):
        user_prompt += f"**Loại:** {product_info['product_type']}\n"
    if product_info.get("vendor"):
        user_prompt += f"**Hãng:** {product_info['vendor']}\n"

    # Research-driven heading (Phase 2 — Google Suggest data)
    research = product_info.get("keyword_research") or {}
    if research and research.get("raw_suggestions"):
        user_prompt += (
            f"\n**🔍 KEYWORD RESEARCH THỰC (từ Google Suggest VN)** — DÙNG ĐỂ DESIGN H2:\n"
        )
        # Top 15 suggestions
        for s in research["raw_suggestions"][:15]:
            user_prompt += f"- {s}\n"
        if research.get("top_questions"):
            user_prompt += "\n**Top câu hỏi khách thường tìm:**\n"
            for q in research["top_questions"][:8]:
                user_prompt += f"- {q}\n"
        # Intent breakdown
        by_intent = research.get("by_intent") or {}
        intent_labels = {
            "price": "💰 Giá",
            "review": "⭐ Review/đánh giá",
            "comparison": "🔀 So sánh / nên mua nào",
            "compatibility": "🔌 Tương thích / dùng được không",
            "guide": "📘 Hướng dẫn / setup",
            "trust": "🏪 Mua ở đâu uy tín",
        }
        non_empty = {k: v for k, v in by_intent.items() if v and k in intent_labels}
        if non_empty:
            user_prompt += "\n**Intent phân loại (dùng cái nào có nhiều suggestion → quan trọng):**\n"
            for k, items in non_empty.items():
                user_prompt += f"- {intent_labels[k]} ({len(items)} suggestions): {', '.join(items[:3])}\n"

        user_prompt += (
            "\n**🎯 NHIỆM VỤ HEADING:**\n"
            "- Design 6-8 H2 (KHÔNG tính H2 đầu tên SP + 'Vì sao Sintech' + 'FAQ') DỰA TRÊN intent + questions thực tế ở trên.\n"
            "- KHÔNG dùng H2 generic 'Điểm nổi bật / Trải nghiệm thực tế'. Thay vào đó, biến câu hỏi search thành H2 (vd 'X có tốt không' → H2 'X có thực sự đáng mua không').\n"
            "- Mix cả intent giá, review, hợp ai, dùng được không, lỗi thường gặp — theo tỉ lệ intent nào nhiều suggestion thì ưu tiên section dài hơn.\n"
            "- Cấu trúc cố định 3 section CUỐI: 'Vì sao nên mua tại Sintech' (2 đoạn × 2 câu), 'Câu hỏi thường gặp' (mỗi câu hỏi H3, lấy từ top questions), Outro + Author signature + Outline.\n"
        )
    else:
        # Fallback template cứng nếu không có research data
        user_prompt += (
            f"\n**🎯 TEMPLATE BẮT BUỘC: Template {template_id} — {template_desc}**\n"
            f"Cấu trúc cụ thể PHẢI tuân theo:\n```\n{template_block}\n```\n"
            f"TUYỆT ĐỐI KHÔNG đổi sang template khác. Mọi H2/H3 phải đúng theo cấu trúc trên.\n"
        )
    if product_info.get("usp"):
        user_prompt += f"**USP nhấn mạnh:** {product_info['usp']}\n"

    specs = product_info.get("specs", "")
    has_real_specs = specs and len(specs.strip()) > 50 and not specs.startswith("(SP chưa có")
    if has_real_specs:
        user_prompt += f"\n**Thông số / mô tả tham khảo (NGUỒN DUY NHẤT để lấy spec):**\n{specs}\n"
    else:
        user_prompt += (
            "\n**⚠️ SẢN PHẨM CHƯA CÓ DATASHEET — TUYỆT ĐỐI KHÔNG BỊA SPEC:**\n"
            "- Chỉ được dùng các spec/số đã xuất hiện trong TÊN SẢN PHẨM phía trên.\n"
            "- KHÔNG thêm Hz/V/A/W/GB/inch/MHz... nếu chưa có trong tên SP.\n"
            "- Section 'Thông số nổi bật' viết theo CÔNG NĂNG (kết nối linh hoạt, thiết kế gọn, "
            "tương thích đa thiết bị) thay vì số bịa.\n"
            "- Thà 3-4 dòng spec đúng còn hơn 7 dòng bịa.\n"
        )

    suggested_links = product_info.get("suggested_links") or []
    if suggested_links:
        user_prompt += "\n**Gợi ý internal link (chọn 3-6 link phù hợp ưu tiên category > liên quan > phụ kiện > nhu cầu):**\n"
        for sl in suggested_links[:10]:
            user_prompt += f"- `[**{sl.get('anchor','')}**]({sl.get('url','')})` ({sl.get('source','')})\n"
        user_prompt += "\nIntro và outro PHẢI có `[**Sintech**](https://sintech.vn)`.\n"

    # Money product → format SPEC-FIRST (mỗi spec/feature là 1 H3 riêng)
    if product_info.get("is_money_product"):
        user_prompt += (
            "\n**💰 MONEY PRODUCT — FORMAT SPEC-FIRST BẮT BUỘC:**\n"
            "Section 'Điểm nổi bật của [tên SP]' phải dùng format **5-8 H3 SPEC/FEATURE riêng** "
            "(không phải H3 generic 'Thiết kế' / 'Hiệu năng'):\n"
            "- Mỗi H3 = **TÊN SPEC/FEATURE cụ thể có số liệu**, ví dụ:\n"
            "  - `### Dung lượng 256GB`\n"
            "  - `### Màn hình Super Retina XDR OLED 6.3\"`\n"
            "  - `### Chip Apple A19 Bionic`\n"
            "  - `### Camera chính 48MP Fusion`\n"
            "  - `### Mặt kính Ceramic Shield 2`\n"
            "- Dưới mỗi H3 = **1-2 đoạn 60-150 từ** diễn giải spec đó trong ngữ cảnh dùng (giải thích spec, "
            "ai phù hợp, có thể đính kèm 1 internal link đến variant/category liên quan).\n"
            "- Thứ tự H3: spec quan trọng nhất TRƯỚC (CPU/GPU/RAM/màn → camera/cảm giác → tính năng → kết nối/pin).\n"
            "- VD đoạn diễn giải tốt:\n"
            "  > `### Dung lượng 256GB`\n"
            "  > Tuy không quá lớn nhưng 256GB vẫn đáp ứng nhu cầu cơ bản như lưu ảnh, video 4K và tải app. "
            "  > Nếu bạn cần lưu nhiều hơn, các phiên bản [**512GB**](url) hoặc [**1TB**](url) sẽ phù hợp hơn.\n"
            "- **CẤM** dùng H3 generic kiểu 'Thiết kế & cảm giác sử dụng' / 'Hiệu năng / cảm giác thao tác' khi là money product — phải SPEC cụ thể.\n"
            "- **BOLD spec số quan trọng** trong văn xuôi (vd `**240Hz**`, `**16GB DDR5**`).\n"
        )

    user_prompt += (
        "\nQUAN TRỌNG — KIỂM TRA KỸ TRƯỚC KHI TRẢ:\n"
        "1. **TUYỆT ĐỐI KHÔNG bịa thông số kỹ thuật**. Chỉ được dùng spec từ TÊN SP + mô tả input. "
        "Cấm thêm số (Hz/V/A/W/GB/inch...) nếu chưa có trong nguồn input. Spec không chắc → BỎ.\n"
        "2. KHÔNG H1. KHÔNG `---`. Public dùng 'bạn', KHÔNG dùng 'anh'.\n"
        "3. **MỌI H2 (kể cả H2 trong body) BẮT BUỘC có ≥2 câu dẫn** ngay dưới heading bao quát toàn bộ nội dung của H2 đó, RỒI mới tới H3. Cấm để H2 đứng kề H3 mà không có đoạn dẫn.\n"
        "4. **Outro KHÔNG có heading H2 riêng** — viết liền sau FAQ, dạng `<p>` mở bằng 'Tóm lại,/Nói ngắn gọn,/Sau tất cả,/Kết lại,'. CẤM chèn H2 'Kết lại về [tên SP]', 'Tổng kết', 'Lời kết' trước outro.\n"
        "5. Viết đủ ý theo outline, KHÔNG ép độ dài cụ thể — mỗi câu phải có nội dung thật, hết ý thì dừng, không kéo dài/lặp/filler. Internal link 3-6 trong body + Sintech ở intro và outro.\n"
        "6. Internal link **bắt buộc** format `[**anchor**](url)` — TUYỆT ĐỐI không dùng `**[anchor](url)**`. **Anchor MAX 30 ký tự**, là keyword NGẮN (vd 'thẻ nhớ MicroSD 64GB', 'chuột gaming', 'màn hình 2K') — TUYỆT ĐỐI KHÔNG dùng full tên SP làm anchor (vd 'Thẻ nhớ MicroSD 64G TEAMGROUP Box Class10 U1 100MB/s' SAI).\n"
        "7. **Title 45-61 ký tự**, KHÔNG 'Sintech' trong title. Đếm KỸ ký tự trước khi trả.\n"
        "8. **Meta 140-160 ký tự** — CỨNG min 140! ĐẾM TỪNG KÝ TỰ TRƯỚC KHI TRẢ. Nếu meta dưới 140c, BỔ SUNG: ngữ cảnh dùng (vd 'trên bàn làm việc rộng', 'cho setup gaming gọn'), lợi ích kép ('vừa A vừa B'), tên ứng dụng/phần mềm phù hợp. Phải có CTA viết HOA phần hành động (XEM NGAY/CHỌN NGAY/THAM KHẢO NGAY/KHÁM PHÁ NGAY). Tham khảo MẪU META trong rules section 4.\n"
        "9. **VĂN PHONG**: KHÔNG cộc lốc. KHÔNG mọi câu đều mở 'Bạn...'. Đa dạng câu mở dùng connector: 'Hiện nay...', 'Đối với...', 'Nhờ đó...', 'Trong khi đó...', 'Ngoài ra...', 'Tuy nhiên...', 'Bên cạnh đó...', 'Một điểm đáng chú ý là...', 'Nếu... thì...'. Đoạn văn 2-3 câu nối ý mượt — câu sau dẫn dắt từ câu trước, KHÔNG liệt kê spec rời rạc.\n"
        "10. Đọc kỹ section 'VĂN PHONG MẪU' ở đầu rules — viết theo tone 'người am hiểu chia sẻ' giống bài PC văn phòng / máy bộ mẫu.\n"
        "11. **VARY câu mở intro** — KHÔNG phải bài nào cũng mở '[Tên SP] là [loại SP]...'. Chọn 1 trong 5 hook ở rules section 7 (định nghĩa / trải nghiệm thực / nhu cầu khách / so sánh / tình huống dùng). Đa dạng giữa các bài.\n"
        "12. **BẮT BUỘC author signature CUỐI bài** (sau outro paragraph), nguyên văn in nghiêng:\n"
        "    *Tư vấn cấu hình bởi team kỹ thuật Sintech — Hotline 0911 713 000 · 457 Trần Xuân Soạn, Q7, TP.HCM.*\n"
        "13. **FAQ section**: Section 'Câu hỏi thường gặp' là H2, **mỗi câu hỏi BẮT BUỘC là H3** (`### [câu hỏi]?`). KHÔNG để câu hỏi dạng paragraph thường hoặc bold. Câu trả lời 2-4 câu paragraph ngay sau H3.\n"
        "14. Output 1 JSON object đúng schema {analysis_md, titles, metas, keywords, outline_md, body_md}, KHÔNG markdown code fence."
    )
    return user_prompt


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI
    api_key = _load_openai_key()
    if not api_key:
        raise RuntimeError("Thiếu OPENAI_API_KEY (env hoặc .env/key_openai.txt).")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        max_tokens=12000,
        temperature=0.7,
    )
    return resp.choices[0].message.content or ""


def _call_codex(system_prompt: str, user_prompt: str, reasoning_effort: str = "low") -> str:
    import codex_provider
    return codex_provider.call_codex(
        system_prompt, user_prompt,
        timeout=240,
        reasoning_effort=reasoning_effort,
    )


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    from anthropic import Anthropic
    api_key = _load_anthropic_key()
    if not api_key:
        raise RuntimeError("Thiếu ANTHROPIC_API_KEY.")
    client = Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=12000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return msg.content[0].text


def regen_metas_only(product_info: dict, current_metas: list, bad_indices: list) -> list:
    """Regen từng meta sai length (140-160c) bằng AI.

    Args:
        product_info: dict chứa product_name, vendor, product_type, specs
        current_metas: 3 meta hiện tại
        bad_indices: list 0-based index các meta cần regen (e.g. [0, 2])

    Returns:
        list 3 meta mới — meta KHÔNG cần regen giữ nguyên, meta cần regen được thay.
        Nếu AI fail → trả về current_metas (không phá).
    """
    if not bad_indices:
        return current_metas

    PATTERN_DESC = {
        0: "M1 = SPEC: '[Tên SP] [màu] [size], [spec chính 1-2 con số], [đặc điểm]. XEM NGAY tại Sintech.'",
        1: "M2 = SETUP/NHU CẦU: 'Setup/Build [tone/use case] cùng [SP] - [tính năng], [đặc điểm]. THAM KHẢO NGAY tại Sintech.'",
        2: "M3 = GIẢI PHÁP: '[SP ngắn] - giải pháp [phục vụ ai], [đặc điểm chốt]. CHỌN NGAY mẫu phù hợp tại Sintech.'",
    }

    slot_descs = "\n".join(f"- Slot M{i+1}: {PATTERN_DESC.get(i, '')}" for i in bad_indices)
    current_block = "\n".join(
        f"- M{i+1} cũ ({len(current_metas[i])}c — SAI vì {'<140' if len(current_metas[i])<140 else '>160'}): {current_metas[i]}"
        for i in bad_indices if i < len(current_metas)
    )

    system = (
        "Bạn là chuyên gia viết SEO meta description tiếng Việt cho cửa hàng Sintech (PC Gaming & Gear). "
        "Mỗi meta description PHẢI có CHÍNH XÁC từ 140 đến 160 ký tự (đếm cả khoảng trắng và dấu câu). "
        "Trả về JSON object đúng schema, KHÔNG markdown fence."
    )

    user = (
        f"**Sản phẩm:** {product_info.get('product_name','')}\n"
        f"**Hãng:** {product_info.get('vendor','')}\n"
        f"**Loại:** {product_info.get('product_type','')}\n\n"
        f"**META CŨ SAI LENGTH (cần viết lại):**\n{current_block}\n\n"
        f"**PATTERN BẮT BUỘC (theo slot):**\n{slot_descs}\n\n"
        "**RULES:**\n"
        "- ĐẾM TỪNG KÝ TỰ trước khi trả — meta DƯỚI 140c hoặc TRÊN 160c bị reject\n"
        "- Phải có: tên SP + spec/lợi ích + ngữ cảnh dùng + CTA HOA cuối câu\n"
        "- CTA mặc định: M1=XEM NGAY tại Sintech / M2=THAM KHẢO NGAY tại Sintech / M3=CHỌN NGAY mẫu phù hợp tại Sintech\n"
        "- CẤM filler: 'bền bỉ', 'đẹp mắt', 'Free ship', 'tốt nhất 2026', 'đáng mua nhất', 'khôn nhất'\n"
        "- CẤM bịa số liệu (Hz/V/A/W/GB/inch/MHz...) chưa có trong tên SP\n"
        "- Nếu meta ngắn dưới 140c → BỔ SUNG: ngữ cảnh dùng cụ thể ('cho setup gaming gọn', 'trên bàn làm việc rộng'), lợi ích kép ('vừa A vừa B'), suffix 'với giá tốt'/'với giá ưu đãi' trước CTA cuối\n"
        "- 1 câu hoàn chỉnh, văn phong tự nhiên, KHÔNG nhồi spec\n\n"
        f"Trả về JSON:\n"
        f"{{\"metas\": [\"<M1 hoặc giữ cũ>\", \"<M2 hoặc giữ cũ>\", \"<M3 hoặc giữ cũ>\"]}}\n"
        f"— Chỉ thay slot {sorted([i+1 for i in bad_indices])}, các slot khác trả về NGUYÊN VĂN meta cũ."
    )

    provider = _resolve_provider()
    try:
        if provider == "codex":
            raw = _call_codex(system, user, reasoning_effort="low")
        elif provider == "anthropic":
            raw = _call_anthropic(system, user)
        else:
            raw = _call_openai(system, user)
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()
        data = json.loads(raw)
        new_metas = data.get("metas") or []
        if len(new_metas) != 3:
            return current_metas
        # Merge: chỉ thay bad slots, giữ slot OK nguyên văn
        merged = list(current_metas)
        for i in bad_indices:
            if i < len(new_metas) and new_metas[i]:
                merged[i] = new_metas[i]
        return merged
    except Exception as e:
        print(f"[regen_metas_only] fail: {e}")
        return current_metas


def auto_fix_metas(product_info: dict, metas: list, max_retries: int = 2) -> tuple:
    """Auto-fix 3 meta về length 140-160c.

    Strategy:
      1. Quick fix (no AI): nếu meta thiếu 1-15c → thử thêm suffix " với giá tốt." / " với giá ưu đãi." trước CTA
      2. AI regen (max N lần): regen các slot vẫn sai

    Returns: (new_metas, info_dict {fixed_by, attempts, still_bad})
    """
    metas = list(metas)
    info = {"fixed_by": [], "attempts": 0, "still_bad": []}

    def _bad_idx(ms):
        return [i for i, m in enumerate(ms) if not (140 <= len(m) <= 160)]

    # Bước 1: quick fix bằng suffix
    QUICK_SUFFIXES = [" với giá tốt", " với giá ưu đãi"]
    for i, m in enumerate(metas):
        L = len(m)
        if 140 <= L <= 160:
            continue
        if L < 140 and L >= 125:  # thiếu 1-15c → thử suffix
            for suf in QUICK_SUFFIXES:
                # Insert suffix trước dấu chấm cuối nếu có
                if m.endswith("."):
                    candidate = m[:-1] + suf + "."
                else:
                    candidate = m + suf
                if 140 <= len(candidate) <= 160:
                    metas[i] = candidate
                    info["fixed_by"].append(f"M{i+1}=quick_suffix")
                    break

    # Bước 2: AI regen các slot vẫn sai
    bad = _bad_idx(metas)
    for attempt in range(max_retries):
        if not bad:
            break
        info["attempts"] = attempt + 1
        new_metas = regen_metas_only(product_info, metas, bad)
        # Chỉ accept slot regen nếu length đúng, không thì giữ nguyên
        for i in bad:
            cand = new_metas[i] if i < len(new_metas) else metas[i]
            if 140 <= len(cand) <= 160:
                metas[i] = cand
                info["fixed_by"].append(f"M{i+1}=ai_regen_attempt{attempt+1}")
        bad = _bad_idx(metas)

    info["still_bad"] = [f"M{i+1}={len(metas[i])}c" for i in bad]
    return metas, info


def generate_blog_post(product_info: dict) -> dict:
    """Tạo bài SEO từ thông tin SP — auto pick provider OpenAI/Anthropic.

    Returns dict: {analysis_md, titles, metas, keywords, outline_md, body_markdown, stats}
    """
    rules = _load_rules()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(rules=rules)
    user_prompt = _build_user_prompt(product_info)

    provider = _resolve_provider()
    if provider == "codex":
        effort = pick_reasoning_effort(
            product_info.get("product_type", ""),
            product_info.get("product_name", ""),
        )
        raw = _call_codex(system_prompt, user_prompt, reasoning_effort=effort)
    elif provider == "anthropic":
        raw = _call_anthropic(system_prompt, user_prompt)
    else:
        raw = _call_openai(system_prompt, user_prompt)

    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"AI ({provider}) không trả JSON hợp lệ: {e}\n--- raw ---\n{raw[:500]}"
        )

    titles = data.get("titles") or []
    metas = data.get("metas") or []
    body_md = data.get("body_md") or data.get("body_markdown") or ""
    return {
        "analysis_md": data.get("analysis_md") or "",
        "titles": titles,
        "metas": metas,
        "keywords": data.get("keywords") or "",
        "outline_md": data.get("outline_md") or "",
        "body_markdown": body_md,
        "stats": {
            "provider": provider,
            "model": {
                "codex": "gpt-5.5 (via Codex CLI)",
                "openai": OPENAI_MODEL,
                "anthropic": CLAUDE_MODEL,
            }.get(provider, "unknown"),
            "reasoning_effort": pick_reasoning_effort(
                product_info.get("product_type", ""),
                product_info.get("product_name", ""),
            ) if provider == "codex" else None,
            "template_id": product_info.get("template_id", "A"),
            "title_lens": [len(t) for t in titles],
            "meta_lens": [len(m) for m in metas],
            "word_count": len(re.findall(r"\w+", body_md, flags=re.UNICODE)),
            "internal_link_count": len(re.findall(r"\[\*\*[^\]]+\]\(https?://[^)]+\)", body_md)),
        },
    }
