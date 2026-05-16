"""Insert cột mới 'Chồng iu tự điền' (checkbox) TRƯỚC cột M hiện tại.
Layout sau insert:
  L = Trạng thái
  M (mới) = Chồng iu tự điền (checkbox)
  N = Đã apply (checkbox cũ M)
  O = Ngày apply (cột N cũ)
"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
tab2 = next(s for s in meta["sheets"] if s["properties"]["title"] == TAB)
sid = tab2["properties"]["sheetId"]

# Insert 1 column at index 12 (col M)
reqs = [
    {"insertDimension": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 12, "endIndex": 13},
        "inheritFromBefore": False,
    }},
]
svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": reqs}).execute()
print("✓ Inserted column at M")

# Set header M
svc.spreadsheets().values().update(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!M1",
    valueInputOption="RAW", body={"values": [["Chồng iu tự điền"]]},
).execute()
print("✓ Header M = 'Chồng iu tự điền'")

# Format cột M: header xanh + checkbox + căn giữa + width
reqs = [
    # Header M style (xanh dương để phân biệt với header xanh lá)
    {"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                  "startColumnIndex": 12, "endColumnIndex": 13},
        "cell": {"userEnteredFormat": {
            "backgroundColor": {"red":0.95,"green":0.4,"blue":0.6},  # hồng cute
            "textFormat": {"bold": True, "foregroundColor": {"red":1,"green":1,"blue":1}, "fontSize": 11},
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
            "wrapStrategy": "WRAP",
        }},
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
    }},
    # Cột M data: BOOLEAN (checkbox)
    {"setDataValidation": {
        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 481,
                  "startColumnIndex": 12, "endColumnIndex": 13},
        "rule": {"condition": {"type": "BOOLEAN"}, "strict": True, "showCustomUi": True},
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
    # Width M = 130
    {"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 12, "endIndex": 13},
        "properties": {"pixelSize": 130}, "fields": "pixelSize",
    }},
    # Conditional format cột M = TRUE → highlight cả dòng cột M-O xanh nhạt
    {"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": sid, "startRowIndex": 1, "startColumnIndex": 12, "endColumnIndex": 13}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "TRUE"}]},
            "format": {"backgroundColor": {"red":0.7,"green":1.0,"blue":0.7}, "textFormat": {"bold": True}},
        },
    }, "index": 0}},
]
svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": reqs}).execute()
print("✓ Format checkbox + width applied")

print("\n" + "="*70)
print("⚠ VỢ CẦN UPDATE Apps Script (vì cột đã shift)")
print("="*70)
print("""
1. Mở sheet → Extensions → Apps Script
2. THAY TOÀN BỘ code cũ bằng đoạn dưới đây:

----- COPY TỪ ĐÂY -----
function onEdit(e) {
  const sheet = e.range.getSheet();
  if (sheet.getName() !== "2. URL Rewrite") return;
  if (e.range.getRow() < 2) return;
  const col = e.range.getColumn();
  // Cột N (14) = "Đã apply" → tick xong thì set cột O (15) ngày
  if (col === 14) {
    const dateCell = sheet.getRange(e.range.getRow(), 15);
    if (e.value === "TRUE") {
      dateCell.setValue(new Date());
    } else {
      dateCell.clearContent();
    }
  }
}
----- COPY TỚI ĐÂY -----

3. Save (Ctrl+S) → Run lần đầu (▶) → Allow nếu hỏi
""")
print("\n✅ DONE. Layout mới:")
print("   L = Trạng thái")
print("   M = Chồng iu tự điền (checkbox hồng) ← VỢ TICK URL CẦN SYNC")
print("   N = Đã apply (checkbox xanh) ← ANH TICK SAU KHI SYNC HARAVAN XONG")
print("   O = Ngày apply (auto)")
