"""scoring_core.py — Shared SEO scoring engine for Sintech marketing_hub.

Unifies the 2 previous scoring systems:
  - `seo.py:analyze_html()`  — crawl scorer (published page, full HTML + canonical/og/schema/load_ms)
  - `seo_quality.py:rate_content()` — content gen scorer (unpublished draft, title/meta/body)

Each `score_*` function is PURE and returns a uniform shape:
    {
        "score": int,          # achieved score (already scaled to `max_score`)
        "max":   int,          # the cap caller requested
        "issues": [dict],      # list of {level, code, msg, severity}
        "meta":  dict,         # raw metrics (lens, counts, flags) for caller drill-down
    }

`severity` ∈ {"high","med","low"} — caller can re-bucket into its own format.
`code/level/msg` mirror the legacy crawl rule structure for `seo.py` compat.

The caller chooses the `max_score` weight per category, so the same rules
power both engines with different total budgets:
    - Crawl  (cap 100): title 10 + meta 10 + structure 25 + links 10 + readability 10 + sintech 15 + technical 20 = 100
    - GenSEO (cap 100): title 20 + meta 20 + structure 25 + links 15 + readability 20 = 100

Thresholds (title length, meta length, word count) are READ from
`data/seo_rules_config.json` if available, fallback to hardcoded constants.

Public API:
    - score_title(title, max_score=10)
    - score_meta(meta, max_score=10, require_cta=True)
    - score_structure(body_html, url_type="product", max_score=25, require_sections=True)
    - score_links(body_html, base_url=None, max_score=10)
    - score_readability(text, max_score=10)
    - score_sintech_sections(body_html, max_score=15)
    - score_technical_seo(soup, canonical_url, has_og, has_schema, load_ms, redirect_chain, max_score=20)
    - html_to_text(html)        — strip script/style → plain text
    - readability_metrics(text) — raw Flesch-like metrics for VN

The legacy `readability_score()` lives here too (was in seo_quality.py).
"""
from __future__ import annotations

import json
import os
import re
import threading
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


# ─────────────────────────── Rules config loader ───────────────────────────
# Mirror of seo.py loader so scoring_core stays standalone (no circular import).
_RULES_PATH = os.path.join(os.path.dirname(__file__), "data", "seo_rules_config.json")
_rules_cache = {"data": None, "mtime": 0}
_rules_lock = threading.Lock()


def _load_rules() -> dict:
    """Load + auto-reload seo_rules_config.json (best-effort)."""
    try:
        mtime = os.path.getmtime(_RULES_PATH)
    except OSError:
        return {"rules": [], "word_count_thresholds": {}}
    with _rules_lock:
        if _rules_cache["data"] is None or mtime != _rules_cache["mtime"]:
            try:
                with open(_RULES_PATH, "r", encoding="utf-8") as f:
                    _rules_cache["data"] = json.load(f)
                _rules_cache["mtime"] = mtime
            except Exception:
                if _rules_cache["data"] is None:
                    _rules_cache["data"] = {"rules": [], "word_count_thresholds": {}}
        return _rules_cache["data"]


def _rule(code: str) -> dict:
    """Find rule by code in config; return default-enabled stub if missing."""
    cfg = _load_rules()
    for r in cfg.get("rules", []):
        if r.get("code") == code:
            return r
    return {"code": code, "enabled": True, "level": "warn", "score": 0, "msg": code}


def _thr(code: str, default):
    """Threshold lookup."""
    r = _rule(code)
    return r.get("threshold", default)


def _enabled(code: str) -> bool:
    """Rule enabled?"""
    return bool(_rule(code).get("enabled", True))


def _word_thresholds(url_type: str) -> tuple:
    cfg = _load_rules()
    wt = cfg.get("word_count_thresholds") or {}
    defaults = {
        "blog":       {"low": 700, "ok": 1500},
        "product":    {"low": 500, "ok": 800},
        "collection": {"low": 150, "ok": 300},
        "page":       {"low": 500, "ok": 800},
        "other":      {"low": 500, "ok": 800},
    }
    d = wt.get(url_type) or defaults.get(url_type) or defaults["product"]
    return int(d.get("low", 500)), int(d.get("ok", 800))


# ─────────────────────────── HTML → text ───────────────────────────

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip > 0:
            self.skip -= 1

    def handle_data(self, data):
        if self.skip == 0:
            self.parts.append(data)

    def get_text(self):
        return " ".join(self.parts)


