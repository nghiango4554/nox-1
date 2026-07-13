"""Don not redirect sai huong (sau audit_redirects.py).

3 viec:
1. CHUOI 301 -> 301 (17 cai): SP cu -> SP moi (da go) -> collection.
   Google phai nhay 2 lan, loang tin hieu. => Tro THANG ve dich cuoi.
2. DICH LA TRANG DANH SACH co click: bai da xoa -> tro ve dich LIEN QUAN.
   (bai 'cach cai dat drivers' 25 click -> danh muc cai Windows & phan mem)
3. REDIRECT RAC che bai CON SONG: Haravan khong ap redirect khi URL ton tai
   (bai macbook van 200) -> redirect do vo hai nhung thua, XOA cho sach.

Chay:  py -3.12 _scripts/fix_redirect_chains.py        # xem truoc
       py -3.12 _scripts/fix_redirect_chains.py --go
"""
import argparse
import json
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

UA = {"User-Agent": "Mozilla/5.0"}
BACKUP = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\haravan_redirects.json")
LIST_PAGES = {"/blogs/huong-dan", "/blogs/news", "/blogs", "/collections", "/collections/all", "/"}

# Bai da xoa -> dich LIEN QUAN (khong tro bua)
RETARGET = {
    "/blogs/news/cach-cai-dat-drivers-day-du-cho-pc-laptop": "/collections/cai-dat-windows-phan-mem",
}


def get(u):
    for i in range(6):
        try:
            r = requests.get("https://sintech.vn" + u, headers=UA, timeout=30, allow_redirects=False)
            if r.status_code == 429:
                time.sleep(8 + i * 4)
                continue
            return r.status_code, r.headers.get("Location", "").replace("https://sintech.vn", "")
        except Exception:
            time.sleep(3)
    return 429, ""


def final_target(t, depth=5):
    """Di het chuoi redirect -> tra ve dich CUOI (200)."""
    seen = set()
    for _ in range(depth):
        if t in seen:
            return None
        seen.add(t)
        code, loc = get(t)
        if code == 200:
            return t
        if code in (301, 302) and loc:
            t = loc
            continue
        return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    dry = not a.go

    H, B = hb._headers(), hb._base()
    reds = json.loads(BACKUP.read_text(encoding="utf-8"))
    plan = []

    print("Đang lần theo từng chuỗi chuyển hướng...\n")
    for r in reds:
        p, t = r["path"], r["target"]

        if p in RETARGET:
            plan.append(("ĐỔI ĐÍCH (bài đã xoá)", r, RETARGET[p]))
            continue

        code, loc = get(t)
        if code in (301, 302) and loc:          # chuoi
            fin = final_target(loc)
            if fin and fin != t:
                plan.append(("TRỎ THẲNG (bỏ chuỗi)", r, fin))
        elif t.rstrip("/") in LIST_PAGES:
            src_code, _ = get(p)
            if src_code == 200:                 # URL nguon CON SONG -> redirect thua
                plan.append(("XOÁ (che bài còn sống)", r, None))

    print(f"=== {'XEM TRƯỚC' if dry else 'SỬA THẬT'} — {len(plan)} redirect ===\n")
    for kind, r, new in plan:
        print(f"  [{kind}]")
        print(f"     {r['path'][:62]}")
        print(f"     {r['target'][:50]}  →  {new or '(xoá)'}")

    if dry:
        print("\nChạy lại với --go để sửa thật.")
        return 0

    ok = fail = 0
    for kind, r, new in plan:
        try:
            if new is None:
                resp = requests.delete(f"{B}/redirects/{r['id']}.json", headers=H, timeout=30)
            else:
                resp = requests.put(f"{B}/redirects/{r['id']}.json", headers=H, timeout=30,
                                    json={"redirect": {"id": r["id"], "path": r["path"], "target": new}})
            if resp.status_code in (200, 201, 204):
                ok += 1
            else:
                chk = requests.get(f"{B}/redirects/{r['id']}.json", headers=H, timeout=30)
                if (new is None and chk.status_code == 404) or \
                   (new and chk.status_code == 200 and chk.json().get("redirect", {}).get("target") == new):
                    ok += 1
                else:
                    fail += 1
                    print(f"  LỖI {resp.status_code}: {r['path'][:48]}")
        except Exception as e:
            fail += 1
            print(f"  LỖI {type(e).__name__}: {r['path'][:48]}")
        time.sleep(0.4)

    print(f"\n[XONG] sửa/xoá {ok} · lỗi {fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
