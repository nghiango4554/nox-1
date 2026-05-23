"""Serper.dev Google Search API — dùng cho research heading đối thủ.

Key: .secrets/serper.env (SERPER_API_KEY) hoặc env var SERPER_API_KEY.
Free plan: 2,500 queries/tháng.

Dùng trong Pass 1 gen outline: search keyword → cào H2/H3 top 5 kết quả
→ đưa vào prompt → AI gen heading unique hơn đối thủ.
"""
from __future__ import annotations

import os
import re
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup

_SECRETS_FILE = Path(__file__).parent.parent / ".secrets" / "serper.env"
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def _get_key() -> str:
    key = os.environ.get("SERPER_API_KEY", "").strip()
    if key:
        return key
    if _SECRETS_FILE.exists():
        for line in _SECRETS_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("SERPER_API_KEY="):
                key = line.split("=", 1)[1].strip()
                if key:
                    return key
    return ""


def is_serper_available() -> bool:
    return bool(_get_key())


def search_google(query: str, num: int = 5) -> list[dict]:
    """Tìm Google qua Serper API. Trả list {title, link, snippet}."""
    key = _get_key()
    if not key:
        return []
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "gl": "vn", "hl": "vi", "num": num},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return [
            {"title": item.get("title", ""), "link": item.get("link", ""), "snippet": item.get("snippet", "")}
            for item in data.get("organic", [])[:num]
        ]
    except Exception as e:
        print(f"[serper] search error: {e}")
        return []


def _extract_headings(url: str) -> list[str]:
    """Cào H2/H3 từ 1 URL. Trả list string."""
    try:
        r = requests.get(url, headers=HEAD, timeout=12, verify=False)
        if r.status_code >= 400:
            return []
        soup = BeautifulSoup(r.content, "lxml")
        headings = []
        for tag in soup.find_all(["h2", "h3"]):
            text = tag.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text).strip()
            if text and len(text) > 5 and len(text) < 120:
                headings.append(f"{'##' if tag.name == 'h2' else '###'} {text}")
        return headings[:25]
    except Exception:
        return []


def research_competitor_headings(keyword: str, max_urls: int = 4) -> dict:
    """Search keyword → cào heading từ top results → trả context cho AI.

    Trả {ok, competitor_headings_text, urls_scraped}
    competitor_headings_text: string nhiều dòng, mỗi dòng là ## H2 hoặc ### H3
    """
    results = search_google(keyword, num=max_urls + 2)
    if not results:
        return {"ok": False, "error": "Serper không trả kết quả hoặc key lỗi."}

    # Bỏ qua sintech.vn (trang mình) và các trang không liên quan
    skip_domains = ("sintech.vn", "facebook.com", "youtube.com", "tiktok.com", "instagram.com")
    urls = [r["link"] for r in results if not any(d in r["link"] for d in skip_domains)][:max_urls]

    all_headings: list[str] = []
    urls_scraped: list[str] = []
    for url in urls:
        h = _extract_headings(url)
        if h:
            all_headings.extend(h)
            urls_scraped.append(url)
        if len(urls_scraped) >= max_urls:
            break

    if not all_headings:
        return {"ok": False, "error": "Không cào được heading từ URL nào."}

    # Dedup giữ thứ tự
    seen: set[str] = set()
    unique: list[str] = []
    for h in all_headings:
        key = re.sub(r"^#+\s*", "", h).lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(h)

    return {
        "ok": True,
        "competitor_headings_text": "\n".join(unique),
        "urls_scraped": urls_scraped,
    }
