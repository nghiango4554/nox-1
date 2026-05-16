"""Quét sheet '2. URL Rewrite' tìm title chứa từ filler: 'bền bỉ', 'đẹp mắt', 'bền bỉ bền bỉ'.
In ra list row + title cũ + title mới đề xuất (đã clean).
"""
import os, sys, re
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1:O", majorDimension="ROWS",
).execute()
rows = res.get("values", [])[1:]

def cell(r, idx):
    return r[idx] if idx < len(r) else ""

# Pattern tìm các filler
PATTERNS = [
    (re.compile(r"bền\s+bỉ\s+bền\s+bỉ", re.I), "bền bỉ bền bỉ"),
    (re.compile(r"\bbền\s+bỉ\b", re.I), "bền bỉ"),
    (re.compile(r"\bđẹp\s+mắt\b", re.I), "đẹp mắt"),
]

def clean_title(t):
    """Xóa filler + dọn dấu câu thừa, normalize space."""
    out = t
    # double trước, single sau
    out = re.sub(r"bền\s+bỉ\s+bền\s+bỉ", "", out, flags=re.I)
    out = re.sub(r"\bbền\s+bỉ\b", "", out, flags=re.I)
    out = re.sub(r"\bđẹp\s+mắt\b", "", out, flags=re.I)
    # dọn dấu phẩy thừa, gạch ngang lẻ ở cuối, double space
    out = re.sub(r"\s*,\s*,+", ", ", out)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s*[,\-–]\s*$", "", out).strip()
    out = re.sub(r"^\s*[,\-–]\s*", "", out).strip()
    out = re.sub(r"\s*,\s*$", "", out).strip()
    return out

hits = []
for i, r in enumerate(rows, start=2):
    titles = [cell(r, 5), cell(r, 6), cell(r, 7)]
    picked = next((t.strip() for t in titles if t.strip()), "")
    if not picked:
        continue
    matches = [name for pat, name in PATTERNS if pat.search(picked)]
    if not matches:
        continue
    cleaned = clean_title(picked)
    synced = cell(r, 12) == "TRUE"
    hits.append({
        "row": i,
        "url": cell(r, 1),
        "synced": synced,
        "matches": matches,
        "old": picked,
        "new": cleaned,
        "len_old": len(picked),
        "len_new": len(cleaned),
    })

print(f"=== {len(hits)} title chứa filler ===\n")
for h in hits:
    flag = "✅synced" if h["synced"] else "  pending"
    print(f"[{h['row']:>4}] {flag}  hits={','.join(h['matches'])}  len {h['len_old']}→{h['len_new']}")
    print(f"   OLD: {h['old']}")
    print(f"   NEW: {h['new']}")
    print()

# Summary
synced_count = sum(1 for h in hits if h["synced"])
print(f"\n--- SUMMARY ---")
print(f"Total hit:    {len(hits)}")
print(f"Đã sync (cần re-sync sau khi fix): {synced_count}")
print(f"Chưa sync:    {len(hits)-synced_count}")
