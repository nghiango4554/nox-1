"""Kiem 620 URL trong tab "404" cua sheet Audit -> ghi trang thai HIEN TAI nguoc len sheet.

Sau khi sua redirect hom nay (13/7), nhieu URL trong danh sach nay co the da song/301.
Muc dich: biet CON BAO NHIEU 404 THAT + cai nao dang tien (tung co click).

Cot ghi them:
  C: Trạng thái hiện tại (200 / 301 → đích / 404 / 410)
  D: Đích chuyển hướng
  E: Click (16 tháng, GSC)
  F: Đề xuất

⚠️ Haravan chan toc do (429) -> retry kien nhan, khong thi URL song bi bao 404 oan.

Chay:  py -3.12 _scripts/check_404_sheet.py
"""
import datetime
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, r"C:\Users\NGHIANGO\.openclaw\workspace")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import gsheet_client
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SH = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "404"
TOKEN = r"C:\Users\NGHIANGO\.openclaw\workspace\gsc\token.json"
UA = {"User-Agent": "Mozilla/5.0"}


def gsc_clicks():
    c = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/webmasters"])
    if c.expired and c.refresh_token:
        c.refresh(Request())
    svc = build("searchconsole", "v1", credentials=c, cache_discovery=False)
    end = datetime.date.today() - datetime.timedelta(days=2)
    start = end - datetime.timedelta(days=479)
    rows = svc.searchanalytics().query(siteUrl="sc-domain:sintech.vn", body={
        "startDate": start.isoformat(), "endDate": end.isoformat(),
        "dimensions": ["page"], "rowLimit": 25000}).execute().get("rows", [])
    return {r["keys"][0].rstrip("/"): r["clicks"] for r in rows}


def check(u):
    for attempt in range(6):
        try:
            r = requests.get(u, headers=UA, timeout=30, allow_redirects=False)
            if r.status_code == 429:
                time.sleep(8 + attempt * 4)
                continue
            loc = r.headers.get("Location", "")
            return u, r.status_code, loc.replace("https://sintech.vn", "")
        except Exception as e:
            if attempt == 5:
                return u, -1, type(e).__name__
            time.sleep(3)
    return u, 429, ""


def main():
    svc = gsheet_client.get_service()
    vals = svc.spreadsheets().values().get(spreadsheetId=SH, range=f"'{TAB}'!A2:A").execute().get("values", [])
    urls = [v[0].strip() for v in vals if v and v[0].strip().startswith("http")]
    print(f"{len(urls)} URL trong tab '{TAB}'")

    clicks = gsc_clicks()
    print(f"GSC: {len(clicks)} URL có dữ liệu click\n")

    print("Đang kiểm HTTP (chậm để tránh 429)...")
    with ThreadPoolExecutor(max_workers=3) as ex:
        res = list(ex.map(check, urls))

    BLOG_LIST = ("/blogs/huong-dan", "/blogs/news", "/blogs", "")
    rows, stat = [], {}
    for u, code, loc in res:
        clk = clicks.get(u.rstrip("/"), 0)
        if code == 200:
            st, sug = "200 SỐNG", "Không phải 404 nữa — bỏ khỏi danh sách"
        elif code in (301, 302):
            if loc.rstrip("/") in BLOG_LIST:
                st, sug = f"{code} → trang danh sách", "⚠️ SAI ĐÍCH — Google coi là soft-404, cần đổi đích liên quan"
            else:
                st, sug = f"{code} → {loc[:40]}", "OK — đã chuyển hướng đúng"
        elif code in (404, 410):
            st = f"{code} CHẾT"
            sug = ("⚠️ CẦN 301 (từng có click)" if clk >= 3
                   else "Bỏ qua — chưa từng có traffic")
        elif code == 429:
            st, sug = "429 bị chặn", "Chưa rõ — chạy lại sau"
        else:
            st, sug = f"{code}", "Kiểm tay"
        stat[st.split()[0]] = stat.get(st.split()[0], 0) + 1
        rows.append([st, loc, clk, sug])

    svc.spreadsheets().values().update(
        spreadsheetId=SH, range=f"'{TAB}'!C1",
        valueInputOption="RAW",
        body={"values": [["Trạng thái hiện tại", "Đích chuyển hướng", "Click (16 tháng)", "Đề xuất"]] + rows}
    ).execute()

    print("\n=== TỔNG KẾT ===")
    for k, v in sorted(stat.items(), key=lambda kv: -kv[1]):
        print(f"  {k:>6}: {v} URL")

    need = [(u, c, s) for (u, code, loc), (s, l, c, sg) in zip(res, rows)
            if code in (404, 410) and c >= 3]
    need.sort(key=lambda x: -x[1])
    print(f"\n=== {len(need)} URL CHẾT còn đáng cứu (≥3 click) ===")
    for u, c, _ in need[:20]:
        print(f"  {c:>5} click · {u.replace('https://sintech.vn','')[:62]}")
    print(f"\n[XONG] đã ghi trạng thái lên tab '{TAB}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
