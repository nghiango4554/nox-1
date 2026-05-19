"""Verify metafields đã sync lên Haravan đúng với expected từ sheet '2. URL Rewrite'.
Đọc rows tick M=TRUE, lookup pid, GET metafields, so sánh title_tag + description_tag.
"""
import os, sys, re, time
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
sys.path.insert(0, os.path.join(WS, "marketing_hub"))
from haravan_client import _request

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

print("Đang đọc sheet...")
res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O", majorDimension="ROWS",
).execute()
rows = res.get("values", [])[1:]

def cell(r, idx):
    return r[idx] if idx < len(r) else ""

todo = []
for i, r in enumerate(rows, start=2):
    if cell(r, 12) != "TRUE":  # cột M = "Đã apply"
        continue
    if cell(r, 11) == "404 - bỏ qua":
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

print(f"→ {len(todo)} URL cần verify\n")

def get_pid(url):
    m = re.match(r"https://sintech\.vn/products/([^/?#]+)", url)
    if not m:
        return None
    handle = m.group(1)
    r = _request("GET", "/products.json", params={"handle": handle, "fields": "id,handle"})
    prods = r.get("products", [])
    return prods[0]["id"] if prods else None

mismatches = []
ok = 0
not_found = 0

for i, url, exp_t, exp_m in todo:
    pid = get_pid(url)
    if not pid:
        print(f"[{i}] ❌ NOT FOUND: {url}")
        not_found += 1
        continue
    mfs = _request("GET", f"/products/{pid}/metafields.json").get("metafields", [])
    got = {}
    for mf in mfs:
        if mf.get("namespace") == "global" and mf.get("key") in ("title_tag", "description_tag"):
            got[mf["key"]] = mf.get("value", "")
    got_t = got.get("title_tag", "")
    got_m = got.get("description_tag", "")
    issues = []
    if got_t.strip() != exp_t.strip():
        issues.append(f"TITLE mismatch\n      EXP: {exp_t}\n      GOT: {got_t}")
    if got_m.strip() != exp_m.strip():
        issues.append(f"META mismatch\n      EXP: {exp_m[:120]}\n      GOT: {got_m[:120]}")
    if issues:
        mismatches.append((i, url, issues))
        print(f"[{i}] ❌ MISMATCH pid={pid}")
        for x in issues:
            print(f"   {x}")
    else:
        ok += 1
    time.sleep(0.3)

print(f"\n=== VERIFY: {ok} OK / {len(mismatches)} MISMATCH / {not_found} NOT FOUND / {len(todo)} total ===")
if mismatches:
    print("\nMismatch rows:", [m[0] for m in mismatches])
