"""Dung 1 chien dich Meta + 3 nhom quang cao + 3 quang cao cho chuong trinh HSSV.

TAT CA deu o trang thai PAUSED. Script nay KHONG bao gio bat ACTIVE.

Chay thu truoc (khong tao gi):   py fb_tao_campaign_hssv.py --thu
Tao that:                        py fb_tao_campaign_hssv.py --tao

⚠️ Can quyen ADVERTISE tren tai khoan quang cao act_751860640427844.
   Tinh toi 14/08/2026 tai khoan Nghia Ngo CHUA duoc gan quyen nay
   -> API tra loi 400 "Nguoi dung khong co quyen tao quang cao" (subcode 1815066).
   Sua o: Business Settings > Tai khoan quang cao > Them nguoi > tick "Quan ly chien dich".
"""

import argparse
import json
import sys
import io
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

G = "https://graph.facebook.com/v21.0"
TOKEN_PATH = Path(__file__).resolve().parent.parent.parent / "state" / "fb_token.json"
ACT = "act_751860640427844"
PAGE = "301535036384702"

# 3 bai da dang tren Trang, moi bai mot goc noi dung khac nhau
BAI = [
    ("uu-dai-PC", "301535036384702_122231288870341726", "Uu dai PC HSSV, uu dai nhieu tang"),
    ("uu-dai-laptop", "301535036384702_122232207740341726", "Uu dai laptop rieng HSSV"),
    # LUU Y: reel co video_id rieng (1942403037144697) KHAC voi post_id.
    # object_story_id phai dung POST_ID, lay bang GET /{video_id}?fields=post_id
    ("reel-RTX5090", "301535036384702_122231728340341726", "Video ban giao PC RTX 5090, goc tay nghe"),
]

NGAN_SACH_TEST = 66_667   # dong / ngay / nhom quang cao (vong test 3 ngay, 3 bai = 600.000d)

TARGETING = {
    "geo_locations": {"countries": ["VN"]},
    "age_min": 18,
    "age_max": 44,
    # Sintech KHONG dung Instagram -> chi chay Facebook. Vo chot 14/8/2026.
    # KHONG khai them facebook_positions: Meta tra "Invalid parameter" voi
    # destination MESSENGER. De trong cho Meta tu chon vi tri hop le.
    "publisher_platforms": ["facebook"],
    # advantage_audience = 0: TAT tinh nang tu mo rong tep cua Meta.
    # Bat len thi moi nhom co the chay tren mot tep khac nhau, luc do khac biet
    # giua 3 bai khong con la khac biet noi dung -> hong phep so sanh.
    "targeting_automation": {"advantage_audience": 0},
}


def cfg():
    with open(TOKEN_PATH, encoding="utf-8") as f:
        return json.load(f)


def goi(duong_dan, payload, tok, thu):
    if thu:
        print(f"  [THU] POST /{duong_dan}")
        for k, v in payload.items():
            if k != "access_token":
                print(f"        {k} = {v}")
        return {"id": f"<se-tao-{duong_dan}>"}
    payload["access_token"] = tok
    r = requests.post(f"{G}/{duong_dan}", data=payload, timeout=60)
    if r.status_code >= 400:
        e = r.json().get("error", {})
        print(f"  LOI HTTP {r.status_code}: {e.get('error_user_msg') or e.get('message')}")
        sys.exit(1)
    return r.json()


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--thu", action="store_true", help="In ra se tao gi, KHONG goi API")
    g.add_argument("--tao", action="store_true", help="Tao that, tat ca deu PAUSED")
    ap.add_argument("--chien-dich", metavar="ID", default=None,
                    help="Dung lai chien dich da co thay vi tao moi (tranh tao trung)")
    a = ap.parse_args()
    thu = a.thu

    c = cfg()
    tok = c["user_access_token"]

    print("=" * 66)
    print("CHIEN DICH HSSV 2026 — vong test 3 bai" + ("  [CHAY THU]" if thu else ""))
    print(f"Tai khoan: {ACT} · Trang: {PAGE}")
    print(f"Ngan sach test: {NGAN_SACH_TEST:,}d/ngay/bai x 3 bai x 3 ngay = {NGAN_SACH_TEST*3*3:,}d")
    print("=" * 66)

    print("\n[1/3] Chien dich")
    if a.chien_dich:
        cid = a.chien_dich
        print(f"  -> dung lai chien dich da co: {cid}")
    else:
        cam = goi(f"{ACT}/campaigns", {
            "name": "HSSV 2026 | Test 3 bai | 15-17.08",
            "objective": "OUTCOME_ENGAGEMENT",
            "status": "PAUSED",
            "special_ad_categories": json.dumps([]),
            # Ngan sach dat o tang nhom quang cao. False = moi nhom giu tien rieng,
            # Meta KHONG duoc tu don tien sang bai thang som -> 3 bai duoc so sanh cong bang.
            "is_adset_budget_sharing_enabled": "false",
        }, tok, thu)
        cid = cam["id"]
        print(f"  -> campaign_id = {cid}")

    ket_qua = []
    for ten, post_id, mo_ta in BAI:
        print(f"\n[2/3] Nhom quang cao — {ten}")
        adset = goi(f"{ACT}/adsets", {
            "name": f"HSSV | {ten}",
            "campaign_id": cid,
            "daily_budget": NGAN_SACH_TEST,
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "LINK_CLICKS",
            # Dau thau tu dong, khong dat tran gia thau. Voi ngan sach nho thi
            # dat tran de lam Meta khong phan phoi duoc, tieu khong het tien.
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "destination_type": "MESSENGER",
            "promoted_object": json.dumps({"page_id": PAGE}),
            "targeting": json.dumps(TARGETING),
            "status": "PAUSED",
        }, tok, thu)
        print(f"  -> adset_id = {adset['id']}  ({mo_ta})")

        print(f"[3/3] Quang cao — {ten}")
        ad = goi(f"{ACT}/ads", {
            "name": f"HSSV | {ten}",
            "adset_id": adset["id"],
            # object_story_id = dung lai BAI DA DANG (giu nguyen like/binh luan da co).
            # call_to_action MESSAGE_PAGE = nut mo Messenger. Thieu no thi Meta bao
            # "noi dung quang cao khong tuong thich voi muc tieu chien dich".
            "creative": json.dumps({
                "object_story_id": post_id,
                "call_to_action": {"type": "MESSAGE_PAGE",
                                   "value": {"app_destination": "MESSENGER"}},
            }),
            "status": "PAUSED",
        }, tok, thu)
        print(f"  -> ad_id = {ad['id']}")
        ket_qua.append((ten, adset["id"], ad["id"]))

    print("\n" + "=" * 66)
    print("XONG. Tat ca deu PAUSED, chua tieu dong nao.")
    for ten, s, q in ket_qua:
        print(f"  {ten:<16} adset={s}  ad={q}")
    if not thu:
        print("\nBuoc tiep: lay link xem truoc cua Meta dua vo xem, roi VO tu bat ACTIVE.")
        print("Script nay khong bat ACTIVE.")


if __name__ == "__main__":
    main()
