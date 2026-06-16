# -*- coding: utf-8 -*-
"""Sync bài build cải thiện (collection_jobs id=1) lên page xay-dung-cau-hinh + chèn 9 ảnh cũ. Rồi restore DB pc-gaming."""
import json, re, sqlite3, time, unicodedata
from pathlib import Path
from bs4 import BeautifulSoup
import requests

PAGE_ID = 1003590100
CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
TOK = CFG.get("access_token") or CFG.get("blog_access_token")
H = {"Authorization": "Bearer %s" % TOK, "Content-Type": "application/json"}


def words(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    stop = {"build", "pc", "online", "va", "cho", "la", "gi", "khi", "nao", "co", "the",
            "khong", "can", "nen", "cua", "den", "tai", "theo", "trong", "o", "dau"}
    return set(w for w in re.findall(r"[a-z0-9]+", s) if len(w) > 1 and w not in stop)


# 1. nội dung cải thiện
conn = sqlite3.connect("data/posts.db")
content = conn.execute("SELECT edited_body_html FROM collection_jobs WHERE id=1").fetchone()[0]

# 2. 9 ảnh cũ (url + heading) từ body backup trang
old = Path("data/_build_page_body_backup.html").read_text(encoding="utf-8")
parts = re.split(r"(<h[1-6][^>]*>.*?</h[1-6]>)", old, flags=re.I | re.S)
cur = "(đầu trang)"
imgs = []
for seg in parts:
    if re.match(r"<h[1-6]", seg or "", re.I):
        cur = re.sub("<[^>]+>", " ", seg).strip()
    for m in re.findall(r'<img[^>]+src="([^"]+)"', seg or ""):
        imgs.append({"src": m, "old_h": cur})

# 3. match mỗi ảnh -> H2 mới gần nghĩa nhất
soup = BeautifulSoup(content, "lxml")
h2s = soup.find_all("h2")
hero = imgs[0]  # ảnh đầu = hero -> top
rest = imgs[1:]
used = set()
plan = []  # (h2_element, img_src, alt)
for im in rest:
    ow = words(im["old_h"])
    best, bestscore = None, -1
    for h in h2s:
        if id(h) in used:
            continue
        sc = len(ow & words(h.get_text()))
        if sc > bestscore:
            best, bestscore = h, sc
    if best is not None and bestscore > 0:
        used.add(id(best))
        plan.append((best, im["src"], im["old_h"]))

def imgtag(src, alt):
    p = soup.new_tag("p"); p["style"] = "text-align:center;margin:16px 0"
    i = soup.new_tag("img"); i["src"] = src; i["alt"] = alt[:80]
    i["style"] = "max-width:100%;height:auto;border-radius:8px"
    p.append(i); return p

# chèn ảnh ngay sau heading match
for h, src, alt in plan:
    h.insert_after(imgtag(src, alt))
# hero chèn đầu body
body = soup.body or soup
first = body.find(True)
if first:
    first.insert_before(imgtag(hero["src"], hero["old_h"]))

new_body = "".join(str(x) for x in (body.contents if body else [soup])).strip()
print("Đã chèn hero + %d ảnh khớp heading (tổng %d/9)" % (len(plan), len(plan) + 1))
for h, src, alt in plan:
    print("   [%s] -> H2: %s" % (alt[:32], h.get_text().strip()[:40]))

# 4. PUT page (Open API)
r = requests.put("https://apis.haravan.com/web/pages/%d.json" % PAGE_ID, headers=H,
                 data=json.dumps({"page": {"id": PAGE_ID, "body_html": new_body}}), timeout=60)
print("PUT page HTTP", r.status_code)
time.sleep(1)
v = requests.get("https://apis.haravan.com/web/pages/%d.json" % PAGE_ID, headers={"Authorization": H["Authorization"]}, timeout=30)
lb = v.json().get("page", {}).get("body_html", "") if v.status_code == 200 else ""
print("LIVE page sau sync: %d ký tự · %d ảnh · %d bảng · title giữ: %s" %
      (len(lb), lb.count("<img"), lb.count("<table"), v.json().get("page", {}).get("title")))

# 5. restore DB pc-gaming (trả collection_jobs id=1 về như cũ)
bks = sorted(Path("data").glob("_pcgaming_DBbackup_*.html"))
if bks:
    good = bks[-1].read_text(encoding="utf-8")
    conn.execute("UPDATE collection_jobs SET edited_body_html=?, updated_at=datetime('now') WHERE id=1", (good,))
    conn.commit()
    print("Đã RESTORE DB pc-gaming (collection_jobs id=1) từ %s (%d ký tự)" % (bks[-1].name, len(good)))
conn.close()
