# -*- coding: utf-8 -*-
"""Dang 1 bai len OA Zalo Sintech theo lich.

Dung:  python zalo_dang_bai.py galax
       python zalo_dang_bai.py jonsbo
       python zalo_dang_bai.py chuot an     <- dang o trang thai AN (status=hide)

Them tham so "an" (hoac "hide") thi bai len OA nhung khong hien voi nguoi doc,
vao trang quan tri Zalo bam hien sau. Luu y: bai an VAN AN mot luot trong han
muc 15 bai moi chu ky.

Doc bai tu nox-outputs/zalo_2bai_draft.json, anh bia tu nox-outputs/zalo_bia_url.json.
Sau khi tao thi TU KIEM lai bang cach doc lai bai tren OA, ghi log ra
nox-outputs/zalo_dang_log.txt. Neu bai da ton tai thi BO QUA, khong tao trung.
"""
import json
import io
import os
import re
import shutil
import sys
import time
import requests

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
STATE = os.path.join(WS, "nox-1", "state", "zalo_oa.json")
OUT = os.path.join(WS, "nox-outputs")
LOG = os.path.join(OUT, "zalo_dang_log.txt")
BASE = "https://openapi.zalo.me/v2.0/article/"


def ghi(msg):
    dong = "[%s] %s" % (time.strftime("%d/%m/%Y %H:%M:%S"), msg)
    # Chay qua Task Scheduler thi stdout co the la cp1252 hoac khong co console.
    # print() vap tieng Viet se nem UnicodeEncodeError va giet ca script,
    # nen bo qua moi loi in an. File log moi la thu that su phai ghi duoc.
    try:
        print(dong)
    except Exception:
        pass
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(dong + "\n")


def chuan(s):
    """Chuan hoa tieu de de so sanh: Zalo doi ky tu dac biet (350M2 <- 350M2)."""
    s = (s or "").lower()
    s = re.sub(r"[²³⁰-₟]", lambda m: {"²": "2", "³": "3"}.get(m.group(0), ""), s)
    return re.sub(r"[^0-9a-zÀ-ỹ]+", "", s)


def lam_moi_token():
    """Token Zalo chi song 25 gio. Task chay cach nhau 1 ngay -> LUON het han.
    Phai refresh truoc moi lan dang. Refresh token dung 1 lan roi xoay vong,
    nen phai ghi de CA HAI vao state. Backup truoc khi ghi."""
    d = json.load(io.open(STATE, encoding="utf-8"))
    shutil.copy2(STATE, STATE + ".bak")
    try:
        r = requests.post(
            "https://oauth.zaloapp.com/v4/oa/access_token",
            headers={"secret_key": d["app_secret"],
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"refresh_token": d["refresh_token"], "app_id": d["app_id"],
                  "grant_type": "refresh_token"}, timeout=60)
        j = r.json()
    except Exception as e:
        ghi("refresh token LOI mang: %s -> dung token cu" % str(e)[:90])
        return d["access_token"]
    if "access_token" not in j:
        ghi("refresh token THAT BAI: %s -> dung token cu" % json.dumps(j, ensure_ascii=False)[:160])
        return d["access_token"]
    now = time.time()
    d["access_token"] = j["access_token"]
    d["refresh_token"] = j.get("refresh_token", d["refresh_token"])
    hsd = int(j.get("expires_in", 90000))
    d["token_lay_luc"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    d["token_het_han"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now + hsd))
    with io.open(STATE, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=1))
    ghi("da lam moi token, han moi: %s" % d["token_het_han"])
    return d["access_token"]


def lay_danh_sach(at):
    ds, off = [], 0
    while off < 300:
        r = requests.get(BASE + "getslice?offset=%d&limit=10&type=normal" % off,
                         headers={"access_token": at}, timeout=60).json()
        if r.get("error") != 0:
            raise RuntimeError("getslice loi: %s" % r.get("message"))
        m = (r.get("data") or {}).get("medias") or []
        ds += m
        if len(m) < 10:
            break
        off += 10
    return ds


