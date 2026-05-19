"""Add cột M (checkbox 'Đã apply') + N (ngày apply) vào tab 2. URL Rewrite."""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

# Lấy sheet ID
meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
tab2 = next(s for s in meta["sheets"] if s["properties"]["title"] == TAB)
sid = tab2["properties"]["sheetId"]
n_rows = tab2["properties"]["gridProperties"]["rowCount"]

# Header M, N
svc.spreadsheets().values().update(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!M1:N1",
    valueInputOption="RAW", body={"values": [["Đã apply", "Ngày apply"]]},
).execute()
print("✓ Header M='Đã apply', N='Ngày apply'")

reqs = [
    # Header M N giống style Tab2 (xanh lá đậm)
    {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 12, "endColumnIndex": 14},
        "cell": {"userEnteredFormat": {
            "backgroundColor": {"red":0.13,"green":0.55,"blue":0.13},
            "textFormat": {"bold": True, "foregroundColor": {"red":1,"green":1,"blue":1}, "fontSize": 11},
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
        }},
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
    }},
    # Cột M: data validation BOOLEAN → render thành checkbox
    {"setDataValidation": {
        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 481,
                  "startColumnIndex": 12, "endColumnIndex": 13},
        "rule": {
            "condition": {"type": "BOOLEAN"},
            "strict": True, "showCustomUi": True,
        },
    }},
    # Cột M căn giữa
    {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 481,
                  "startColumnIndex": 12, "endColumnIndex": 13},
        "cell": {"userEnteredFormat": {
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
        }},
        "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment)",
    }},
    # Cột N format date dd/mm/yyyy + căn giữa
    {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 481,
                  "startColumnIndex": 13, "endColumnIndex": 14},
        "cell": {"userEnteredFormat": {
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "numberFormat": {"type": "DATE", "pattern": "dd/MM/yyyy"},
        }},
        "fields": "userEnteredFormat(horizontalAlignment,verticalAlignment,numberFormat)",
    }},
    # Width M = 100, N = 130
    {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 12, "endIndex": 13},
        "properties": {"pixelSize": 100}, "fields": "pixelSize",
    }},
    {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 13, "endIndex": 14},
        "properties": {"pixelSize": 130}, "fields": "pixelSize",
    }},
]
svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": reqs}).execute()
print("✓ Checkbox + format căn giữa applied (M2:M481)")

print("\n" + "="*70)
print("⚠ BƯỚC TIẾP — vợ paste script Apps Script (1 lần duy nhất):")
print("="*70)
print("""
1. Mở sheet → menu **Extensions** → **Apps Script**
2. Xóa nội dung sẵn (function myFunction...) → paste đoạn dưới đây:

----- COPY TỪ ĐÂY -----
function onEdit(e) {
  const sheet = e.range.getSheet();
  if (sheet.getName() !== "2. URL Rewrite") return;
  if (e.range.getColumn() !== 13) return;          // chỉ trigger khi sửa cột M
  if (e.range.getRow() < 2) return;                // bỏ header
  const dateCell = sheet.getRange(e.range.getRow(), 14);  // cột N
  if (e.value === "TRUE") {
    dateCell.setValue(new Date());
  } else {
    dateCell.clearContent();
  }
}
----- COPY TỚI ĐÂY -----

3. Bấm icon **💾 Save** (hoặc Ctrl+S)
4. Bấm nút **Run** (▶) lần đầu → popup xin permission → Allow
5. Đóng tab Apps Script, quay lại sheet
6. Test: tick 1 checkbox bất kỳ ở cột M → cột N tự ra ngày hôm nay 🎉
""")
