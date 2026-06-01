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


# ─────────────────── Cào BẢNG THÔNG SỐ sản phẩm ───────────────────

# Trang JS-heavy / không cào được table tĩnh → bỏ qua khi cào spec.
_SPEC_SKIP_DOMAINS = (
    "shopee.vn", "lazada.vn", "tiki.vn", "sendo.vn",
    "facebook.com", "youtube.com", "tiktok.com", "instagram.com",
    "thegioididong.com",  # specs render bằng JS, không có <table> tĩnh
)


def _extract_spec_table(url: str) -> list[dict]:
    """Cào bảng thông số kỹ thuật từ 1 trang SP. Trả list {label, value}.

    Hỗ trợ 3 dạng markup: <table> 2 cột · <dl>/<dt>/<dd> · <li>/<div> 2 con (nhãn+giá trị).
    """
    try:
        r = requests.get(url, headers=HEAD, timeout=14, verify=False)
        if r.status_code >= 400:
            return []
        soup = BeautifulSoup(r.content, "lxml")
    except Exception:
        return []

    specs: list[dict] = []
    seen: set[str] = set()

    def add(label: str, value: str) -> None:
        label = re.sub(r"\s+", " ", label or "").strip().strip(":").strip()
        value = re.sub(r"\s+", " ", value or "").strip()
        if not label or not value or label.lower() == value.lower():
            return
        if len(label) < 2 or len(label) > 50 or len(value) > 400:
            return
        k = label.lower()
        if k in seen:
            return
        seen.add(k)
        specs.append({"label": label, "value": value})

    # 1) Bảng 2 cột (CellphoneS, FPTShop, GearVN...)
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if len(cells) == 2:
                add(cells[0].get_text(" ", strip=True), cells[1].get_text(" ", strip=True))

    # 2) Definition list
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            add(dt.get_text(" ", strip=True), dd.get_text(" ", strip=True))

    # 3) Fallback: li/div có đúng 2 con block (nhãn + giá trị)
    if len(specs) < 5:
        for el in soup.find_all(["li", "div"]):
            kids = el.find_all(recursive=False)
            if len(kids) == 2:
                add(kids[0].get_text(" ", strip=True), kids[1].get_text(" ", strip=True))

    return specs


def fetch_product_specs(query: str, max_urls: int = 5, min_specs: int = 6) -> dict:
    """Search Google → cào bảng thông số từ trang SP đầu tiên đủ spec.

    Trả {ok, source_url, specs:[{label,value}], specs_text, tried}.
    Chọn trang đạt >= min_specs dòng; nếu không có thì lấy trang nhiều spec nhất.
    """
    results = search_google(query, num=max_urls + 3)
    if not results:
        return {"ok": False, "error": "Serper không trả kết quả hoặc key lỗi."}

    tried: list[dict] = []
    best: dict | None = None
    for r in results:
        link = r["link"]
        if any(d in link for d in _SPEC_SKIP_DOMAINS):
            continue
        specs = _extract_spec_table(link)
        tried.append({"url": link, "n": len(specs)})
        if specs and (best is None or len(specs) > len(best["specs"])):
            best = {"url": link, "specs": specs}
        if len(specs) >= min_specs:
            break
        if len(tried) >= max_urls:
            break

    if not best:
        return {"ok": False, "error": "Không cào được bảng thông số từ trang nào.",
                "tried": tried}

    specs_text = "\n".join(f"- {s['label']}: {s['value']}" for s in best["specs"])
    return {
        "ok": True,
        "source_url": best["url"],
        "specs": best["specs"],
        "specs_text": specs_text,
        "tried": tried,
    }


# ─────────────────── Phát hiện SPEC LỆCH (gốc vs web) ───────────────────

def _web_value(web: dict, *keywords: str, exclude: tuple = ()) -> str:
    for label, val in web.items():
        if any(k in label for k in keywords) and not any(x in label for x in exclude):
            return val
    return ""


