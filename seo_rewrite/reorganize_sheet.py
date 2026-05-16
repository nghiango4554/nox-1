"""Sắp xếp lại sheet 'SEO Duplicates' thành 2 tab clean:
  Tab '1. Overview': 1 dòng = 1 nhóm trùng (Loại | Nội dung | Số trang | URLs)
  Tab '2. URL Rewrite': 1 dòng = 1 URL (Loại trùng | URL | Tên | Title cũ | Meta cũ | T1 T2 T3 | M1 M2 M3 | Status)
"""
import os, sys, json, csv
sys.stdout.reconfigure(encoding="utf-8")

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

WS = r"C:\Users\Nghia Dep Gai\.openclaw\workspace"
TOKEN = os.path.join(WS, ".secrets", "google_token.json")
TSV = os.path.join(WS, "seo_duplicates.tsv")
PROCESSED = os.path.join(WS, "seo_rewrite", "auto_run", "processed.json")
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"

OLD_TAB = "SEO Duplicates"
TAB1 = "1. Overview"
TAB2 = "2. URL Rewrite"

creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
svc = build("sheets", "v4", credentials=creds)

# === STEP 1: Đọc data hiện tại từ sheet (cột E-N có rewrite) ===
print("Đọc data rewrite hiện có...")
res = svc.spreadsheets().values().get(
    spreadsheetId=SHEET_ID, range=f"'{OLD_TAB}'!E2:N", majorDimension="ROWS",
).execute()
existing_rewrite = {}  # url -> [name, t_old, m_old, T1, T2, T3, M1, M2, M3]
for row in res.get("values", []):
    if not row or not row[0].startswith("http"):
        continue
    row += [""] * (10 - len(row))
    url = row[0]
    existing_rewrite[url] = row[1:10]
print(f"  Đã có rewrite cho {len(existing_rewrite)} URL")

# === STEP 2: Đọc TSV để build OVERVIEW + URL list ===
overview_rows = [["Loại", "Nội dung trùng", "Số trang", "URLs"]]
url_to_dup_types = {}  # url -> set of (loại, nội_dung)
with open(TSV, encoding="utf-8") as f:
    rd = csv.reader(f, delimiter="\t")
    next(rd)
    for row in rd:
        loai, content, count, urls_joined = row
        overview_rows.append([loai, content, int(count), urls_joined])
        for u in urls_joined.split(" | "):
            u = u.strip()
            if not u: continue
            url_to_dup_types.setdefault(u, []).append(f"{loai}: {content[:60]}")

# === STEP 3: Build URL REWRITE rows ===
rewrite_rows = [["Loại trùng", "URL", "Tên hiện tại", "Title hiện tại", "Meta hiện tại",
                 "Title đề xuất 1", "Title đề xuất 2", "Title đề xuất 3",
                 "Meta đề xuất 1", "Meta đề xuất 2", "Meta đề xuất 3", "Trạng thái"]]
unique_urls = list(url_to_dup_types.keys())
for url in sorted(unique_urls):
    dup_types = " || ".join(url_to_dup_types[url])
    if url in existing_rewrite:
        r = existing_rewrite[url]
        status = "Đã sinh" if any(r[3:]) else "Chưa"
        rewrite_rows.append([dup_types, url, r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], status])
    else:
        rewrite_rows.append([dup_types, url, "", "", "", "", "", "", "", "", "", "Chưa"])

print(f"Overview: {len(overview_rows)-1} nhóm | Rewrite: {len(rewrite_rows)-1} URL")

# === STEP 4: Tạo / clear 2 tabs mới ===
meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
existing_tabs = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

requests = []
for tab in (TAB1, TAB2):
    if tab not in existing_tabs:
        requests.append({"addSheet": {"properties": {"title": tab}}})
if requests:
    svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": requests}).execute()
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existing_tabs = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

tab1_id = existing_tabs[TAB1]
tab2_id = existing_tabs[TAB2]

# Clear
for tab in (TAB1, TAB2):
    svc.spreadsheets().values().clear(spreadsheetId=SHEET_ID, range=f"'{tab}'").execute()

# Push data
svc.spreadsheets().values().update(
    spreadsheetId=SHEET_ID, range=f"'{TAB1}'!A1",
    valueInputOption="RAW", body={"values": overview_rows},
).execute()
print(f"  ✓ {TAB1}: {len(overview_rows)} rows pushed")

svc.spreadsheets().values().update(
    spreadsheetId=SHEET_ID, range=f"'{TAB2}'!A1",
    valueInputOption="RAW", body={"values": rewrite_rows},
).execute()
print(f"  ✓ {TAB2}: {len(rewrite_rows)} rows pushed")

