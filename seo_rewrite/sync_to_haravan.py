"""Sync title + meta description từ sheet '2. URL Rewrite' lên Haravan.
Workflow:
  1. Đọc rows có cột M (col 13) = TRUE và status != '404 - bỏ qua'
  2. Cho mỗi row, lấy:
     - URL (cột B = col 2)
     - Title chọn = cell ĐẦU TIÊN có content trong cột F-H (col 6-8)
     - Meta chọn = cell ĐẦU TIÊN có content trong cột I-K (col 9-11)
  3. Tìm product trên Haravan qua handle URL
  4. PUT /products/{pid}.json với metafields_global_title_tag + metafields_global_description_tag
     (theme Haravan render từ field flat này, KHÔNG đọc /products/{pid}/metafields.json — đã verify)
  5. Set cột N (col 14) = TRUE, cột O (col 15) = today
"""
import os, sys, json, re, time
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
sys.path.insert(0, os.path.join(WS, "marketing_hub"))
from haravan_client import _request

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

DRY_RUN = "--dry" in sys.argv  # --dry để chỉ in, không update

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

# Đọc full data tab
print("Đang đọc sheet...")
res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O", majorDimension="ROWS",
).execute()
rows = res.get("values", [])
header = rows[0]
data_rows = rows[1:]
print(f"  Total {len(data_rows)} rows")

# Filter rows cần sync: cột O (idx 14) = TRUE và status (idx 11) != '404 - bỏ qua'
def cell(r, idx):
    return r[idx] if idx < len(r) else ""

todo = []
for i, r in enumerate(data_rows, start=2):  # row index 2-481
    chong_iu = cell(r, 14)  # cột O = "Chồng iu tự điền"
    status = cell(r, 11)    # cột L
    if chong_iu != "TRUE":
        continue
    if status == "404 - bỏ qua":
        continue
    url = cell(r, 1)  # cột B
    if not url.startswith("http"):
        continue
    # Lấy title đầu tiên có content
    titles = [cell(r, 5), cell(r, 6), cell(r, 7)]
    metas = [cell(r, 8), cell(r, 9), cell(r, 10)]
    title_choose = next((t.strip() for t in titles if t.strip()), "")
    meta_choose = next((m.strip() for m in metas if m.strip()), "")
    if not title_choose or not meta_choose:
        print(f"  ⚠ Row {i}: thiếu title hoặc meta — skip ({url})")
        continue
    todo.append((i, url, title_choose, meta_choose))

print(f"\n→ {len(todo)} URL cần sync (đã tick checkbox và có title+meta đầy đủ)\n")

if not todo:
    sys.exit(0)

if DRY_RUN:
    print("🔍 DRY RUN — chỉ in, không update Haravan:\n")

# Lookup handle from URL → product_id via Haravan API
def get_id_from_url(url):
    """URL có dạng https://sintech.vn/products/<handle> hoặc /blogs/<group>/<handle>"""
    m = re.match(r"https://sintech\.vn/products/([^/?#]+)", url)
    if m:
        handle = m.group(1)
        try:
            r = _request("GET", "/products.json", params={"handle": handle, "fields": "id,title,handle"})
            prods = r.get("products", [])
            if prods:
                return ("product", prods[0]["id"], prods[0]["title"])
        except Exception as e:
            print(f"  ! lookup err: {e}")
        return None, None, None
    return None, None, None

ok = 0
fail = 0
updates_for_sheet = []

for sheet_row, url, title, meta in todo:
    print(f"[{sheet_row}] {url}")
    print(f"   T: {title}")
    print(f"   M: {meta[:80]}...")
    kind, pid, current_name = get_id_from_url(url)
    if not pid:
        print("   ❌ Không tìm thấy product trên Haravan")
        fail += 1
        continue
    print(f"   → product #{pid} ({current_name[:50]})")
    if not DRY_RUN:
        try:
            _request("PUT", f"/products/{pid}.json", payload={
                "product": {
                    "id": pid,
                    "metafields_global_title_tag": title,
                    "metafields_global_description_tag": meta,
                }
            })
            print(f"   ✅ SYNCED OK")
            ok += 1
            updates_for_sheet.append({
                "range": f"'{TAB}'!M{sheet_row}:N{sheet_row}",
                "values": [[True, datetime.now().strftime("%Y-%m-%d")]],
            })
        except Exception as e:
            print(f"   ❌ ERR: {e}")
            fail += 1
    time.sleep(0.5)  # Haravan rate limit guard
    print()

# Update sheet: set N = TRUE, O = today cho rows đã sync OK
if updates_for_sheet:
    body = {"valueInputOption": "USER_ENTERED", "data": updates_for_sheet}
    svc.spreadsheets().values().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
    print(f"✓ Updated checkbox + date cho {len(updates_for_sheet)} rows trong sheet")

print(f"\n=== KẾT QUẢ: {ok} OK / {fail} FAIL / {len(todo)} total ===")
