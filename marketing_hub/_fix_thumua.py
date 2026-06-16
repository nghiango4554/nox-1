# -*- coding: utf-8 -*-
"""Fix bài thu mua: style heading/text + gỡ link google hỏng + thêm internal link nhóm SP + decorate bảng + hero."""
import json, re, time
from pathlib import Path
from bs4 import BeautifulSoup
import requests

PAGE_ID = 1003609040
CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
TOK = CFG.get("access_token") or CFG.get("blog_access_token")
H = {"Authorization": "Bearer %s" % TOK, "Content-Type": "application/json"}

H2S = "font-size:17pt;font-weight:700;color:#000;margin:24px 0 6px;line-height:1.38"
H3S = "font-size:13.5pt;font-weight:700;color:#000;margin:18px 0 4px;line-height:1.4"
PS = "font-size:12pt;line-height:1.65;margin:10px 0;color:#222"

# map section price -> (collection url, anchor text)
LINKS = {
    "VGA cũ": ("/collections/vga", "VGA mới"),
    "Mainboard cũ": ("/collections/mainboard", "Mainboard mới"),
    "RAM cũ": ("/collections/ram", "RAM mới"),
    "CPU cũ": ("/collections/cpu", "CPU mới"),
    "màn hình cũ": ("/collections/man-hinh-may-tinh", "màn hình mới"),
    "nguồn PC cũ": ("/collections/nguon", "nguồn máy tính mới"),
}

soup = BeautifulSoup(Path("state/_thumua_clean.html").read_text(encoding="utf-8"), "lxml")
root = soup.body or soup

# gỡ <a> google-wrapper / empty (giữ text)
for a in root.find_all("a"):
    href = a.get("href") or ""
    if (not href) or "google.com/url" in href or href.strip() in ("https://sintech.vn", "https://sintech.vn/"):
        a.unwrap()

# duyệt: bỏ title + Mục lục, gắn style, chèn internal link cuối mỗi section price
nodes = list(root.children)
final = []
skip = False
seen_title = False
pending_link = None
for n in nodes:
    name = getattr(n, "name", None)
    if name == "h2":
        ht = n.get_text().strip()
        # đóng section trước: chèn link nếu có
        if pending_link is not None:
            final.append(pending_link); pending_link = None
        if not seen_title and "Bảng giá thu mua linh kiện máy tính cũ tại TP" in ht:
            seen_title = True; continue
        if "Mục lục" in ht:
            skip = True; continue
        skip = False
        n["style"] = H2S
        # nếu là section bảng giá -> chuẩn bị link nhóm
        for key, (url, txt) in LINKS.items():
            if key in ht:
                p = soup.new_tag("p"); p["style"] = PS
                p.append("Bạn cũng có thể tham khảo giá ")
                a = soup.new_tag("a", href=url); a.string = txt
                a["style"] = "color:#1a5fb4;text-decoration:underline"
                p.append(a); p.append(" tại Sintech để so sánh với giá thu cũ.")
                pending_link = p
                break
    elif name == "h3":
        if skip: continue
        n["style"] = H3S
    elif name == "p":
        if skip: continue
        if not n.has_attr("style") or "font-size" not in (n.get("style") or ""):
            n["style"] = PS
    if skip:
        continue
    final.append(n)
if pending_link is not None:
    final.append(pending_link)

# decorate bảng
TBL = "border-collapse:collapse;width:100%;margin:18px 0;font-size:15px;border:1px solid #e2e8f0"
HEAD = "background:#1f3a5f;font-weight:700;padding:11px 13px;text-align:left;border:1px solid #1f3a5f;color:#ffffff"
TD = "padding:10px 13px;border:1px solid #e6eaf0;vertical-align:top;color:#222"

def fw(el):
    st = re.sub(r"color\s*:\s*[^;]+;?", "", el.get("style") or "", flags=re.I).strip().rstrip(";")
    el["style"] = (st + ";" if st else "") + "color:#ffffff"

cont = soup.new_tag("div")
for n in final:
    cont.append(n)
for t in cont.find_all("table"):
    t["style"] = TBL
    for ri, tr in enumerate(t.find_all("tr")):
        cells = tr.find_all(["td", "th"])
        if ri == 0:
            for c in cells:
                c["style"] = HEAD; fw(c)
                for s in c.find_all(True): fw(s)
        else:
            bg = "#f4f7fb" if ri % 2 == 0 else "#ffffff"
            for c in cells: c["style"] = TD + ";background:" + bg
    par = t.parent
    if not (par and par.name == "div" and "overflow-x" in (par.get("style") or "")):
        t.wrap(soup.new_tag("div", style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin:18px 0;border-radius:8px"))

body_html = "".join(str(x) for x in cont.contents).strip()

# hero từ backup trang
old = Path("data/_thumua_page_body_backup.html").read_text(encoding="utf-8")
hero = re.findall(r'<img[^>]+src="([^"]+)"', old)
hero_html = ('<p style="text-align:center;margin:16px 0"><img src="%s" alt="Bảng giá thu mua linh kiện máy tính cũ tại Sintech" style="max-width:100%%;height:auto;border-radius:8px"></p>' % hero[0]) if hero else ""

body_html = re.sub(r'^\s*(<p[^>]*>\s*)?Paste\s*', lambda m: (m.group(1) or ""), body_html)
final_html = hero_html + body_html
final_html = re.sub(r'^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+', '', final_html)

pr = requests.put("https://apis.haravan.com/web/pages/%d.json" % PAGE_ID, headers=H,
                  data=json.dumps({"page": {"id": PAGE_ID, "body_html": final_html}}), timeout=60)
print("PUT HTTP", pr.status_code)
time.sleep(1)
v = requests.get("https://apis.haravan.com/web/pages/%d.json" % PAGE_ID, headers={"Authorization": H["Authorization"]}, timeout=30).json()["page"]["body_html"]
internal = len(re.findall(r'href="/collections/', v))
print("LIVE: %d ký tự · h2-styled=%d · %d ảnh · %d bảng · internal link nhóm=%d · google-link=%d" %
      (len(v), v.count("font-size:17pt"), v.count("<img"), v.count("<table"), internal, v.count("google.com/url")))