def html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        s = _HTMLStripper()
        s.feed(html)
        text = s.get_text()
    except Exception:
        # Fallback: brute-force regex strip
        text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def strip_tables(html: str) -> str:
    """Remove <table>...</table> blocks.

    Bảng là dữ liệu dạng cột (KHÔNG có dấu câu giữa các ô) → khi flatten thành
    text sẽ thành 1 'câu' giả dài 100+ token, làm tụt readability oan. Strip
    bảng TRƯỚC khi chấm readability (bảng vẫn được tính ở structure score).
    """
    if not html:
        return html
    return re.sub(r"<table[\s\S]*?</table>", " ", html, flags=re.IGNORECASE)


# ─────────────────────────── Readability VN ───────────────────────────

# Chỉ đếm "bị + động từ" (passive tiêu cực: bị hỏng/bị chậm/bị nhiễu). Bỏ "được"
# vì tiếng Việt "được" thường trung tính/tích cực ("được tư vấn", "được trang bị")
# → không phải passive xấu, đếm "được" làm tụt điểm oan.
_PASSIVE_MARKERS = re.compile(r"\bbị\s+\w+", re.IGNORECASE)
_FILLER_PHRASES = [
    "trong bài này", "sản phẩm này mang lại", "người dùng sẽ", "category này",
    "search intent", "khôn nhất", "carte này", "chia sẻ với bạn", "đem đến",
    "bền bỉ", "đẹp mắt", "tốt nhất 2026", "đáng mua nhất", "rẻ nhất",
]


def readability_metrics(text: str) -> dict:
    """Flesch-like readability for Vietnamese.

    Returns dict: score (0-100), n_words, n_sentences, avg_sentence_len,
    avg_word_len, complex_pct, passive_pct, filler_count, level, issues.
    """
    if not text or len(text) < 50:
        return {"score": 0, "n_words": 0, "n_sentences": 0, "issues": ["Text quá ngắn"]}

    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    n_sentences = max(len(sentences), 1)
    words = re.findall(r"\w+", text, re.UNICODE)
    n_words = max(len(words), 1)

    avg_sentence_len = n_words / n_sentences
    avg_word_len = sum(len(w) for w in words) / n_words

    # NGƯỠNG câu phức 35 (không phải 25): tiếng Việt đếm theo ÂM TIẾT (\w+), 1 từ
    # thực tế ~1.5-1.8 âm tiết → 1 câu Việt ~20 từ thật = ~30-35 token. Ngưỡng 25
    # cũ phạt oan câu bình thường.
    complex_count = sum(1 for s in sentences if len(re.findall(r"\w+", s)) > 35)
    complex_pct = complex_count * 100 / n_sentences

    passive_count = len(_PASSIVE_MARKERS.findall(text))
    passive_pct = passive_count * 100 / n_sentences

    tl = text.lower()
    filler_count = sum(tl.count(p) for p in _FILLER_PHRASES)

    # HỆ SỐ avg_sentence_len 0.9 (không phải 1.5): hiệu chỉnh cho tiếng Việt —
    # đếm âm tiết làm avg phồng ~1.6x so với English. 1.5 cũ phạt quá nặng.
    base = 100 - (avg_sentence_len * 0.9) - (max(0, avg_word_len - 5) * 3) - (complex_pct * 0.3)
    base -= min(passive_pct * 0.5, 15)
    base -= min(filler_count * 3, 20)
    score = max(0, min(100, round(base, 1)))

    if score >= 75:
        level = "🟢 Rất dễ đọc"
    elif score >= 60:
        level = "🟢 Dễ đọc"
    elif score >= 45:
        level = "🟡 Tạm ổn"
    elif score >= 30:
        level = "🟠 Khó đọc"
    else:
        level = "🔴 Rất khó"

    return {
        "score": score,
        "level": level,
        "n_words": n_words,
        "n_sentences": n_sentences,
        "avg_sentence_len": round(avg_sentence_len, 1),
        "avg_word_len": round(avg_word_len, 2),
        "complex_pct": round(complex_pct, 1),
        "passive_pct": round(passive_pct, 1),
        "filler_count": filler_count,
    }


# Back-compat alias (old API name).
def readability_score(text: str) -> dict:
    return readability_metrics(text)


