# -*- coding: utf-8 -*-
"""Hen gio 1 bai FB nhieu anh.

  py fb_hen_gio.py --caption <file.txt> --anh <f1> <f2> ... --khi "3/9 20:00" [--that]

Khong co --that thi chi in ke hoach. Giờ theo múi giờ Việt Nam.
"""
import argparse, json, os, sys, datetime

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

import requests

G = "https://graph.facebook.com/v25.0"
VN = datetime.timezone(datetime.timedelta(hours=7))
STATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")
_c = json.load(open(os.path.join(STATE, "facebook_token.json"), encoding="utf-8"))
PAGE, TOKEN = _c["page_id"], _c["page_token"]


def gio_unix(chuoi):
    ngay, gio = chuoi.split()
    d, m = [int(x) for x in ngay.split("/")]
    h, mi = [int(x) for x in gio.split(":")]
    nay = datetime.datetime.now(VN)
    return int(datetime.datetime(nay.year, m, d, h, mi, tzinfo=VN).timestamp())


def up_anh(p):
    with open(p, "rb") as fh:
        r = requests.post("%s/%s/photos" % (G, PAGE),
                          data={"published": "false", "access_token": TOKEN},
                          files={"source": fh}, timeout=180)
    if r.status_code != 200:
        raise SystemExit("LOI up anh %s: %s" % (os.path.basename(p), r.text[:300]))
    return r.json()["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--caption", required=True)
    ap.add_argument("--anh", nargs="+", required=True)
    ap.add_argument("--khi", required=True, help='vd "3/9 20:00"')
    ap.add_argument("--that", action="store_true")
    a = ap.parse_args()

    caption = open(a.caption, encoding="utf-8").read().strip()
    khi = gio_unix(a.khi)
    con = (khi - datetime.datetime.now(VN).timestamp()) / 60
    print("=== KE HOACH ===")
    print("  trang   : %s" % PAGE)
    print("  hen luc : %s (con %.0f phut)" % (
        datetime.datetime.fromtimestamp(khi, VN).strftime("%d/%m/%Y %H:%M"), con))
    if con < 10:
        raise SystemExit("LOI: Facebook yeu cau hen it nhat 10 phut ke tu bay gio.")
    if con > 60 * 24 * 180:
        raise SystemExit("LOI: khong hen qua 6 thang.")
    for i, f in enumerate(a.anh, 1):
        if not os.path.exists(f):
            raise SystemExit("KHONG THAY ANH: %s" % f)
        print("    %d. %s (%.0f KB)" % (i, os.path.basename(f), os.path.getsize(f) / 1024))
    print("  caption : %d ky tu, %d dong" % (len(caption), caption.count("\n") + 1))
    if not a.that:
        print("\n>>> Chua tao gi. Them --that de dat lich that.")
        return

    print("\n=== UP ANH ===")
    ids = []
    for i, f in enumerate(a.anh, 1):
        pid = up_anh(f)
        ids.append(pid)
        print("  %d/%d %s -> %s" % (i, len(a.anh), os.path.basename(f), pid))

    data = {"message": caption, "published": "false",
            "scheduled_publish_time": str(khi), "access_token": TOKEN}
    for i, pid in enumerate(ids):
        data["attached_media[%d]" % i] = json.dumps({"media_fbid": pid})
    r = requests.post("%s/%s/feed" % (G, PAGE), data=data, timeout=180)
    if r.status_code != 200:
        raise SystemExit("LOI tao bai: %s" % r.text[:500])
    print("\n=== XONG ===")
    print("  post_id : %s" % r.json().get("id"))
    print("  se len luc %s" % datetime.datetime.fromtimestamp(khi, VN).strftime("%d/%m/%Y %H:%M"))


if __name__ == "__main__":
    main()
