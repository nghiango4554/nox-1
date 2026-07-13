"""Verify FAQPage schema tren trang LIVE: parse JSON-LD that, doi chieu so cau hoi voi body bai.

BAI HOC 13/7: KHONG duoc grep chu "FAQPage" — comment FAQJSON trong body cung chua chu do
-> grep bao PASS gia. Phai parse JSON-LD roi dem mainEntity.

Chay:  py -3.12 _scripts/faq_verify.py
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import requests

import faq_schema
import haravan_blog as hb

BLOGS = {1000906526: "news", 1000960873: "huong-dan"}
LD_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S)


def live_faq_count(url: str) -> int:
    """So cau hoi FAQPage tren trang live. -1 = JSON hong, -2 = khong tai duoc."""
    try:
        h = requests.get(url + "?v=faqcheck", timeout=30).text
    except Exception:
        return -2
    for b in LD_RE.findall(h):
        try:
            d = json.loads(b.strip())
        except Exception:
            continue
        if d.get("@type") == "FAQPage":
            return len(d.get("mainEntity") or [])
    return 0


def main():
    rows = []
    for bid, slug in BLOGS.items():
        page = 1
        while True:
            arts = hb.list_articles(bid, limit=50, page=page)
            if not arts:
                break
            for a in arts:
                exp = len(faq_schema.extract_faq(a.get("body_html") or ""))
                if exp >= faq_schema.MIN_QUESTIONS:
                    rows.append((f"https://sintech.vn/blogs/{slug}/{a['handle']}", a["handle"], exp))
            page += 1

    print(f"Kiem {len(rows)} bai co khoi FAQ trong body...\n")
    with ThreadPoolExecutor(max_workers=8) as ex:
        got = list(ex.map(lambda r: live_faq_count(r[0]), rows))

    ok = [(r, g) for r, g in zip(rows, got) if g == r[2] and g > 0]
    bad = [(r, g) for r, g in zip(rows, got) if not (g == r[2] and g > 0)]

    print(f"DUNG : {len(ok)} bai — schema live khop so cau hoi trong bai")
    print(f"LECH : {len(bad)}")
    for (url, handle, exp), g in bad:
        ly = {0: "live KHONG co FAQPage", -1: "JSON hong", -2: "khong tai duoc trang"}.get(g, f"live {g} cau")
        print(f"   trong bai {exp} cau · {ly}  — {handle}")
    print(f"\nTong cau hoi len schema: {sum(g for _, g in ok)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
