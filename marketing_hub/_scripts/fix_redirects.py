"""Sua 301 SAI DICH -> dich LIEN QUAN (phuong an A cua ke hoach hoi phuc traffic).

BOI CANH (13/7/2026): 224 bai "huong dan cai dat phan mem" tung mang ~37.000 click/16 thang.
Dev cu xoa bai va 301 TAT CA ve /blogs/huong-dan (trang DANH SACH blog).
=> Google coi la soft-404: KHONG chuyen giao thu hang, trang bay khoi index.
=> Ca site tut theo (hang TB 9.8 -> 20.3, click 1097 -> 195/tuan).

Luat Google: 301 chi chuyen giao suc manh khi dich LIEN QUAN VE NOI DUNG.
Tro het ve trang danh sach = vut di.

Backup: nox-outputs/haravan_redirects.json (toan bo 1138 redirect truoc khi sua).

Chay:  py -3.12 _scripts/fix_redirects.py        # xem truoc
       py -3.12 _scripts/fix_redirects.py --go   # sua that
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import requests

import haravan_blog as hb

BACKUP = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\haravan_redirects.json")
BLOG_LIST = ("/blogs/huong-dan", "/blogs/news", "/blogs")

# Dich theo phan mem — trang LIEN QUAN THAT, khong tro bua
RULES = [
    (r"office|word|excel|powerpoint",
     "/blogs/huong-dan/office-2021-ban-quyen-khac-gi-office-crack-khi-dung-cho-cong-viec-hang-ngay"),
    (r"autocad|photoshop|premiere|illustrator|after-effects|indesign|lightroom|coreldraw|"
     r"audition|animate|dreamweaver|media-encoder|acrobat|adobe|bridge-cc|3ds-?max|sketchup|revit",
     "/blogs/huong-dan/build-pc-do-hoa"),
    (r"windows|win-?1[01]|ghost", "/collections/cai-dat-windows-phan-mem"),
    (r"psu|nguon-may-tinh", "/collections/psu-nguon"),
    (r"steam|game", "/collections/pc-gaming"),
]
# KHONG co FALLBACK. Tro bua ve mot collection chung = LAI TAO RA dung cai loi dang di sua
# (Google coi la soft-404). URL nao khong khop luat -> BAO CAO cho vo xu ly rieng, khong dung.


def target_for(path: str):
    p = path.lower()
    for pat, tg in RULES:
        if re.search(pat, p):
            return tg
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    dry = not a.go

    reds = json.loads(BACKUP.read_text(encoding="utf-8"))
    bad = [r for r in reds if r["target"].rstrip("/") in BLOG_LIST]
    print(f"=== {'XEM TRƯỚC' if dry else 'SỬA THẬT'} — {len(bad)} chuyển hướng sai đích ===\n")

    H, B = hb._headers(), hb._base()
    plan, skip = {}, []
    for r in bad:
        tg = target_for(r["path"])
        if not tg:
            skip.append(r)
            continue
        plan.setdefault(tg, []).append(r)

    for tg, items in sorted(plan.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(items):>2} URL  ->  {tg}")
        for r in items[:3]:
            print(f"        {r['path'][:66]}")
        if len(items) > 3:
            print(f"        ... và {len(items)-3} URL nữa")
    if skip:
        print(f"\n  ⚠ {len(skip)} URL KHÔNG khớp luật -> GIỮ NGUYÊN, vợ xem xử lý riêng:")
        for r in skip:
            print(f"        {r['path'][:66]}")
    print()

    if dry:
        print("Chạy lại với --go để sửa thật.")
        return 0

    ok = fail = 0
    for r in bad:
        tg = target_for(r["path"])
        if not tg:
            continue
        try:
            resp = requests.put(f"{B}/redirects/{r['id']}.json", headers=H, timeout=30,
                                json={"redirect": {"id": r["id"], "path": r["path"], "target": tg}})
            if resp.status_code in (200, 201):
                ok += 1
            else:
                # Haravan hay tra loi gia -> GET lai kiem chung
                chk = requests.get(f"{B}/redirects/{r['id']}.json", headers=H, timeout=30)
                if chk.status_code == 200 and chk.json().get("redirect", {}).get("target") == tg:
                    ok += 1
                else:
                    fail += 1
                    print(f"  LỖI HTTP {resp.status_code}: {r['path'][:50]}")
        except Exception as e:
            fail += 1
            print(f"  LỖI {type(e).__name__}: {r['path'][:50]}")
        time.sleep(0.4)

    print(f"\n[XONG] sửa {ok} · lỗi {fail}")
    print("  -> Verify: py -3.12 _scripts/fix_redirects.py  (xem còn cái nào sai đích không)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
