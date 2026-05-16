"""Verify title/meta render trên web thật (sintech.vn) cho 70 SP đã tick M=TRUE.
So sánh với expected trong sheet '2. URL Rewrite'.
"""
import os, sys, re, time, urllib.request, html as htmllib
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(WS, ".secrets", "google_token.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "2. URL Rewrite"

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

print(f"→ {len(todo)} URL cần check live\n")

def fetch(url):
    bust = f"{url}?_={int(time.time()*1000)}"
    req = urllib.request.Request(bust, headers={"User-Agent":"Mozilla/5.0","Cache-Control":"no-cache","Pragma":"no-cache"})
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", errors="ignore")

def extract(h):
    t = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']', h, re.I)
    title = htmllib.unescape(re.sub(r"\s+", " ", t.group(1).strip())) if t else ""
    title = re.sub(r"\s*[–\-]\s*Sintech\s*$", "", title).strip()
    meta  = htmllib.unescape(m.group(1).strip()) if m else ""
    return title, meta

mismatches = []
ok = 0
err = 0

for idx, (i, url, exp_t, exp_m) in enumerate(todo, 1):
    try:
        h = fetch(url)
    except Exception as e:
        print(f"[{i}] ⚠️  FETCH ERR: {e}")
        err += 1
        continue
    got_t, got_m = extract(h)
    issues = []
    if got_t.strip() != exp_t.strip():
        issues.append(("TITLE", exp_t, got_t))
    if got_m.strip()[:120] != exp_m.strip()[:120]:
        issues.append(("META", exp_m[:140], got_m[:140]))
    if issues:
        mismatches.append((i, url, issues))
        print(f"[{i}] ❌ MISMATCH  {url.split('/')[-1]}")
        for tag, e, g in issues:
            print(f"   {tag}")
            print(f"     EXP: {e}")
            print(f"     GOT: {g}")
    else:
        ok += 1
    if idx % 10 == 0:
        print(f"  ... {idx}/{len(todo)} done")
    time.sleep(0.4)

print(f"\n=== WEB VERIFY: {ok} OK / {len(mismatches)} MISMATCH / {err} ERR / {len(todo)} total ===")
if mismatches:
    print("\nRows mismatch:", [m[0] for m in mismatches])
