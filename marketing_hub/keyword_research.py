"""Keyword research bằng Google Suggest API (free, no auth) — pull search
suggestions thực tế của khách Việt cho SP.

Endpoint: http://suggestqueries.google.com/complete/search
Trả JSON: ["query", ["suggestion 1", "suggestion 2", ...], [], {...}]

Mục đích: feed list suggestions này vào AI prompt → AI design H2 dựa trên
intent thực sự (giá, review, hợp ai, dùng được không, lỗi thường gặp...)
thay vì heading template cứng.
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

import requests

SUGGEST_URL = "http://suggestqueries.google.com/complete/search"
TIMEOUT = 5            # mỗi query — short để không hang lâu
MAX_TOTAL_TIME = 25    # tổng thời gian cho 1 product research, hard cap
MAX_QUERIES = 16       # cap tổng số queries để giảm rate-limit risk
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Variations để pull đa dạng intent — sẽ append vào keyword chính
# Dựa trên search intent phổ biến VN: giá / review / so sánh / hợp ai / lỗi
QUERY_VARIATIONS = [
    "",                           # raw — autocomplete cơ bản
    " giá",                       # intent giá
    " review",                    # intent review
    " có tốt không",              # intent đánh giá
    " đánh giá",                  # intent review
    " mua ở đâu",                 # intent mua
    " dùng được không",           # intent compatibility
    " hợp với ai",                # intent target user
    " so sánh",                   # intent comparison
    " setup",                     # intent hướng dẫn
    " lỗi",                       # intent troubleshoot
    " cấu hình",                  # intent build/spec
    " bao nhiêu tiền",            # intent giá
    " chính hãng",                # intent trust
    " có nên mua",                # intent decision
]


def get_suggestions(query: str, hl: str = "vi", gl: str = "vn", timeout: int = TIMEOUT) -> List[str]:
    """Gọi Google Suggest API cho 1 query, trả list suggestions."""
    if not query or not query.strip():
        return []
    try:
        r = requests.get(
            SUGGEST_URL,
            params={"client": "firefox", "q": query.strip(), "hl": hl, "gl": gl},
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        if r.status_code != 200:
            return []
        # Response format: ["query", ["s1", "s2", ...]]
        data = json.loads(r.text)
        if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
            return [s for s in data[1] if isinstance(s, str)]
    except Exception as e:
        print(f"[suggest skip] {query}: {e}")
    return []


def _shorten_keyword_for_search(product_name: str, vendor: str = "", product_type: str = "") -> List[str]:
    """Tạo các keyword cốt lõi để search — không dùng full tên SP (quá specific).

    Vd: "Laptop Asus Gaming TUF F16 FX607JU-N3139W (i7-13650HX, 16GB...)"
    → ["Asus TUF F16", "Asus Gaming TUF", "TUF F16 FX607JU"]
    """
    if not product_name:
        return []
    name = re.sub(r"\s+", " ", product_name).strip()

    # Bỏ phần spec trong ngoặc (...) và sau dấu —/–/-
    base = re.split(r"\s*[\(\[]\s*", name, maxsplit=1)[0]
    base = re.split(r"\s*[—–]\s*", base, maxsplit=1)[0]
    base = base.strip()

    # Bỏ tiền tố loại SP đầu tên (Laptop / CPU / Mainboard / Card Màn Hình / ...)
    leading_categories = [
        r"^Laptop\s+", r"^CPU\s+", r"^Mainboard\s+", r"^RAM\s+",
        r"^Ổ\s+Cứng\s+(SSD|HDD)\s+", r"^Card\s+Màn\s+Hình\s+", r"^VGA\s+",
        r"^Vỏ\s+Case\s+", r"^Nguồn\s+", r"^Tản\s+Nhiệt\s+(Khí|Nước)?\s*",
        r"^Fan\s+Case\s+", r"^Màn\s+Hình\s+(Văn\s+Phòng|Gaming|Cong)?\s*",
        r"^Phím\s+(Cơ|Văn\s+Phòng)?\s*", r"^Chuột\s+(Gaming|Văn\s+Phòng)?\s*",
        r"^PC\s+(Gaming|Văn\s+Phòng)\s+", r"^Tai\s+Nghe\s+(Gaming)?\s*",
    ]
    short = base
    for pat in leading_categories:
        short = re.sub(pat, "", short, flags=re.IGNORECASE).strip()
    # Bỏ modifier words bất kỳ vị trí nào (Gaming / Văn phòng / Cong / AI Creator / Đồ họa)
    short = re.sub(r"\s+(Gaming|Văn\s+Phòng|Cong|Đồ\s+Họa|AI\s+Creator)\b", " ", short, flags=re.IGNORECASE)
    short = re.sub(r"\s+", " ", short).strip()

    # Tạo variations
    variants = set()
    if short and len(short) >= 3:
        variants.add(short)
    # Vendor + 2-3 từ đầu của short
    if vendor and short:
        words = short.split()
        if vendor.lower() not in short.lower():
            if len(words) >= 2:
                variants.add(f"{vendor} {' '.join(words[:3])}")
            else:
                variants.add(f"{vendor} {short}")
        # Cũng add "model + last 2 words"
        if len(words) >= 3:
            variants.add(" ".join(words[-3:]))
    # Vendor + product type chung (vd "laptop Lenovo")
    if vendor and product_type:
        pt = product_type.lower().replace("văn phòng", "").replace("gaming", "").strip()
        if pt and len(pt) >= 3:
            variants.add(f"{pt} {vendor}".strip())

    # Loại variant chứa từ rác / quá dài
    out = []
    for v in variants:
        v = v.strip()
        if not v or len(v) < 3 or len(v) > 60:
            continue
        # Skip variant có vendor lặp lại
        if vendor and v.lower().count(vendor.lower()) > 1:
            continue
        out.append(v)
    return out


def research_keyword_for_product(product_name: str, vendor: str = "",
                                  product_type: str = "", max_results: int = 30) -> Dict:
    """Pull Google Suggest cho 1 SP — return aggregated suggestions phân loại.

    Returns dict:
    {
        "core_keywords": [...],          # các keyword cốt lõi đã rút từ tên SP
        "raw_suggestions": [...],        # tất cả suggestions raw từ Google
        "by_intent": {                   # phân loại theo intent
            "price": [...],
            "review": [...],
            "comparison": [...],
            "compatibility": [...],
            "guide": [...],
            "other": [...],
        },
        "top_questions": [...],           # top 10 questions có dạng câu hỏi
    }
    """
    cores = _shorten_keyword_for_search(product_name, vendor, product_type)
    if not cores:
        return {"core_keywords": [], "raw_suggestions": [], "by_intent": {}, "top_questions": []}

    # Reorder cores: ưu tiên short cores trước (max 3)
    cores_sorted = sorted(cores, key=lambda c: len(c))[:3]

    # Build queries: cap tổng MAX_QUERIES để tránh hang
    queries = []
    for core in cores_sorted:
        for variation in QUERY_VARIATIONS[:6]:  # 6 variations × 3 cores = 18 max
            queries.append(core + variation)
            if len(queries) >= MAX_QUERIES:
                break
        if len(queries) >= MAX_QUERIES:
            break

    # Parallel fetch với hard timeout overall
    all_suggestions = set()
    start_ts = time.time()

    def _fetch(q):
        if time.time() - start_ts > MAX_TOTAL_TIME:
            return []
        return get_suggestions(q)

    try:
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(_fetch, q) for q in queries]
            for fut in futures:
                if time.time() - start_ts > MAX_TOTAL_TIME:
                    # Cancel remaining
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    break
                try:
                    sugg_list = fut.result(timeout=max(1, MAX_TOTAL_TIME - (time.time() - start_ts)))
                    for s in sugg_list:
                        all_suggestions.add(s.strip())
                except Exception:
                    pass
    except Exception as e:
        print(f"[keyword research aborted] {e}")

    raw = sorted(all_suggestions, key=lambda x: len(x))

    # Phân loại theo intent
    by_intent = {
        "price": [],
        "review": [],
        "comparison": [],
        "compatibility": [],
        "guide": [],
        "trust": [],
        "other": [],
    }
    for s in raw:
        sl = s.lower()
        if any(k in sl for k in ["giá", "bao nhiêu", "tiền", "rẻ"]):
            by_intent["price"].append(s)
        elif any(k in sl for k in ["review", "đánh giá", "test", "có tốt", "có ngon"]):
            by_intent["review"].append(s)
        elif any(k in sl for k in ["so sánh", " vs ", "khác", "nên mua"]):
            by_intent["comparison"].append(s)
        elif any(k in sl for k in ["dùng được", "hợp", "tương thích", "support"]):
            by_intent["compatibility"].append(s)
        elif any(k in sl for k in ["setup", "cài đặt", "hướng dẫn", "cấu hình", "build"]):
            by_intent["guide"].append(s)
        elif any(k in sl for k in ["chính hãng", "uy tín", "shop nào", "ở đâu"]):
            by_intent["trust"].append(s)
        else:
            by_intent["other"].append(s)

    # Top câu hỏi — suggestions có dạng câu hỏi (kết thúc ?, hoặc bắt đầu what/how/...)
    question_pattern = re.compile(
        r"(có|nên|làm sao|thế nào|bao nhiêu|tốt không|được không|là gì|nào tốt|hợp với)",
        flags=re.IGNORECASE,
    )
    top_questions = [s for s in raw if question_pattern.search(s)][:10]

    return {
        "core_keywords": cores,
        "raw_suggestions": raw[:max_results],
        "by_intent": by_intent,
        "top_questions": top_questions,
    }


# CLI smoke test
if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    test_products = [
        ("Màn hình E-DRA EGM27F120H 27 inch FullHD 120Hz IPS", "EDRA", "MÀN HÌNH"),
        ("Laptop Lenovo Văn phòng ThinkPad L580 (i5-8250U, 16GB, 512GB)", "LENOVO", "LAPTOP"),
    ]
    for name, vendor, ptype in test_products:
        print(f"\n=== {name} ===")
        res = research_keyword_for_product(name, vendor, ptype)
        print(f"Core keywords: {res['core_keywords']}")
        print(f"Raw suggestions ({len(res['raw_suggestions'])}):")
        for s in res["raw_suggestions"][:15]:
            print(f"  - {s}")
        print(f"Top questions ({len(res['top_questions'])}):")
        for q in res["top_questions"]:
            print(f"  ? {q}")
        print("By intent:")
        for intent, items in res["by_intent"].items():
            if items:
                print(f"  [{intent}] ({len(items)}): {items[:3]}")
