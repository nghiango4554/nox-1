"""Đổ CSV crawl đối thủ vào tab 'Đối thủ' (gid 1142582322). Clear → write → freeze+bold header."""
import csv, sys
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-1\.secrets\google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "Đối thủ"
TAB_GID = 1142582322
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CSV_PATH = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-1\competitor_research\minhtuanmobile_seo_patterns.csv")

# CSV col -> header tiếng Việt (giữ đúng thứ tự CSV)
HEADER_MAP = [
    ("url", "URL"), ("page_type", "Loại trang"), ("title", "Title tag"),
    ("title_len", "Dài title"), ("meta_desc", "Meta description"), ("meta_len", "Dài meta"),
    ("h1", "H1"), ("h2_list", "Danh sách H2"), ("h2_count", "Số H2"),
    ("word_count", "Word count"), ("schema_type", "Schema"), ("cta_present", "Có CTA"),
    ("title_pattern", "Pattern title"), ("meta_pattern", "Pattern meta"),
    ("news_category", "Phân loại news"), ("note", "Nhận xét"),
]


def main():
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("CSV rỗng — abort"); return

    cols = [c for c, _ in HEADER_MAP]
    header = [h for _, h in HEADER_MAP]
    values = [header] + [[r.get(c, "") for c in cols] for r in rows]

    # Clear tab
    svc.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range=f"'{TAB}'").execute()
    # Write
    svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1",
        valueInputOption="RAW", body={"values": values},
    ).execute()
    # Format: freeze header + bold + auto-resize vài cột
    svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": [
        {"updateSheetProperties": {
            "properties": {"sheetId": TAB_GID, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"}},
        {"repeatCell": {
            "range": {"sheetId": TAB_GID, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {"textFormat": {"bold": True},
                     "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 1.0}}},
            "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
    ]}).execute()

    by_type = {}
    for r in rows:
        by_type[r["page_type"]] = by_type.get(r["page_type"], 0) + 1
    print(f"FILLED {len(rows)} rows vào '{TAB}'. Breakdown: {by_type}")


if __name__ == "__main__":
    main()
