# -*- coding: utf-8 -*-
"""Blog Rewrite — P3 generation (provider THẬT).

Prompt versioned + JSON parser/repair + HTML sanitize (bs4 whitelist) + quality metrics.
KHÔNG PUT Haravan · KHÔNG apply · KHÔNG upload/rehost ảnh (giữ URL cũ + flag external).
"""
import json, re, html as _html
from urllib.parse import urlparse
import requests, urllib3
from bs4 import BeautifulSoup

import ai_provider

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROMPT_VERSION = "BLOG_REWRITE_PROMPT_V1"
GEN_TIMEOUT = 300

BLOG_REWRITE_PROMPT_V1 = """Bạn là biên tập viên SEO công nghệ cho Sintech.vn (cửa hàng máy tính, linh kiện, PC gaming tại TP.HCM).

NHIỆM VỤ: Viết một bài blog MỚI NGUYÊN BẢN dựa trên CHỦ ĐỀ và FACTS của bài cũ (bài cũ nghi copy từ đối thủ).

TUYỆT ĐỐI:
- KHÔNG spin chữ, KHÔNG paraphrase tuần tự từng câu.
- KHÔNG giữ bố cục cũ nếu bố cục có dấu hiệu copy → tạo outline mới.
- TUYỆT ĐỐI KHÔNG lặp lại chuỗi 5+ từ liên tiếp giống nguyên văn bài cũ; viết câu MỚI cấu trúc khác hẳn (mục tiêu trùng lặp 5-gram ≤ 12%). Với bài so sánh: viết lại nội dung từng ô bảng theo cách diễn đạt riêng, gom facts theo nhu cầu người dùng.
- KHÔNG mô phỏng văn phong nguồn đối thủ. KHÔNG sao chép đoạn văn.
- KHÔNG giữ tên thương hiệu/đối thủ, watermark, hay link quảng bá đối thủ (vd "cùng GEARVN tìm hiểu", alt ảnh tên đối thủ).
- KHÔNG bịa thông số, KHÔNG bịa giá, KHÔNG bịa nguồn. Giữ facts kỹ thuật ĐÚNG.
- KHÔNG tự đổi handle, KHÔNG tự publish, KHÔNG nhắc rằng bài do AI viết.

YÊU CẦU:
- Xác định search intent, viết outline mới, tổ chức lại luận điểm, bổ sung giải thích hữu ích.
- Giọng văn buyer-facing dễ đọc, phù hợp Sintech. Heading trong body CHỈ dùng H2/H3.
- Mở đầu ngắn (2-3 câu), có đoạn tóm tắt, có kết luận, CTA Sintech nhẹ ở cuối.
- Giữ internal link Sintech hợp lý nếu còn phù hợp; flag external link & external image (KHÔNG tự xóa).
- Tên sản phẩm/spec/thuật ngữ kỹ thuật được phép giống (không phải copy).
- ẢNH: Bài gốc có sẵn ảnh trên CDN Sintech (hstatic.net) — GIỮ LẠI các ảnh này (dùng ĐÚNG src được cung cấp), chèn vào vị trí hợp lý trong body mới (rải đều sau các H2). VIẾT LẠI thuộc tính alt thành mô tả tiếng Việt tự nhiên, BỎ HẾT tên thương hiệu nguồn (GEARVN, FPT...) trong alt và src. KHÔNG bịa ảnh mới.

CHỈ trả về JSON hợp lệ ĐÚNG schema sau (không markdown, không text ngoài JSON):
{
  "search_intent": "",
  "new_outline": [{"heading": "", "purpose": ""}],
  "title_options": ["", "", ""],
  "recommended_title": "",
  "meta_description_options": ["", "", ""],
  "recommended_meta_description": "",
  "summary_html": "",
  "body_html": "",
  "tags_suggestion": [],
  "internal_links_preserved": [],
  "external_links_flagged": [],
  "external_images_flagged": [],
  "facts_to_manual_verify": [],
  "editor_notes": []
}"""

REPAIR_SUFFIX = ("\n\nLƯU Ý: Phản hồi trước KHÔNG phải JSON hợp lệ hoặc thiếu field. "
                 "Trả về DUY NHẤT object JSON đúng schema, body_html không rỗng, "
                 "title_options và meta_description_options mỗi cái >=3 phần tử.")


def fetch_live_article(blog_id, article_id, cfg):
    H = {"Authorization": f"Bearer {cfg['blog_access_token']}", "Accept": "application/json"}
    r = requests.get(f"{cfg['open_api_base']}/blogs/{blog_id}/articles/{article_id}.json",
                     headers=H, verify=False, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"fetch live article {article_id} HTTP {r.status_code}")
    return r.json().get("article", {})