def nap_bai(ma):
    """Tim bai trong 2 file draft. Tra ve (bai, url_anh_bia)."""
    cap = (("zalo_2bai_draft.json", "zalo_bia_url.json"),
           ("zalo_sp_draft.json", "zalo_bia_sp_url.json"))
    for f_bai, f_url in cap:
        p = os.path.join(OUT, f_bai)
        if not os.path.exists(p):
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        if ma in d:
            u = json.load(io.open(os.path.join(OUT, f_url), encoding="utf-8"))
            return d[ma], u[ma]
    raise SystemExit("khong tim thay bai '%s' trong file draft nao" % ma)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("thieu tham so: ten bai (vd galax, jonsbo, mesh, ssd...)")
    ma = sys.argv[1]
    an = len(sys.argv) > 2 and sys.argv[2].lower().lstrip("-") in ("an", "hide", "ẩn")
    mong_muon = "hide" if an else "show"

    bai, url = nap_bai(ma)

    ghi("=== BAT DAU dang bai %s (trang thai: %s) ===" % (ma, mong_muon))
    at = lam_moi_token()

    # 1. chong trung: bai cung tieu de da co thi dung
    truoc = lay_danh_sach(at)
    if any(chuan(a.get("title")) == chuan(bai["title"]) for a in truoc):
        ghi("BO QUA: bai '%s' DA CO tren OA, khong tao trung" % bai["title"][:50])
        return
    ghi("OA dang co %d bai truoc khi dang" % len(truoc))

    # 2. gan anh bia that
    bai = dict(bai)
    bai["cover"] = {"cover_type": "photo", "photo_url": url, "status": "show"}
    bai["status"] = mong_muon

    # 3. tao bai
    h = {"access_token": at, "Content-Type": "application/json"}
    r = requests.post(BASE + "create", headers=h,
                      data=json.dumps(bai).encode("utf-8"), timeout=120)
    res = r.json()
    if res.get("error") != 0:
        ghi("LOI tao bai: HTTP %s | %s" % (r.status_code, r.text[:300]))
        raise SystemExit(1)
    ghi("da gui yeu cau tao, HTTP %s, dang cho Zalo xu ly" % r.status_code)

    # 4. cho bai xuat hien roi doc lai de tu kiem
    moi = None
    for i in range(30):
        time.sleep(4)
        try:
            sau = lay_danh_sach(at)
        except Exception as e:
            ghi("  lan %d: doc lai loi %s" % (i + 1, str(e)[:80]))
            continue
        tim = [a for a in sau if chuan(a.get("title")) == chuan(bai["title"])]
        if tim:
            moi = tim[0]
            ghi("bai da len sau %d giay" % ((i + 1) * 4))
            break
        ghi("  lan %d: chua thay, cho tiep" % (i + 1))

    if not moi:
        ghi("CANH BAO: tao khong bao loi nhung chua thay bai. Kiem tay tren OA.")
        raise SystemExit(1)

    # 5. tu kiem noi dung that tren OA
    d = requests.get(BASE + "getdetail?id=%s&type=normal" % moi["id"],
                     headers={"access_token": at}, timeout=60).json()
    dt = d.get("data") or {}
    cov = (dt.get("cover") or {}).get("photo_url") or ""
    ghi("  id        : %s" % dt.get("id"))
    ghi("  tieu de   : %s" % (dt.get("title") or "")[:70])
    ghi("  trang thai: %s" % dt.get("status"))
    ghi("  so doan   : %d (soan %d)" % (len(dt.get("body") or []), len(bai["body"])))
    ghi("  anh bia   : %s" % (cov[:90] if cov else "TRONG"))
    ghi("  link xem  : %s" % (dt.get("link_view") or "?"))

    loi = []
    if dt.get("status") != mong_muon:
        loi.append("trang thai la '%s', dang can '%s'" % (dt.get("status"), mong_muon))
    if not cov:
        loi.append("thieu anh bia")
    if len(dt.get("body") or []) != len(bai["body"]):
        loi.append("so doan lech")
    ghi("TU KIEM: %s" % ("DAT" if not loi else "CO VAN DE -> " + "; ".join(loi)))
    ghi("=== XONG %s ===" % ma)


if __name__ == "__main__":
    main()
