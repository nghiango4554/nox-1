# -*- coding: utf-8 -*-
"""3 bài: product Mini PC NUC + collection PC AI Workstation (smart) + product HDD Toshiba.
Format chuẩn, giữ ảnh (giàn đều), body-only, KHÔNG top/bot. Collection KHÔNG đụng title/meta."""
import re, time, urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup
import haravan_client as hc

DOC = Path("state/_doc_current.html").read_text(encoding="utf-8")
LK = "color:#e74c3c;font-weight:700;text-decoration:underline"
BLOG_S = {"h2": "font-size:17pt;font-weight:700;color:#000;margin:24px 0 5px;line-height:1.38;font-family:Arial,sans-serif",
          "h3": "font-size:13pt;font-weight:700;color:#000;margin:18px 0 4px;line-height:1.38;font-family:Arial,sans-serif",
          "p": "font-family:Arial,sans-serif;font-size:12pt;font-weight:500;line-height:1.65;margin:10px 0;color:#000",
          "li": "margin:6px 0;color:#000;font-size:12pt;font-weight:500;font-family:Arial,sans-serif;line-height:1.65"}
PROD_S = {"h2": "font-size:17pt;font-weight:700;color:#000;margin:22px 0 5px;line-height:1.38;font-family:Arial,sans-serif",
          "h3": "font-size:12pt;font-weight:700;color:#000;margin:16px 0 4px;line-height:1.38;font-family:Arial,sans-serif",
          "p": "font-family:Arial,sans-serif;font-size:11pt;font-weight:500;line-height:1.65;margin:10px 0;color:#000",
          "li": "margin:6px 0;color:#000;font-size:11pt;font-weight:500;font-family:Arial,sans-serif;line-height:1.65"}

# (kind, id, title, next_title, alt, font)
ARTS = [
    ("product", 1062537121, "Mini PC Intel NUC 10 BXNUC10I5FNH2 i5-10210U",
     "PC AI Workstation cho Local AI và Deep Learning", "Mini PC Intel NUC 10 BXNUC10I5FNH2", PROD_S),
    ("smart", 1004683611, "PC AI Workstation cho Local AI và Deep Learning",
     "Ổ cứng HDD Toshiba MQ01ABF050 500GB SATA III", "PC AI Workstation", BLOG_S),
    ("product", 1053655520, "Ổ cứng HDD Toshiba MQ01ABF050 500GB SATA III",
     None, "Ổ cứng HDD Toshiba MQ01ABF050 500GB", PROD_S),
]


def in_table(el):
    p = el.parent
    while p:
        if getattr(p, "name", None) == "table":
            return True
        p = p.parent
    return False


def slice_article(title, nxt):
    soup = BeautifulSoup(DOC, "lxml")
    root = soup.body or soup
    cont = soup.new_tag("div")
    state = "before"
    for n in list(root.children):
        nm = getattr(n, "name", None)
        if nm is None:
            continue
        txt = n.get_text().strip()
        if state == "before":
            if nm == "h2" and title in txt:
                state = "in"
            continue
        if nm == "h2" and nxt and nxt in txt:
            break
        if nm == "p" and txt.lower() == "paste":
            continue
        cont.append(n.extract())
    return soup, cont


def fmt(soup, cont, S):
    for a in cont.find_all("a"):
        href = a.get("href") or ""
        m = re.search(r"[?&]q=([^&]+)", href)
        real = urllib.parse.unquote(m.group(1)) if m else href
        path = re.sub(r"^https?://[^/]+", "", real)
        if not a.get_text().strip():
            a.unwrap(); continue
        a["href"] = (path if path and path != "/" else "https://sintech.vn"); a["style"] = LK
        for x in list(a.attrs):
            if x not in ("href", "style"):
                del a[x]
    for h in cont.find_all("h2"):
        h["style"] = S["h2"]
    for h in cont.find_all("h3"):
        h["style"] = S["h3"]
    for p in cont.find_all("p"):
        if not p.has_attr("style") or "font-size" not in (p.get("style") or ""):
            p["style"] = S["p"]
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


def imgtag(soup, src, alt):
    p = soup.new_tag("p"); p["style"] = "text-align:center;margin:14px 0"
    i = soup.new_tag("img"); i["src"] = src; i["alt"] = alt
    i["style"] = "max-width:600px;width:100%;height:auto;border-radius:8px"
    p.append(i); return p


def place(soup, cont, imgs, alt):
    if not imgs:
        return
    fp = cont.find("p")
    if fp:
        fp.insert_after(imgtag(soup, imgs[0], alt))
    rest = imgs[1:]
    h2s = cont.find_all("h2")
    targets = h2s[1:-2] if len(h2s) > 3 else h2s[1:]
    if rest and targets:
        for i, src in enumerate(rest):
            h = targets[i * len(targets) // len(rest)]
            nxt = h.find_next_sibling("h2")
            tag = imgtag(soup, src, alt)
            (nxt.insert_before(tag) if nxt else cont.append(tag))


for kind, oid, title, nxt, alt, S in ARTS:
    soup, cont = slice_article(title, nxt)
    if kind == "product":
        old = hc._request("GET", "/products/%d.json" % oid)["product"].get("body_html") or ""
    else:  # smart collection
        old = hc._request("GET", "/smart_collections/%d.json" % oid)["smart_collection"].get("body_html") or ""
    Path("data/_b3b_%s_OLD_%s.html" % (oid, time.strftime("%H%M%S"))).write_text(old, encoding="utf-8")
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', old)
    fmt(soup, cont, S)
    place(soup, cont, imgs, alt)
    body = "".join(str(x) for x in cont.contents).strip()
    body = re.sub(r"&lt;/?a\b[^&]*&gt;", "", body)
    body = re.sub(r"^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+", "", body)
    if kind == "product":
        hc._request("PUT", "/products/%d.json" % oid, payload={"product": {"id": oid, "body_html": body}})
        time.sleep(1)
        vb = hc._request("GET", "/products/%d.json" % oid)["product"].get("body_html") or ""
    else:
        hc._request("PUT", "/smart_collections/%d.json" % oid, payload={"smart_collection": {"id": oid, "body_html": body}})
        time.sleep(1)
        vb = hc._request("GET", "/smart_collections/%d.json" % oid)["smart_collection"].get("body_html") or ""
    print("%-8s %d | %d ảnh · %d bảng · link đỏ %d · hotline %d · escaped %d" %
          (kind, oid, vb.count("<img"), vb.count("<table"), vb.count("#e74c3c"), vb.count("0911 713 000"), vb.count("&lt;a")))
