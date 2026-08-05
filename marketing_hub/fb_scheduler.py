# -*- coding: utf-8 -*-
"""Lên lịch bài FB nhiều ảnh qua Graph API.

Cách chạy (từ thư mục nox-1):
    py marketing_hub/fb_scheduler.py --kiem            # chỉ kiểm token + lịch, KHÔNG tạo gì
    py marketing_hub/fb_scheduler.py --bai 1           # tạo lịch cho bài số 1
    py marketing_hub/fb_scheduler.py --bai 2-9         # tạo lịch bài 2 tới 9
    py marketing_hub/fb_scheduler.py --xem             # liệt kê bài đã lên lịch trên Trang

Cách hoạt động (chuẩn Graph API cho bài nhiều ảnh có hẹn giờ):
  1. Mỗi ảnh -> POST /{page}/photos  với published=false  -> nhận photo_id
  2. POST /{page}/feed với message + attached_media[i]={"media_fbid":id}
     + published=false + scheduled_publish_time=<unix>
  Meta tự đăng đúng giờ. Giờ hẹn phải cách hiện tại 10 phút tới 6 tháng.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

VN = timezone(timedelta(hours=7))
G = "https://graph.facebook.com/v25.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # …/nox-1
WS = os.path.dirname(ROOT)                                             # …/workspace
STATE = os.path.join(ROOT, "state")
KE_HOACH = os.path.join(WS, "nox-outputs", "_lich_dang_fb.json")


def doc_token() -> tuple:
    """Trả (page_id, token). Ưu tiên facebook_token.json, fallback file tạm."""
    f = os.path.join(STATE, "facebook_token.json")
    if os.path.exists(f):
        c = json.load(open(f, encoding="utf-8"))
        return c["page_id"], c["page_token"]
    t = open(os.path.join(STATE, "_fb_tmp.txt"), encoding="utf-8").read().strip()
    return "301535036384702", t


PAGE, TOKEN = doc_token()


def gio_unix(chuoi: str) -> int:
    """'4/8 20:00' -> unix timestamp theo giờ VN. Tự suy ra năm hiện tại."""
    ngay, gio = chuoi.split()
    d, m = [int(x) for x in ngay.split("/")]
    h, mi = [int(x) for x in gio.split(":")]
    nam = datetime.now(VN).year
    return int(datetime(nam, m, d, h, mi, tzinfo=VN).timestamp())


def kiem_token() -> bool:
    r = requests.get(f"{G}/debug_token", params={"input_token": TOKEN, "access_token": TOKEN}, timeout=30)
    d = r.json().get("data", {})
    sc = d.get("scopes", [])
    ea = d.get("expires_at", 0)
    print(f"  loại token : {d.get('type')} · app {d.get('application')}")
    han = "không bao giờ" if ea == 0 else datetime.fromtimestamp(ea, VN).strftime("%d/%m %H:%M")
    print(f"  hết hạn    : {han}")
    thieu = [q for q in ("pages_manage_posts", "pages_read_engagement") if q not in sc]
    print(f"  quyền      : {'ĐỦ' if not thieu else 'THIẾU ' + ', '.join(thieu)}")
    r2 = requests.get(f"{G}/{PAGE}", params={"fields": "id,name", "access_token": TOKEN}, timeout=30)
    if r2.status_code == 200:
        print(f"  trang      : {r2.json().get('name')} (id {PAGE})")
    else:
        print(f"  trang      : LỖI {r2.status_code} {str(r2.json())[:110]}")
        return False
    return not thieu


def up_anh(duong_dan: str) -> str:
    """Upload 1 ảnh ở trạng thái CHƯA ĐĂNG, trả photo_id."""
    with open(duong_dan, "rb") as f:
        r = requests.post(f"{G}/{PAGE}/photos",
                          data={"published": "false", "access_token": TOKEN},
                          files={"source": f}, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"upload lỗi {r.status_code}: {str(r.json())[:220]}")
    return r.json()["id"]


def len_lich(caption: str, anh: list, khi: int) -> str:
    """Tạo bài nhiều ảnh có hẹn giờ. Trả post_id."""
    ids = []
    for i, a in enumerate(anh, 1):
        pid = up_anh(a)
        ids.append(pid)
        print(f"        ảnh {i}/{len(anh)} -> {pid}")
        time.sleep(0.6)
    data = {"message": caption, "published": "false",
            "scheduled_publish_time": str(khi), "access_token": TOKEN}
    for i, pid in enumerate(ids):
        data[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
    r = requests.post(f"{G}/{PAGE}/feed", data=data, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"tạo bài lỗi {r.status_code}: {str(r.json())[:260]}")
    return r.json()["id"]


def xem_lich():
    r = requests.get(f"{G}/{PAGE}/scheduled_posts",
                     params={"fields": "id,message,scheduled_publish_time", "limit": 50,
                             "access_token": TOKEN}, timeout=30)
    if r.status_code != 200:
        print(f"  LỖI {r.status_code}: {str(r.json())[:200]}")
        return
    ds = r.json().get("data", [])
    print(f"  {len(ds)} bài đang hẹn giờ trên Trang:")
    for p in sorted(ds, key=lambda x: x.get("scheduled_publish_time", 0)):
        t = p.get("scheduled_publish_time")
        khi = datetime.fromtimestamp(t, VN).strftime("%d/%m %H:%M") if t else "?"
        m = (p.get("message") or "").split("\n")[0][:52]
        print(f"    · {khi}  {m}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kiem", action="store_true", help="chỉ kiểm tra, không tạo gì")
    ap.add_argument("--xem", action="store_true", help="liệt kê bài đã hẹn giờ")
    ap.add_argument("--bai", help="số bài, vd 1 hoặc 2-9")
    a = ap.parse_args()

    print("=== KIỂM TOKEN ===")
    ok = kiem_token()
    if not ok:
        print("\n>>> Token không đủ quyền, DỪNG.")
        sys.exit(1)

    if a.xem:
        print("\n=== LỊCH HIỆN CÓ ===")
        xem_lich()
        return
    if a.kiem or not a.bai:
        ke = json.load(open(KE_HOACH, encoding="utf-8"))
        print(f"\n=== KẾ HOẠCH {len(ke)} BÀI (chưa tạo gì) ===")
        for b in ke:
            khi = gio_unix(b["lich"])
            con = (khi - time.time()) / 3600
            print(f"  {b['stt']:>2}. {b['lich']:<11} (còn {con:5.1f}h)  {len(b['anh'])} ảnh · {b['tieu_de'][:42]}")
        print("\n>>> Thêm --bai 1 để tạo lịch bài 1.")
        return

    ke = json.load(open(KE_HOACH, encoding="utf-8"))
    if "-" in a.bai:
        d, c = [int(x) for x in a.bai.split("-")]
        chon = [b for b in ke if d <= b["stt"] <= c]
    else:
        chon = [b for b in ke if b["stt"] == int(a.bai)]

    print(f"\n=== TẠO LỊCH {len(chon)} BÀI ===")
    xong = []
    for b in chon:
        khi = gio_unix(b["lich"])
        con = (khi - time.time()) / 60
        print(f"\n  Bài {b['stt']} · {b['lich']} (còn {con:.0f} phút) · {b['tieu_de'][:40]}")
        if con < 12:
            print("     BỎ QUA: giờ hẹn phải cách hiện tại ít nhất 10 phút")
            continue
        cap = open(b["caption"], encoding="utf-8").read().strip()
        try:
            pid = len_lich(cap, b["anh"], khi)
            print(f"     ĐÃ LÊN LỊCH -> post_id {pid}")
            xong.append({"stt": b["stt"], "post_id": pid, "lich": b["lich"]})
        except Exception as e:
            print(f"     LỖI: {str(e)[:240]}")

    if xong:
        p = os.path.join(WS, "nox-outputs", "_fb_da_len_lich.json")
        cu = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
        json.dump(cu + xong, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n>>> Đã lưu {len(xong)} bài vào _fb_da_len_lich.json")
    print("\n=== ĐỌC LẠI LỊCH TRÊN TRANG ĐỂ KIỂM CHỨNG ===")
    time.sleep(3)
    xem_lich()


if __name__ == "__main__":
    main()
