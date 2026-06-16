# -*- coding: utf-8 -*-
"""Format + sync bài thu mua linh kiện cũ lên page thuamualinhkiencu: gỡ Mục lục, decorate bảng, giữ ảnh hero."""
import json, re, time
from pathlib import Path
from bs4 import BeautifulSoup
import requests

PAGE_ID = 1003609040
CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
TOK = CFG.get("access_token") or CFG.get("blog_access_token")
H = {"Authorization": "Bearer %s" % TOK, "Content-Type": "application/json"}

soup = BeautifulSoup(Path("state/_thumua_clean.html").read_text(encoding="utf-8"), "lxml")
root = soup.body or soup

# 1. gỡ H2 tiêu đề đầu + section "Mục lục nhanh" (H2 + các phần tử tới H2 kế)
nodes = list(root.children)
out = []
skip_until_h2 = False
seen_title = False
for n in nodes:
    name = getattr(n, "name", None)
    if name == "h2":
        ht = n.get_text().strip()
        if not seen_title and "Bảng giá thu mua linh kiện máy tính cũ tại TP" in ht:
            seen_title = True
            continue  # bỏ tiêu đề
        if "Mục lục" in ht:
            skip_until_h2 = True
            continue  # bỏ heading mục lục + nội dung sau
        skip_until_h2 = False
    if skip_until_h2:
        continue
    out.append(n)

# 2. decorate bảng (header tối + chữ trắng cả thẻ con + zebra + wrapper)
TBL = "border-collapse:collapse;width:100%;margin:18px 0;font-size:15px;border:1px solid #e2e8f0"
HEAD = "background:#1f3a5f;font-weight:700;padding:11px 13px;text-align:left;border:1px solid #1f3a5f;color:#ffffff"
TD = "padding:10px 13px;border:1px solid #e6eaf0;vertical-align:top;color:#222"
EVEN = "#f4f7fb"

def force_white(el):
    st = re.sub(r"color\s*:\s*[^;]+;?", "", el.get("style") or "", flags=re.I).strip().rstrip(";")
    el["style"] = (st + ";" if st else "") + "color:#ffffff"

container = soup.new_tag("div")
for n in out:
    container.append(n)
for t in container.find_all("table"):
    t["style"] = TBL
    rows = t.find_all("tr")
    for ri, tr in enumerate(rows):
        cells = tr.find_all(["td", "th"])
        if ri == 0:
            for cell in cells:
                cell["style"] = HEAD
                force_white(cell)
                for sub in cell.find_all(True):
                    force_white(sub)
        else:
            bg = EVEN if ri % 2 == 0 else "#ffffff"
            for cell in cells:
                cell["style"] = TD + ";background:" + bg
    par = t.parent
    if not (par and par.name == "div" and "overflow-x" in (par.get("style") or "")):
        wrap = soup.new_tag("div", style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin:18px 0;border-radius:8px")
        t.wrap(wrap)

body_html = "".join(str(x) for x in container.contents).strip()

# 3. ảnh hero từ live page
live = requests.get("https://apis.haravan.com/web/pages/%d.json" % PAGE_ID,
                    headers={"Authorization": H["Authorization"]}, timeout=30).json()["page"]
Path("data/_thumua_page_body_backup.html").write_text(live.get("body_html") or "", encoding="utf-8")
hero = re.findall(r'<img[^>]+src="([^"]+)"', live.get("body_html") or "")
hero_html = ""
if hero:
    hero_html = ('<p style="text-align:center;margin:16px 0"><img src="%s" alt="Bảng giá thu mua linh kiện máy tính cũ tại Sintech" '
                 'style="max-width:100%%;height:auto;border-radius:8px"></p>' % hero[0])

# 4. ráp: hero + content; dọn 'Paste' + đoạn rỗng đầu
body_html = re.sub(r'^\s*(<p[^>]*>\s*)?Paste\s*', lambda m: (m.group(1) or ""), body_html)
final = hero_html + body_html
final = re.sub(r'^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+', '', final)

# 5. PUT page
pr = requests.put("https://apis.haravan.com/web/pages/%d.json" % PAGE_ID, headers=H,
                  data=json.dumps({"page": {"id": PAGE_ID, "body_html": final}}), timeout=60)
print("PUT page HTTP", pr.status_code)
time.sleep(1)
v = requests.get("https://apis.haravan.com/web/pages/%d.json" % PAGE_ID,
                 headers={"Authorization": H["Authorization"]}, timeout=30).json()["page"]
vb = v.get("body_html") or ""
print("LIVE: %d ký tự · %d ảnh · %d bảng · còn Mục lục: %s · title: %s" %
      (len(vb), vb.count("<img"), vb.count("<table"), "Mục lục" in vb, v.get("title")))
print("intro:", re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", vb)).strip()[:70])