# ─────────────────────────── Helpers ───────────────────────────

def _scale(raw: float, raw_max: float, max_score: int) -> int:
    """Scale raw points (0..raw_max) → integer (0..max_score)."""
    if raw_max <= 0:
        return 0
    pts = round((raw / raw_max) * max_score)
    return max(0, min(max_score, int(pts)))


def _issue(level: str, code: str, msg: str, severity: str) -> dict:
    return {"level": level, "code": code, "msg": msg, "severity": severity}


def _empty(max_score: int, meta: dict | None = None) -> dict:
    return {"score": 0, "max": max_score, "issues": [], "meta": meta or {}}


# ─────────────────────────── 1. TITLE ───────────────────────────

def score_title(title: str | None, max_score: int = 10) -> dict:
    """Score SEO title length + brand-suffix sanity.

    Sub-budget (raw 20, then scaled to max_score):
      - length (sweet 45-61 → 13, mild miss 14-44/62-... → 7-8, missing → 0): 13/20
      - "no sintech in raw title" bonus: 7/20
    """
    title = (title or "").strip()
    tl = len(title)
    issues = []
    meta = {"len": tl}

    # Length scoring (raw points out of 13).
    if tl == 0:
        len_raw = 0
        issues.append(_issue("error", "no_title", "Thiếu thẻ <title>", "high"))
    elif 45 <= tl <= 61:
        len_raw = 13
    elif tl > 61:
        thr = _thr("title_long", 61)
        len_raw = 7
        issues.append(_issue("warn", "title_long",
                             f"Title quá dài ({tl} ký tự, max {thr}) — Google sẽ cắt", "med"))
    elif tl < 20:
        thr = _thr("title_short", 20)
        len_raw = 5
        issues.append(_issue("warn", "title_short",
                             f"Title quá ngắn ({tl} ký tự, nên ≥{thr})", "med"))
    else:
        # 20..44 → partial (close but under sweet spot)
        len_raw = 8
        issues.append(_issue("warn", "title_short",
                             f"Title {tl}c — chưa tận dụng SERP (sweet spot 45-61)", "med"))

    # Brand-suffix bonus (raw 7): "sintech" must NOT appear in raw title
    # (Haravan auto-appends " - Sintech..." which we strip before check).
    brand_raw = 0
    if title:
        cleaned = re.sub(r"\s*[-–—|]\s*sintech.*$", "", title.lower()).strip()
        if "sintech" in cleaned:
            issues.append(_issue("warn", "sintech_in_title",
                                 "Title gốc chứa 'Sintech' (không tính suffix Haravan) — rule cấm",
                                 "med"))
        else:
            brand_raw = 7

    raw = len_raw + brand_raw
    return {
        "score": _scale(raw, 20, max_score),
        "max": max_score,
        "issues": issues,
        "meta": meta,
    }


# ─────────────────────────── 2. META DESCRIPTION ───────────────────────────

def score_meta(meta_desc: str | None, max_score: int = 10, require_cta: bool = True) -> dict:
    """Score meta description length + presence of UPPERCASE CTA.

    Sub-budget (raw 20, then scaled to max_score):
      - length (sweet 140-160 → 13, mild miss → 6-7, missing → 0): 13/20
      - CTA keyword (XEM/CHỌN/THAM KHẢO/KHÁM PHÁ/MUA NGAY): 7/20
        if require_cta=False (e.g. crawl on non-product), CTA bonus folded into length budget.
    """
    meta_desc = (meta_desc or "").strip()
    ml = len(meta_desc)
    issues = []
    has_cta = False

    if require_cta:
        len_raw_max = 13.0
        cta_raw_max = 7.0
    else:
        len_raw_max = 20.0
        cta_raw_max = 0.0

    if ml == 0:
        len_raw = 0
        issues.append(_issue("error", "no_meta", "Thiếu meta description", "high"))
    elif 140 <= ml <= 160:
        len_raw = len_raw_max
    elif ml > 160:
        thr = _thr("meta_long", 160)
        len_raw = len_raw_max * (7.0 / 13.0)
        issues.append(_issue("warn", "meta_long",
                             f"Meta quá dài ({ml} ký tự, max {thr}) — bị cắt", "med"))
    elif ml < 140:
        thr = _thr("meta_short", 140)
        len_raw = len_raw_max * (6.0 / 13.0)
        issues.append(_issue("warn", "meta_short",
                             f"Meta quá ngắn ({ml} ký tự, nên ≥{thr})", "med"))
    else:
        len_raw = len_raw_max * 0.7

    cta_raw = 0.0
    if require_cta and meta_desc:
        cta_keywords = ["XEM NGAY", "CHỌN NGAY", "THAM KHẢO NGAY", "KHÁM PHÁ NGAY", "MUA NGAY"]
        has_cta = any(kw in meta_desc for kw in cta_keywords)
        if has_cta:
            cta_raw = cta_raw_max
        else:
            issues.append(_issue("warn", "meta_no_cta",
                                 "Meta description thiếu CTA viết HOA "
                                 "(XEM NGAY / CHỌN NGAY / THAM KHẢO NGAY / KHÁM PHÁ NGAY)",
                                 "low"))

    raw = len_raw + cta_raw
    return {
        "score": _scale(raw, len_raw_max + cta_raw_max, max_score),
        "max": max_score,
        "issues": issues,
        "meta": {"len": ml, "has_cta": has_cta},
    }


