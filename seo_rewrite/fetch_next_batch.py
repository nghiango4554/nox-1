"""Fetch next N URLs chưa làm (skip processed.json)"""
import os, sys, json, csv, re, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
PROCESSED = os.path.join(WS, "seo_rewrite", "auto_run", "processed.json")
TSV = os.path.join(WS, "seo_duplicates.tsv")

DONE_URLS = {
    "https://sintech.vn/products/ram-apacer-ddr5-16gb-5600mhz-oc-nox-white-16x1",
    "https://sintech.vn/products/mainboard-asus-rog-strix-b860-a-wifi-ddr5",
    "https://sintech.vn/products/chuot-co-day-hp-gaming-mouse-x600-co-led",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-th360-v2-argb-snow",
    "https://sintech.vn/products/laptop-asus-rog-strix-g15-g513ic-hn002t-cu-dep",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-ocypus-delta-l24-bk-argb-v2-trang",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-ocypus-delta-l24-bk-argb-v2-den",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-ocypus-delta-l36-bk-argb-v2-den",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-ocypus-sigma-l36-pro-den",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-segotep-kunlun-mu-360-a-rgb",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-magfloe-420-ultra-argb",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-magfloe-360-ultra-argb",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-la240-s-argb-sync",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-th360-v2-ultra-argb-snow",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-th360-v2-ultra-argb-black",
}

# Add Gemini-processed
if os.path.exists(PROCESSED):
    state = json.load(open(PROCESSED, encoding="utf-8"))
    DONE_URLS |= set(state["urls"])

UA = "Mozilla/5.0"
import html as h

def fetch(url):
    try:
        req = urllib.request.Request(url + ".json", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            p = json.loads(r.read().decode("utf-8"))["product"]
        req2 = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req2, timeout=15) as r:
            html_s = r.read().decode("utf-8", errors="replace")
        t = re.search(r"<title>([^<]+)</title>", html_s, re.I)
        m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html_s, re.I)
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p.get("body_html", "")))
        return {
            "url": url,
            "name": p.get("title", ""),
            "vendor": p.get("vendor", ""),
            "type": p.get("product_type", ""),
            "price": (p.get("variants") or [{}])[0].get("price", ""),
            "current_title": h.unescape((t.group(1) if t else "").strip().replace("\n", " ")).replace("        ", " ")[:100],
            "current_meta": h.unescape((m.group(1) if m else "").strip())[:200],
            "desc": body[:500],
        }
    except Exception as e:
        return {"url": url, "error": str(e)}

# Read all URLs
urls_seen = []
seen_set = set()
with open(TSV, encoding="utf-8") as f:
    rd = csv.reader(f, delimiter="\t")
    next(rd)
    for row in rd:
        for u in row[3].split(" | "):
            u = u.strip()
            if u and u not in seen_set:
                seen_set.add(u)
                urls_seen.append(u)

todo = [u for u in urls_seen if u not in DONE_URLS]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 10
print(f"# Còn {len(todo)} URL chưa làm. Fetch {N} URL kế tiếp:\n")

out = []
for i, url in enumerate(todo[:N], start=1):
    print(f"[{i}/{N}] {url}")
    out.append(fetch(url))

OUT = os.path.join(WS, "seo_rewrite", "next_batch.json")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\n→ Saved {OUT}")
print(f"→ next_row hiện tại: {state.get('next_row', 22) if os.path.exists(PROCESSED) else 22}")
