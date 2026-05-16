"""Apply fix:
- 136 title chứa filler ('bền bỉ' / 'đẹp mắt' / 'bền bỉ bền bỉ') → clean.
- 2 title HP Pavilion X360 (row 131, 132) → rewrite cho dễ đọc.
Chỉ update cell title đang được PICK (cell đầu tiên có content trong F-H).
"""
import os, sys, re
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

DRY_RUN = "--dry" in sys.argv

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O", majorDimension="ROWS",
).execute()
rows = res.get("values", [])[1:]

def cell(r, idx):
    return r[idx] if idx < len(r) else ""

def clean_title(t):
    out = t
    out = re.sub(r"bền\s+bỉ\s+bền\s+bỉ", "", out, flags=re.I)
    out = re.sub(r"\bbền\s+bỉ\b", "", out, flags=re.I)
    out = re.sub(r"\bđẹp\s+mắt\b", "", out, flags=re.I)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"\s*,\s*,+", ", ", out)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s*[,\-–]\s*$", "", out).strip()
    out = re.sub(r"^\s*[,\-–]\s*", "", out).strip()
    return out

# Manual rewrites — vợ yêu cầu sửa hẳn
MANUAL = {
    131: "Laptop HP Pavilion X360 14 i3 2-in-1 cảm ứng vàng FHD",
    132: "Laptop HP Pavilion X360 14 i3 2-in-1 cảm ứng xanh FHD",
}

PATTERNS = [
    re.compile(r"bền\s+bỉ\s+bền\s+bỉ", re.I),
    re.compile(r"\bbền\s+bỉ\b", re.I),
    re.compile(r"\bđẹp\s+mắt\b", re.I),
]

updates = []  # list of {"range":..., "values":[[val]]}
log = []

for i, r in enumerate(rows, start=2):
    titles = [cell(r, 5), cell(r, 6), cell(r, 7)]
    # tìm cột pick (5=F, 6=G, 7=H)
    pick_col = next((idx for idx, t in enumerate(titles) if t.strip()), None)
    if pick_col is None:
        continue
    picked = titles[pick_col].strip()
    new_title = None
    reason = None

    if i in MANUAL:
        new_title = MANUAL[i]
        reason = "MANUAL HP Pavilion"
    elif any(p.search(picked) for p in PATTERNS):
        new_title = clean_title(picked)
        reason = "filler clean"

    if not new_title or new_title == picked:
        continue

    col_letter = ["F", "G", "H"][pick_col]
    updates.append({
        "range": f"'{TAB}'!{col_letter}{i}",
        "values": [[new_title]],
    })
    log.append((i, col_letter, reason, picked, new_title))

print(f"=== {len(updates)} cập nhật ===\n")
for i, col, reason, old, new in log[:10]:
    print(f"[{i}{col}] {reason}")
    print(f"  - {old}")
    print(f"  + {new}\n")
if len(log) > 10:
    print(f"... và {len(log) - 10} cập nhật nữa\n")

if DRY_RUN:
    print("🔍 DRY RUN — không ghi sheet")
    sys.exit(0)

# Batch update
body = {"valueInputOption": "USER_ENTERED", "data": updates}
svc.spreadsheets().values().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
print(f"✅ Đã update {len(updates)} cell title trên sheet.")

# Final summary
manual_count = sum(1 for _,_,r,_,_ in log if r.startswith("MANUAL"))
filler_count = sum(1 for _,_,r,_,_ in log if r == "filler clean")
print(f"\n--- TỔNG ---")
print(f"  Filler clean:    {filler_count}")
print(f"  Manual rewrite:  {manual_count}")
print(f"  Tổng:            {len(log)}")
