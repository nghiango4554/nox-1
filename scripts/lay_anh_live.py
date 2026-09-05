# -*- coding: utf-8 -*-
"""Keo TOAN BO anh dang chay tren web live cua 1 SP ve dia, de lam anh moi cho ChatGPT.

    python lay_anh_live.py <handle> [thu_muc_ra]

Vi sao (vo chot 23/08/2026): thu muc `thumb_chuan/std/<handle>/` la ban CHUAN HOA
tu 30/06, co the da cu so voi anh dang chay tren web. Gen tu anh cu la gen tu du lieu
sai. Luon keo anh LIVE ve truoc khi gen.
"""
import io, os, sys, urllib.request
sys.path.insert(0, r"C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub")
import haravan_client as hc

RA = r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\anh_live"


def lay(handle, thu_muc=RA):
    prods = hc._request("GET", "/products.json",
                        params={"handle": handle, "limit": 1}).get("products", [])
    if not prods:
        raise SystemExit("khong tim thay SP tren Haravan: " + handle)
    p = prods[0]
    imgs = sorted(p.get("images") or [], key=lambda x: x.get("position") or 0)
    d = os.path.join(thu_muc, handle[:45])
    os.makedirs(d, exist_ok=True)
    ra = []
    for i, im in enumerate(imgs, 1):
        f = os.path.join(d, "live_%02d.jpg" % i)
        try:
            raw = urllib.request.urlopen(im["src"], timeout=40).read()
            open(f, "wb").write(raw)
            ra.append((f, im.get("position"), len(raw)))
        except Exception as e:  # noqa: BLE001
            print("  loi tai anh %d: %s" % (i, str(e)[:60]))
    print("%s -> %d anh live" % (p.get("title", "")[:52], len(ra)))
    for f, pos, sz in ra:
        print("   pos %-3s %7d byte  %s" % (pos, sz, os.path.basename(f)))
    return d, ra


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    lay(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else RA)