# === STEP 5: Format đẹp ===
def hdr_format(sheet_id, n_cols, color):
    return [
        # Header bg + bold
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": color,
                "textFormat": {"bold": True, "foregroundColor": {"red":1,"green":1,"blue":1}, "fontSize": 11},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "wrapStrategy": "WRAP",
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)",
        }},
        # Freeze row 1
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }},
    ]

# Tab 1 widths: Loại 110, Nội dung 380, Số trang 80, URLs 700
tab1_widths = [(0,1,110), (1,2,380), (2,3,80), (3,4,700)]
# Tab 2 widths: Loại 200, URL 350, Tên 280, T cũ 250, M cũ 280, T1/2/3 230 each, M1/2/3 320 each, Status 100
tab2_widths = [
    (0,1,200), (1,2,350), (2,3,280), (3,4,250), (4,5,280),
    (5,6,230), (6,7,230), (7,8,230),
    (8,9,320), (9,10,320), (10,11,320),
    (11,12,100),
]

def col_width_reqs(sheet_id, widths):
    return [{"updateDimensionProperties": {
        "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": s, "endIndex": e},
        "properties": {"pixelSize": w}, "fields": "pixelSize",
    }} for (s,e,w) in widths]

# Conditional format: số trang ≥ 10 đỏ / ≥ 5 cam (Tab 1)
cf_tab1 = [
    {"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": tab1_id, "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 3}],
        "booleanRule": {
            "condition": {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "10"}]},
            "format": {"backgroundColor": {"red":0.95,"green":0.45,"blue":0.45}, "textFormat": {"bold": True, "foregroundColor": {"red":1,"green":1,"blue":1}}},
        },
    }, "index": 0}},
    {"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": tab1_id, "startRowIndex": 1, "startColumnIndex": 2, "endColumnIndex": 3}],
        "booleanRule": {
            "condition": {"type": "NUMBER_GREATER_THAN_EQ", "values": [{"userEnteredValue": "5"}]},
            "format": {"backgroundColor": {"red":1,"green":0.85,"blue":0.4}, "textFormat": {"bold": True}},
        },
    }, "index": 1}},
]

# Conditional format: cột Trạng thái (Tab 2)
cf_tab2 = [
    {"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": tab2_id, "startRowIndex": 1, "startColumnIndex": 11, "endColumnIndex": 12}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Đã sinh"}]},
            "format": {"backgroundColor": {"red":0.7,"green":0.95,"blue":0.7}, "textFormat": {"bold": True}},
        },
    }, "index": 0}},
    {"addConditionalFormatRule": {"rule": {
        "ranges": [{"sheetId": tab2_id, "startRowIndex": 1, "startColumnIndex": 11, "endColumnIndex": 12}],
        "booleanRule": {
            "condition": {"type": "TEXT_EQ", "values": [{"userEnteredValue": "Chưa"}]},
            "format": {"backgroundColor": {"red":0.95,"green":0.85,"blue":0.7}},
        },
    }, "index": 1}},
]

# Wrap text cho cột nội dung dài
wrap_reqs = [
    # Tab 1: cột B (Nội dung), D (URLs)
    {"repeatCell": {
        "range": {"sheetId": tab1_id, "startRowIndex": 1, "startColumnIndex": 1, "endColumnIndex": 2},
        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}},
        "fields": "userEnteredFormat.wrapStrategy",
    }},
    {"repeatCell": {
        "range": {"sheetId": tab1_id, "startRowIndex": 1, "startColumnIndex": 3, "endColumnIndex": 4},
        "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP"}},
        "fields": "userEnteredFormat.wrapStrategy",
    }},
    # Tab 2: cột Loại trùng, Tên, Title cũ, Meta cũ, T1-3, M1-3 → wrap
    {"repeatCell": {
        "range": {"sheetId": tab2_id, "startRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 11},
        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)",
    }},
]

all_reqs = (
    hdr_format(tab1_id, 4, {"red":0.26,"green":0.52,"blue":0.96})
    + col_width_reqs(tab1_id, tab1_widths)
    + cf_tab1
    + hdr_format(tab2_id, 12, {"red":0.13,"green":0.55,"blue":0.13})
    + col_width_reqs(tab2_id, tab2_widths)
    + cf_tab2
    + wrap_reqs
)
svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": all_reqs}).execute()
print("  ✓ Format applied (header màu, freeze, widths, conditional, wrap)")

print("\n=== DONE ===")
print(f"📊 Tab '1. Overview': {len(overview_rows)-1} nhóm trùng")
print(f"📝 Tab '2. URL Rewrite': {len(rewrite_rows)-1} URL")
print(f"🔗 https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
print(f"\n⚠ Tab cũ '{OLD_TAB}' vẫn còn — vợ vào sheet xóa tay nếu thấy ổn rồi.")
