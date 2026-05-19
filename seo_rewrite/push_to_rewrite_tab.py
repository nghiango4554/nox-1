"""Push rows vào tab '2. URL Rewrite' bằng cách lookup URL → row.
Format: 1 dòng / 1 URL × 11 cột.
- 1 row format: [URL, Tên, Title cũ, Meta cũ, T1, T2, T3, M1, M2, M3, Status]
- Tab có 12 cột: A=Loại trùng (giữ nguyên), B=URL, C=Tên, D=Title cũ, E=Meta cũ, F-H=T1-3, I-K=M1-3, L=Status
- Chỉ update cột C-L (URL ở cột B đã có sẵn từ lúc reorganize)
"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
PROCESSED = os.path.join(WS, "seo_rewrite", "auto_run", "processed.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

rows_file = sys.argv[1]
with open(rows_file, encoding="utf-8") as f:
    rows = json.load(f)

# Validate length (skip 404 rows)
print("=== VALIDATE ===")
issues = 0
for r in rows:
    if r[10] == "404 - bỏ qua":
        continue
    for i, t in enumerate(r[3:6], 1):
        if len(t) > 61:
            print(f"  ❌ T{i} {len(t)}c: {t[:70]}")
            issues += 1
    for i, m in enumerate(r[6:9], 1):
        if len(m) > 160:
            print(f"  ❌ M{i} {len(m)}c (DÀI): {m[:60]}")
            issues += 1
        elif len(m) < 140:
            print(f"  ⚠ M{i} {len(m)}c (NGẮN): {m[:60]}")
print()

# Connect
creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

# Read URL→row map từ tab "2. URL Rewrite" (cột B)
print("Loading URL→row map từ sheet...")
res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!B1:B", majorDimension="COLUMNS",
).execute()
url_col = res.get("values", [[]])[0]
url_to_row = {url: i + 1 for i, url in enumerate(url_col) if url.startswith("http")}
print(f"  Total URL rows: {len(url_to_row)}")

# Build batch update — mỗi row update C-L (10 cột)
data_updates = []
not_found = []
for r in rows:
    url = r[0]
    if url not in url_to_row:
        not_found.append(url)
        continue
    sheet_row = url_to_row[url]
    # values cho C-L (cols 3-12 = 10 cells): name, t_old, m_old, T1, T2, T3, M1, M2, M3, status
    cells = r[1:11]
    data_updates.append({
        "range": f"'{TAB}'!C{sheet_row}:L{sheet_row}",
        "values": [cells],
    })

if not_found:
    print(f"⚠ Không tìm thấy {len(not_found)} URL trong sheet:")
    for u in not_found: print(f"   - {u}")

if data_updates:
    body = {"valueInputOption": "RAW", "data": data_updates}
    res = svc.spreadsheets().values().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
    print(f"\n✅ Updated {res.get('totalUpdatedRows')} rows / {res.get('totalUpdatedCells')} cells")

# Save processed.json
state = json.load(open(PROCESSED, encoding="utf-8"))
new_urls = [r[0] for r in rows if r[0] not in state["urls"]]
state["urls"].extend(new_urls)
with open(PROCESSED, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print(f"   processed.json: {len(state['urls'])} URL total")
