# -*- coding: utf-8 -*-
"""Resize 8 ảnh collection PC-AI về 600x338 + nén body (vì 422 quá dài) + PUT body-only."""
import re, time, base64, hashlib, json, io
from pathlib import Path
import requests
from PIL import Image
import haravan_client as hc
import collection_content_writer as ccw

CID = 1004683611
THEME = 1001489132
CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
HUP = {"Authorization": "Bearer %s" % CFG["access_token"], "Content-Type": "application/json"}
W, H = 600, 338


def make(content):
    im = Image.open(io.BytesIO(content)).convert("RGB")
    w, h = im.size; r = w / h
    if r >= 1.4:
        s = max(W / w, H / h); nw, nh = round(w * s), round(h * s)
        im = im.resize((nw, nh), Image.LANCZOS)
        l, t = (nw - W) // 2, (nh - H) // 2; im = im.crop((l, t, l + W, t + H))
    else:
        s = min(W / w, H / h); nw, nh = max(1, round(w * s)), max(1, round(h * s))
        im = im.resize((nw, nh), Image.LANCZOS)
        c = Image.new("RGB", (W, H), (255, 255, 255)); c.paste(im, ((W - nw) // 2, (H - nh) // 2)); im = c
    o = io.BytesIO(); im.save(o, "JPEG", quality=85); return o.getvalue()


def resize_upload(src):
    r = requests.get(src if src.startswith("http") else "https:" + src, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code != 200:
        return None
    key = "assets/blog/r6-%s.jpg" % hashlib.md5(src.encode()).hexdigest()[:10]
    for _ in range(3):
        rr = requests.put("https://apis.haravan.com/web/themes/%d/assets.json" % THEME, headers=HUP,
                          json={"asset": {"key": key, "attachment": base64.b64encode(make(r.content)).decode("ascii")}}, timeout=90)
        if rr.status_code in (200, 201):
            return rr.json()["asset"]["public_url"]
        time.sleep(2)
    return None


body = hc._request("GET", "/smart_collections/%d.json" % CID)["smart_collection"].get("body_html") or ""
done = 0
for s in re.findall(r'<img[^>]+src="([^"]+)"', body):
    if "/r6-" in s:
        continue
    new = resize_upload(s)
    if new:
        body = body.replace(s, new); done += 1
body = ccw.compress_html(body)
print("resized %d ảnh · body len sau nén %d" % (done, len(body)))
hc._request("PUT", "/smart_collections/%d.json" % CID, payload={"smart_collection": {"id": CID, "body_html": body}})
time.sleep(1)
vb = hc._request("GET", "/smart_collections/%d.json" % CID)["smart_collection"].get("body_html") or ""
print("LIVE collection: %d ảnh · len %d · r6=%d" % (vb.count("<img"), len(vb), vb.count("/r6-")))
