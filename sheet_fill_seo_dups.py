"""OAuth flow + fill 'SEO Duplicates' tab trong sheet 'Audit'.
Lần đầu chạy: mở browser cho vợ Allow consent → token cache local.
Lần sau: dùng token cache, không cần consent nữa.
"""
import os, sys, csv
sys.stdout.reconfigure(encoding="utf-8")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SECRETS_DIR = r"C:\Users\Nghia Dep Gai\.openclaw\workspace\.secrets"
OAUTH_FILE = os.path.join(SECRETS_DIR, "google_oauth.json")
TOKEN_FILE = os.path.join(SECRETS_DIR, "google_token.json")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB_NAME = "SEO Duplicates"
TSV_FILE = r"C:\Users\Nghia Dep Gai\.openclaw\workspace\seo_duplicates.tsv"


def get_creds():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_FILE, SCOPES)
            print("\n[!] OAuth flow: browser sẽ mở. Vợ chọn Gmail và bấm 'Allow' nha 🥰")
            creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"[+] Token saved -> {TOKEN_FILE}")
    return creds


def main():
    creds = get_creds()
    svc = build("sheets", "v4", credentials=creds)

    # Đọc TSV
    with open(TSV_FILE, encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    print(f"[*] TSV: {len(rows)} dòng (1 header + {len(rows)-1} data)")

    # Kiểm tra tab
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    tab = next((s for s in meta["sheets"] if s["properties"]["title"] == TAB_NAME), None)
    if not tab:
        print(f"[!] Tab '{TAB_NAME}' chưa tồn tại — tạo mới")
        req = {"requests": [{"addSheet": {"properties": {"title": TAB_NAME}}}]}
        svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body=req).execute()
        meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        tab = next(s for s in meta["sheets"] if s["properties"]["title"] == TAB_NAME)

    sheet_id = tab["properties"]["sheetId"]

    # Clear tab cũ
    svc.spreadsheets().values().clear(
        spreadsheetId=SHEET_ID, range=f"'{TAB_NAME}'"
    ).execute()
    print(f"[*] Cleared tab '{TAB_NAME}'")

    # Ghi data
    body = {"values": rows}
    res = svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB_NAME}'!A1",
        valueInputOption="RAW",
        body=body,
    ).execute()
    print(f"[+] Ghi {res.get('updatedRows')} dòng × {res.get('updatedColumns')} cột vào '{TAB_NAME}'")

    # Format: header bold + freeze + auto-resize + highlight số trang ≥10
    formatting = {
        "requests": [
            # Header bold + bg
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.26, "green": 0.52, "blue": 0.96},
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "horizontalAlignment": "CENTER",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            },
            # Freeze row 1
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            # Column widths
            {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 130}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2}, "properties": {"pixelSize": 350}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 2, "endIndex": 3}, "properties": {"pixelSize": 80}, "fields": "pixelSize"}},
            {"updateDimensionProperties": {"range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": 4}, "properties": {"pixelSize": 600}, "fields": "pixelSize"}},
            # Conditional format: số trang ≥10 → đỏ
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 3}],
                        "booleanRule": {
                            "condition": {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "10"}]},
                            "format": {
                                "backgroundColor": {"red": 0.95, "green": 0.45, "blue": 0.45},
                                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            },
                        },
                    },
                    "index": 0,
                }
            },
            # Conditional format: 5≤số trang<10 → cam
            {
                "addConditionalFormatRule": {
                    "rule": {
                        "ranges": [{"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 3}],
                        "booleanRule": {
                            "condition": {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "5"}]},
                            "format": {
                                "backgroundColor": {"red": 1, "green": 0.85, "blue": 0.4},
                                "textFormat": {"bold": True},
                            },
                        },
                    },
                    "index": 1,
                }
            },
            # Wrap text cho cột nội dung và URLs
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 1, "endColumnIndex": 2},
                    "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
                    "fields": "userEnteredFormat.wrapStrategy",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 1, "startColumnIndex": 3, "endColumnIndex": 4},
                    "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP"}},
                    "fields": "userEnteredFormat.wrapStrategy",
                }
            },
        ]
    }
    svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body=formatting).execute()
    print("[+] Đã format: header bold xanh, freeze row 1, highlight số trang ≥5 (cam) / ≥10 (đỏ)")

    print(f"\n✅ XONG! Mở: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={sheet_id}")


if __name__ == "__main__":
    main()
