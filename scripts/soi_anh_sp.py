# -*- coding: utf-8 -*-
"""SOI 1 tam anh san pham: DO bang pixel + KE LINE de mat cham.

Vo chot 22/08/2026, tach ra tu buoi chuan hoa anh PSU.

Y tuong: viec kiem mot tam anh SP co HAI TANG, dung mot tang la hut.

  Tang 1 - DO. May quet tung diem anh, ra hop bao SP chinh xac toi pixel:
    khung co vuong, SP chiem bao nhieu % be rong, le 4 phia, lech tam,
    nen co trang thuan. Mat KHONG lam duoc: chenh 3px tren anh 1000px
    thi nhin kieu gi cung khong ra.

  Tang 2 - KE LINE. Ve truc giua + hop muc tieu 85% + hop bao that len anh,
    de MAT cham nhung thu KHONG do duoc: do cao camera, canh goc dung co
    trung truc giua khong, duong di cua bo day, chu tren vo co dung model.

  RANH GIOI nay hoc duoc bang mau: buoi 22/08 co gang do "do cao camera"
  bang cong thuc THAN/TONG thi HONG 3 lan (MW650 ra 19,9% ma anh dung,
  Delta P750 ra 57,1% ca truoc lan sau khien tuong day hut). Cai gi phai
  hieu hinh moi biet thi dung co gang quy ve con so.

Dung:
    python soi_anh_sp.py anh1.jpg anh2.png ...
    python soi_anh_sp.py --hub <product-handle>        # keo anh 1 tu hub ve soi
    python soi_anh_sp.py --hub <handle> --idx 3        # soi anh thu tu idx tren hub

Sinh ra <ten>_SOI.png ben canh anh goc, va in bang so.
Chay tren Windows nho dat PYTHONUTF8=1 neu console bao loi encode.
"""
import io
import json
import os
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

HUB = "http://127.0.0.1:5055"
NGUONG = 232        # duoi muc nay coi la than san pham, tren la nen
MUC_TIEU = 85.0     # be rong SP mong muon, % khung
DUNG_SAI_RONG = 3.0     # lech qua nay thi bao LECH
DUNG_SAI_LE = 6         # chenh le hai ben qua nay (px) thi bao LECH


# ---------------------------------------------------------------- do bang pixel
def do(im):
    """Tra ve dict cac so do, hoac None neu anh trang tron."""
    im = im.convert("RGB")
    W, H = im.size
    px = im.load()
    x0, x1, y0, y1 = W, -1, H, -1
    so_sp = 0
    so_trang_thuan = 0
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            if r < NGUONG or g < NGUONG or b < NGUONG:
                so_sp += 1
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
            elif r > 250 and g > 250 and b > 250:
                so_trang_thuan += 1
    if x1 < 0:
        return None
    so_nen = W * H - so_sp
    return {
        "W": W, "H": H,
        "hop": (x0, y0, x1, y1),
        "vuong": abs(W - H) <= 2,
        "rong": (x1 - x0 + 1) / W * 100,
        "cao": (y1 - y0 + 1) / H * 100,
        "le_trai": x0, "le_phai": W - 1 - x1,
        "le_tren": y0, "le_duoi": H - 1 - y1,
        "lech_ngang": (x0 + x1) / 2 - W / 2,
        "lech_doc": (y0 + y1) / 2 - H / 2,
        "nen_trang": so_trang_thuan / so_nen * 100 if so_nen else 0.0,
    }


