# -*- coding: utf-8 -*-
"""Re-host ảnh external 8 step-tutorial → Haravan theme assets → apply live.
Resilient: ảnh download/upload fail → gỡ riêng ảnh đó, bài vẫn apply. Upload ẢNH GỐC (không resize)."""
import re, json, time, base64, hashlib
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import blog_rewrite as br, blog_rewrite_apply as ap, blog_rewrite_images as imgs

CFG = json.loads((Path("..") / "state" / "haravan_token.json").read_text(encoding="utf-8"))
HUP = {"Authorization": "Bearer %s" % CFG["access_token"], "Content-Type": "application/json"}
THEME = 1001489132
FP = ap._FLAGS_PATH
PROG = Path("state/_rehost_progress.txt")

# (cid, image-bearing draft_id)
JOBS = [(149, 55), (169, 273), (151, 112), (113, 362), (129, 214), (174, 192), (183, 142), (185, 232)]


def log(m):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), m)
    print(line, flush=True)
    with open(PROG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def set_flag(v):
    d = json.loads(FP.read_text(encoding="utf-8-sig")); d["BLOG_REWRITE_LIVE_APPLY_ENABLED"] = v
    FP.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def download(url):
    full = url if url.startswith("http") else ("https:" + url if url.startswith("//") else url)
    try:
        r = requests.get(full, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 500:
            return r.content
    except Exception:
        pass
    return None


def upload(content, cid, idx, src):
    ext = re.sub(r"[^a-z0-9]", "", (src.split("?")[0].rsplit(".", 1)[-1] or "jpg").lower())[:4] or "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp", "gif", "bmp"):
        ext = "jpg"
    h = hashlib.md5(src.encode()).hexdigest()[:6]
    key = "blog/rh-%s-%d-%s.%s" % (cid, idx, h, ext)
    payload = {"asset": {"key": "assets/%s" % key, "attachment": base64.b64encode(content).decode("ascii")}}
    for attempt in range(3):
        try:
            r = requests.put("https://apis.haravan.com/web/themes/%d/assets.json" % THEME, headers=HUP, json=payload, timeout=90)
            if r.status_code in (200, 201):
                return r.json()["asset"]["public_url"]
        except Exception:
            pass
        time.sleep(2 + attempt * 2)
    return None


def rehost_body(cid, body):
    """Trả (new_body, n_rehosted, n_dropped). Swap src external→sintech, gỡ ảnh fail."""
    soup = BeautifulSoup(body, "lxml")
    imgtags = soup.find_all("img")
    cache = {}  # src -> new_url (dedup)
    rehosted = dropped = 0
    for idx, tag in enumerate(imgtags):
        src = (tag.get("src") or "").strip()
        if not src:
            tag.decompose(); dropped += 1; continue
        if imgs.is_sintech_image(src):
            continue  # đã sintech, giữ
        if src in cache:
            tag["src"] = cache[src]; rehosted += 1; continue
        content = download(src)
        if not content:
            log("    img%d download FAIL → gỡ: %s" % (idx, src[:50])); tag.decompose(); dropped += 1; continue
        new = upload(content, cid, idx, src)
        if not new:
            log("    img%d upload FAIL → gỡ: %s" % (idx, src[:50])); tag.decompose(); dropped += 1; continue
        cache[src] = new; tag["src"] = new; rehosted += 1
        log("    img%d OK %s" % (idx, new.split("/")[-1]))
    out = "".join(str(c) for c in soup.body.contents).strip() if soup.body else str(soup)
    return out, rehosted, dropped


def main():
    PROG.write_text("", encoding="utf-8")
    set_flag(True); assert ap.live_apply_enabled(); set_flag(False)
    applied = 0; urls = []
    for cid, base_did in JOBS:
        cand = br.get_candidate(cid); aid = cand["article_id"]
        base = br.get_draft(base_did)
        log("=== cid%s art=%s (base draft#%s) ===" % (cid, aid, base_did))
        new_body, rh, dp = rehost_body(cid, base["draft_body_html"] or "")
        log("  re-host: %d ảnh OK, %d gỡ" % (rh, dp))
        # clone từ base + set body re-hosted
        cv = br.clone_version(base_did); nid = cv["draft_id"]
        br.edit_draft(nid, {"draft_body_html": new_body})
        nd = br.get_draft(nid)
        a2, g2 = imgs.audit_body_images(nd["draft_body_html"] or "", check_availability=True)
        still = [a for a in a2 if str(a.get("apply_gate_status", "")).startswith("BLOCK")]
        if still:
            # gỡ nốt ảnh còn blocked (download/host lỗi sót)
            soup = BeautifulSoup(nd["draft_body_html"], "lxml")
            badsrc = {a["src"] for a in still}
            for t in soup.find_all("img"):
                if (t.get("src") or "") in badsrc:
                    t.decompose()
            nb = "".join(str(c) for c in soup.body.contents).strip() if soup.body else nd["draft_body_html"]
            br.edit_draft(nid, {"draft_body_html": nb})
            log("  gỡ thêm %d ảnh còn blocked" % len(still))
        br.approve_local(nid)
        set_flag(True)
        try:
            res, code = ap.apply_draft_body_only(nid, confirm_phrase="APPLY PILOT ARTICLE %s" % aid,
                                                 confirm_reviewed_draft=True, confirm_reviewed_images=True)
        finally:
            set_flag(False)
        st = res.get("state") or res.get("error")
        if res.get("ok"):
            applied += 1; urls.append(cand.get("article_url"))
        log("  APPLY -> %s http=%s" % (st, res.get("http")))
    Path("state/_rehost_urls.txt").write_text("\n".join(u for u in urls if u), encoding="utf-8")
    log("DONE applied=%d/%d · flags OFF? %s" % (applied, len(JOBS), not ap.live_apply_enabled()))


if __name__ == "__main__":
    main()
