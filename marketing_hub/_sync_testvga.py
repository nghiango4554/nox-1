# -*- coding: utf-8 -*-
"""Format chuẩn + sync bài 'Phần mềm test VGA' lên blog (1002792621), chèn 11 ảnh live cuối H2 khớp."""
import json, re, time, urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup
import blog_rewrite_apply as ap

BLOG_ID, ART_ID = 1000960873, 1002792621

S = {"h2": "font-size:17pt;font-weight:700;color:#000;margin:24px 0 5px;line-height:1.38;font-family:Arial,sans-serif",
     "h3": "font-size:13pt;font-weight:700;color:#000;margin:18px 0 4px;line-height:1.38;font-family:Arial,sans-serif",
     "p": "font-family:Arial,sans-serif;font-size:12pt;font-weight:500;line-height:1.65;margin:10px 0;color:#000",
     "li": "margin:6px 0;color:#000;font-size:12pt;font-weight:500;font-family:Arial,sans-serif;line-height:1.65",
     "strong": "color:#e74c3c;font-weight:700;text-decoration:underline"}
LINKSTYLE = "color:#e74c3c;font-weight:700;text-decoration:underline"

def _in_table(el):
    p = el.parent
    while p is not None:
        if getattr(p, "name", None) == "table":
            return True
        p = p.parent
    return False


soup = BeautifulSoup(Path("state/_testvga_clean.html").read_text(encoding="utf-8"), "lxml")
root = soup.body or soup

# 1. fix google links: decode -> clean; homepage/empty -> unwrap
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

# 2. bỏ escaped <a> (nếu có dạng text) — phòng hờ (xử lý sau khi serialize)
# 3. duyệt node: bỏ title + Mục lục, style h2/h3/p/li
nodes = list(root.children)
out = []
seen_title = False
skip = False
for n in nodes:
    name = getattr(n, "name", None)
    if name == "h2":
        ht = n.get_text().strip()
        if not seen_title and "Phần mềm test VGA và benchmark GPU dễ dùng" in ht:
            seen_title = True; continue
        if "Mục lục" in ht:
            skip = True; continue
        skip = False
        n["style"] = S["h2"]
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
# style li/strong + decorate bảng
for li in cont.find_all("li"):
    li["style"] = S["li"]
for st in cont.find_all("strong"):
    if not _in_table(st):
        st["style"] = S["strong"]
TBL = "border-collapse:collapse;width:100%;margin:18px 0;font-size:15px;border:1px solid #e2e8f0"
HEAD = "background:#1f3a5f;font-weight:700;padding:11px 13px;text-align:left;border:1px solid #1f3a5f;color:#ffffff"
TD = "padding:10px 13px;border:1px solid #e6eaf0;vertical-align:top;color:#222"
def _fw(el):
    s = re.sub(r"color\s*:\s*[^;]+;?", "", el.get("style") or "", flags=re.I).strip().rstrip(";")
    el["style"] = (s + ";" if s else "") + "color:#ffffff"
for t in cont.find_all("table"):
    t["style"] = TBL
    for ri, tr in enumerate(t.find_all("tr")):
        cells = tr.find_all(["td", "th"])
        if ri == 0:
            for c in cells:
                c["style"] = HEAD; _fw(c)
                for s2 in c.find_all(True): _fw(s2)
        else:
            bg = "#f4f7fb" if ri % 2 == 0 else "#ffffff"
            for c in cells: c["style"] = TD + ";background:" + bg
    par = t.parent
    if not (par and par.name == "div" and "overflow-x" in (par.get("style") or "")):
        t.wrap(soup.new_tag("div", style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin:18px 0;border-radius:8px"))

# 4. ảnh live + map -> H2 mới (keyword), chèn CUỐI section
code, art = ap._fetch_live_article(BLOG_ID, ART_ID)
lb = art.get("body_html") or ""
# (src, keyword H2 đích) ; hero=None -> top
imgs = []
parts = re.split(r"(<h[1-6][^>]*>.*?</h[1-6]>)", lb, flags=re.I | re.S)
cur = None
for seg in parts:
    if re.match(r"<h[1-6]", seg or "", re.I):
        cur = re.sub("<[^>]+>", " ", seg).strip()
    for mm in re.findall(r'<img[^>]+src="([^"]+)"', seg or ""):
        imgs.append((mm, cur))
KEYMAP = [("FurMark", "FurMark"), ("Kombustor", "FurMark"), ("3DMark", "3DMark"), ("OCCT", "OCCT"),
          ("Unigine", "Unigine"), ("GPU‑Z", "GPU-Z"), ("GPU-Z", "GPU-Z"), ("GPUMemTest", "GPUMemTest"),
          ("AIDA64", "AIDA64"), ("HWiNFO", "GPU-Z"), ("Afterburner", "Afterburner")]
def target_kw(live_h):
    if not live_h:
        return None
    for k, dest in KEYMAP:
        if k.lower() in live_h.lower():
            return dest
    return None

h2list = cont.find_all("h2")
def imgtag(src):
    p = soup.new_tag("p"); p["style"] = "text-align:center;margin:14px 0"
    i = soup.new_tag("img"); i["src"] = src; i["alt"] = "Minh hoạ phần mềm test VGA"
    i["style"] = "max-width:100%;height:auto;border-radius:8px"
    p.append(i); return p
# section-end map: H2 -> list ảnh chèn cuối
pending = {}
hero = imgs[0][0] if imgs else None
for src, lh in imgs[1:]:
    dest = target_kw(lh)
    if not dest:
        continue
    h = next((x for x in h2list if dest.lower() in x.get_text().lower()), None)
    if h:
        pending.setdefault(id(h), (h, []))[1].append(src)
# chèn ảnh ở CUỐI mỗi section (ngay trước H2 kế)
for hid, (h, srcs) in pending.items():
    nxt = h.find_next_sibling("h2")
    block = [imgtag(s) for s in srcs]
    if nxt:
        for b in block: nxt.insert_before(b)
    else:
        for b in block: cont.append(b)

body_html = "".join(str(x) for x in cont.contents).strip()
# escaped <a> dạng text (phòng hờ) + Paste + đoạn rỗng
body_html = re.sub(r"&lt;/?a\b[^&]*&gt;", "", body_html)
body_html = re.sub(r"^\s*(<p[^>]*>\s*)?Paste\s*", lambda m: (m.group(1) or ""), body_html)
hero_html = ('<p style="text-align:center;margin:16px 0"><img src="%s" alt="Phần mềm test VGA" style="max-width:100%%;height:auto;border-radius:8px"></p>' % hero) if hero else ""
final = hero_html + body_html
final = re.sub(r"^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+", "", final)

# 5. backup + sync blog (body-only)
Path("data/_testvga_OLD_backup_%s.html" % time.strftime("%Y%m%d_%H%M%S")).write_text(lb, encoding="utf-8")
status, _ = ap._put_article(BLOG_ID, ART_ID, {"id": ART_ID, "body_html": final})
print("PUT blog HTTP", status)
time.sleep(1)
code2, v = ap._fetch_live_article(BLOG_ID, ART_ID)
vb = v.get("body_html") or ""
print("LIVE: %d ký tự · %d ảnh · %d bảng · h2-styled=%d · link đỏ=%d · escaped=%d · title: %s" %
      (len(vb), vb.count("<img"), vb.count("<table"), vb.count("font-size:17pt"),
       vb.count("#e74c3c"), vb.count("&lt;a"), v.get("title")[:40]))
