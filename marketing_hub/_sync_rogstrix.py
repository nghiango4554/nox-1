# -*- coding: utf-8 -*-
"""Format + sync mô tả product ROG Strix G15 (id 1074894155). Body-only, giữ gallery/title/giá."""
import re, time, urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup
import haravan_client as hc

PID = 1074894155
S = {"h2": "font-size:17pt;font-weight:700;color:#000;margin:24px 0 5px;line-height:1.38;font-family:Arial,sans-serif",
     "h3": "font-size:13pt;font-weight:700;color:#000;margin:18px 0 4px;line-height:1.38;font-family:Arial,sans-serif",
     "p": "font-family:Arial,sans-serif;font-size:12pt;font-weight:500;line-height:1.65;margin:10px 0;color:#000",
     "li": "margin:6px 0;color:#000;font-size:12pt;font-weight:500;font-family:Arial,sans-serif;line-height:1.65"}
LINKSTYLE = "color:#e74c3c;font-weight:700;text-decoration:underline"


def in_table(el):
    p = el.parent
    while p:
        if getattr(p, "name", None) == "table":
            return True
        p = p.parent
    return False


# live product: backup + ảnh body cũ
prod = hc._request("GET", "/products/%d.json" % PID)["product"]
old = prod.get("body_html") or ""
Path("data/_rogstrix_OLD_backup_%s.html" % time.strftime("%Y%m%d_%H%M%S")).write_text(old, encoding="utf-8")
old_imgs = re.findall(r'<img[^>]+src="([^"]+)"', old)

soup = BeautifulSoup(Path("state/_rogstrix_clean.html").read_text(encoding="utf-8"), "lxml")
root = soup.body or soup

# fix links
for a in root.find_all("a"):
    href = a.get("href") or ""
    m = re.search(r"[?&]q=([^&]+)", href)
    real = urllib.parse.unquote(m.group(1)) if m else href
    txt = a.get_text().strip()
    if (not real) or real.rstrip("/") in ("https://sintech.vn", "http://sintech.vn") or not txt:
        a.unwrap()
    else:
        a["href"] = real; a["style"] = LINKSTYLE
        for x in list(a.attrs):
            if x not in ("href", "style"):
                del a[x]

# bỏ title H2 + Mục lục, style
out, seen_title, skip = [], False, False
for n in list(root.children):
    name = getattr(n, "name", None)
    if name == "h2":
        ht = n.get_text().strip()
        if not seen_title and "Laptop ASUS ROG Strix G15 G513IM-HN008W cũ" in ht:
            seen_title = True; continue
        if "Mục lục" in ht:
            skip = True; continue
        skip = False; n["style"] = S["h2"]
    elif name == "h3" and not skip:
        n["style"] = S["h3"]
    elif name == "p" and not skip and (not n.has_attr("style") or "font-size" not in (n.get("style") or "")):
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
        st["style"] = LINKSTYLE
# decorate bảng
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

# thêm internal link (đỏ đậm gạch chân) — cross-sell ở cuối section "Phù hợp với ai?" hoặc "Có nên mua"
LINKS = [("/collections/laptop-gaming", "laptop gaming"),
         ("/collections/laptop-asus", "laptop ASUS"),
         ("/collections/laptop-cu", "laptop cũ giá tốt")]
anchor_h2 = None
for h in cont.find_all("h2"):
    if "Có nên mua" in h.get_text() or "Phù hợp với ai" in h.get_text():
        anchor_h2 = h; break
if anchor_h2 is not None:
    lp = soup.new_tag("p"); lp["style"] = S["p"]
    lp.append("Bạn có thể tham khảo thêm các dòng ")
    for i, (url, txt) in enumerate(LINKS):
        a = soup.new_tag("a", href=url); a.string = txt; a["style"] = LINKSTYLE
        lp.append(a)
        lp.append(", " if i < len(LINKS) - 2 else (" và " if i == len(LINKS) - 2 else " khác tại Sintech."))
    nxt = anchor_h2.find_next_sibling("h2")
    if nxt:
        nxt.insert_before(lp)
    else:
        cont.append(lp)

body_html = "".join(str(x) for x in cont.contents).strip()
body_html = re.sub(r"&lt;/?a\b[^&]*&gt;", "", body_html)
body_html = re.sub(r"^\s*(<p[^>]*>\s*)?Paste\s*", lambda m: (m.group(1) or ""), body_html)

# ảnh body cũ (nếu có) -> hero DƯỚI intro
hero_html = ""
if old_imgs:
    hero_html = ('<p style="text-align:center;margin:16px 0"><img src="%s" alt="Laptop ASUS ROG Strix G15 G513IM-HN008W cũ" style="max-width:100%%;height:auto;border-radius:8px"></p>' % old_imgs[0])

# chèn hero sau đoạn intro đầu
m = re.search(r"(</p>)", body_html)
if hero_html and m:
    body_html = body_html[:m.end()] + hero_html + body_html[m.end():]
elif hero_html:
    body_html = hero_html + body_html
body_html = re.sub(r"^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+", "", body_html)

# PUT body-only
res = hc._request("PUT", "/products/%d.json" % PID, payload={"product": {"id": PID, "body_html": body_html}})
np = res.get("product", {})
print("PUT product OK · title giữ: %s" % np.get("title"))
time.sleep(1)
v = hc._request("GET", "/products/%d.json" % PID)["product"]
vb = v.get("body_html") or ""
print("LIVE body: %d ký tự · %d ảnh body · %d bảng · h2-styled=%d · link đỏ=%d · escaped=%d · gallery ảnh giữ=%d" %
      (len(vb), vb.count("<img"), vb.count("<table"), vb.count("font-size:17pt"),
       vb.count("#e74c3c"), vb.count("&lt;a"), len(v.get("images", []))))