# ─────────────────────────── 3. STRUCTURE (H1/H2/H3 + word count + FAQ + signature) ───────────────────────────

def score_structure(body_html: str | None, url_type: str = "product",
                    max_score: int = 25, require_sections: bool = True) -> dict:
    """Score body structure: word count, H1/H2/H3 hierarchy, FAQ, signature.

    Args:
        body_html: full body HTML
        url_type: 'product' | 'collection' | 'blog' | 'page' | 'other'
        max_score: weight cap
        require_sections: if True (gen-content mode), require FAQ + signature.
            If False (crawl mode), still detect them but don't deduct (caller scores via sintech_sections).
    """
    body_html = body_html or ""
    issues = []
    text = html_to_text(body_html)
    n_words = len(re.findall(r"\w+", text, flags=re.UNICODE))

    # Sub-budget (raw 25, matches legacy seo_quality.py):
    #  content thin: 5 (≥100 words)
    #  H1=0 in body: 5
    #  H2: ≥3 → 6, ≥1 → 3, else 0
    #  H3: ≥2 → 4, ≥1 → 2, else 0
    #  FAQ presence: 3 (require_sections only; else 0 budget → folded into content+H1)
    #  Signature:    2 (require_sections only; else 0 budget → folded)
    if require_sections:
        b_content, b_h1, b_h2, b_h3, b_faq, b_sig = 5, 5, 6, 4, 3, 2
    else:
        b_content, b_h1, b_h2, b_h3, b_faq, b_sig = 8, 7, 6, 4, 0, 0

    # Content / word count
    low_thr, ok_thr = _word_thresholds(url_type)
    if n_words < 100:
        c_raw = 0
        issues.append(_issue("error", "thin_content",
                             f"THIN CONTENT — chỉ {n_words} từ (cần ≥100)", "high"))
    elif n_words < low_thr:
        c_raw = b_content * 0.5
        issues.append(_issue("warn", "low_content",
                             f"Nội dung mỏng ({n_words} từ, chuẩn {url_type} ≥{ok_thr})", "med"))
    elif n_words < ok_thr:
        c_raw = b_content * 0.8
        issues.append(_issue("info", "thin_content",
                             f"Nội dung khá ngắn ({n_words} từ, chuẩn {url_type} ≥{ok_thr})", "low"))
    else:
        c_raw = b_content

    # H1 in body — must be 0 (page-level H1 lives in <title>/H1 outside body)
    n_h1 = len(re.findall(r"<h1\b", body_html, re.I))
    if n_h1 == 0:
        h1_raw = b_h1
    else:
        h1_raw = 0
        issues.append(_issue("warn", "h1_in_body",
                             f"Có {n_h1} <h1> trong body (page đã có H1 ở title)", "med"))

    # H2 count
    n_h2 = len(re.findall(r"<h2\b", body_html, re.I))
    if n_h2 >= 3:
        h2_raw = b_h2
    elif n_h2 >= 1:
        h2_raw = b_h2 * 0.5
    else:
        h2_raw = 0
        if b_h2 > 0:
            issues.append(_issue("warn", "no_h2",
                                 "Không có <h2> — cần ≥3 cho cấu trúc", "high"))

    # H3 count
    n_h3 = len(re.findall(r"<h3\b", body_html, re.I))
    if n_h3 >= 2:
        h3_raw = b_h3
    elif n_h3 >= 1:
        h3_raw = b_h3 * 0.5
    else:
        h3_raw = 0
        if b_h3 > 0:
            issues.append(_issue("info", "no_h3",
                                 "Thiếu <h3> — chưa có FAQ hoặc subsection", "low"))

    # FAQ
    has_faq = bool(re.search(r"câu\s*hỏi\s*thường\s*gặp|FAQ|hỏi\s*đáp", body_html, re.I))
    if has_faq:
        faq_raw = b_faq
    else:
        faq_raw = 0
        if b_faq > 0:
            issues.append(_issue("info", "missing_faq", "Thiếu section FAQ", "low"))

    # Signature Sintech (legacy gen scorer matched only the exact long string)
    body_lower = body_html.lower()
    has_signature = "tư vấn cấu hình bởi team kỹ thuật sintech" in body_lower
    if has_signature:
        sig_raw = b_sig
    else:
        sig_raw = 0
        if b_sig > 0:
            issues.append(_issue("info", "missing_signature",
                                 "Thiếu signature Sintech cuối bài", "low"))

    raw_total = c_raw + h1_raw + h2_raw + h3_raw + faq_raw + sig_raw
    raw_max = b_content + b_h1 + b_h2 + b_h3 + b_faq + b_sig

    return {
        "score": _scale(raw_total, raw_max, max_score),
        "max": max_score,
        "issues": issues,
        "meta": {
            "n_h1": n_h1, "n_h2": n_h2, "n_h3": n_h3, "n_words": n_words,
            "has_faq": has_faq, "has_signature": has_signature,
        },
    }


