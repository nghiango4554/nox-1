"""Smart pick T1+M1 best cho các row có 3T+3M chưa tick (O != TRUE).
Chấm điểm và chọn title/meta tốt nhất theo pattern, clear T2/T3/M2/M3.
"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

PROD_TYPES = ['Chuột','Bàn','Tản','AIO','Case','Vỏ','Combo','RAM','Laptop','Tai','Loa','Card','VGA','Mainboard','Main','CPU','Nguồn','PSU','Phím','Tay cầm','Màn','Ghế','Fan','Box','Cáp','Cục','Cockpit','Macbook','Apple','Thẻ','SSD','Ổ','Túi','Kit','PC','Tay','Sạc','Hub','Microsd']

def starts_with_type(t):
    return any(t.startswith(p) for p in PROD_TYPES)

def title_score(t):
    if not t:
        return 9999
    score = 0
    if not starts_with_type(t): score += 30
    L = len(t)
    if L > 61: score += 200
    elif L < 45: score += 100
    else:
        score += abs(54 - L)  # sweet spot 54c
    if 'sintech' in t.lower(): score += 500
    return score

def meta_score(m):
    if not m:
        return 9999
    L = len(m)
    if L < 140: score = 100 + (140 - L)
    elif L > 160: score = 100 + (L - 160)
    else: score = abs(150 - L)
    return score

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

print("Đang đọc sheet...")
res = svc.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O").execute()
rows = res.get("values", [])[1:]

def cell(r, idx): return r[idx].strip() if idx < len(r) and r[idx] else ""

updates = []  # batch update entries
for i, r in enumerate(rows, start=2):  # row index 2-481
    o = r[14] if len(r) > 14 else ""
    if o == "TRUE":
        continue
    titles = [cell(r, 5), cell(r, 6), cell(r, 7)]
    metas = [cell(r, 8), cell(r, 9), cell(r, 10)]
    # Cần ít nhất 2 title hoặc 2 meta để smart pick có ý nghĩa
    n_t = sum(1 for t in titles if t)
    n_m = sum(1 for m in metas if m)
    if n_t < 2 and n_m < 2:
        continue  # row đã chỉ 1T+1M → skip
    # Pick best
    best_t = min(titles, key=title_score) if any(titles) else ""
    best_m = min(metas, key=meta_score) if any(metas) else ""
    # Update F-K = [best_t, "", "", best_m, "", ""]
    updates.append({
        "range": f"'{TAB}'!F{i}:K{i}",
        "values": [[best_t, "", "", best_m, "", ""]],
    })

print(f"→ Sẽ smart-pick + clear cho {len(updates)} rows")
if not updates:
    sys.exit(0)

# Batch update theo chunks 100
CHUNK = 100
for i in range(0, len(updates), CHUNK):
    body = {"valueInputOption": "USER_ENTERED", "data": updates[i:i+CHUNK]}
    svc.spreadsheets().values().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
    print(f"  ✓ Đã update batch {i+1}-{min(i+CHUNK, len(updates))}")

print(f"\n✅ DONE - {len(updates)} rows đã trim về T1+M1 best")
