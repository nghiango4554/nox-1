"""Audit toàn bộ title + meta đang được PICK trên sheet '2. URL Rewrite'.
Bắt các dấu hiệu:
  TITLE:
    - len > 61
    - len < 30
    - filler (bền bỉ, đẹp mắt)
    - lặp word liên tiếp ("trắng trắng")
    - duplicate giữa các SP
    - trống
  META:
    - len > 160
    - len < 140
    - thiếu CTA (KHÁM PHÁ NGAY / XEM NGAY / CHỌN NGAY / THAM KHẢO NGAY)
    - filler
    - lặp word liên tiếp
    - duplicate giữa các SP
    - trống
Output ra file audit_report.md.
"""
import os, sys, re
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

WS = r"C:\Users\NGHIANGO\.openclaw\workspace"
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

CTA_PATTERN = re.compile(r"\b(KHÁM PHÁ NGAY|XEM NGAY|CHỌN NGAY|THAM KHẢO NGAY)\b", re.I)
FILLER_PATTERN = re.compile(r"\b(bền\s+bỉ|đẹp\s+mắt)\b", re.I)
DUP_WORD_PATTERN = re.compile(r"\b(\w+)\s+\1\b", re.I | re.UNICODE)

# Pattern cho lặp cụm 2 từ (ví dụ "kim loại kim loại")
DUP_PHRASE_PATTERN = re.compile(r"\b(\w+\s+\w+)\s+\1\b", re.I | re.UNICODE)

records = []
for i, r in enumerate(rows, start=2):
    if cell(r, 11) == "404 - bỏ qua":
        continue
    titles = [cell(r,5), cell(r,6), cell(r,7)]
    metas  = [cell(r,8), cell(r,9), cell(r,10)]
    pick_t_col = next((idx for idx,t in enumerate(titles) if t.strip()), None)
    pick_m_col = next((idx for idx,m in enumerate(metas)  if m.strip()), None)
    title = titles[pick_t_col].strip() if pick_t_col is not None else ""
    meta  = metas[pick_m_col].strip()  if pick_m_col is not None else ""
    records.append({
        "row": i,
        "url": cell(r,1),
        "synced": cell(r,12) == "TRUE",
        "title": title,
        "meta": meta,
        "title_col": ["F","G","H"][pick_t_col] if pick_t_col is not None else None,
        "meta_col":  ["I","J","K"][pick_m_col] if pick_m_col is not None else None,
    })

issues_t = defaultdict(list)
issues_m = defaultdict(list)

# Duplicate detection
title_seen = defaultdict(list)
meta_seen  = defaultdict(list)
for rec in records:
    if rec["title"]:
        title_seen[rec["title"].lower()].append(rec["row"])
    if rec["meta"]:
        meta_seen[rec["meta"].lower()].append(rec["row"])

for rec in records:
    i = rec["row"]; t = rec["title"]; m = rec["meta"]

    # TITLE checks
    if not t:
        issues_t["empty"].append((i, "(trống)"))
    else:
        ln = len(t)
        if ln > 61:
            issues_t["too_long"].append((i, ln, t))
        elif ln < 30:
            issues_t["too_short"].append((i, ln, t))
        if FILLER_PATTERN.search(t):
            issues_t["filler"].append((i, t))
        dup = DUP_WORD_PATTERN.search(t) or DUP_PHRASE_PATTERN.search(t)
        if dup:
            issues_t["dup_word"].append((i, dup.group(0), t))
        if len(title_seen[t.lower()]) > 1:
            other = [x for x in title_seen[t.lower()] if x != i]
            issues_t["dup_across"].append((i, t, other))

    # META checks
    if not m:
        issues_m["empty"].append((i, "(trống)"))
    else:
        ln = len(m)
        if ln > 160:
            issues_m["too_long"].append((i, ln, m))
        elif ln < 140:
            issues_m["too_short"].append((i, ln, m))
        if not CTA_PATTERN.search(m):
            issues_m["no_cta"].append((i, m))
        if FILLER_PATTERN.search(m):
            issues_m["filler"].append((i, m))
        dup = DUP_WORD_PATTERN.search(m) or DUP_PHRASE_PATTERN.search(m)
        if dup:
            issues_m["dup_word"].append((i, dup.group(0), m))
        if len(meta_seen[m.lower()]) > 1:
            other = [x for x in meta_seen[m.lower()] if x != i]
            issues_m["dup_across"].append((i, m, other))