# ------------------------------------------------------------------- ke line
def ke_line(im, d):
    """Ve truc giua, hop muc tieu 85% va hop bao that len ban sao cua anh."""
    v = im.convert("RGB").copy()
    W, H = v.size
    dr = ImageDraw.Draw(v, "RGBA")
    net = max(2, W // 400)
    try:
        f = ImageFont.truetype("arialbd.ttf", max(16, W // 55))
    except OSError:
        f = ImageFont.load_default()

    mw = W * MUC_TIEU / 100                      # hop muc tieu, xanh duong
    dr.rectangle([(W - mw) / 2, (H - mw) / 2, (W + mw) / 2, (H + mw) / 2],
                 outline=(80, 160, 255, 150), width=net)
    x0, y0, x1, y1 = d["hop"]                    # hop bao that, xanh la
    dr.rectangle([x0, y0, x1, y1], outline=(0, 190, 90, 220), width=max(2, W // 330))
    dr.line([(W / 2, 0), (W / 2, H)], fill=(255, 60, 60, 200), width=net)
    dr.line([(0, H / 2), (W, H / 2)], fill=(255, 60, 60, 110), width=max(1, W // 600))

    dr.text((6, H / 2 + 6), str(d["le_trai"]), fill=(0, 130, 0), font=f)
    dr.text((x1 + 8, H / 2 + 6), str(d["le_phai"]), fill=(0, 130, 0), font=f)
    dr.text((W / 2 + 8, 6), str(d["le_tren"]), fill=(0, 130, 0), font=f)
    dr.text((W / 2 + 8, y1 + 8), str(d["le_duoi"]), fill=(0, 130, 0), font=f)
    return v


# ---------------------------------------------------------------------- in ra
def in_bang(ten, d):
    lt, lp = d["le_trai"], d["le_phai"]
    ltr, ld = d["le_tren"], d["le_duoi"]
    dat_rong = abs(d["rong"] - MUC_TIEU) <= DUNG_SAI_RONG
    dat_tp = abs(lt - lp) <= DUNG_SAI_LE
    dat_td = abs(ltr - ld) <= DUNG_SAI_LE
    print("\n=== %s ===" % ten)
    print("  khung           %dx%d   vuong: %s" % (d["W"], d["H"], "co" if d["vuong"] else "KHONG"))
    print("  SP chiem rong   %.1f%%  (muc tieu %.0f%%)   %s"
          % (d["rong"], MUC_TIEU, "DAT" if dat_rong else "LECH"))
    print("  SP chiem cao    %.1f%%" % d["cao"])
    print("  le trai/phai    %d/%d   chenh %dpx   %s" % (lt, lp, abs(lt - lp), "DAT" if dat_tp else "LECH"))
    print("  le tren/duoi    %d/%d   chenh %dpx   %s" % (ltr, ld, abs(ltr - ld), "DAT" if dat_td else "LECH"))
    print("  lech tam        ngang %+.1fpx  doc %+.1fpx" % (d["lech_ngang"], d["lech_doc"]))
    print("  nen trang thuan %.1f%%" % d["nen_trang"])
    return dat_rong and dat_tp and dat_td


NHAC = """
  --- May chi do duoc bay nhieu. Mo file *_SOI.png ra MAT cham not: ---
      1. Mat tren (luoi quat hay nap tron) da la mang lon nhat trong khung chua?
      2. Canh goc dung co nam tren vach do giua khung khong?
      3. Neu co day: day co thoat ra mat hong PHAI, bo gon, chay ngang,
         cat cut o mep phai, khong che mat truoc khong?
      4. Chu tren vo co dung model cua SP nay khong?
"""


# ------------------------------------------------------------------- lay anh
def anh_tu_hub(handle, idx=None):
    """Keo anh tu hub ve. idx=None thi lay ANH DAI DIEN (dau manifest)."""
    goc = "%s/thumbs/img/std/%s" % (HUB, handle)
    if idx is None:
        man = json.load(urllib.request.urlopen(goc + "/manifest.json", timeout=30))
        if not man:
            raise RuntimeError("manifest rong")
        idx = man[0]["idx"]
    raw = urllib.request.urlopen("%s/%d.jpg" % (goc, idx), timeout=40).read()
    return Image.open(io.BytesIO(raw)), "%s_%s" % (handle[:40], idx)


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    viec = []
    if argv[0] == "--hub":
        if len(argv) < 2:
            print("thieu handle")
            return 1
        idx = None
        if "--idx" in argv:
            idx = int(argv[argv.index("--idx") + 1])
        im, ten = anh_tu_hub(argv[1], idx)
        viec.append((ten, im, os.getcwd()))
    else:
        for fn in argv:
            viec.append((os.path.splitext(os.path.basename(fn))[0],
                         Image.open(fn), os.path.dirname(os.path.abspath(fn))))

    dat_het = True
    for ten, im, thu_muc in viec:
        d = do(im)
        if not d:
            print("\n=== %s ===\n  anh trang tron, khong thay san pham" % ten)
            dat_het = False
            continue
        dat_het = in_bang(ten, d) and dat_het
        ra = os.path.join(thu_muc, ten + "_SOI.png")
        ke_line(im, d).save(ra)
        print("  -> %s" % ra)
    print(NHAC)
    return 0 if dat_het else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
