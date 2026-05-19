"""Push batch rows vào sheet 'SEO Duplicates' append theo cột E onwards."""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = r"C:\Users\NGHIANGO\.openclaw\workspace\.secrets\google_token.json"
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "SEO Duplicates"

def push_rows(rows, start_row):
    """Ghi rows vào E{start_row}."""
    creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
    svc = build("sheets", "v4", credentials=creds)
    # Validate
    print("=== VALIDATE ===")
    bad = 0
    for r in rows:
        for i, t in enumerate(r[4:7], 1):
            if len(t) > 61:
                print(f"  ❌ T{i} {len(t)}c: {t}")
                bad += 1
        for i, m in enumerate(r[7:10], 1):
            if len(m) > 160 or len(m) < 140:
                print(f"  ⚠ M{i} {len(m)}c: {m[:60]}")
    if bad:
        print(f"\n!!! {bad} TITLE QUÁ DÀI — DỪNG, FIX TRƯỚC.")
        sys.exit(1)
    body = {"values": rows}
    res = svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB}'!E{start_row}",
        valueInputOption="RAW",
        body=body,
    ).execute()
    print(f"\n✅ Pushed {res.get('updatedRows')} rows × {res.get('updatedColumns')} cols → '{TAB}'!E{start_row}")

if __name__ == "__main__":
    rows_file = sys.argv[1]
    start_row = int(sys.argv[2])
    with open(rows_file, encoding="utf-8") as f:
        rows = json.load(f)
    push_rows(rows, start_row)
