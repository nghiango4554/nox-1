# -*- coding: utf-8 -*-
"""Backup mô tả(body_html) + title + meta des của 50 trang top traffic (sheet Lịch sử Audit)."""
import json, re, sqlite3, time
from pathlib import Path
import requests
import haravan_client as hc
import blog_rewrite_apply as ap

CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
TOK = CFG.get("access_token") or CFG.get("blog_access_token")
H = {"Authorization": "Bearer %s" % TOK}

# 50 URL — đọc bằng regex từ file tạo sheet (tránh import gsheet)
src = (Path("..") / ".." / "_build_audit_history_tab.py").read_text(encoding="utf-8")
block = src.split("ROWS = [", 1)[1].split("]", 1)[0]
URLS = re.findall(r'\("(https?://[^"]+)"', block)

# ── lookups ──
pages = {}
r = requests.get("https://apis.haravan.com/web/pages.json", headers=H, params={"limit": 250}, timeout=30)
for p in r.json().get("pages", []):
    pages[p.get("handle")] = p

cols = {}
for typ in ("smart_collections", "custom_collections"):
    page = 1
    while page <= 6:
        try:
            d = hc._request("GET", "/%s.json" % typ, params={"page": page, "limit": 250})
        except Exception:
            break
        cc = d.get(typ, [])
        if not cc:
            break
        for c in cc:
            cols[c.get("handle")] = c
        page += 1

conn = sqlite3.connect("data/posts.db"); conn.row_factory = sqlite3.Row
prod = {r["handle"]: r for r in conn.execute("SELECT handle,title,body_html FROM haravan_products WHERE handle IS NOT NULL")}
blogc = {}
for r in conn.execute("SELECT article_url,blog_id,article_id FROM blog_rewrite_candidates WHERE article_url IS NOT NULL"):
    blogc[(r["article_url"] or "").rstrip("/")] = (r["blog_id"], r["article_id"])
conn.close()


def crawl_meta(url):
    try:
        h = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"}).text
        t = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
        md = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', h, re.I)
        if not md:
            md = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)', h, re.I)
        return (re.sub(r"\s+", " ", t.group(1)).strip() if t else ""), (md.group(1).strip() if md else "")
    except Exception as e:
        return "", "ERR:%s" % str(e)[:40]


def handle_of(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


records = []
for url in URLS:
    rec = {"url": url, "type": "", "entity_title": "", "body_html": "", "seo_title_live": "", "meta_des_live": ""}
    hd = handle_of(url)
    try:
        if "/pages/" in url and hd in pages:
            rec["type"] = "page"; rec["entity_title"] = pages[hd].get("title"); rec["body_html"] = pages[hd].get("body_html") or ""
        elif "/products/" in url and hd in prod:
            rec["type"] = "product"; rec["entity_title"] = prod[hd]["title"]; rec["body_html"] = prod[hd]["body_html"] or ""
        elif "/collections/" in url and hd in cols:
            rec["type"] = "collection"; rec["entity_title"] = cols[hd].get("title"); rec["body_html"] = cols[hd].get("body_html") or ""
        elif "/blogs/" in url:
            rec["type"] = "blog"
            bc = blogc.get(url.rstrip("/"))
            if bc:
                code, art = ap._fetch_live_article(bc[0], bc[1])
                if art:
                    rec["entity_title"] = art.get("title"); rec["body_html"] = art.get("body_html") or ""
        elif url.rstrip("/") in ("https://sintech.vn", "http://sintech.vn"):
            rec["type"] = "homepage"
        else:
            rec["type"] = "unknown"
    except Exception as e:
        rec["body_html"] = "FETCH_ERR:%s" % str(e)[:60]
    rec["seo_title_live"], rec["meta_des_live"] = crawl_meta(url)
    records.append(rec)
    time.sleep(0.2)

ts = time.strftime("%Y%m%d_%H%M%S")
outdir = Path("data") / ("_audit50_backup_%s" % ts)
outdir.mkdir(parents=True, exist_ok=True)
(outdir / "backup.json").write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
# readable summary
L = ["BACKUP 50 TRANG TOP TRAFFIC — %s\n" % ts]
for i, r in enumerate(records, 1):
    L.append("=" * 80)
    L.append("[%d] %s  (%s)" % (i, r["url"], r["type"]))
    L.append("  entity_title: %s" % r["entity_title"])
    L.append("  SEO title (live): %s" % r["seo_title_live"])
    L.append("  meta des (live): %s" % r["meta_des_live"])
    L.append("  body_html: %d ký tự" % len(r["body_html"]))
(outdir / "summary.txt").write_text("\n".join(L), encoding="utf-8")

okbody = sum(1 for r in records if r["body_html"] and not r["body_html"].startswith(("FETCH_ERR", "")))
print("Đã backup %d trang -> %s/" % (len(records), outdir))
print("  có body_html: %d · có meta des: %d · có SEO title: %d" % (
    sum(1 for r in records if len(r["body_html"]) > 10),
    sum(1 for r in records if r["meta_des_live"] and not r["meta_des_live"].startswith("ERR")),
    sum(1 for r in records if r["seo_title_live"])))
from collections import Counter
print("  theo loại:", dict(Counter(r["type"] for r in records)))
