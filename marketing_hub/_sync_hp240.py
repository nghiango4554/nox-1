# -*- coding: utf-8 -*-
"""Format + sync mô tả product HP 240 G8 (id 1074894236). Product font + giữ 3 ảnh body + link."""
import re, time, urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup
import haravan_client as hc

PID = 1074894236
S = {"h2": "font-size:17pt;font-weight:700;color:#000;margin:22px 0 5px;line-height:1.38;font-family:Arial,sans-serif",
     "h3": "font-size:12pt;font-weight:700;color:#000;margin:16px 0 4px;line-height:1.38;font-family:Arial,sans-serif",
     "p": "font-family:Arial,sans-serif;font-size:11pt;font-weight:500;line-height:1.65;margin:10px 0;color:#000",
     "li": "margin:6px 0;color:#000;font-size:11pt;font-weight:500;font-family:Arial,sans-serif;line-height:1.65"}
LK = "color:#e74c3c;font-weight:700;text-decoration:underline"


def in_table(el):
    p = el.parent
    while p:
        if getattr(p, "name", None) == "table":
            return True
        p = p.parent
    return False


# ảnh body cũ
prod = hc._request("GET", "/products/%d.json" % PID)["product"]
old = prod.get("body_html") or ""
Path("data/_hp240_OLD_backup_%s.html" % time.strftime("%Y%m%d_%H%M%S")).write_text(old, encoding="utf-8")
imgs = re.findall(r'<img[^>]+src="([^"]+)"', old)

soup = BeautifulSoup(Path("state/_doc_current.html").read_text(encoding="utf-8"), "lxml")
root = soup.body or soup
for a in root.find_all("a"):
    href = a.get("href") or ""
    m = re.search(r"[?&]q=([^&]+)", href)
    real = urllib.parse.unquote(m.group(1)) if m else href
    path = re.sub(r"^https?://[^/]+", "", real)
    txt = a.get_text().strip()
    if not txt:
        a.unwrap(); continue
    a["href"] = (path if path and path != "/" else "https://sintech.vn"); a["style"] = LK
    for x in list(a.attrs):
        if x not in ("href", "style"):
            del a[x]

out, seen, skip = [], False, False
for n in list(root.children):
    nm = getattr(n, "name", None)
    if nm == "h2":
        ht = n.get_text().strip()
        if not seen and "Laptop HP 240 G8 Notebook PC i3-1005G1 cũ" in ht:
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

def imgtag(src):
    p = soup.new_tag("p"); p["style"] = "text-align:center;margin:14px 0"
    i = soup.new_tag("img"); i["src"] = src; i["alt"] = "Laptop HP 240 G8 i3-1005G1 cũ"
    i["style"] = "max-width:600px;width:100%;height:auto;border-radius:8px"
    p.append(i); return p

# ảnh 2,3 -> cuối section "Cấu hình", "Màn hình"
h2s = cont.find_all("h2")
imgmap = [("Cấu hình", imgs[1] if len(imgs) > 1 else None), ("Màn hình", imgs[2] if len(imgs) > 2 else None)]
for kw, src in imgmap:
    if not src:
        continue
    h = next((x for x in h2s if kw.lower() in x.get_text().lower()), None)
    if h:
        nxt = h.find_next_sibling("h2")
        (nxt.insert_before(imgtag(src)) if nxt else cont.append(imgtag(src)))

body_html = "".join(str(x) for x in cont.contents).strip()
body_html = re.sub(r"&lt;/?a\b[^&]*&gt;", "", body_html)
# hero (ảnh 1) dưới intro
hero = ("<p style=\"text-align:center;margin:16px 0\"><img src=\"%s\" alt=\"Laptop HP 240 G8 i3-1005G1 cũ\" style=\"max-width:600px;width:100%%;height:auto;border-radius:8px\"></p>" % imgs[0]) if imgs else ""
m = re.search(r"(</p>)", body_html)
body_html = (body_html[:m.end()] + hero + body_html[m.end():]) if (hero and m) else (hero + body_html)
body_html = re.sub(r"^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+", "", body_html)

top = '<p style="%s">Laptop HP 240 G8 i3-1005G1 cũ đang có tại <a href="https://sintech.vn" style="%s">Sintech</a> — máy đã kiểm tra kỹ, phù hợp văn phòng, học tập, giá tốt.</p>' % (S["p"], LK)
bot = '<p style="%s">Liên hệ <a href="https://sintech.vn" style="%s">Sintech</a> để kiểm tra máy và tư vấn trước khi mua. Hotline 0911 713 000 · 457 Trần Xuân Soạn, Q7, TP.HCM.</p>' % (S["p"], LK)
final = top + body_html + bot

res = hc._request("PUT", "/products/%d.json" % PID, payload={"product": {"id": PID, "body_html": final}})
print("PUT product · title giữ:", res.get("product", {}).get("title"))
time.sleep(1)
v = hc._request("GET", "/products/%d.json" % PID)["product"]
vb = v.get("body_html") or ""
print("LIVE: %d ảnh body · %d bảng · h2 17pt=%d · link đỏ=%d · internal=%d · gallery=%d" %
      (vb.count("<img"), vb.count("<table"), vb.count("font-size:17pt"), vb.count("#e74c3c"),
       len(re.findall(r'href="/collections/', vb)), len(v.get("images", []))))