def _num_near(text: str, unit_re: str, block_words=("tối đa", "nâng cấp", "lên đến", "lên tới", "upgrade", "max")) -> int | None:
    """Tìm số + đơn vị trong text, BỎ QUA nếu đứng sau từ chỉ mức nâng cấp (tránh báo nhầm)."""
    for m in re.finditer(unit_re, text, re.I):
        seg = text[max(0, m.start() - 22):m.start()].lower()
        if any(w in seg for w in block_words):
            continue
        for g in m.groups():
            if g and g.isdigit():
                return int(g)
    return None


def detect_spec_conflicts(body_text: str, web_specs: list[dict]) -> list[dict]:
    """So spec GỐC (body_text — mô tả Haravan) vs spec WEB (structured) trên các
    field chính. Trả list {field, body, web} khi LỆCH RÕ.

    Conservative: chỉ flag khi CẢ HAI nguồn có giá trị extract được rõ ràng;
    bỏ qua ngữ cảnh "tối đa/nâng cấp" để khỏi báo nhầm.
    """
    body = re.sub(r"\s+", " ", (body_text or "")).strip()
    web = {(s.get("label") or "").lower(): (s.get("value") or "") for s in (web_specs or [])}
    conflicts: list[dict] = []

    # RAM (GB)
    web_ram = _num_near(_web_value(web, "ram", exclude=("loại", "khe", "bus", "công nghệ")), r"(\d+)\s*gb")
    body_ram = _num_near(body, r"ram[^0-9]{0,15}(\d+)\s*gb|(\d+)\s*gb[^0-9a-z]{0,4}ram")
    if web_ram and body_ram and web_ram != body_ram:
        conflicts.append({"field": "RAM", "body": f"{body_ram}GB", "web": f"{web_ram}GB"})

    # Ổ cứng (quy về GB)
    def _sto(s):
        m = re.search(r"(\d+)\s*(tb|gb)", s, re.I)
        if not m:
            return None
        n = int(m.group(1))
        return n * 1000 if m.group(2).lower() == "tb" else n
    web_sto = _sto(_web_value(web, "ổ cứng", "lưu trữ", "ssd", "hdd", "dung lượng lưu"))
    body_sto = None
    for m in re.finditer(r"(\d+)\s*(tb|gb)\s*(ssd|hdd|nvme|pcie|emmc)", body, re.I):
        seg = body[max(0, m.start() - 22):m.start()].lower()
        if "tối đa" in seg or "nâng cấp" in seg:
            continue
        n = int(m.group(1))
        body_sto = n * 1000 if m.group(2).lower() == "tb" else n
        break
    if web_sto and body_sto and web_sto != body_sto:
        def _fmt(g):
            return f"{g // 1000}TB" if g >= 1000 and g % 1000 == 0 else f"{g}GB"
        conflicts.append({"field": "Ổ cứng", "body": _fmt(body_sto), "web": _fmt(web_sto)})

    # Màn hình (inch)
    def _inch(s):
        m = re.search(r"(\d{2}[.,]?\d?)\s*inch", s, re.I)
        return float(m.group(1).replace(",", ".")) if m else None
    web_in = _inch(_web_value(web, "kích thước màn"))
    body_in = _inch(body)
    if web_in and body_in and abs(web_in - body_in) > 0.05:
        conflicts.append({"field": "Màn hình", "body": f'{body_in}"', "web": f'{web_in}"'})

    # Tần số quét (Hz)
    web_hz = _num_near(_web_value(web, "tần số", "refresh", "quét") or " ".join(web.values()), r"(\d+)\s*hz")
    body_hz = _num_near(body, r"(\d+)\s*hz")
    if web_hz and body_hz and web_hz != body_hz:
        conflicts.append({"field": "Tần số quét", "body": f"{body_hz}Hz", "web": f"{web_hz}Hz"})

    return conflicts