# Output console summary + file detail
out = []
def w(s=""):
    out.append(s); print(s)

w(f"# Audit Title + Meta — {len(records)} rows\n")

# TITLE
w("## TITLE issues")
w(f"- empty: {len(issues_t['empty'])}")
w(f"- too_long (>61): {len(issues_t['too_long'])}")
w(f"- too_short (<30): {len(issues_t['too_short'])}")
w(f"- filler (bền bỉ / đẹp mắt): {len(issues_t['filler'])}")
w(f"- duplicate word: {len(issues_t['dup_word'])}")
w(f"- duplicate across products: {len(issues_t['dup_across'])}")
w("")

# META
w("## META issues")
w(f"- empty: {len(issues_m['empty'])}")
w(f"- too_long (>160): {len(issues_m['too_long'])}")
w(f"- too_short (<140): {len(issues_m['too_short'])}")
w(f"- thiếu CTA: {len(issues_m['no_cta'])}")
w(f"- filler: {len(issues_m['filler'])}")
w(f"- duplicate word: {len(issues_m['dup_word'])}")
w(f"- duplicate across products: {len(issues_m['dup_across'])}")
w("")

def section(title, items, formatter):
    if not items:
        return
    w(f"### {title} ({len(items)})")
    for it in items:
        w(formatter(it))
    w("")

w("## DETAIL — TITLE\n")
section("Title TOO LONG (>61)", issues_t["too_long"],
        lambda x: f"- [{x[0]}] len={x[1]}: {x[2]}")
section("Title TOO SHORT (<30)", issues_t["too_short"],
        lambda x: f"- [{x[0]}] len={x[1]}: {x[2]}")
section("Title FILLER", issues_t["filler"],
        lambda x: f"- [{x[0]}]: {x[1]}")
section("Title DUPLICATE WORD", issues_t["dup_word"],
        lambda x: f"- [{x[0]}] (\"{x[1]}\"): {x[2]}")
section("Title DUPLICATE giữa các SP", issues_t["dup_across"],
        lambda x: f"- [{x[0]}] trùng row {x[2]}: {x[1]}")
section("Title EMPTY", issues_t["empty"], lambda x: f"- [{x[0]}]")

w("## DETAIL — META\n")
section("Meta TOO LONG (>160)", issues_m["too_long"],
        lambda x: f"- [{x[0]}] len={x[1]}: {x[2][:200]}")
section("Meta TOO SHORT (<140)", issues_m["too_short"],
        lambda x: f"- [{x[0]}] len={x[1]}: {x[2]}")
section("Meta thiếu CTA", issues_m["no_cta"],
        lambda x: f"- [{x[0]}]: {x[1][:200]}")
section("Meta FILLER", issues_m["filler"],
        lambda x: f"- [{x[0]}]: {x[1][:200]}")
section("Meta DUPLICATE WORD", issues_m["dup_word"],
        lambda x: f"- [{x[0]}] (\"{x[1]}\"): {x[2][:200]}")
section("Meta DUPLICATE giữa các SP", issues_m["dup_across"],
        lambda x: f"- [{x[0]}] trùng row {x[2]}: {x[1][:200]}")
section("Meta EMPTY", issues_m["empty"], lambda x: f"- [{x[0]}]")

with open("audit_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print(f"\n→ Saved: audit_report.md")
