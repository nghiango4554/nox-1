"""SEO Quality Rater + Readability Scorer cho content SP/collection/blog.

Refactor C (2026-05-16): refactored to delegate to `scoring_core.py`.
Public API (signatures + output keys) UNCHANGED for backward compat with
DB columns (`quality_score`, `quality_breakdown`) and UI templates
(`content_jobs`, `blog_jobs`, `collection_jobs`).

Public API:
  - readability_score(text) -> dict (re-export from scoring_core)
  - rate_content(title, meta, body_html, url_type) -> dict (uses scoring_core)
"""
from __future__ import annotations

import re

import scoring_core
from scoring_core import html_to_text, readability_metrics


# Re-export readability_score (legacy alias, used by seo.py).
readability_score = readability_metrics


# ─────────────────────────── SEO QUALITY RATER 0-100 ───────────────────────────

# Weight budget (must sum to 100 to keep tier mapping intact):
#  title 20 + meta 20 + structure 25 + links 15 + readability 20 = 100
_WEIGHTS = {
    "title": 20,
    "meta": 20,
    "structure": 25,
    "links": 15,
    "readability": 20,
}


def rate_content(title: str, meta: str, body_html: str, url_type: str = "product") -> dict:
    """Chấm điểm content theo 5 category. Total = 100.

    Args:
        title: SEO title (metafields_global_title_tag)
        meta: meta description
        body_html: body HTML đầy đủ
        url_type: 'product' | 'collection' | 'blog'

    Return dict (legacy schema — UI templates depend on these keys):
      score: 0-100
      max: 100
      tier: emoji label
      breakdown: dict {title, meta, structure, links, readability}
        each: {score, max, issues, ...extra meta keys (len, n_h1, ...)}
      issues_high: list[str]
      issues_med: list[str]
      issues_low: list[str]
      readability: dict from readability_score()
    """
    title = (title or "")
    meta = (meta or "")
    body_html = body_html or ""

    text = html_to_text(body_html)
    n_words = len(re.findall(r"\w+", text))

    # ─── Delegate to scoring_core ───
    t = scoring_core.score_title(title, max_score=_WEIGHTS["title"])
    m = scoring_core.score_meta(meta, max_score=_WEIGHTS["meta"], require_cta=True)
    s = scoring_core.score_structure(body_html, url_type=url_type,
                                     max_score=_WEIGHTS["structure"],
                                     require_sections=True)
    l = scoring_core.score_links(body_html, base_url=None,
                                 max_score=_WEIGHTS["links"])
    rd_full = readability_metrics(text)  # raw metrics for `readability` field
    r = scoring_core.score_readability(text, max_score=_WEIGHTS["readability"])

    # ─── Bucket issues into high/med/low (legacy str-list format) ───
    issues_high, issues_med, issues_low = scoring_core.bucket_issues(
        t["issues"], m["issues"], s["issues"], l["issues"], r["issues"],
    )

    # ─── Build breakdown dict in legacy shape ───
    # Each category keeps {score, max, issues: list[str], ...extra}
    def _flatten_issues(issues: list) -> list:
        out = []
        for it in issues or []:
            msg = it.get("msg", "")
            sev = it.get("severity", "low")
            prefix = {"high": "❌ ", "med": "⚠️ ", "low": "⚠️ "}.get(sev, "")
            # Strip leading emoji if already present
            if msg.startswith(("❌", "⚠️", "ℹ️", "🚨", "🔴", "🟡", "🟠", "🟢", "🔵")):
                out.append(msg)
            else:
                out.append(prefix + msg)
        return out

    breakdown = {
        "title": {
            "score": t["score"], "max": t["max"],
            "issues": _flatten_issues(t["issues"]),
            "len": t["meta"].get("len", 0),
        },
        "meta": {
            "score": m["score"], "max": m["max"],
            "issues": _flatten_issues(m["issues"]),
            "len": m["meta"].get("len", 0),
        },
        "structure": {
            "score": s["score"], "max": s["max"],
            "issues": _flatten_issues(s["issues"]),
            "n_h1": s["meta"].get("n_h1", 0),
            "n_h2": s["meta"].get("n_h2", 0),
            "n_h3": s["meta"].get("n_h3", 0),
            "n_words": s["meta"].get("n_words", n_words),
        },
        "links": {
            "score": l["score"], "max": l["max"],
            "issues": _flatten_issues(l["issues"]),
            "n_internal": l["meta"].get("n_internal", 0),
        },
        "readability": {
            "score": r["score"], "max": r["max"],
            "issues": _flatten_issues(r["issues"]),
            "raw_score": rd_full.get("score"),
            "level": rd_full.get("level"),
            "avg_sentence_len": rd_full.get("avg_sentence_len"),
            "avg_word_len": rd_full.get("avg_word_len"),
            "complex_pct": rd_full.get("complex_pct"),
            "passive_pct": rd_full.get("passive_pct"),
            "filler_count": rd_full.get("filler_count"),
            "n_words": rd_full.get("n_words"),
        },
    }

    total = sum(b["score"] for b in breakdown.values())

    if total >= 80:
        tier = "🟢 Excellent"
    elif total >= 65:
        tier = "🟢 Tốt"
    elif total >= 50:
        tier = "🟡 OK"
    elif total >= 35:
        tier = "🟠 Cần fix"
    else:
        tier = "🔴 Cần làm lại"

    return {
        "score": total,
        "max": 100,
        "tier": tier,
        "breakdown": breakdown,
        "issues_high": issues_high,
        "issues_med": issues_med,
        "issues_low": issues_low,
        "readability": rd_full,
    }
