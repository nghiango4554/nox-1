"""Push manual_batch JSON vào sheet + cập nhật processed.json"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
PROCESSED = os.path.join(WS, "seo_rewrite", "auto_run", "processed.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "SEO Duplicates"

rows_file = sys.argv[1]
with open(rows_file, encoding="utf-8") as f:
    rows = json.load(f)

# Validate
print("=== VALIDATE ===")
issues = 0
for r in rows:
    name = r[1][:50]
    for i, t in enumerate(r[4:7], 1):
        if len(t) > 61:
            print(f"  ❌ T{i} {len(t)}c: {t[:70]}")
            issues += 1
    for i, m in enumerate(r[7:10], 1):
        if len(m) > 160:
            print(f"  ❌ M{i} {len(m)}c (DÀI): {m[:60]}")
            issues += 1
        elif len(m) < 140:
            print(f"  ⚠ M{i} {len(m)}c (NGẮN): {m[:60]}")

# Load state
state = json.load(open(PROCESSED, encoding="utf-8"))
start_row = state["next_row"]

# Push
creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)
body = {"values": rows}
res = svc.spreadsheets().values().update(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!E{start_row}",
    valueInputOption="RAW", body=body,
).execute()
print(f"\n✅ Pushed {res['updatedRows']} rows × {res['updatedColumns']} cols → '{TAB}'!E{start_row}")

# Update state
state["urls"].extend([r[0] for r in rows])
state["next_row"] += len(rows)
with open(PROCESSED, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print(f"   New next_row: {state['next_row']} | Total processed: {len(state['urls'])}")
