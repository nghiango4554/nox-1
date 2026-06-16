# -*- coding: utf-8 -*-
"""Format + re-host 6 ảnh + sync bài 'CMD tự chạy' lên blog (1002414345)."""
import json, re, time, base64, hashlib, urllib.parse, sqlite3
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import blog_rewrite_apply as ap

BLOG_ID, ART_ID = 1000906526, 1002414345
THEME = 1001489132
CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
HUP = {"Authorization": "Bearer %s" % CFG["access_token"], "Content-Type": "application/json"}
S = {"h2": "font-size:17pt;font-weight:700;color:#000;margin:24px 0 5px;line-height:1.38;font-family:Arial,sans-serif",
     "h3": "font-size:13pt;font-weight:700;color:#000;margin:18px 0 4px;line-height:1.38;font-family:Arial,sans-serif",
     "p": "font-family:Arial,sans-serif;font-size:12pt;font-weight:500;line-height:1.65;margin:10px 0;color:#000",
     "li": "margin:6px 0;color:#000;font-size:12pt;font-weight:500;font-family:Arial,sans-serif;line-height:1.65"}
LK = "color:#e74c3c;font-weight:700;text-decoration:underline"


def in_table(el):
    p = el.parent
    while p:
        if getattr(p, "name", None) == "table":
            return True
        p = p.parent
    return False


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
    key = "blog/rh-cmd-%d-%s.%s" % (idx, hashlib.md5(src.encode()).hexdigest()[:6], ext)
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
        if not seen and "CMD tự chạy trên Windows có đáng lo không" in ht:
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

# re-host 6 ảnh từ draft#116, map -> H2 mới
conn = sqlite3.connect("data/posts.db")
src_body = conn.execute("SELECT draft_body_html FROM blog_rewrite_drafts WHERE id=116").fetchone()[0]
conn.close()
old = []
cur = ""
for seg in re.split(r"(<h[1-6][^>]*>.*?</h[1-6]>)", src_body, flags=re.I | re.S):
    if re.match(r"<h[1-6]", seg or "", re.I):
        cur = re.sub("<[^>]+>", " ", seg).strip()
    for m in re.findall(r'<img[^>]+src="([^"]+)"', seg or ""):
        old.append((m, cur))
KW = [("ngẫu nhiên", "Vì sao CMD tự bật"), ("tự mở", "Vì sao CMD tự bật"),
      ("danh sách khởi động", "Tắt ứng dụng khởi động"), ("Task Scheduler", "Task Scheduler"),
      ("tài khoản Windows", "cài Windows")]
def dest(h):
    for k, d in KW:
        if k.lower() in (h or "").lower():
            return d
    return None
h2s = cont.find_all("h2")
def imgtag(url):
    p = soup.new_tag("p"); p["style"] = "text-align:center;margin:14px 0"
    i = soup.new_tag("img"); i["src"] = url; i["alt"] = "Minh hoạ lỗi CMD tự chạy"
    i["style"] = "max-width:600px;width:100%;height:auto;border-radius:8px"
    p.append(i); return p
pending = {}; done = 0
for idx, (src, lh) in enumerate(old):
    d = dest(lh)
    if not d:
        continue
    h = next((x for x in h2s if d.lower() in x.get_text().lower()), None)
    if not h:
        continue
    content = download(src)
    if not content:
        continue
    new = upload(content, idx, src)
    if not new:
        continue
    pending.setdefault(id(h), (h, []))[1].append(new); done += 1
for hid, (h, urls) in pending.items():
    nxt = h.find_next_sibling("h2")
    for u in urls:
        (nxt.insert_before(imgtag(u)) if nxt else cont.append(imgtag(u)))

body_html = "".join(str(x) for x in cont.contents).strip()
body_html = re.sub(r"&lt;/?a\b[^&]*&gt;", "", body_html)
body_html = re.sub(r"^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+", "", body_html)
top = '<p style="%s"><a href="https://sintech.vn" style="%s">Sintech</a> hướng dẫn cách kiểm tra và khắc phục khi Command Prompt (CMD) tự chạy trên Windows, áp dụng cho cả PC và laptop.</p>' % (S["p"], LK)
bot = '<p style="%s">Nếu CMD vẫn tự mở do lỗi phần cứng hoặc nghi nhiễm sâu, liên hệ <a href="https://sintech.vn" style="%s">Sintech</a> để kiểm tra. Hotline 0911 713 000 · 457 Trần Xuân Soạn, Q7, TP.HCM.</p>' % (S["p"], LK)
final = top + body_html + bot

code, art = ap._fetch_live_article(BLOG_ID, ART_ID)
Path("data/_cmd_OLD_backup_%s.html" % time.strftime("%Y%m%d_%H%M%S")).write_text(art.get("body_html") or "", encoding="utf-8")
status, _ = ap._put_article(BLOG_ID, ART_ID, {"id": ART_ID, "body_html": final})
print("PUT HTTP %s · re-host %d/6 ảnh" % (status, done))
time.sleep(1)
c2, v = ap._fetch_live_article(BLOG_ID, ART_ID)
vb = v.get("body_html") or ""
print("LIVE: %d ảnh · %d bảng · h2-styled=%d · link đỏ=%d · internal=%d · chatgpt=%d · escaped=%d · title: %s" %
      (vb.count("<img"), vb.count("<table"), vb.count("font-size:17pt"), vb.count("#e74c3c"),
       len(re.findall(r'href="/(collections|pages)/', vb)), vb.count("chatgpt"), vb.count("&lt;a"), v.get("title")[:36]))
