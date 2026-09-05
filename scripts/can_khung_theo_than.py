# -*- coding: utf-8 -*-
"""Can lai khung anh dai dien theo THAN MAY, khong tinh bo day.

Vi sao (vo bat 23/08/2026): buoc chuan hoa cua hub can giua theo HOP BAO, ma hop bao
tinh ca bo day chay ra mep. SP nao day dai thi than may bi day lech trai va co nho lai
— con 103 chi con 44% be rong trong khi khuon cua cum la 68-72%.

Cach do than: cot nao thuoc than may thi co cot pixel toi CAO; cot chi co day thi thap.
Lay cac cot cao >= 35% chieu cao anh.

    python can_khung_theo_than.py <anh_vao> <anh_ra> [--rong 68] [--xem]
"""
import sys
from PIL import Image

NG = 232
RONG_DICH = 68.0     # % be rong khung ma than may nen chiem
CAO_TOI_DA = 80.0    # % chieu cao, tran an toan


def hop_than(im):
    im = im.convert("RGB"); W, H = im.size; px = im.load()
    cc = [0]*W
    for x in range(W):
        ys = [y for y in range(H) if min(px[x, y]) < NG]
        if ys:
            cc[x] = ys[-1]-ys[0]+1
    cot = [x for x in range(W) if cc[x] >= H*0.55]
    if not cot:
        return None
    a, b = cot[0], cot[-1]
    ys = [y for y in range(H) if any(min(px[x, y]) < NG for x in range(a, b+1, 2))]
    return a, ys[0], b, ys[-1]


def can(im, rong_dich=RONG_DICH):
    """Tra ve anh vuong moi, than may chiem `rong_dich`% be rong va nam giua."""
    W, H = im.size
    x0, y0, x1, y1 = hop_than(im)
    tw, th = x1-x0+1, y1-y0+1
    ra = max(W, H)
    k = (ra*rong_dich/100)/tw
    if th*k > ra*CAO_TOI_DA/100:          # cao qua thi thu nho lai cho vua
        k = (ra*CAO_TOI_DA/100)/th
    lon = im.convert("RGB").resize((int(W*k), int(H*k)), Image.LANCZOS)
    # tam than may tren anh da phong
    cx, cy = (x0+x1+1)/2*k, (y0+y1+1)/2*k
    ra_im = Image.new("RGB", (ra, ra), (255, 255, 255))
    ra_im.paste(lon, (int(ra/2-cx), int(ra/2-cy)))
    return ra_im


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    rong = RONG_DICH
    if "--rong" in sys.argv:
        rong = float(sys.argv[sys.argv.index("--rong")+1])
    im = Image.open(sys.argv[1])
    ra = can(im, rong)
    ra.save(sys.argv[2], quality=95)
    b = hop_than(ra)
    print("-> %s  than rong %.1f%%  le T/P %d/%d" % (
        sys.argv[2], (b[2]-b[0]+1)/ra.size[0]*100, b[0], ra.size[0]-1-b[2]))
