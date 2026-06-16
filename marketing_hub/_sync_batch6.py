# -*- coding: utf-8 -*-
"""4 bài: Dell Inspiron 3530 (product) + Keo tản nhiệt (blog huong-dan) +
Naraka (blog news, 0 ảnh - đối thủ) + Xóa watermark PS (blog news, 13 ảnh).
Format chuẩn, KHÔNG top/bot, gỡ dòng gạch, ảnh giữ + resize 600x338 ngay trong sync."""
import re, time, urllib.parse, base64, hashlib, json, io
from pathlib import Path
import requests
from PIL import Image
from bs4 import BeautifulSoup
import haravan_client as hc, blog_rewrite_apply as ap

DOC = Path("state/_doc_current.html").read_text(encoding="utf-8")
THEME = 1001489132
CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
HUP = {"Authorization": "Bearer %s" % CFG["access_token"], "Content-Type": "application/json"}
W, H = 600, 338
LK = "color:#e74c3c;font-weight:700;text-decoration:underline"
BLOG_S = {"h2": "font-size:17pt;font-weight:700;color:#000;margin:24px 0 5px;line-height:1.38;font-family:Arial,sans-serif",
          "h3": "font-size:13pt;font-weight:700;color:#000;margin:18px 0 4px;line-height:1.38;font-family:Arial,sans-serif",
          "p": "font-family:Arial,sans-serif;font-size:12pt;font-weight:500;line-height:1.65;margin:10px 0;color:#000",
          "li": "margin:6px 0;color:#000;font-size:12pt;font-weight:500;font-family:Arial,sans-serif;line-height:1.65"}
PROD_S = {"h2": "font-size:17pt;font-weight:700;color:#000;margin:22px 0 5px;line-height:1.38;font-family:Arial,sans-serif",
          "h3": "font-size:12pt;font-weight:700;color:#000;margin:16px 0 4px;line-height:1.38;font-family:Arial,sans-serif",
          "p": "font-family:Arial,sans-serif;font-size:11pt;font-weight:500;line-height:1.65;margin:10px 0;color:#000",
          "li": "margin:6px 0;color:#000;font-size:11pt;font-weight:500;font-family:Arial,sans-serif;line-height:1.65"}
DASH = re.compile(r'^[\s—–\-_=•·.*]{3,}$')

# (kind, id, art_id, title, next, alt, font, drop_title)
ARTS = [
    ("product", 1073184360, None, "Bàn phím cơ AULA F75 4890 có dây Pink Switch",
     "Laptop Dell Inspiron 5577 cũ đẹp", "Bàn phím cơ AULA F75 4890 Pink Switch", PROD_S, True),
    ("product", 1074894135, None, "Laptop Dell Inspiron 5577 cũ đẹp",
     "Chuột có dây chính hãng tại Sintech", "Laptop Dell Inspiron 5577 cũ", PROD_S, True),
    ("smart", 1004688128, None, "Chuột có dây chính hãng tại Sintech",
     "Phần mềm bản quyền cho PC, laptop và doanh nghiệp", "Chuột có dây chính hãng", BLOG_S, True),
    ("smart", 1004733391, None, "Phần mềm bản quyền cho PC, laptop và doanh nghiệp",
     None, "Phần mềm bản quyền", BLOG_S, True),
]
CACHE = {}


def in_table(el):
    p = el.parent
    while p:
        if getattr(p, "name", None) == "table":
            return True
        p = p.parent
    return False