# ─────────────────────────── 4. LINKS ───────────────────────────

def score_links(body_html: str | None, base_url: str | None = None,
                max_score: int = 10) -> dict:
    """Count internal vs external links + check CTA href to sintech.vn root.

    Args:
        body_html: full HTML (body or full page)
        base_url: if provided, internal = same netloc as base_url.
            Else, internal = href contains 'sintech.vn'.
    """
    body_html = body_html or ""
    issues = []

    # Internal/external counting
    if base_url:
        try:
            host = urlparse(base_url).netloc.lower()
        except Exception:
            host = "sintech.vn"
    else:
        host = "sintech.vn"

    n_internal = 0
    n_external = 0
    for m in re.finditer(r'''href\s*=\s*["']([^"']+)["']''', body_html, re.I):
        href = m.group(1).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        try:
            if base_url:
                absolute = urljoin(base_url, href)
                th = urlparse(absolute).netloc.lower()
            else:
                th = urlparse(href).netloc.lower()
        except Exception:
            continue
        if not th:
            # Relative — treat as internal
            n_internal += 1
            continue
        if th == host or th.endswith("." + host) or host in th:
            n_internal += 1
        else:
            n_external += 1

    # Sub-budget (raw 15, matches legacy seo_quality.py):
    #   internal links: 10 (≥5→10, ≥3→7, ≥1→4, else 0)
    #   CTA href root:  5
    if n_internal >= 5:
        int_raw = 10
    elif n_internal >= 3:
        int_raw = 7
    elif n_internal >= 1:
        int_raw = 4
        issues.append(_issue("info", "few_internal",
                             f"Chỉ có {n_internal} internal link, nên ≥3", "low"))
    else:
        int_raw = 0
        issues.append(_issue("warn", "no_internal",
                             "Không có internal link Sintech", "high"))

    cta_present = bool(re.search(
        r'''href=["']https?://(?:www\.)?sintech\.vn/?["']''',
        body_html, re.I))
    cta_raw = 5 if cta_present else 0
    if not cta_present:
        issues.append(_issue("info", "no_cta_link",
                             "Thiếu CTA <a href='https://sintech.vn'> trong intro/outro", "med"))

    raw = int_raw + cta_raw
    return {
        "score": _scale(raw, 15, max_score),
        "max": max_score,
        "issues": issues,
        "meta": {"n_internal": n_internal, "n_external": n_external, "has_cta_link": cta_present},
    }


# ─────────────────────────── 5. READABILITY ───────────────────────────

