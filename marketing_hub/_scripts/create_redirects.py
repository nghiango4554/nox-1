"""Tao 301 cho cac URL tung co traffic ma nay 404 va CHUA co redirect nao.

Bo sung cho fix_redirects.py (cai do chi SUA redirect sai dich dang co).
Vi du that: bai Acrobat Pro DC 2021 (5.685 click) — 404, khong he co redirect => mat trang.

Dich lay tu cung bo RULES cua fix_redirects (khong tro bua; khong khop luat thi BO QUA).

Chay:  py -3.12 _scripts/create_redirects.py        # xem truoc
       py -3.12 _scripts/create_redirects.py --go
"""
import argparse
import datetime
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import haravan_blog as hb
from fix_redirects import BACKUP, target_for

TOKEN = r"C:\Users\NGHIANGO\.openclaw\workspace\gsc\token.json"
UA = {"User-Agent": "Mozilla/5.0"}
MIN_CLICK = 3   # duoi muc nay khong dang tao redirect


def gsc_pages():
    creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/webmasters"])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    end = datetime.date.today() - datetime.timedelta(days=2)
    start = end - datetime.timedelta(days=479)
    rows = svc.searchanalytics().query(siteUrl="sc-domain:sintech.vn", body={
        "startDate": start.isoformat(), "endDate": end.isoformat(),
        "dimensions": ["page"], "rowLimit": 25000}).execute().get("rows", [])
    return {r["keys"][0]: r["clicks"] for r in rows if r["clicks"] >= MIN_CLICK}


def is_dead(u):
    """⚠️ Haravan chan toc do (429) -> phai kien nhan retry, khong thi URL chet bi BO SOT
    (bai Acrobat 5.685 click suyt lot luoi vi ly do nay)."""
    for attempt in range(6):
        try:
            r = requests.get(u, headers=UA, timeout=30, allow_redirects=False)
            if r.status_code == 429:
                time.sleep(10 + attempt * 5)
                continue
            return u, r.status_code
        except Exception:
            time.sleep(3)
    return u, 429


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    dry = not a.go

    have = {r["path"] for r in json.loads(BACKUP.read_text(encoding="utf-8"))}
    pages = gsc_pages()
    print(f"GSC: {len(pages)} URL từng có ≥{MIN_CLICK} click (16 tháng)")

    # chi xet URL CHUA co redirect va co dich hop luat
    cand = [(u, c) for u, c in pages.items()
            if u.replace("https://sintech.vn", "") not in have
            and target_for(u.replace("https://sintech.vn", ""))]
    print(f"Trong đó {len(cand)} URL chưa có redirect + khớp luật đích. Đang kiểm HTTP...")

    with ThreadPoolExecutor(max_workers=2) as ex:   # cham lai, tranh 429
        st = dict(ex.map(is_dead, [u for u, _ in cand]))

    blocked = [u for u, _ in cand if st[u] == 429]
    if blocked:
        print(f"  ⚠ {len(blocked)} URL vẫn bị Haravan chặn (429) — CHƯA biết sống/chết, chạy lại sau")
    dead = sorted([(u, c, st[u]) for u, c in cand if st[u] in (404, 410)], key=lambda x: -x[1])
    print(f"\n=== {len(dead)} URL CHẾT chưa có redirect (tổng {sum(d[1] for d in dead)} click) ===\n")
    for u, c, _ in dead[:25]:
        p = u.replace("https://sintech.vn", "")
        print(f"  {c:>6} click · {p[:52]}")
        print(f"          -> {target_for(p)}")
    if len(dead) > 25:
        print(f"  ... và {len(dead)-25} URL nữa")

    if dry:
        print("\nChạy lại với --go để tạo thật.")
        return 0

    H, B = hb._headers(), hb._base()
    ok = fail = 0
    for u, c, _ in dead:
        p = u.replace("https://sintech.vn", "")
        tg = target_for(p)
        try:
            r = requests.post(f"{B}/redirects.json", headers=H, timeout=30,
                              json={"redirect": {"path": p, "target": tg}})
            if r.status_code in (200, 201):
                ok += 1
            else:
                fail += 1
                print(f"  LỖI {r.status_code}: {p[:56]} — {r.text[:70]}")
        except Exception as e:
            fail += 1
            print(f"  LỖI {type(e).__name__}: {p[:56]}")
        time.sleep(0.4)
    print(f"\n[XONG] tạo {ok} redirect · lỗi {fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
