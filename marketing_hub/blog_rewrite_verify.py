# -*- coding: utf-8 -*-
"""Blog Rewrite — P5F canonical/semantic HTML verify (read-only).

Haravan normalize whitespace/entity/attr-order khi lưu → raw hash lệch nhưng nội
dung giống. So sánh SEMANTIC signature (text/img/href/heading/structure) để KHÔNG
gọi mismatch giả. KHÔNG PUT.
"""
import re, hashlib, html as _html
from bs4 import BeautifulSoup


def _h(s):
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def canonicalize_article_html(html):
    """Chuẩn hóa: bỏ whitespace thừa, unescape entity, lower tag — để so canonical."""
    soup = BeautifulSoup(html or "", "lxml")
    txt = soup.get_text(" ")
    return re.sub(r"\s+", " ", _html.unescape(txt)).strip()


def build_article_verify_signature(html):
    soup = BeautifulSoup(html or "", "lxml")
    plain = canonicalize_article_html(html)
    img_src = [i.get("src", "") for i in soup.find_all("img")]
    link_href = [a.get("href", "") for a in soup.find_all("a")]
    heads = [re.sub(r"\s+", " ", h.get_text(" ")).strip() for h in soup.find_all(["h2", "h3"])]
    struct = {t: len(soup.find_all(t)) for t in
              ("h2", "h3", "p", "img", "a", "ul", "ol", "li", "table", "tr", "td")}
    raw_norm = re.sub(r"\s+", " ", (html or "")).strip()
    return {
        "raw_hash": _h(raw_norm),
        "canonical_hash": _h(plain.lower()),
        "plain_text_hash": _h(plain),
        "structure": struct,
        "image_src_ordered": img_src, "image_src_hash": _h("|".join(img_src)),
        "link_href_ordered": link_href, "link_href_hash": _h("|".join(link_href)),
        "heading_text_ordered": heads, "heading_text_hash": _h("|".join(heads)),
        "html_safety": {
            "script": "<script" in (html or "").lower(),
            "iframe": "<iframe" in (html or "").lower(),
            "javascript": "javascript:" in (html or "").lower(),
            "onerror": "onerror=" in (html or "").lower(),
        },
    }


def compare_article_signatures(expected, live):
    """Trả taxonomy: VERIFIED_RAW / VERIFIED_CANONICAL / VERIFIED_SEMANTIC_WITH_NORMALIZATION /
    VERIFY_MISMATCH_REAL / VERIFY_READ_FAILED."""
    if not live:
        return {"status": "VERIFY_READ_FAILED", "reasons": ["no live signature"]}
    if expected["raw_hash"] == live["raw_hash"]:
        return {"status": "VERIFIED_RAW", "reasons": []}
    if expected["canonical_hash"] == live["canonical_hash"]:
        return {"status": "VERIFIED_CANONICAL", "reasons": ["raw khác do normalize, canonical giống"]}
    # semantic: text + img + href + heading + structure giống → chỉ normalize
    sem_ok = (expected["plain_text_hash"] == live["plain_text_hash"]
              and expected["image_src_hash"] == live["image_src_hash"]
              and expected["link_href_hash"] == live["link_href_hash"]
              and expected["heading_text_hash"] == live["heading_text_hash"]
              and expected["structure"] == live["structure"])
    if sem_ok:
        return {"status": "VERIFIED_SEMANTIC_WITH_NORMALIZATION",
                "reasons": ["Haravan normalize whitespace/entity — nội dung semantic giống hệt"]}
    reasons = []
    if expected["plain_text_hash"] != live["plain_text_hash"]:
        reasons.append("text khác")
    if expected["image_src_hash"] != live["image_src_hash"]:
        reasons.append("ảnh src khác")
    if expected["link_href_hash"] != live["link_href_hash"]:
        reasons.append("link href khác")
    if expected["heading_text_hash"] != live["heading_text_hash"]:
        reasons.append("heading khác")
    if expected["structure"] != live["structure"]:
        reasons.append(f"structure khác {expected['structure']} vs {live['structure']}")
    return {"status": "VERIFY_MISMATCH_REAL", "reasons": reasons}


# ═══════════════════ P7.2 — PUBLIC-PAGE FALLBACK COMPARATOR ═══════════════════
def _plain_lower(s):
    """Strip tag → unescape → collapse whitespace → lower. So body article, KHÔNG so layout."""
    t = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", _html.unescape(t)).strip().lower()


def _fragments(text, span=6, step=35, maxn=14):
    """Lấy các đoạn ~span từ rải đều để làm dấu vân tay nội dung."""
    words = text.split()
    out = []
    for i in range(0, min(len(words), step * maxn), step):
        seg = " ".join(words[i:i + span])
        if len(seg) > 20:
            out.append(seg)
    return out


def _coverage(fragments, hay):
    if not fragments:
        return 0.0
    return sum(1 for f in fragments if f in hay) / len(fragments)


def compare_public_page(public_html, draft_body, original_body):
    """Fallback khi Haravan read API 502: so dấu vân tay nội dung article (containment)
    của draft vs original trong text trang public. Trả verdict DRAFT/ORIGINAL/UNCERTAIN.

    public page chứa cả layout (nav/footer) nên dùng containment các đoạn ĐẶC TRƯNG
    (loại bỏ đoạn trùng giữa draft & original) thay vì so structure toàn trang."""
    page = _plain_lower(public_html)
    draft_t = _plain_lower(draft_body)
    orig_t = _plain_lower(original_body)
    df = _fragments(draft_t)
    of = _fragments(orig_t)
    # đoạn riêng của mỗi bản (không xuất hiện ở bản kia) → phân biệt được
    df_u = [f for f in df if f not in orig_t]
    of_u = [f for f in of if f not in draft_t]
    draft_cov = _coverage(df_u or df, page)
    orig_cov = _coverage(of_u or of, page)
    if draft_cov >= 0.6 and draft_cov >= orig_cov + 0.3:
        verdict = "DRAFT"
    elif orig_cov >= 0.6 and orig_cov >= draft_cov + 0.3:
        verdict = "ORIGINAL"
    else:
        verdict = "UNCERTAIN"
    return {"verdict": verdict, "draft_coverage": round(draft_cov, 3),
            "original_coverage": round(orig_cov, 3),
            "draft_unique_fragments": len(df_u), "original_unique_fragments": len(of_u)}
