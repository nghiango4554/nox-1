"""Tô vàng nguyên dòng các row có status '404 - bỏ qua' hoặc tương tự trong sheet '2. URL Rewrite'."""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"
SHEET_GID = 2026751490

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

print("Đang đọc sheet...")
res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O", majorDimension="ROWS",
).execute()
rows = res.get("values", [])

target = []
for i, r in enumerate(rows):
    status = (r[11] if len(r) > 11 else "").lower()
    if "404" in status or "bỏ qua" in status or "lỗi" in status:
        target.append(i)

print(f"Tìm thấy {len(target)} dòng 404/lỗi")
if not target:
    sys.exit(0)

YELLOW = {"red": 1.0, "green": 0.949, "blue": 0.6}
requests = []
for idx in target:
    requests.append({
        "repeatCell": {
            "range": {
                "sheetId": SHEET_GID,
                "startRowIndex": idx,
                "endRowIndex": idx + 1,
                "startColumnIndex": 0,
                "endColumnIndex": 15,
            },
            "cell": {"userEnteredFormat": {"backgroundColor": YELLOW}},
            "fields": "userEnteredFormat.backgroundColor",
        }
    })

svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": requests}).execute()
print(f"✓ Đã tô vàng {len(requests)} dòng trong sheet '{TAB}'")
print("Sample rows (1-indexed):", [i + 1 for i in target[:10]])
