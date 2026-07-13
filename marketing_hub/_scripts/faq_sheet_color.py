"""To mau xen ke theo TUNG BAI trong tab "FAQ Blog (duyệt)" -> nhin la biet block nao thuoc bai nao.

Chay lai duoc nhieu lan (idempotent): moi lan doc lai sheet, to lai tu dau.
Gen dang chay nen -> chay lai script nay sau khi gen xong de to not dong moi.

Chay:  py -3.12 _scripts/faq_sheet_color.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, r"C:\Users\NGHIANGO\.openclaw\workspace")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import gsheet_client

SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "FAQ Blog (duyệt)"
NCOL = 11

# 4 mau pastel luan phien — du nhat de doc chu den, du khac nhau de tach block
PALETTE = [
    {"red": 0.898, "green": 0.945, "blue": 0.996},  # xanh duong nhat
    {"red": 0.925, "green": 0.973, "blue": 0.925},  # xanh la nhat
    {"red": 1.000, "green": 0.953, "blue": 0.898},  # cam nhat
    {"red": 0.960, "green": 0.925, "blue": 0.976},  # tim nhat
]


def main():
    svc = gsheet_client.get_service()
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    sid = next((s["properties"]["sheetId"] for s in meta["sheets"]
                if s["properties"]["title"] == TAB), None)
    if sid is None:
        print(f"Khong thay tab {TAB!r}")
        return 1

    vals = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!I2:I").execute().get("values", [])
    if not vals:
        print("Tab chua co du lieu.")
        return 0

    # gom dong lien tiep cung handle thanh 1 block
    reqs, blocks = [], []
    cur, start = None, 0
    for i, r in enumerate(vals):
        h = (r[0] if r else "").strip()
        if h != cur:
            if cur is not None:
                blocks.append((cur, start, i))
            cur, start = h, i
    blocks.append((cur, start, len(vals)))

    for k, (h, s, e) in enumerate(blocks):
        if not h:
            continue
        reqs.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": s + 1, "endRowIndex": e + 1,
                      "startColumnIndex": 0, "endColumnIndex": NCOL},
            "cell": {"userEnteredFormat": {
                "backgroundColor": PALETTE[k % len(PALETTE)],
                "textFormat": {"foregroundColor": {"red": 0, "green": 0, "blue": 0},
                               "bold": False},  # chu DEN cho de doc
                "wrapStrategy": "WRAP",
                "verticalAlignment": "TOP"}},
            "fields": "userEnteredFormat(backgroundColor,textFormat,wrapStrategy,verticalAlignment)"}})

    # gui theo lo 100 request cho nhe
    for i in range(0, len(reqs), 100):
        svc.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID, body={"requests": reqs[i:i + 100]}).execute()

    print(f"[OK] Da to mau {len(blocks)} bai ({len(vals)} dong) — 4 mau pastel luan phien.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
