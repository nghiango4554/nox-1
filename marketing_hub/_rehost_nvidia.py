# -*- coding: utf-8 -*-
"""Re-host 15 ảnh NVIDIA (bizweb) -> Sintech -> chèn cuối H2 khớp trên bài live (1002431245)."""
import json, re, time, base64, hashlib
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import blog_rewrite_apply as ap

BLOG_ID, ART_ID = 1000906526, 1002431245
THEME = 1001489132
CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
HUP = {"Authorization": "Bearer %s" % CFG["access_token"], "Content-Type": "application/json"}


def download(url):
    full = url if url.startswith("http") else "https:" + url
    try:
        r = requests.get(full, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 500:
            return r.content
    except Exception:
        pass
    return None


def upload(content, idx, src):
    ext = re.sub(r"[^a-z0-9]", "", (src.split("?")[0].rsplit(".", 1)[-1] or "jpg").lower())[:4] or "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        ext = "jpg"
    key = "blog/rh-nvidia-%d-%s.%s" % (idx, hashlib.md5(src.encode()).hexdigest()[:6], ext)
    payload = {"asset": {"key": "assets/%s" % key, "attachment": base64.b64encode(content).decode("ascii")}}
    for att in range(3):
        try:
            r = requests.put("https://apis.haravan.com/web/themes/%d/assets.json" % THEME, headers=HUP, json=payload, timeout=90)
            if r.status_code in (200, 201):
                return r.json()["asset"]["public_url"]
        except Exception:
            pass
        time.sleep(2)
    return None


# ảnh gốc + heading từ draft#223
import sqlite3
conn = sqlite3.connect("data/posts.db")
src_body = conn.execute("SELECT draft_body_html FROM blog_rewrite_drafts WHERE id=223").fetchone()[0]
conn.close()
old = []
for seg in re.split(r"(<h[1-6][^>]*>.*?</h[1-6]>)", src_body, flags=re.I | re.S):
    if re.match(r"<h[1-6]", seg or "", re.I):
        cur = re.sub("<[^>]+>", " ", seg).strip()
    for m in re.findall(r'<img[^>]+src="([^"]+)"', seg or ""):
        old.append((m, cur if "cur" in dir() else ""))

# map heading ảnh cũ -> keyword tìm H2 mới
KW = [("Power Management", "hiệu năng của GPU"), ("Pre-Rendered", "Giảm độ trễ"), ("V-Sync", "V-Sync"),
      ("Texture Filtering", "lọc texture"), ("Anisotropic", "bất đẳng hướng"), ("MFAA", "MFAA"),
      ("FXAA", "răng cưa"), ("Antialiasing", "răng cưa"), ("Transparency", "trong suốt"),
      ("CUDA", "hiệu năng của GPU"), ("DSR", "hiệu năng của GPU"), ("Ambient Occlusion", "hiệu năng của GPU"),
      ("Adjust Image", "ưu tiên hiệu năng"), ("mở NVIDIA", "Trước khi chỉnh"), ("dành 10 phút", "Trước khi chỉnh")]


def dest_kw(h):
    for k, d in KW:
        if k.lower() in (h or "").lower():
            return d
    return None


# live body (đã format)
code, art = ap._fetch_live_article(BLOG_ID, ART_ID)
soup = BeautifulSoup(art.get("body_html") or "", "lxml")
cont = soup.body or soup
h2s = cont.find_all("h2")


def imgtag(url):
    p = soup.new_tag("p"); p["style"] = "text-align:center;margin:14px 0"
    i = soup.new_tag("img"); i["src"] = url; i["alt"] = "Minh hoạ tối ưu card NVIDIA"
    i["style"] = "max-width:600px;width:100%;height:auto;border-radius:8px"
    p.append(i); return p


pending = {}
done = 0
for idx, (src, lh) in enumerate(old):
    d = dest_kw(lh)
    if not d:
        print("  skip (no dest):", lh[:30]); continue
    h = next((x for x in h2s if d.lower() in x.get_text().lower()), None)
    if not h:
        print("  no H2 for:", d); continue
    content = download(src)
    if not content:
        print("  dl fail:", src[:40]); continue
    new = upload(content, idx, src)
    if not new:
        print("  up fail:", src[:40]); continue
    pending.setdefault(id(h), (h, []))[1].append(new)
    done += 1
    if done % 5 == 0:
        print("  ...re-host %d/15" % done)

for hid, (h, urls) in pending.items():
    nxt = h.find_next_sibling("h2")
    for u in urls:
        (nxt.insert_before(imgtag(u)) if nxt else cont.append(imgtag(u)))

nb = "".join(str(x) for x in cont.contents).strip()
status, _ = ap._put_article(BLOG_ID, ART_ID, {"id": ART_ID, "body_html": nb})
print("PUT HTTP %s · re-host %d/15 ảnh" % (status, done))
time.sleep(1)
c2, v = ap._fetch_live_article(BLOG_ID, ART_ID)
print("LIVE: %d ảnh · %d bảng" % ((v.get("body_html") or "").count("<img"), (v.get("body_html") or "").count("<table")))
