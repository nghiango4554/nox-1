# -*- coding: utf-8 -*-
"""Format + sync bài 'Tối ưu card NVIDIA' lên blog (1002431245). Fix link host chatgpt->sintech."""
import re, time, urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup
import blog_rewrite_apply as ap

BLOG_ID, ART_ID = 1000906526, 1002431245
S = {"h2": "font-size:17pt;font-weight:700;color:#000;margin:24px 0 5px;line-height:1.38;font-family:Arial,sans-serif",
     "h3": "font-size:13pt;font-weight:700;color:#000;margin:18px 0 4px;line-height:1.38;font-family:Arial,sans-serif",
     "p": "font-family:Arial,sans-serif;font-size:12pt;font-weight:500;line-height:1.65;margin:10px 0;color:#000",
     "li": "margin:6px 0;color:#000;font-size:12pt;font-weight:500;font-family:Arial,sans-serif;line-height:1.65"}
LK = "color:#e74c3c;font-weight:700;text-decoration:underline"
FIX404 = {"/collections/nvidia": "/collections/vga-card-man-hinh"}


def in_table(el):
    p = el.parent
    while p:
        if getattr(p, "name", None) == "table":
            return True
        p = p.parent
    return False


soup = BeautifulSoup(Path("state/_doc_current.html").read_text(encoding="utf-8"), "lxml")
root = soup.body or soup

# fix link: decode q= -> path (bỏ host chatgpt/sintech) -> relative; empty -> unwrap
for a in root.find_all("a"):
    href = a.get("href") or ""
    m = re.search(r"[?&]q=([^&]+)", href)
    real = urllib.parse.unquote(m.group(1)) if m else href
    path = re.sub(r"^https?://[^/]+", "", real)
    txt = a.get_text().strip()
    if not txt:
        a.unwrap(); continue
    if not path or path == "/":
        path = "https://sintech.vn"
    path = FIX404.get(path.rstrip("/"), path)
    a["href"] = path; a["style"] = LK
    for x in list(a.attrs):
        if x not in ("href", "style"):
            del a[x]

# bỏ title H2 + style
out, seen, skip = [], False, False
for n in list(root.children):
    nm = getattr(n, "name", None)
    if nm == "h2":
        ht = n.get_text().strip()
        if not seen and "Tối ưu card NVIDIA để chơi game mượt hơn" in ht:
            seen = True; continue
        if "Mục lục" in ht:
            skip = True; continue
        skip = False; n["style"] = S["h2"]
    elif nm == "h3" and not skip:
        n["style"] = S["h3"]
    elif nm == "p" and not skip and (not n.has_attr("style") or "font-size" not in (n.get("style") or "")):
        n["style"] = S["p"]
    if skip:
        continue
    out.append(n)

cont = soup.new_tag("div")
for n in out:
    cont.append(n)
for li in cont.find_all("li"):
    li["style"] = S["li"]
for st in cont.find_all("strong"):
    if not in_table(st):
        st["style"] = LK

TBL = "border-collapse:collapse;width:100%;margin:18px 0;font-size:15px;border:1px solid #e2e8f0"
HEAD = "background:#1f3a5f;font-weight:700;padding:11px 13px;text-align:left;border:1px solid #1f3a5f;color:#ffffff"
TD = "padding:10px 13px;border:1px solid #e6eaf0;vertical-align:top;color:#222"
def fw(el):
    s = re.sub(r"color\s*:\s*[^;]+;?", "", el.get("style") or "", flags=re.I).strip().rstrip(";")
    el["style"] = (s + ";" if s else "") + "color:#ffffff"
for t in cont.find_all("table"):
    t["style"] = TBL
    for ri, tr in enumerate(t.find_all("tr")):
        cells = tr.find_all(["td", "th"])
        if ri == 0:
            for c in cells:
                c["style"] = HEAD; fw(c)
                for s2 in c.find_all(True): fw(s2)
        else:
            bg = "#f4f7fb" if ri % 2 == 0 else "#ffffff"
            for c in cells: c["style"] = TD + ";background:" + bg
    par = t.parent
    if not (par and par.name == "div" and "overflow-x" in (par.get("style") or "")):
        t.wrap(soup.new_tag("div", style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin:18px 0;border-radius:8px"))

body_html = "".join(str(x) for x in cont.contents).strip()
body_html = re.sub(r"&lt;/?a\b[^&]*&gt;", "", body_html)
body_html = re.sub(r"^\s*(<p[^>]*>\s*)?Paste\s*", lambda m: (m.group(1) or ""), body_html)
body_html = re.sub(r"^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+", "", body_html)

top = '<p style="%s"><a href="https://sintech.vn" style="%s">Sintech</a> chia sẻ cách tối ưu card NVIDIA để chơi game mượt hơn, áp dụng được cho cả PC và laptop gaming.</p>' % (S["p"], LK)
bot = '<p style="%s">Cần tư vấn nâng cấp hoặc kiểm tra VGA, liên hệ <a href="https://sintech.vn" style="%s">Sintech</a> — Hotline 0911 713 000 · 457 Trần Xuân Soạn, Q7, TP.HCM.</p>' % (S["p"], LK)
final = top + body_html + bot

code, art = ap._fetch_live_article(BLOG_ID, ART_ID)
Path("data/_nvidia_OLD_backup_%s.html" % time.strftime("%Y%m%d_%H%M%S")).write_text(art.get("body_html") or "", encoding="utf-8")
status, _ = ap._put_article(BLOG_ID, ART_ID, {"id": ART_ID, "body_html": final})
print("PUT blog HTTP", status)
time.sleep(1)
c2, v = ap._fetch_live_article(BLOG_ID, ART_ID)
vb = v.get("body_html") or ""
internal = len(re.findall(r'href="/(collections|pages)/', vb))
print("LIVE: %d ký tự · %d bảng · h2-styled=%d · link đỏ=%d · internal collection/page=%d · chatgpt=%d · escaped=%d · title: %s" %
      (len(vb), vb.count("<table"), vb.count("font-size:17pt"), vb.count("#e74c3c"), internal,
       vb.count("chatgpt.com"), vb.count("&lt;a"), v.get("title")[:38]))