_BRAND_WORDS = ("gearvn", "gear vn", "fptshop", "fpt shop", "cellphones", "memoryzone",
                "thegioididong", "tgdđ", "tgdd", "hacom", "hoàng hà", "phong vũ", "an phát")


def _clean_alt(alt, title):
    a = _html.unescape(alt or "")
    low = a.lower()
    if any(b in low for b in _BRAND_WORDS) or not a.strip():
        # alt lộ thương hiệu nguồn / rỗng → thay bằng mô tả từ title
        return title[:80]
    return a.strip()[:120]


def extract_images(body, title):
    """Trả [(src, cleaned_alt, is_external)] — TẤT CẢ ảnh (Sintech CDN + external).
    External giữ URL tạm + flag rehost (P5), KHÔNG drop."""
    out = []
    for tag in re.findall(r"<img[^>]+>", body or "", re.I):
        sm = re.search(r'src="([^"]+)"', tag, re.I)
        am = re.search(r'alt="([^"]*)"', tag, re.I)
        if not sm:
            continue
        src = sm.group(1)
        h = (urlparse(src).hostname or "").lower()
        is_ext = bool(h) and not any(o in h for o in _OWN_IMG)
        out.append((src, _clean_alt(am.group(1) if am else "", title), is_ext))
    return out


def build_user_prompt(title, original_body, images=None):
    text = re.sub(r"<[^>]+>", " ", original_body or "")
    text = re.sub(r"\s+", " ", _html.unescape(text)).strip()[:6000]
    img_block = ""
    if images:
        lst = "\n".join(f'- <img src="{s}" alt="{a}">' + ("  [external — sẽ rehost sau]" if ext else "")
                        for s, a, ext in images)
        img_block = (f"\n\nẢNH CẦN GIỮ ({len(images)} ảnh, dùng ĐÚNG src, chèn rải đều sau các H2, "
                     f"alt đã làm sạch — chỉnh alt hợp ngữ cảnh. GIỮ CẢ ảnh external, KHÔNG bỏ):\n{lst}\n")
    return (f"TIÊU ĐỀ BÀI CŨ: {title}\n\n"
            f"NỘI DUNG GỐC (chỉ tham khảo CHỦ ĐỀ + FACTS, KHÔNG copy câu chữ):\n{text}{img_block}\n"
            f"Viết bài MỚI nguyên bản theo yêu cầu. Giữ ĐỦ {len(images or [])} ảnh trên. CHỈ trả JSON đúng schema.")


_JSON_RE = re.compile(r"\{.*\}", re.S)
_REQUIRED = ("body_html", "recommended_title", "title_options", "meta_description_options")


def parse_draft(text):
    """Trích + validate JSON. Raise ValueError nếu không hợp lệ."""
    m = _JSON_RE.search(text or "")
    if not m:
        raise ValueError("không tìm thấy JSON")
    obj = json.loads(m.group(0))
    for k in _REQUIRED:
        if k not in obj:
            raise ValueError(f"thiếu field {k}")
    if not (obj.get("body_html") or "").strip():
        raise ValueError("body_html rỗng")
    if len(obj.get("title_options") or []) < 3:
        raise ValueError("title_options < 3")
    if len(obj.get("meta_description_options") or []) < 3:
        raise ValueError("meta_description_options < 3")
    return obj


# ─────────── HTML sanitize (bs4 whitelist) ───────────
_ALLOWED = {"p", "br", "h2", "h3", "ul", "ol", "li", "strong", "em", "a",
            "table", "thead", "tbody", "tr", "th", "td", "blockquote", "img"}
_ALLOWED_ATTR = {"a": {"href", "title"}, "img": {"src", "alt"}}
_OWN_IMG = ("sintech.vn", "myharavan")
SINTECH_STORE_ID = "200000860097"
# style kẻ bảng (theme Haravan KHÔNG tự kẻ table trong body → phải inline style)
_STYLE_TABLE = "border-collapse:collapse;width:100%;margin:16px 0"
_STYLE_TH = "border:1px solid #ccc;padding:8px 10px;background:#f4f4f4;text-align:left"
_STYLE_TD = "border:1px solid #ccc;padding:8px 10px"


def _img_is_sintech(src):
    # dùng helper centralize store-aware (P5D) — KHÔNG duplicate logic
    import blog_rewrite_images as _im
    return _im.is_sintech_image(src)