def score_readability(text: str | None, max_score: int = 10) -> dict:
    """Score readability based on Flesch-like VN metrics."""
    text = text or ""
    rm = readability_metrics(text)
    rs = rm.get("score", 0)

    # Raw scale 0-20 → match legacy seo_quality.py bands exactly:
    # ≥70 → 20, ≥55 → 16, ≥40 → 11, ≥25 → 6, else 2
    if rs >= 70:
        raw = 20
    elif rs >= 55:
        raw = 16
    elif rs >= 40:
        raw = 11
    elif rs >= 25:
        raw = 6
    else:
        raw = 2

    issues = []
    if rs < 50:
        issues.append(_issue("warn", "readability",
                             f"Readability {rs} ({rm.get('level','')}) — bài khó đọc", "med"))
    if rm.get("filler_count", 0) > 0:
        issues.append(_issue("warn", "filler_phrases",
                             f"Có {rm['filler_count']} filler phrases bị cấm", "med"))
    if rm.get("passive_pct", 0) > 30:
        issues.append(_issue("info", "passive_voice",
                             f"Passive voice {rm['passive_pct']}% — văn thụ động quá nhiều", "low"))
    if rm.get("complex_pct", 0) > 30:
        issues.append(_issue("info", "long_sentences",
                             f"{rm['complex_pct']}% câu > 25 từ — viết câu ngắn hơn", "low"))

    return {
        "score": _scale(raw, 20, max_score),
        "max": max_score,
        "issues": issues,
        "meta": {
            "raw_score": rs,
            "level": rm.get("level"),
            "avg_sentence_len": rm.get("avg_sentence_len"),
            "avg_word_len": rm.get("avg_word_len"),
            "complex_pct": rm.get("complex_pct"),
            "passive_pct": rm.get("passive_pct"),
            "filler_count": rm.get("filler_count"),
            "n_words": rm.get("n_words"),
            "n_sentences": rm.get("n_sentences"),
        },
    }


# ─────────────────────────── 6. SINTECH-SPECIFIC SECTIONS (product pages) ───────────────────────────

def score_sintech_sections(body_html: str | None, url_type: str = "product",
                           max_score: int = 15) -> dict:
    """Score Sintech-mandated sections (product pages only).

    Sections checked (5 items, 3 raw points each):
      - "Vì sao mua tại Sintech" + policy line
      - FAQ
      - Signature ("Tư vấn cấu hình bởi team kỹ thuật Sintech")
      - "Trải nghiệm thực tế"
      - "Phù hợp với" / "Phù hợp cho"
    Non-product pages get 0 weight (returns empty) — caller should not include this category.
    """
    body_html = body_html or ""
    body_lower = body_html.lower()
    text_lower = html_to_text(body_html).lower()
    issues = []

    if url_type != "product":
        # Non-product: skip (caller can omit this category from total).
        return _empty(max_score, {"applies": False})

    # Each of 5 checks worth 3 raw points = 15 raw total.
    raw = 0.0

    # 1. "Vì sao mua tại Sintech" section
    has_why = ("vì sao" in body_lower or "vi sao" in text_lower) and "sintech" in body_lower
    if has_why:
        raw += 3
        if "trả góp 0%" not in body_lower and "thẻ tín dụng" not in body_lower:
            issues.append(_issue("info", "missing_sintech_policy",
                                 "Thiếu câu chính sách Sintech (trả góp 0%, kiểm hàng...)", "low"))
    else:
        issues.append(_issue("warn", "missing_sintech_section",
                             "Thiếu section 'Vì sao nên mua tại Sintech'", "med"))

    # 2. FAQ
    faq_signals = ["câu hỏi thường gặp", "faq", "hỏi đáp", "thường gặp"]
    has_faq = any(sig in body_lower for sig in faq_signals)
    if has_faq:
        raw += 3
    else:
        issues.append(_issue("warn", "missing_faq",
                             "Trang sản phẩm thiếu section FAQ", "med"))

    # 3. Signature
    sig_signals = [
        "tư vấn cấu hình bởi team kỹ thuật sintech",
        "tư vấn bởi team kỹ thuật sintech",
        "team kỹ thuật sintech",
    ]
    has_sig = any(sig in body_lower for sig in sig_signals)
    if has_sig:
        raw += 3
    else:
        issues.append(_issue("info", "missing_signature",
                             "Thiếu signature 'Tư vấn cấu hình bởi team kỹ thuật Sintech' cuối bài",
                             "low"))

    # 4. "Trải nghiệm thực tế"
    has_real_exp = "trải nghiệm thực tế" in body_lower or "trải nghiệm" in body_lower
    if has_real_exp:
        raw += 3
    else:
        issues.append(_issue("info", "missing_real_experience",
                             "Thiếu section 'Trải nghiệm thực tế'", "low"))

    # 5. "Phù hợp với ai"
    has_suitable = "phù hợp với" in body_lower or "phù hợp cho" in body_lower
    if has_suitable:
        raw += 3
    else:
        issues.append(_issue("info", "missing_suitable",
                             "Thiếu section 'Phù hợp với ai'", "low"))

    return {
        "score": _scale(raw, 15, max_score),
        "max": max_score,
        "issues": issues,
        "meta": {
            "applies": True,
            "has_why_sintech": has_why,
            "has_faq": has_faq,
            "has_signature": has_sig,
            "has_real_experience": has_real_exp,
            "has_suitable": has_suitable,
        },
    }


