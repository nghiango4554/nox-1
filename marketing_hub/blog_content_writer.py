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
NHIỆM VỤ: Viết bài blog hướng dẫn / tin tức cho khách hàng (1500-3000 từ).
BODY HTML: viết đủ ý theo cấu trúc, KHÔNG ép độ dài. Mỗi câu có nội dung thật. KHÔNG H1 (page đã có H1 article title).

"""
    + sintech_rules.common_rules_block(cta_note="Blog có thể dùng thêm CTA 'TÌM HIỂU NGAY'.")
    + """

CẤU TRÚC BODY (blog hướng dẫn):
- Intro 3-4 câu nêu vấn đề + ai phù hợp + tóm tắt giải pháp + CTA <a href="https://sintech.vn"><strong>Sintech</strong></a>
- 4-6 section H2 phân tích chi tiết (mỗi H2 có 2-4 đoạn + H3 nếu cần)
- H2 "Câu hỏi thường gặp" — 4-5 FAQ H3
- Outro 2-3 câu chốt + CTA mua/inbox Sintech
- Có ít nhất 3 internal link về sintech.vn (collection/product chính)

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

Viết lại: title 45-61c + meta 140-160c + body_html theo cấu trúc blog hướng dẫn — đủ ý, không lặp, không filler kéo dài.
Trả JSON thuần."""

    try:
        import ai_provider
        raw = ai_provider.call_ai(_SYSTEM_PROMPT, user_msg, timeout=240)
    except Exception as e:
        return {"ok": False, "error": f"AI: {e}"}

    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {"ok": False, "error": "Codex không trả JSON.", "raw": text[:500]}
        try:
            data = json.loads(m.group(0))
        except Exception as e:
            return {"ok": False, "error": f"JSON parse: {e}", "raw": text[:500]}

    title = (data.get("title") or "").strip()
    meta = (data.get("meta") or "").strip()
    body_html = (data.get("body_html") or "").strip()

    if not title or not meta or not body_html:
        return {"ok": False, "error": "Codex trả thiếu field.", "raw": text[:500]}

    return {
        "ok": True,
        "title": title,
        "meta": meta,
        "body_html": body_html,
        "title_len": len(title),
        "meta_len": len(meta),
    }


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
