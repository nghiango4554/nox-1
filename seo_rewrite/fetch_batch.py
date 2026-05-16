"""Fetch metadata cô đọng cho 1 batch URL từ Sintech, output JSON."""
import sys, json, re, urllib.request, csv, os
sys.stdout.reconfigure(encoding="utf-8")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

def fetch(url):
    try:
        req = urllib.request.Request(url + ".json", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))["product"]
    except Exception as e:
        return {"error": str(e)}

def fetch_html(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        title = re.search(r"<title>([^<]+)</title>", html, re.I)
        meta = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        import html as h
        return {
            "current_title": h.unescape((title.group(1) if title else "").strip().replace("\n"," ").replace("        "," ")),
            "current_meta": h.unescape((meta.group(1) if meta else "").strip()),
        }
    except Exception as e:
        return {"err": str(e)}

# Đọc list URL từ TSV, skip 5 demo đã làm
DEMO_DONE = {
    "https://sintech.vn/products/ram-apacer-ddr5-16gb-5600mhz-oc-nox-white-16x1",
    "https://sintech.vn/products/mainboard-asus-rog-strix-b860-a-wifi-ddr5",
    "https://sintech.vn/products/chuot-co-day-hp-gaming-mouse-x600-co-led",
    "https://sintech.vn/products/tan-nhiet-nuoc-aio-thermaltake-th360-v2-argb-snow",
    "https://sintech.vn/products/laptop-asus-rog-strix-g15-g513ic-hn002t-cu-dep",
}

urls_seen = []
seen_set = set()
with open(r"C:\Users\Nghia Dep Gai\.openclaw\workspace\seo_duplicates.tsv", encoding="utf-8") as f:
    rd = csv.reader(f, delimiter="\t")
    next(rd)
    for row in rd:
        for u in row[3].split(" | "):
            u = u.strip()
            if u and u not in seen_set and u not in DEMO_DONE:
                seen_set.add(u)
                urls_seen.append(u)

batch_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1
batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
start = (batch_idx - 1) * batch_size
end = start + batch_size
batch = urls_seen[start:end]

print(f"# Batch {batch_idx} | URLs {start+1}-{end} (tổng {len(urls_seen)} URL chưa làm)\n")

out = []
for i, url in enumerate(batch, start=1):
    print(f"[{i}/{len(batch)}] {url}")
    p = fetch(url)
    h = fetch_html(url)
    if "error" in p:
        print(f"   ! product err: {p['error']}")
        out.append({"url": url, "error": p["error"]})
        continue
    body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p.get("body_html","")))
    item = {
        "url": url,
        "name": p.get("title",""),
        "vendor": p.get("vendor",""),
        "type": p.get("product_type",""),
        "price": (p.get("variants") or [{}])[0].get("price",""),
        "current_title": h.get("current_title",""),
        "current_meta": h.get("current_meta",""),
        "desc_300": body[:600],
    }
    out.append(item)

OUT_DIR = r"C:\Users\Nghia Dep Gai\.openclaw\workspace\seo_rewrite"
os.makedirs(OUT_DIR, exist_ok=True)
with open(os.path.join(OUT_DIR, f"batch_{batch_idx:02d}_data.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\n→ Saved {len(out)} items → batch_{batch_idx:02d}_data.json")