def sanitize_html(raw):
    soup = BeautifulSoup(raw or "", "lxml")
    for bad in soup(["script", "style", "iframe"]):
        bad.decompose()
    external_links, external_images = [], []
    for tag in list(soup.find_all(True)):
        name = tag.name.lower()
        if name not in _ALLOWED:
            tag.unwrap()
            continue
        allowed = _ALLOWED_ATTR.get(name, set())
        for attr in list(tag.attrs):
            v = tag.attrs[attr]
            if attr not in allowed:
                del tag.attrs[attr]
                continue
            if attr == "href":
                vs = str(v).strip().lower()
                if vs.startswith("javascript:") or vs.startswith("data:"):
                    del tag.attrs[attr]
                elif vs.startswith("http") and "sintech.vn" not in vs:
                    external_links.append(str(v))
            if attr == "src":
                if not _img_is_sintech(str(v)):  # store-id aware (hstatic dùng chung mọi shop)
                    external_images.append(str(v))
    # kẻ đường bảng (table/th/td) — theme Haravan không tự style table trong body
    for t in soup.find_all("table"):
        t["style"] = _STYLE_TABLE
        # wrapper responsive mobile (overflow-x) — div thêm SAU whitelist nên không bị strip
        wrap = soup.new_tag("div", style="overflow-x:auto;-webkit-overflow-scrolling:touch")
        t.wrap(wrap)
    for th in soup.find_all("th"):
        th["style"] = _STYLE_TH
    for td in soup.find_all("td"):
        td["style"] = _STYLE_TD
    body = soup.body
    cleaned = "".join(str(c) for c in body.contents) if body else str(soup)
    return cleaned.strip(), external_links, external_images


# ─────────── quality metrics ───────────
def _words(htmltext):
    t = re.sub(r"<[^>]+>", " ", htmltext or "")
    t = re.sub(r"[^\wÀ-ỹ ]", " ", _html.unescape(t).lower())
    return [w for w in t.split() if w]


def _ngrams(words, n=5):
    return set(tuple(words[i:i + n]) for i in range(len(words) - n + 1))


def _longest_common_phrase(a, b):
    sa = set(_ngrams(a, 5))
    best = 0
    if not sa:
        return 0
    i = 0
    while i < len(b) - 4:
        if tuple(b[i:i + 5]) in sa:
            j = i + 5
            while j < len(b) and tuple(b[max(0, j - 4):j + 1]) and tuple(b[j - 4:j + 1]) in sa:
                j += 1
            best = max(best, j - i)
            i = j
        else:
            i += 1
    return best


def quality_metrics(original_body, draft_body):
    ow, dw = _words(original_body), _words(draft_body)
    og, dg = _ngrams(ow), _ngrams(dw)
    overlap = round(len(og & dg) / len(dg), 4) if dg else 0.0
    lcp = _longest_common_phrase(ow, dw)
    headings = (draft_body or "").count("<h2") + (draft_body or "").count("<h3")
    return {
        "word_count_original": len(ow), "word_count_draft": len(dw),
        "heading_count_draft": headings,
        "normalized_5gram_overlap": overlap, "longest_common_phrase": lcp,
        "html_validation": "ok",
    }


def quality_scorecard(qm, ext_links, ext_imgs):
    overlap = qm["normalized_5gram_overlap"]
    return {
        "originality": "low" if overlap > 0.15 else ("medium" if overlap > 0.05 else "high"),
        "structure": "ok" if qm["heading_count_draft"] >= 2 else "thin",
        "coverage": "ok" if qm["word_count_draft"] >= 250 else "thin",
        "html": qm["html_validation"],
        "links": f"{len(ext_links)} external flagged",
        "manual_verification": "required" if overlap > 0.15 else "optional",
    }


def _reinsert_images(body, images):
    """Chèn lại ảnh Sintech (cleaned alt) rải đều sau các H2 nếu AI làm rơi ảnh."""
    if not images:
        return body
    tags = [f'<img src="{s}" alt="{a}">' for s, a in images]
    parts = re.split(r"(</h2>)", body, flags=re.I)
    if len(parts) <= 1:  # không có H2 → chèn cuối
        return body + "".join(f"<p>{t}</p>" for t in tags)
    # phân bổ ảnh sau các </h2>
    out, idx = [], 0
    for seg in parts:
        out.append(seg)
        if seg.lower() == "</h2>" and idx < len(tags):
            out.append(f"<p>{tags[idx]}</p>")
            idx += 1
    while idx < len(tags):  # ảnh dư → cuối bài
        out.append(f"<p>{tags[idx]}</p>"); idx += 1
    return "".join(out)


