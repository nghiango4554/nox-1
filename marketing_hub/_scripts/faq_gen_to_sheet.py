"""Gen FAQ cho MOI bai blog chua co FAQ -> ghi NGAY len Google Sheet (tab rieng), tung bai mot.

Vo duyet tren sheet (cot "Duyệt": OK / Sửa / Bỏ), sau do day len bang faq_sheet_push.py.
Ghi tung bai -> mo sheet la thay tien do chay dan; script chet giua chung cung khong mat viec.
Chay lai = RESUME: bo qua bai da co trong sheet.

Chay:  py -3.12 _scripts/faq_gen_to_sheet.py            (tat ca bai con lai)
       py -3.12 _scripts/faq_gen_to_sheet.py --n 20     (gioi han)
"""
import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, r"C:\Users\NGHIANGO\.openclaw\workspace")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import gsheet_client

import faq_schema
from faq_gen import _plain, gather_hints, gen_faq, pick_targets, render_block

SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "FAQ Blog (duyệt)"
JSON_OUT = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_preview\faq_all_pending.json")
PROVIDERS = ["codex", "claude"]
HEADER = ["STT", "Bài viết", "URL", "Lượt hiển thị", "#", "Câu hỏi", "Câu trả lời",
          "Duyệt (OK/Sửa/Bỏ)", "handle", "article_id", "blog_id"]


def ensure_tab(svc):
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    tabs = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    if TAB in tabs:
        return tabs[TAB]

    res = svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": [
        {"addSheet": {"properties": {"title": TAB, "gridProperties": {"frozenRowCount": 1}}}}
    ]}).execute()
    sid = res["replies"][0]["addSheet"]["properties"]["sheetId"]

    svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1",
        valueInputOption="RAW", body={"values": [HEADER]}).execute()
    svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": [
        {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1},
            "cell": {"userEnteredFormat": {
                "backgroundColor": {"red": 0.12, "green": 0.31, "blue": 0.47},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
            "fields": "userEnteredFormat(backgroundColor,textFormat)"}},
        {"updateDimensionProperties": {  # cot Cau tra loi rong
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 6, "endIndex": 7},
            "properties": {"pixelSize": 520}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {  # cot Cau hoi
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 5, "endIndex": 6},
            "properties": {"pixelSize": 360}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {  # cot Bai viet
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 300}, "fields": "pixelSize"}},
    ]}).execute()
    print(f"[OK] Da tao tab moi: {TAB}")
    return sid


def done_handles(svc) -> set:
    """Handle da co trong sheet (cot I) -> resume, khong gen lai."""
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!I2:I").execute()
    return {r[0] for r in res.get("values", []) if r}


def append_rows(svc, rows):
    svc.spreadsheets().values().append(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!A1",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS",
        body={"values": rows}).execute()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None, help="Gioi han so bai (mac dinh: het)")
    ap.add_argument("--dual", action="store_true", help="2 worker song song, moi worker 1 AI")
    a = ap.parse_args()

    svc = gsheet_client.get_service()
    ensure_tab(svc)
    already = done_handles(svc)
    print(f"Da co trong sheet: {len(already)} bai\n")

    targets = pick_targets(a.n or 10**6)
    targets = [t for t in targets if t["handle"] not in already]
    print(f"=== Gen FAQ cho {len(targets)} bai con lai (uu tien impressions GSC) ===\n", flush=True)

    saved = []
    if JSON_OUT.exists():
        saved = json.loads(JSON_OUT.read_text(encoding="utf-8"))

    ok = fail = 0
    for i, t in enumerate(targets, 1):
        try:
            hints = gather_hints(t["title"])
            faqs = gen_faq(t["title"], _plain(t["body"]), hints)
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(targets)}] LOI {type(e).__name__}: {str(e)[:70]} — {t['handle'][:45]}", flush=True)
            continue

        if len(faqs) < faq_schema.MIN_QUESTIONS:
            fail += 1
            print(f"[{i}/{len(targets)}] BO (AI tra <2 cau) — {t['handle'][:45]}", flush=True)
            continue

        stt = len(already) + ok + 1  # so thu tu BAI (chi hien o dong dau moi bai)
        rows = [[stt if k == 0 else "", t["title"] if k == 0 else "", t["url"] if k == 0 else "",
                 t["imp"] if k == 0 else "", k + 1, f["q"], f["a"], "",
                 t["handle"], str(t["id"]), str(t["blog_id"])]
                for k, f in enumerate(faqs)]
        try:
            append_rows(svc, rows)
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(targets)}] LOI GHI SHEET: {str(e)[:70]}", flush=True)
            continue

        saved.append({**{k: t[k] for k in ("blog_id", "id", "handle", "title", "url", "imp")},
                      "faqs": faqs, "block_html": render_block(t["title"], faqs)})
        JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
        JSON_OUT.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")

        ok += 1
        print(f"[{i}/{len(targets)}] bai #{stt} · OK {len(faqs)} cau · {t['imp']} imp — {t['title'][:44]}", flush=True)
        time.sleep(0.5)

    print(f"\n[XONG {datetime.now():%H:%M}] len sheet: {ok} bai · loi/bo: {fail}")
    print(f"  Sheet tab : {TAB}")
    print(f"  JSON      : {JSON_OUT}")
    print("  -> Vo duyet tren sheet, sau do day: py -3.12 _scripts/faq_sheet_push.py --go")
    return 0


if __name__ == "__main__":
    sys.exit(main())
