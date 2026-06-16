# -*- coding: utf-8 -*-
"""Resize MỌI ảnh đã chèn trong các bài audit hôm nay về chuẩn 600x338.
ngang (ratio>=1.4) -> cover (lấp đầy, crop) · vuông/đứng -> contain (nền trắng).
Tải -> resize -> upload theme assets -> thay src trong body -> PUT (body-only)."""
import re, time, base64, hashlib, json, io
from pathlib import Path
import requests
from PIL import Image
import haravan_client as hc
import blog_rewrite_apply as ap

THEME = 1001489132
CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
HUP = {"Authorization": "Bearer %s" % CFG["access_token"], "Content-Type": "application/json"}
W, H = 600, 338

# (kind, id[, article_id])
TARGETS = [
    ("blog", 1000906526, 1002420376),   # quạt tản nhiệt
    ("blog", 1000906526, 1002717797),   # top 10 thương hiệu
    ("product", 1068255170),            # i9
    ("product", 1074653556),            # GM-03
    ("product", 1074564335),            # CF-AX90
    ("product", 1062537121),            # NUC
    ("product", 1053655520),            # HDD
    ("smart", 1004683611),              # PC AI collection
]
CACHE = {}


def make_600x338(content):
    im = Image.open(io.BytesIO(content)).convert("RGB")
    w, h = im.size
    ratio = w / h
    if ratio >= 1.4:  # ngang -> cover
        scale = max(W / w, H / h)
        nw, nh = round(w * scale), round(h * scale)
        im = im.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - W) // 2, (nh - H) // 2
        im = im.crop((left, top, left + W, top + H))
    else:  # vuông/đứng -> contain nền trắng
        scale = min(W / w, H / h)
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        im = im.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGB", (W, H), (255, 255, 255))
        canvas.paste(im, ((W - nw) // 2, (H - nh) // 2))
        im = canvas
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return out.getvalue()


def process_src(src):
    if src in CACHE:
        return CACHE[src]
    try:
        r = requests.get(src if src.startswith("http") else "https:" + src, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or len(r.content) < 300:
            CACHE[src] = None; return None
        data = make_600x338(r.content)
        key = "assets/blog/r6-%s.jpg" % hashlib.md5(src.encode()).hexdigest()[:10]
        for _ in range(3):
            rr = requests.put("https://apis.haravan.com/web/themes/%d/assets.json" % THEME,
                              headers=HUP, json={"asset": {"key": key, "attachment": base64.b64encode(data).decode("ascii")}}, timeout=90)
            if rr.status_code in (200, 201):
                CACHE[src] = rr.json()["asset"]["public_url"]; return CACHE[src]
            time.sleep(2)
    except Exception as e:
        print("   ERR", str(e)[:50])
    CACHE[src] = None
    return None


def get_body(t):
    if t[0] == "blog":
        return ap._fetch_live_article(t[1], t[2])[1].get("body_html") or ""
    if t[0] == "product":
        return hc._request("GET", "/products/%d.json" % t[1])["product"].get("body_html") or ""
    return hc._request("GET", "/smart_collections/%d.json" % t[1])["smart_collection"].get("body_html") or ""


def put_body(t, body):
    if t[0] == "blog":
        ap._put_article(t[1], t[2], {"id": t[2], "body_html": body})
    elif t[0] == "product":
        hc._request("PUT", "/products/%d.json" % t[1], payload={"product": {"id": t[1], "body_html": body}})
    else:
        hc._request("PUT", "/smart_collections/%d.json" % t[1], payload={"smart_collection": {"id": t[1], "body_html": body}})


for t in TARGETS:
    body = get_body(t)
    srcs = re.findall(r'<img[^>]+src="([^"]+)"', body)
    if not srcs:
        print("%-10s %d | 0 ảnh" % (t[0], t[1])); continue
    done = 0
    for s in srcs:
        if "/r6-" in s:   # đã resize rồi
            continue
        new = process_src(s)
        if new:
            body = body.replace(s, new); done += 1
    put_body(t, body)
    print("%-10s %d | resize %d/%d ảnh -> 600x338" % (t[0], t[1], done, len(srcs)))
