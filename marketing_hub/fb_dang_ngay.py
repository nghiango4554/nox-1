# -*- coding: utf-8 -*-
"""Dang NGAY 1 bai nhieu anh len Trang FB (khong hen gio).

  py fb_dang_ngay.py --caption <file.txt> --anh <thu_muc> [--that]

Khong co --that thi chi in ke hoach, KHONG dang gi.
Luong: moi anh -> POST /{page}/photos published=false -> photo_id
       roi POST /{page}/feed message + attached_media + published=true
"""
import argparse, json, os, sys, glob

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

import requests

G = "https://graph.facebook.com/v25.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../nox-1
STATE = os.path.join(ROOT, "state")


def doc_token():
    f = os.path.join(STATE, "facebook_token.json")
    c = json.load(open(f, encoding="utf-8"))
    return c["page_id"], c["page_token"]


PAGE, TOKEN = doc_token()


def up_anh(duong_dan):
    with open(duong_dan, "rb") as fh:
        r = requests.post("%s/%s/photos" % (G, PAGE),
                          data={"published": "false", "access_token": TOKEN},
                          files={"source": fh}, timeout=180)
    if r.status_code != 200:
        raise SystemExit("LOI up anh %s: %s" % (os.path.basename(duong_dan), r.text[:300]))
    return r.json()["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--caption", required=True)
    ap.add_argument("--anh", required=True, help="thu muc chua anh")
    ap.add_argument("--that", action="store_true", help="dang that; khong co thi chi in")
    a = ap.parse_args()

    caption = open(a.caption, encoding="utf-8").read().strip()
    files = sorted(glob.glob(os.path.join(a.anh, "*.png")) + glob.glob(os.path.join(a.anh, "*.jpg")))
    files.sort(key=lambda p: os.path.basename(p))

    print("=== KE HOACH ===")
    print("  trang   : %s" % PAGE)
    print("  so anh  : %d" % len(files))
    for i, f in enumerate(files, 1):
        print("    %2d. %s (%.0f KB)" % (i, os.path.basename(f), os.path.getsize(f) / 1024))
    print("  caption : %d ky tu, %d dong" % (len(caption), caption.count("\n") + 1))
    if not a.that:
        print("\n>>> Chua dang gi. Them --that de dang that.")
        return

    print("\n=== DANG UP ANH ===")
    ids = []
    for i, f in enumerate(files, 1):
        pid = up_anh(f)
        ids.append(pid)
        print("  %2d/%d  %s -> %s" % (i, len(files), os.path.basename(f), pid))

    data = {"message": caption, "published": "true", "access_token": TOKEN}
    for i, pid in enumerate(ids):
        data["attached_media[%d]" % i] = json.dumps({"media_fbid": pid})
    r = requests.post("%s/%s/feed" % (G, PAGE), data=data, timeout=180)
    if r.status_code != 200:
        raise SystemExit("LOI tao bai: %s" % r.text[:500])
    post_id = r.json().get("id")
    print("\n=== XONG ===")
    print("  post_id : %s" % post_id)
    print("  link    : https://www.facebook.com/%s" % post_id.replace("_", "/posts/"))


if __name__ == "__main__":
    main()
