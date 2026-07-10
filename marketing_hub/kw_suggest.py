# -*- coding: utf-8 -*-
"""kw_suggest.py — Kéo gợi ý Google Autocomplete (đúng cách vợ research thủ công).

Google Autocomplete = danh sách gợi ý hiện ra khi gõ vào ô tìm kiếm.
Đây là truy vấn NGƯỜI THẬT gõ, xếp theo độ phổ biến. API công khai, KHÔNG cần key,
không giới hạn quota thực tế. Đây là nguồn "intent tìm kiếm" rẻ nhất và đúng nhất
cho heading bài SP/collection.

⚠️ Autocomplete KHÔNG cho volume tuyệt đối (bao nhiêu lượt/tháng). Nó chỉ nói
"cụm này đủ phổ biến để Google gợi ý". Muốn volume tuyệt đối phải dùng
Keyword Planner hoặc DataForSEO.

Dùng:
    python kw_suggest.py "usb 64gb" "ổ cứng camera"
    from kw_suggest import harvest; harvest(["fan case"])
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://suggestqueries.google.com/complete/search"

# Hậu tố kéo ra câu hỏi — chính là loại heading ăn featured snippet + AI Overview
MODIFIERS = ["", " có", " cách", " bao nhiêu", " là gì", " loại nào tốt",
             " khác nhau", " nên mua"]


def suggest(query: str, hl: str = "vi", gl: str = "vn", timeout: int = 15) -> list:
    """Gợi ý cho 1 truy vấn. Trả list rỗng nếu lỗi (không raise)."""
    url = f"{ENDPOINT}?client=firefox&hl={hl}&gl={gl}&q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        raw = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")
        return json.loads(raw)[1]
    except Exception as e:
        print(f"[kw_suggest] lỗi {query!r}: {str(e)[:60]}", file=sys.stderr)
        return []


def harvest(seeds, modifiers=None, delay: float = 0.25) -> dict:
    """Quét seed × hậu tố → {seed: [long-tail duy nhất]}. Giữ thứ tự Google trả về
    (thứ tự = độ phổ biến giảm dần)."""
    mods = MODIFIERS if modifiers is None else modifiers
    out, seen = {}, set()
    for s in seeds:
        found = []
        for m in mods:
            for x in suggest(s + m):
                k = x.lower().strip()
                if k in seen or k == s.lower():
                    continue
                seen.add(k)
                found.append(x)
            time.sleep(delay)
        out[s] = found
    return out


def questions_only(results: dict) -> list:
    """Lọc riêng gợi ý dạng câu hỏi — nguồn tốt nhất cho H2/H3 và FAQ."""
    marks = ("có ", "cách ", "bao nhiêu", "là gì", "loại nào", "khác nhau",
             "nên mua", "được không", "bao lâu", "tại sao", "vì sao")
    qs = []
    for lst in results.values():
        qs += [x for x in lst if any(m in x.lower() for m in marks)]
    return qs


if __name__ == "__main__":
    seeds = sys.argv[1:] or ["usb 64gb"]
    res = harvest(seeds)
    for s, lst in res.items():
        print(f"\n### {s}  ({len(lst)} gợi ý)")
        for x in lst:
            print("   -", x)
    qs = questions_only(res)
    print(f"\n=== {len(qs)} gợi ý dạng CÂU HỎI (ưu tiên làm H2/H3/FAQ) ===")
    for q in qs:
        print("   ?", q)
