"""Tick TRUE cột M cho TẤT CẢ row có URL hợp lệ (skip '404 - bỏ qua').
Cột N = today.
"""
import os, sys
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O", majorDimension="ROWS",
).execute()
rows = res.get("values", [])[1:]

def cell(r, idx):
    return r[idx] if idx < len(r) else ""

today = datetime.now().strftime("%Y-%m-%d")
updates = []
already_ticked = 0
new_ticks = 0
skipped_404 = 0
skipped_invalid = 0

for i, r in enumerate(rows, start=2):
    if cell(r, 11) == "404 - bỏ qua":
        skipped_404 += 1
        continue
    url = cell(r, 1)
    if not url.startswith("http"):
        skipped_invalid += 1
        continue
    titles = [cell(r, 5), cell(r, 6), cell(r, 7)]
    metas  = [cell(r, 8), cell(r, 9), cell(r, 10)]
    if not any(t.strip() for t in titles) or not any(m.strip() for m in metas):
        skipped_invalid += 1
        continue
    if cell(r, 12) == "TRUE":
        already_ticked += 1
        continue
    updates.append({
        "range": f"'{TAB}'!M{i}:N{i}",
        "values": [[True, today]],
    })
    new_ticks += 1

print(f"Tổng row valid:       {already_ticked + new_ticks}")
print(f"  Đã TRUE từ trước:   {already_ticked}")
print(f"  Tick TRUE mới:      {new_ticks}")
print(f"Skip 404:             {skipped_404}")
print(f"Skip invalid/empty:   {skipped_invalid}")

if updates:
    svc.spreadsheets().values().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={"valueInputOption":"USER_ENTERED","data":updates},
    ).execute()
    print(f"\n✅ Tick TRUE thêm {len(updates)} row")
else:
    print("\n(Không có gì để tick)")
