"""Re-sync title/meta cho các SP đã tick TRUE nhưng web render sai.
Dùng PUT /products/{pid}.json với metafields_global_title_tag + metafields_global_description_tag
(theme Haravan đọc field flat này, không đọc metafield endpoint).
"""
import os, sys, re, time
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
sys.path.insert(0, os.path.join(WS, "marketing_hub"))
from haravan_client import _request

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

DRY_RUN = "--dry" in sys.argv
ROW_FILTER = None
for a in sys.argv[1:]:
    if a.startswith("--rows="):
        ROW_FILTER = set(int(x) for x in a.split("=",1)[1].split(","))

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

print("Đọc sheet...")
res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O", majorDimension="ROWS",
).execute()
rows = res.get("values", [])[1:]

def cell(r, idx):
    return r[idx] if idx < len(r) else ""

todo = []
for i, r in enumerate(rows, start=2):
    if cell(r, 12) != "TRUE":
        continue
    if cell(r, 11) == "404 - bỏ qua":
        continue
    if ROW_FILTER and i not in ROW_FILTER:
        continue
    url = cell(r, 1)
    if not url.startswith("http"):
        continue
    titles = [cell(r, 5), cell(r, 6), cell(r, 7)]
    metas = [cell(r, 8), cell(r, 9), cell(r, 10)]
    t = next((x.strip() for x in titles if x.strip()), "")
    m = next((x.strip() for x in metas if x.strip()), "")
    if not t or not m:
        continue
    todo.append((i, url, t, m))

print(f"→ {len(todo)} URL sẽ re-sync (PUT product field flat)\n")

if DRY_RUN:
    print("🔍 DRY RUN — không update Haravan\n")

ok = 0
fail = 0

for i, url, t, m in todo:
    mh = re.match(r"https://sintech\.vn/products/([^/?#]+)", url)
    if not mh:
        print(f"[{i}] ❌ URL không phải product: {url}")
        fail += 1
        continue
    handle = mh.group(1)
    try:
        r = _request("GET", "/products.json", params={"handle": handle, "fields": "id,handle"})
        prods = r.get("products", [])
        if not prods:
            print(f"[{i}] ❌ NOT FOUND: {handle}")
            fail += 1
            continue
        pid = prods[0]["id"]
        if DRY_RUN:
            print(f"[{i}] {handle} pid={pid}")
            print(f"    T: {t}")
            print(f"    M: {m[:80]}...")
            ok += 1
        else:
            _request("PUT", f"/products/{pid}.json", payload={
                "product": {
                    "id": pid,
                    "metafields_global_title_tag": t,
                    "metafields_global_description_tag": m,
                }
            })
            print(f"[{i}] ✅ {handle} (pid={pid})")
            ok += 1
        time.sleep(0.4)
    except Exception as e:
        print(f"[{i}] ❌ ERR ({handle}): {e}")
        fail += 1

print(f"\n=== RE-SYNC: {ok} OK / {fail} FAIL / {len(todo)} total ===")