def generate_real_draft(candidate, cfg, provider="claude"):
    """Fetch live → prompt (kèm ảnh Sintech) → AI THẬT → parse(+repair 1) → sanitize →
    đảm bảo giữ ảnh → quality + image audit. Raise nếu fail."""
    art = fetch_live_article(candidate["blog_id"], candidate["article_id"], cfg)
    original_body = art.get("body_html") or ""
    keep_images = extract_images(original_body, candidate.get("title", ""))
    user = build_user_prompt(candidate.get("title", ""), original_body, images=keep_images)
    out = ai_provider.call_ai_single(provider, BLOG_REWRITE_PROMPT_V1, user,
                                     timeout=GEN_TIMEOUT, reasoning_effort="low")
    try:
        obj = parse_draft(out)
    except ValueError:
        out2 = ai_provider.call_ai_single(provider, BLOG_REWRITE_PROMPT_V1,
                                          user + REPAIR_SUFFIX, timeout=GEN_TIMEOUT)
        obj = parse_draft(out2)  # repair 1 lần; lỗi nữa → raise lên worker
    clean_body, ext_links, ext_imgs = sanitize_html(obj["body_html"])
    # đảm bảo giữ ĐỦ ảnh (Sintech + external): nếu AI rơi ảnh → re-insert deterministic
    draft_img_srcs = set(re.findall(r'<img[^>]+src="([^"]+)"', clean_body, re.I))
    missing = [(s, a) for s, a, ext in keep_images if s not in draft_img_srcs]
    reinserted = 0
    if missing:
        clean_body = _reinsert_images(clean_body, missing)
        reinserted = len(missing)
    n_external = sum(1 for _, _, ext in keep_images if ext)
    # làm sạch alt lộ brand còn sót trong draft (nếu AI giữ alt cũ)
    def _fix_alt(m):
        return f'alt="{_clean_alt(m.group(1), candidate.get("title",""))}"'
    clean_body = re.sub(r'alt="([^"]*)"', _fix_alt, clean_body)
    obj["body_html"] = clean_body
    final_imgs = re.findall(r'<img[^>]+>', clean_body, re.I)
    # brand trong NỘI DUNG HIỂN THỊ (text + alt) → fail thật; trong SRC filename → chỉ flag rehost (P4)
    visible = re.sub(r"<[^>]+>", " ", clean_body).lower()
    alts = " ".join(re.findall(r'alt="([^"]*)"', clean_body, re.I)).lower()
    srcs = " ".join(re.findall(r'src="([^"]*)"', clean_body, re.I)).lower()
    brand_visible = [b for b in _BRAND_WORDS if b in visible or b in alts]
    brand_in_src = sorted(set(b for b in _BRAND_WORDS if b in srcs))
    qm = quality_metrics(original_body, clean_body)
    qm["image_audit"] = {
        "image_count_original": len(keep_images), "image_count_draft": len(final_imgs),
        "external_images": n_external, "reinserted": reinserted,
        "status": "IMAGES_PRESERVED" if len(final_imgs) >= len(keep_images) else "IMAGES_DROPPED",
        "source_brand_in_visible": brand_visible,
        "source_brand_in_src_filename": brand_in_src,  # → image plan rehost ở P4/P5
    }
    obj["_external_links_flagged"] = ext_links
    obj["_external_images_flagged"] = ext_imgs
    obj["_quality"] = qm
    obj["_scorecard"] = quality_scorecard(qm, ext_links, ext_imgs)
    obj["_scorecard"]["images"] = qm["image_audit"]["status"]
    obj["_scorecard"]["brand_cleanup"] = "PASS" if not brand_visible else "FAIL"
    obj["_original_body"] = original_body
    bad = (qm["normalized_5gram_overlap"] > 0.15 or qm["image_audit"]["status"] == "IMAGES_DROPPED"
           or bool(brand_visible))
    obj["_approval_status"] = "review_required" if bad else "draft_ready"
    return obj


def provider_health(provider="claude"):
    try:
        import claude_provider, codex_provider
        if provider == "claude":
            return {"provider": "claude", "available": claude_provider.is_claude_available(),
                    "model": "claude-cli", "prompt_version": PROMPT_VERSION}
    except Exception as e:
        return {"provider": provider, "available": False, "error": str(e)[:80]}
    return {"provider": provider, "available": False}