def make600(content):
    im = Image.open(io.BytesIO(content)).convert("RGB")
    w, h = im.size; r = w / h
    if r >= 1.4:
        s = max(W / w, H / h); nw, nh = round(w * s), round(h * s)
        im = im.resize((nw, nh), Image.LANCZOS); l, t = (nw - W) // 2, (nh - H) // 2
        im = im.crop((l, t, l + W, t + H))
    else:
        s = min(W / w, H / h); nw, nh = max(1, round(w * s)), max(1, round(h * s))
        im = im.resize((nw, nh), Image.LANCZOS)
        c = Image.new("RGB", (W, H), (255, 255, 255)); c.paste(im, ((W - nw) // 2, (H - nh) // 2)); im = c
    o = io.BytesIO(); im.save(o, "JPEG", quality=85); return o.getvalue()


def resize_upload(src):
    if src in CACHE:
        return CACHE[src]
    try:
        r = requests.get(src if src.startswith("http") else "https:" + src, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 300:
            key = "assets/blog/r6-%s.jpg" % hashlib.md5(src.encode()).hexdigest()[:10]
            for _ in range(3):
                rr = requests.put("https://apis.haravan.com/web/themes/%d/assets.json" % THEME, headers=HUP,
                                  json={"asset": {"key": key, "attachment": base64.b64encode(make600(r.content)).decode("ascii")}}, timeout=90)
                if rr.status_code in (200, 201):
                    CACHE[src] = rr.json()["asset"]["public_url"]; return CACHE[src]
                time.sleep(2)
    except Exception as e:
        print("   img ERR", str(e)[:40])
    CACHE[src] = None; return None


def slice_article(title, nxt, drop_title=True):
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
                if drop_title:
                    continue          # bỏ H2 tiêu đề
                # else: giữ H2 đầu (nó là section thật, không phải title)
            else:
                continue
        elif nm == "h2" and nxt and nxt in txt:
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
        if DASH.fullmatch(p.get_text().strip() or "x"):  # gỡ dòng gạch
            p.decompose(); continue
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
    imgs = [u for u in (resize_upload(s) for s in imgs) if u]  # resize 600x338 tất cả
    if not imgs:
        return 0
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
    return len(imgs)


for kind, oid, aid, title, nxt, alt, S, drop_title in ARTS:
    soup, cont = slice_article(title, nxt, drop_title)
    if kind == "product":
        old = hc._request("GET", "/products/%d.json" % oid)["product"].get("body_html") or ""
    elif kind == "smart":
        old = hc._request("GET", "/smart_collections/%d.json" % oid)["smart_collection"].get("body_html") or ""
    else:
        old = ap._fetch_live_article(oid, aid)[1].get("body_html") or ""
    Path("data/_b6_%s_OLD_%s.html" % (aid or oid, time.strftime("%H%M%S"))).write_text(old, encoding="utf-8")
    src_imgs = re.findall(r'<img[^>]+src="([^"]+)"', old)
    fmt(soup, cont, S)
    n = place(soup, cont, src_imgs, alt)
    body = "".join(str(x) for x in cont.contents).strip()
    body = re.sub(r"&lt;/?a\b[^&]*&gt;", "", body)
    body = re.sub(r"^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+", "", body)
    if kind == "product":
        hc._request("PUT", "/products/%d.json" % oid, payload={"product": {"id": oid, "body_html": body}})
        time.sleep(1)
        vb = hc._request("GET", "/products/%d.json" % oid)["product"].get("body_html") or ""
    elif kind == "smart":
        import collection_content_writer as ccw
        comp = ccw.compress_html(body)
        try:
            hc._request("PUT", "/smart_collections/%d.json" % oid, payload={"smart_collection": {"id": oid, "body_html": comp}})
            time.sleep(1)
            vb = hc._request("GET", "/smart_collections/%d.json" % oid)["smart_collection"].get("body_html") or ""
            print("smart    %s | PUT OK (nén %d) | %d ảnh(r6 %d) · %d bảng · hotline %d" %
                  (oid, len(comp), vb.count("<img"), vb.count("/r6-"), vb.count("<table"), vb.count("0911 713 000")))
        except Exception as e:
            print("smart    %s | PUT FAIL (%s) — body nén %d quá dài, cần sync qua tool" % (oid, str(e)[-30:], len(comp)))
        continue
    else:
        ap._put_article(oid, aid, {"id": aid, "body_html": body})
        time.sleep(1)
        vb = ap._fetch_live_article(oid, aid)[1].get("body_html") or ""
    print("%-8s %s | %d ảnh(r6 %d) · %d bảng · link đỏ %d · hotline %d · dash %d · escaped %d" %
          (kind, aid or oid, vb.count("<img"), vb.count("/r6-"), vb.count("<table"),
           vb.count("#e74c3c"), vb.count("0911 713 000"), len(re.findall(r'[—–\-]{3,}', vb)), vb.count("&lt;a")))
