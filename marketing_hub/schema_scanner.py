"""Schema scanner — parse JSON-LD structured data từ HTML.

Phase 4B của Task 4 SEO Crawl Optimization. Fetch URL, extract toàn bộ
<script type="application/ld+json"> blocks, identify schema @type
(Product/Article/FAQPage/BreadcrumbList/Organization/...), trả về dict cho
seo_schema_upsert() lưu DB.

Handle robust:
- Malformed JSON → ghi vào errors[], không crash.
- @graph nested → flatten extract @type của từng node.
- @type là array → flatten ra nhiều type.
- @type là string đơn lẻ → 1 type.
- @type vắng → skip block đó, không count.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup

import db

logger = logging.getLogger(__name__)

USER_AGENT = "SintechHubSEOBot/1.0 (+marketing_hub schema)"
DEFAULT_TIMEOUT = 12

# Schema types coi như "rich snippet eligible" cho Sintech
PRIORITY_TYPES = {
    "product": {"Product"},
    "faq": {"FAQPage"},
    "article": {"Article", "NewsArticle", "BlogPosting", "TechArticle"},
}


def _extract_types_from_node(node: Any) -> list:
    """Trả về list @type strings từ 1 JSON-LD node. Hỗ trợ:
    - @type là string: ["Product"]
    - @type là array: ["Product", "Thing"]
    - @type vắng: []
    """
    if not isinstance(node, dict):
        return []
    t = node.get("@type")
    if isinstance(t, str):
        return [t]
    if isinstance(t, list):
        return [str(x) for x in t if isinstance(x, (str, int))]
    return []


def _iter_jsonld_nodes(payload: Any) -> Iterable[dict]:
    """Yield mọi node có khả năng chứa @type, kể cả nested @graph + array root."""
    if isinstance(payload, list):
        for item in payload:
            yield from _iter_jsonld_nodes(item)
        return
    if not isinstance(payload, dict):
        return
    yield payload
    graph = payload.get("@graph")
    if isinstance(graph, list):
        for node in graph:
            yield from _iter_jsonld_nodes(node)


def extract_jsonld_from_html(html: str) -> dict:
    """Parse HTML, extract toàn bộ JSON-LD script blocks.

    Return:
        {
          "blocks": [ {raw_text, parsed_or_None, types: [...], error: str|None} ],
          "all_types": ["Product", "BreadcrumbList", ...]  # dedup, preserve order
          "errors": ["block#0: Expecting value...", ...]
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script", attrs={"type": "application/ld+json"})

    blocks = []
    all_types: list = []
    seen_types: set = set()
    errors: list = []

    for idx, tag in enumerate(scripts):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            blocks.append({"index": idx, "error": "empty_block", "types": []})
            errors.append(f"block#{idx}: empty")
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            err = f"block#{idx}: {e.msg} at line {e.lineno} col {e.colno}"
            blocks.append({"index": idx, "error": err, "types": []})
            errors.append(err)
            continue

        types_here: list = []
        for node in _iter_jsonld_nodes(payload):
            for t in _extract_types_from_node(node):
                types_here.append(t)
                if t not in seen_types:
                    seen_types.add(t)
                    all_types.append(t)
        blocks.append({"index": idx, "error": None, "types": types_here})

    return {"blocks": blocks, "all_types": all_types, "errors": errors}


def scan_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Fetch URL + extract JSON-LD. Return dict sẵn cho db.seo_schema_upsert()."""
    out = {
        "schema_types": None,
        "schema_count": 0,
        "has_product": False,
        "has_faq": False,
        "has_article": False,
        "schema_errors": None,
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "fetch_error": None,
    }
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        out["fetch_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        out["schema_errors"] = json.dumps([out["fetch_error"]], ensure_ascii=False)
        return out

    if r.status_code != 200:
        out["fetch_error"] = f"HTTP {r.status_code}"
        out["schema_errors"] = json.dumps([out["fetch_error"]], ensure_ascii=False)
        return out

    parsed = extract_jsonld_from_html(r.text)
    all_types = parsed["all_types"]
    errors = parsed["errors"]
    blocks = parsed["blocks"]

    out["schema_count"] = len([b for b in blocks if b.get("error") is None])
    out["schema_types"] = json.dumps(all_types, ensure_ascii=False) if all_types else None
    out["schema_errors"] = json.dumps(errors, ensure_ascii=False) if errors else None

    types_lower = {t.lower() for t in all_types}
    out["has_product"] = any(t.lower() in types_lower for t in PRIORITY_TYPES["product"])
    out["has_faq"] = any(t.lower() in types_lower for t in PRIORITY_TYPES["faq"])
    out["has_article"] = any(t.lower() in types_lower for t in PRIORITY_TYPES["article"])
    return out


def update_page_schema(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """Scan URL + upsert DB. Return scan result."""
    data = scan_url(url, timeout=timeout)
    db.seo_schema_upsert(url, data)
    return data


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: py -3.12 schema_scanner.py <url> [<url> ...]")
        sys.exit(1)
    for u in sys.argv[1:]:
        print(f"\n=== {u} ===")
        result = scan_url(u)
        print(f"  count: {result['schema_count']}")
        print(f"  types: {result['schema_types']}")
        print(f"  has_product/faq/article: {result['has_product']}/{result['has_faq']}/{result['has_article']}")
        if result.get("fetch_error"):
            print(f"  fetch_error: {result['fetch_error']}")
        if result.get("schema_errors"):
            print(f"  errors: {result['schema_errors']}")
