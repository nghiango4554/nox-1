"""Helper gen content cho BLOG ARTICLE (huong-dan/news) qua Codex CLI.

Flow:
  1. fetch_blog_context(url) — scrape HTML thật từ sintech.vn lấy title + h1 + existing body
  2. gen_blog_content(url, name, ...) — call Codex sinh title + meta + body HTML (1500-3000 từ)
  3. sync_blog_to_haravan(blog_id, article_id, ...) — PUT /blogs/{blog_id}/articles/{article_id}
"""
import re
import json
from typing import Optional
import requests
from bs4 import BeautifulSoup

import sintech_rules
import haravan_client
from collection_content_writer import compress_html, sanitize_pasted_html  # reuse

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def fetch_blog_context(url: str) -> dict:
    """Scrape sintech.vn article page → lấy title + h1 + body text snippet."""
    try:
        r = requests.get(url, headers=HEAD, timeout=20, allow_redirects=True, verify=False)
        if r.status_code >= 400:
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        soup = BeautifulSoup(r.content, "lxml")

        title_tag = soup.find("title")
        page_title = title_tag.get_text().strip() if title_tag else ""
        page_title = re.sub(r"\s*[-–|]\s*Sintech.*$", "", page_title, flags=re.I).strip()

        h1_tag = soup.find("h1")
        h1 = h1_tag.get_text().strip() if h1_tag else ""

        meta_desc_el = soup.find("meta", attrs={"name": "description"})
        existing_meta = meta_desc_el.get("content", "").strip() if meta_desc_el else ""

        body_el = (soup.select_one(".article-content")
                   or soup.select_one(".rte")
                   or soup.select_one("article")
                   or soup.select_one("main"))
        body_snippet = body_el.get_text(" ", strip=True)[:3000] if body_el else ""

        return {
            "ok": True,
            "page_title": page_title,
            "h1": h1,
            "existing_meta": existing_meta,
            "body_snippet": body_snippet,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


_SYSTEM_PROMPT = (
    """Bạn là chuyên gia content + SEO cho Sintech.vn (shop PC/laptop/gaming gear, nền tảng Haravan).

⚠️ GIỚI HẠN CỨNG — ĐỌC TRƯỚC KHI VIẾT:
- Xác định loại bài → áp đúng hạn mức từ:
    Tin nhanh: 700-1.000 từ | Hướng dẫn: 1.000-1.500 từ
    Tư vấn mua: 1.400-1.900 từ | So sánh: 1.600-2.200 từ
    Build PC: 1.800-2.600 từ | Top list: 1.800-2.500 từ
- Ngân sách từ mỗi section = tổng mục tiêu ÷ số H2. Viết đủ ngân sách đó rồi DỪNG, chuyển H2 tiếp.
- H3 CHỈ DÙNG cho: bước hướng dẫn (Bước 1/2/3) và FAQ. Bài tư vấn mua / tin nhanh / so sánh: KHÔNG dùng H3 ngoài FAQ — dùng prose hoặc bullet thay thế.
- Câu nào bỏ đi mà không mất ý → BỎ LUÔN. KHÔNG filler, KHÔNG diễn giải lại điều đã nói.
KHÔNG H1.

"""
    + sintech_rules.common_rules_block(cta_note="Blog có thể dùng thêm CTA 'TÌM HIỂU NGAY'.",
                                       is_product=False)
    + """

CẤU TRÚC BODY — tuân thủ outline đã gen (KHÔNG tự thêm H2/H3):
- Intro 2-3 câu: câu đầu chạm ngay rủi ro/phân vân thật — KHÔNG mở kiểu "Bài viết này sẽ giúp..."
- Bullet key takeaway 4-6 điểm (nếu bài tư vấn/so sánh/build) ngay sau intro
- Mỗi đoạn văn tối đa 3 câu, 1 ý — cắt ngay khi ý đã đủ
- Internal link chèn từ intro hoặc H2 đầu — anchor là keyword/danh mục cụ thể, KHÔNG dùng "tại đây"
- FAQ cuối (loại tư vấn/so sánh/build/top): 3-5 H3 câu hỏi thực tế — KHÔNG lặp nội dung đã viết
- Kết luận: 1-2 đoạn plain text + CTA tự nhiên — KHÔNG tạo H2 riêng cho kết luận
- Ít nhất 3 internal link sintech.vn

BẢNG DỮ LIỆU:
- Tư vấn mua: 1 bảng so sánh nhanh theo tình huống/phân khúc
- Build/so sánh/ngân sách/VGA/màn hình: 2 bảng (cấu hình theo mốc giá + FPS/thông số tham khảo)
- Style: <table style="width:100%;border-collapse:collapse"> — th/td có border:1px solid #ddd; padding:8px
- FPS/giá 2026 được phép dùng, ghi "(tham khảo, 2026)"

WORDING:
- Keyword volume cao: dùng tên model, tên phân khúc, cụm search phổ biến trong H2 và đoạn đầu mỗi section
- KHÔNG "tốt nhất/đáng mua nhất" vô tiêu chí — dùng "phù hợp nếu", "đáng cân nhắc khi"
- Phân biệt: thông tin chắc ≠ dự đoán xu hướng ≠ số liệu tham khảo
- CTA tự nhiên, KHÔNG ép thành đoạn bán hàng lộ liễu

E-E-A-T — GIỌNG TRẢI NGHIỆM THẬT (Experience, tín hiệu Google ưu tiên):
- Ưu tiên NGÔI THỨ NHẤT số nhiều "mình / bên mình / tụi mình" (giọng shop có trải nghiệm), KHÔNG viết như bài bách khoa khách quan khô khan.
- Mỗi bài chèn 1-3 nhận định TRẢI NGHIỆM/THỰC TẾ thay vì chỉ liệt kê: "khi bên mình lắp thử cho khách thấy...", "dùng thực tế mình nhận thấy...", "nhiều khách phản hồi với bên mình rằng...". Viết "khi dùng mình thấy nó..." thay cho "sản phẩm có...".
- KHÔNG bịa trải nghiệm phi lý (vd "mình đã test mọi tựa game") — chỉ nêu cảm nhận/quan sát hợp lý của một shop bán & lắp máy.
- Tiêu đề KHÔNG phóng đại/gây sốc. Trong bài KHÔNG cam kết tuyệt đối ("chạy mượt 100%", "bao max setting mọi game", "bền vĩnh viễn").
- KHÔNG internal link đánh lừa hay banner điều hướng dày đặc về trang bán hàng — link phải đúng ngữ cảnh người đọc cần.

OUTPUT BẮT BUỘC: chỉ JSON thuần, KHÔNG markdown code fence.
{
  "title": "...",
  "meta": "...",
  "body_html": "..."
}"""
)


def gen_blog_content(blog_url: str, article_title: str,
                     page_title: str = "", existing_meta: str = "",
                     body_snippet: str = "") -> dict:
    """Gen title + meta + body HTML cho 1 blog article (AI fallback chain Codex→Claude→Gemini)."""
    user_msg = f"""BLOG ARTICLE cần viết:
- Tiêu đề hiện tại: {article_title}
- URL: {blog_url}
- Page title hiện tại (Haravan): {page_title or '(rỗng)'}
- Meta hiện tại: {existing_meta or '(rỗng)'}
- Nội dung hiện tại (snippet 3000c): {body_snippet[:1500] if body_snippet else '(rỗng)'}

Viết lại: title 40-51c + meta 140-160c + body_html theo cấu trúc blog hướng dẫn — đủ ý, không lặp, không filler kéo dài.
Trả JSON thuần."""

    try:
        import ai_provider
        raw = ai_provider.call_ai(_SYSTEM_PROMPT, user_msg, timeout=240)
    except Exception as e:
        return {"ok": False, "error": f"AI: {e}"}

    return _parse_blog_json(raw)


def _parse_blog_json(raw: str) -> dict:
    """Parse output AI → {ok, title, meta, body_html, title_len, meta_len}."""
    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {"ok": False, "error": "AI không trả JSON.", "raw": text[:500]}
        try:
            data = json.loads(m.group(0))
        except Exception as e:
            return {"ok": False, "error": f"JSON parse: {e}", "raw": text[:500]}

    title = (data.get("title") or "").strip()
    meta = (data.get("meta") or "").strip()
    body_html = (data.get("body_html") or "").strip()

    if not title or not meta or not body_html:
        return {"ok": False, "error": "AI trả thiếu field.", "raw": text[:500]}

    # E-E-A-T: tự chèn hộp tác giả + Person schema cuối bài blog (idempotent).
    try:
        import author_block
        body_html = author_block.ensure_author_box(body_html)
    except Exception as _e:
        print(f"[blog] author_box skip: {_e}")

    return {
        "ok": True,
        "title": title,
        "meta": meta,
        "body_html": body_html,
        "title_len": len(title),
        "meta_len": len(meta),
    }


_OUTLINE_SYSTEM_PROMPT = """Bạn là chuyên gia SEO content cho Sintech.vn (cửa hàng PC gaming, linh kiện & gear tại TP.HCM).
Năm: 2026. NHIỆM VỤ: nhận heading đối thủ đã cào → dựng bộ heading SEO chuẩn 2026 ĐÚNG loại bài → rewrite wording unique.

# BƯỚC 0 — Nhận diện loại bài & số từ mục tiêu (tự làm, không in)
Phân topic vào 1 dạng (hoặc lai) và ghi nhớ số từ mục tiêu tương ứng:
A. "Tin công nghệ / cập nhật nhanh" → 700–1.000 từ
B. "Thủ thuật / sửa lỗi / hướng dẫn cài đặt" → 1.000–1.500 từ
C. "Tư vấn chọn mua" → 1.400–1.900 từ
D. "So sánh A vs B" → 1.600–2.200 từ
E. "Build PC theo ngân sách / cấu hình mẫu" → 1.800–2.600 từ
F. "Top sản phẩm / top cấu hình" → 1.800–2.500 từ
→ Xác định loại → chọn số H2/H3 phù hợp để bài đạt đúng độ dài mục tiêu.

# BƯỚC 1 — Áp KHUNG theo loại bài
A (Tin nhanh): mối đe dọa/điểm mới → cơ chế hoạt động → ảnh hưởng thực tế → việc cần làm ngay → (FAQ nếu còn chỗ)
B (Hướng dẫn): vấn đề/lỗi phổ biến → điều kiện cần → các bước thực hiện (BẮT BUỘC H2 "Bước N:" cụ thể, làm được ngay) → lưu ý thường gặp → FAQ
C (Tư vấn mua): xác định nhu cầu/phân khúc → từng tiêu chí chọn (1 H2/tiêu chí) → sai lầm hay gặp → gợi ý theo ngân sách → CTA → FAQ
D (So sánh): tổng quan 2 lựa chọn → so sánh từng tiêu chí → bảng tóm tắt → nên chọn theo nhu cầu → CTA → FAQ
E (Build PC): nhu cầu/mục đích dùng → nguyên tắc cân đối → từng linh kiện → cấu hình mẫu theo mốc giá → sai lầm khi build → CTA → FAQ
F (Top list): tiêu chí xếp hạng → từng lựa chọn (1 H2/SP) → so sánh nhanh → chọn theo nhu cầu/ngân sách → CTA → FAQ

# BƯỚC 2 — Rules SEO + Chất lượng (áp MỌI loại)
1. TITLE HOOK: title phải có keyword chính + pain-point hoặc ngữ cảnh ("dễ nhầm lẫn", "tránh mua sai", "có đáng mua", "nên chọn gì 2026").
2. INTRO CHẠM VẤN ĐỀ: H2 đầu hoặc intro phải chạm rủi ro/phân vân thật trong 2 câu đầu — KHÔNG mở quá chung chung.
3. QUESTION-HEADING: ≥30% heading dạng câu hỏi tự nhiên (Featured Snippet + PAA).
4. LONG-TAIL SO SÁNH: đối chiếu đặc trưng của chính chủ đề (thương hiệu/chuẩn kỹ thuật/phân khúc giá/công nghệ cũ-mới). KHÔNG bê ví dụ ngành khác.
5. FRESH ANGLE: ≥1 góc trend 2026 mà đối thủ chưa có.
6. INTERNAL LINK SỚM: outline phải chỉ định 1 vị trí chèn link nội bộ từ H2 đầu hoặc intro — anchor phải là keyword/danh mục rõ nghĩa, KHÔNG dùng "tại đây".
7. CTA TỰ NHIÊN: 1 H2 đẩy danh mục/sản phẩm Sintech liên quan — không ép thành đoạn bán hàng lộ liễu với bài kiến thức.
8. FAQ THỰC TẾ: chỉ bài loại B/C/D/E/F mới cần FAQ — 3-5 H3 là câu hỏi người mua thật sự hay hỏi, KHÔNG lặp nội dung bài.
9. DEDUP: gộp heading trùng chủ đề.
10. WORDING UNIQUE: buyer-facing tự nhiên, KHÔNG "tốt nhất/đáng mua nhất" nếu không có tiêu chí — dùng "phù hợp với", "đáng cân nhắc nếu".
11. DATA INTEGRITY: phân biệt rõ thông tin chắc chắn / xu hướng dự đoán / số liệu tham khảo. KHÔNG bịa giá, FPS, benchmark chưa kiểm chứng.

# OUTPUT BẮT BUỘC
JSON array thuần, KHÔNG markdown code fence, KHÔNG giải thích thêm.
[{"h2": "...", "h3s": ["...", "..."]}, ...]
Giới hạn cứng:
- Loại A (tin nhanh): 3 H2, tổng H3 ≤ 4
- Loại B (hướng dẫn): 4 H2, tổng H3 ≤ 6
- Loại C (tư vấn mua): 4-5 H2, tổng H3 ≤ 8
- Loại D (so sánh): 5 H2, tổng H3 ≤ 8
- Loại E/F (build/top): 5-6 H2, tổng H3 ≤ 10
H3 rỗng ("h3s": []) là hợp lệ — ưu tiên prose rõ hơn H3 thừa.
KHÔNG bịa thông số kỹ thuật cụ thể, KHÔNG ghi giá."""


def gen_outline(article_title: str, keyword: str = "", intent: str = "",
                unique_angle: str = "") -> dict:
    """Pass 1: Research heading đối thủ qua Serper → Gen unique H2/H3 outline.

    Trả {ok, outline_text, outline_json, urls_scraped (nếu có)}.
    """
    kw = keyword or article_title

    # Serper: cào heading đối thủ để AI gen khác biệt hơn
    competitor_ctx = ""
    urls_scraped: list[str] = []
    try:
        import serper_search
        if serper_search.is_serper_available():
            res = serper_search.research_competitor_headings(kw, max_urls=4)
            if res.get("ok"):
                competitor_ctx = res["competitor_headings_text"]
                urls_scraped = res.get("urls_scraped", [])
    except Exception as e:
        print(f"[gen_outline serper] {e}")

    competitor_block = ""
    if competitor_ctx:
        competitor_block = f"""
HEADING ĐỐI THỦ (đã cào từ top Google — dùng để TRÁNH TRÙNG, tạo heading KHÁC BIỆT):
{competitor_ctx[:2000]}

→ Phân tích góc chưa được khai thác, tạo outline riêng của Sintech.
"""

    user_msg = f"""BÀI BLOG cần outline:
- Tiêu đề: {article_title}
- Keyword chính: {kw}
- Search intent: {intent or '(suy ra từ tiêu đề)'}
- Góc viết riêng: {unique_angle or '(chọn góc khác biệt với đối thủ thường dùng)'}
{competitor_block}
Tạo outline H2/H3 đầy đủ, độc đáo, KHÁC đối thủ. Trả JSON array thuần."""
    try:
        import ai_provider
        raw = ai_provider.call_ai(_OUTLINE_SYSTEM_PROMPT, user_msg, timeout=120)
    except Exception as e:
        return {"ok": False, "error": f"AI outline: {e}"}

    text = (raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)

    def _parse_outline_json(s):
        data = json.loads(s)
        if not isinstance(data, list):
            return None
        lines = []
        for sec in data:
            h2 = (sec.get("h2") or "").strip()
            if h2:
                lines.append(f"## {h2}")
            for h3 in (sec.get("h3s") or []):
                lines.append(f"### {h3.strip()}")
        return "\n".join(lines), data

    try:
        outline_text, outline_json = _parse_outline_json(text)
        return {"ok": True, "outline_text": outline_text, "outline_json": outline_json, "urls_scraped": urls_scraped}
    except Exception:
        m = re.search(r"\[[\s\S]*\]", text)
        if m:
            try:
                outline_text, outline_json = _parse_outline_json(m.group(0))
                return {"ok": True, "outline_text": outline_text, "outline_json": outline_json, "urls_scraped": urls_scraped}
            except Exception:
                pass
        return {"ok": False, "error": "AI không trả outline JSON hợp lệ.", "raw": text[:400]}


def gen_blog_with_outline(brief: dict, outline_text: str) -> dict:
    """Pass 2: Gen bài blog đầy đủ, BẮT BUỘC bám outline đã research.

    Trả dict giống gen_blog_content_from_brief (ok, title, meta, body_html...).
    Auto-retry meta nếu ra < 140c.
    """
    title = (brief.get("article_title") or brief.get("title") or "").strip()
    link_hint = brief.get("internal_link_hint") or ""

    # Estimate article type from outline H2 count and title to set word budget hint
    h2_count = outline_text.count("\n## ")
    _type_hint = "tư vấn mua → 1.400-1.900 từ" if h2_count <= 6 else "build/top → 1.800-2.600 từ"
    if any(w in title.lower() for w in ["tin ", "cập nhật", "phát hành", "ra mắt"]):
        _type_hint = "tin nhanh → 700-1.000 từ"
    elif any(w in title.lower() for w in ["hướng dẫn", "cách ", "cài ", "sửa ", "khắc phục"]):
        _type_hint = "hướng dẫn → 1.000-1.500 từ"
    elif any(w in title.lower() for w in ["so sánh", "vs ", " hay "]):
        _type_hint = "so sánh → 1.600-2.200 từ"
    elif any(w in title.lower() for w in ["build", "cấu hình", "ngân sách"]):
        _type_hint = "build PC → 1.800-2.600 từ"
    elif any(w in title.lower() for w in ["top ", "tốt nhất", "đáng mua"]):
        _type_hint = "top list → 1.800-2.500 từ"

    user_msg = f"""BÀI BLOG MỚI — BÁM ĐÚNG OUTLINE, VIẾT GỌN ĐÚNG SỐ TỪ:
- Tiêu đề: {title}
- Keyword chính: {brief.get('keyword', '') or '(theo tiêu đề)'}
- Góc viết riêng: {brief.get('unique_angle', '') or '(theo outline)'}
- Internal link ưu tiên: {link_hint or '(collection/product Sintech liên quan nhất)'}
- Loại bài & ngân sách từ: {_type_hint} — chia đều cho {h2_count or 5} H2, mỗi section ~{int(1600/(h2_count or 5))} từ rồi DỪNG

OUTLINE (giữ đúng thứ tự, KHÔNG thêm/bỏ heading):
{outline_text}

Quy tắc viết:
- Mỗi section viết đủ ngân sách rồi chuyển tiếp — KHÔNG viết thêm dù "còn ý"
- Mỗi đoạn tối đa 3 câu, 1 ý — câu nào bỏ không mất ý thì bỏ
- H3 CHỈ dùng cho bước hướng dẫn (Bước 1/2/3) và FAQ — bài tư vấn/so sánh/tin: KHÔNG H3 ngoài FAQ
- title 40-51c + meta 140-160c (CTA HOA cuối)
- KHÔNG bịa giá, KHÔNG bịa thông số, KHÔNG filler
- Ít nhất 3 internal link sintech.vn (anchor là keyword/danh mục cụ thể)
- Nếu outline có "Các bước": viết đủ Bước 1, Bước 2... người đọc tự làm được
- Build/so sánh/ngân sách/VGA: 2 bảng HTML <table>. Tư vấn mua: 1 bảng so sánh nhanh. Số liệu ghi "(tham khảo, 2026)".
Trả JSON thuần."""

    try:
        import ai_provider
        raw = ai_provider.call_ai(_SYSTEM_PROMPT, user_msg, timeout=360)
    except Exception as e:
        return {"ok": False, "error": f"AI: {e}"}

    result = _parse_blog_json(raw)
    if result.get("ok") and len(result.get("meta", "")) < 140:
        try:
            import ai_provider
            retry_sys = "Bạn là SEO copywriter. Viết lại meta description tiếng Việt đủ 140-160 ký tự, có CTA HOA (VD: KHÁM PHÁ NGAY) cuối."
            retry_user = f"Bài: {result['title']}\nMeta cũ ({len(result['meta'])}c): {result['meta']}\nViết lại đủ 140-160c, chỉ trả text thuần không dấu ngoặc kép."
            new_meta = ai_provider.call_ai(retry_sys, retry_user, timeout=60).strip()
            new_meta = re.sub(r'^["\']+|["\']+$', '', new_meta).strip()
            if 135 <= len(new_meta) <= 165:
                result["meta"] = new_meta
                result["meta_len"] = len(new_meta)
        except Exception:
            pass
    return result


def gen_blog_content_from_brief(brief: dict) -> dict:
    """Gen bài blog MỚI từ brief (KHÔNG cào URL) — dùng cho job ai_pillar (T4 Pillar–Cluster).

    brief lấy từ row blog_jobs: article_title, keyword, intent, content_layer,
    unique_angle, article_type, pillar, internal_link_hint.
    """
    title = (brief.get("article_title") or brief.get("title") or "").strip()
    link_hint = brief.get("internal_link_hint") or ""
    layer_note = {
        "money": "money — sát sản phẩm, intent mua rõ, hướng người đọc tới quyết định mua.",
        "support": "support — giải quyết vấn đề trước khi mua/nâng cấp, xây niềm tin.",
        "media": "media — ngoài lề có kiểm soát, kéo traffic rộng nhưng vẫn liên quan tệp khách Sintech.",
    }.get((brief.get("content_layer") or "").strip(), brief.get("content_layer") or "")

    user_msg = f"""BÀI BLOG MỚI cần viết (VIẾT MỚI HOÀN TOÀN — không có nội dung cũ để tham khảo):
- Tiêu đề dự kiến: {title}
- Keyword chính: {brief.get('keyword', '') or '(theo tiêu đề)'}
- Search intent: {brief.get('intent', '') or '(suy ra từ tiêu đề)'}
- Lớp nội dung: {layer_note}
- Góc viết riêng (BẮT BUỘC bám): {brief.get('unique_angle', '') or '(tự chọn góc khác biệt)'}
- Loại bài: {brief.get('article_type', '')}
- Thuộc Pillar: {brief.get('pillar', '')}
- Internal link nên ưu tiên chèn về: {link_hint or '(collection/product Sintech liên quan nhất)'}

Viết: title 40-51c (bám keyword, KHÔNG chứa "Sintech") + meta 140-160c (CTA HOA cuối) + body_html theo đúng cấu trúc blog hướng dẫn ở trên. Bám keyword + intent + góc viết riêng. KHÔNG bịa thông số kỹ thuật. Có ít nhất 3 internal link về sintech.vn (ưu tiên {link_hint or 'collection/product liên quan'}). Trả JSON thuần."""

    try:
        import ai_provider
        raw = ai_provider.call_ai(_SYSTEM_PROMPT, user_msg, timeout=240)
    except Exception as e:
        return {"ok": False, "error": f"AI: {e}"}
    return _parse_blog_json(raw)


def sync_blog_to_haravan(blog_id: int, article_id: int,
                         title: str, meta: str, body_html: str) -> dict:
    """Sync article lên Haravan: body + SEO flat field trong 1 PUT.

    Theme đọc title/meta từ flat field `metafields_global_*` (verified 15/5).
    KHÔNG đổi field `title` (tên bài) để giữ slug.
    """
    import job_sync
    body_compressed = compress_html(sanitize_pasted_html(body_html))
    try:
        haravan_client.update_article(int(blog_id), int(article_id), {
            "body_html": body_compressed,
            **job_sync.seo_metafields(title, meta),
        })
    except Exception as e:
        return {"ok": False, "error": f"PUT article: {e}"}

    return {"ok": True}