# ─────────────────────────── 7. TECHNICAL SEO (crawl only) ───────────────────────────

def score_technical_seo(canonical_url: str | None, has_og: bool, has_schema: bool,
                        load_ms: int, redirect_chain: list | None = None,
                        max_score: int = 20) -> dict:
    """Score technical SEO: canonical + og + schema + load_ms + redirect chain.

    Sub-budget (raw 20):
      - canonical: 4
      - og tags: 4
      - schema: 4
      - load_ms: 8 (≤1500ms full, ≤3000ms half, else 0)
    Penalty: redirect chain ≥2 → warn (no score deduct, just issue).
    """
    issues = []
    raw = 0.0

    # Canonical
    if canonical_url:
        raw += 4
    else:
        issues.append(_issue("warn", "no_canonical", "Thiếu thẻ canonical", "med"))

    # OG
    if has_og:
        raw += 4
    else:
        issues.append(_issue("warn", "no_og", "Thiếu Open Graph tags (og:title)", "med"))

    # Schema
    if has_schema:
        raw += 4
    else:
        issues.append(_issue("info", "no_schema", "Thiếu schema.org JSON-LD", "low"))

    # Load
    if load_ms and load_ms > 0:
        if load_ms <= 1500:
            raw += 8
        elif load_ms <= 3000:
            raw += 4
            issues.append(_issue("info", "slow",
                                 f"Tải hơi chậm ({load_ms}ms, mong <1500ms)", "low"))
        else:
            issues.append(_issue("warn", "very_slow", f"Tải chậm ({load_ms}ms)", "med"))
    else:
        # No load info — give half.
        raw += 4

    # Redirect chain
    redirect_chain = redirect_chain or []
    if len(redirect_chain) >= 3:
        issues.append(_issue("warn", "redirect_long_chain",
                             f"Redirect chain dài {len(redirect_chain)} hop", "med"))
    elif len(redirect_chain) >= 2:
        issues.append(_issue("warn", "redirect_chain",
                             f"Redirect chain {len(redirect_chain)} hop", "med"))

    return {
        "score": _scale(raw, 20, max_score),
        "max": max_score,
        "issues": issues,
        "meta": {
            "has_canonical": bool(canonical_url),
            "has_og": bool(has_og),
            "has_schema": bool(has_schema),
            "fast_load": (load_ms or 0) <= 1500 and (load_ms or 0) > 0,
            "load_ms": load_ms,
            "n_redirects": len(redirect_chain),
        },
    }


# ─────────────────────────── Issue bucketing helper ───────────────────────────

def bucket_issues(*issue_lists) -> tuple:
    """Flatten + bucket issues by severity into (high, med, low) string lists.

    Caller uses this for the seo_quality-style output (`issues_high/med/low: list[str]`).
    """
    high, med, low = [], [], []
    for il in issue_lists:
        for it in il or []:
            msg = it.get("msg", "")
            sev = it.get("severity", "low")
            if sev == "high":
                high.append("❌ " + msg if not msg.startswith(("❌", "🚨")) else msg)
            elif sev == "med":
                med.append("⚠️ " + msg if not msg.startswith(("⚠️", "❌")) else msg)
            else:
                low.append("ℹ️ " + msg if not msg.startswith(("ℹ️", "⚠️")) else msg)
    return high, med, low
