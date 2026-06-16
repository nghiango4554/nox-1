# -*- coding: utf-8 -*-
"""Tách 1 Doc chứa 3 bài → format chuẩn + giữ ảnh cũ (giàn đều theo H2) + sync.
KHÔNG chèn top/bot (rule 15/6: bài đã có intro + footer 'Tư vấn cấu hình...' sẵn)."""
import re, time, urllib.parse, sqlite3
from pathlib import Path
from bs4 import BeautifulSoup
import haravan_client as hc, blog_rewrite_apply as ap

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

# (kind, target..., title_h2, next_title_h2|None, alt, font)
ARTS = [
    ("blog", 1000906526, 1002420376, "Cách lắp quạt tản nhiệt cho PC đúng hướng gió",
     "Các thương hiệu linh kiện máy tính phổ biến", "Cách lắp quạt tản nhiệt cho PC", BLOG_S),
    ("blog", 1000906526, 1002717797, "Các thương hiệu linh kiện máy tính phổ biến",
     "Vỏ Case MAGIC GM-03 MESH Black", "Thương hiệu linh kiện máy tính", BLOG_S),
    ("product", 1074653556, None, "Vỏ Case MAGIC GM-03 MESH Black",
     None, "Vỏ Case MAGIC GM-03 MESH Black", PROD_S),
]


def in_table(el):
    p = el.parent
    while p:
        if getattr(p, "name", None) == "table":
            return True
        p = p.parent
    return False


def slice_article(title, next_title):
    """Trả về div chứa các block của bài (đã bỏ H2 tiêu đề)."""
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
                state = "in"      # bỏ chính H2 tiêu đề
            continue
        # state == in
        if nm == "h2" and next_title and next_title in txt:
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
        txt = a.get_text().strip()
        if not txt:
            a.unwrap(); continue
        a["href"] = (path if path and path != "/" else "https://sintech.vn"); a["style"] = LK
        for x in list(a.attrs):
            if x not in ("href", "style"):
                del a[x]
    for h in cont.find_all("h2"):
        if "Mục lục" not in h.get_text():
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


def place_images(soup, cont, imgs, alt):
    """hero (img0) dưới intro; còn lại giàn đều CUỐI các H2 (trước H2 kế), né 2 H2 cuối (Vì sao mua/FAQ)."""
    if not imgs:
        return
    # hero dưới p intro đầu
    first_p = cont.find("p")
    if first_p:
        first_p.insert_after(imgtag(soup, imgs[0], alt))
    rest = imgs[1:]
    h2s = cont.find_all("h2")
    # bỏ 2 H2 cuối (thường 'Vì sao nên mua' + 'Câu hỏi thường gặp') khỏi chỗ chèn ảnh
    targets = h2s[1:-2] if len(h2s) > 3 else h2s[1:]
    if rest and targets:
        step = max(1, len(targets) // len(rest))
        picked = targets[::step][:len(rest)]
        for src, h in zip(rest, picked):
            nxt = h.find_next_sibling("h2")
            tag = imgtag(soup, src, alt)
            (nxt.insert_before(tag) if nxt else cont.append(tag))


for kind, a1, a2, title, nxt, alt, S in ARTS:
    soup, cont = slice_article(title, nxt)
    # lấy ảnh cũ
    if kind == "blog":
        _, art = ap._fetch_live_article(a1, a2)
        old = art.get("body_html") or ""
    else:
        prod = hc._request("GET", "/products/%d.json" % a1)["product"]
        old = prod.get("body_html") or ""
    Path("data/_batch3_%s_OLD_%s.html" % (a2 or a1, time.strftime("%H%M%S"))).write_text(old, encoding="utf-8")
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', old)
    fmt(soup, cont, S)
    place_images(soup, cont, imgs, alt)
    body_html = "".join(str(x) for x in cont.contents).strip()
    body_html = re.sub(r"&lt;/?a\b[^&]*&gt;", "", body_html)
    body_html = re.sub(r"^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+", "", body_html)
    if kind == "blog":
        st, _ = ap._put_article(a1, a2, {"id": a2, "body_html": body_html})
        time.sleep(1)
        _, v = ap._fetch_live_article(a1, a2)
        vb = v.get("body_html") or ""
        print("BLOG %d | PUT %s | %d ảnh · %d bảng · link đỏ %d · hotline %d · escaped %d | %s"
              % (a2, st, vb.count("<img"), vb.count("<table"), vb.count("#e74c3c"),
                 vb.count("0911 713 000"), vb.count("&lt;a"), (v.get("title") or "")[:30]))
    else:
        hc._request("PUT", "/products/%d.json" % a1, payload={"product": {"id": a1, "body_html": body_html}})
        time.sleep(1)
        vb = hc._request("GET", "/products/%d.json" % a1)["product"].get("body_html") or ""
        print("PROD %d | %d ảnh · %d bảng · link đỏ %d · hotline %d · escaped %d"
              % (a1, vb.count("<img"), vb.count("<table"), vb.count("#e74c3c"),
                 vb.count("0911 713 000"), vb.count("&lt;a")))
