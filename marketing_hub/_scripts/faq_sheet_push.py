"""Doc tab "FAQ Blog (duyệt)" tren Google Sheet -> day cac bai vo DA DUYET len Haravan.

Nguon su that = SHEET, khong phai file JSON: vo sua cau hoi/cau tra loi trong sheet thi
len web dung y het nhu vay.

Cot "Duyệt":
  OK  (hoac ok/x/v/duyet/đồng ý) -> day
  Bỏ  (bo/skip/x bo)             -> khong day
  rong                           -> chua duyet, khong day
Mot bai chi day khi >=2 dong cua bai do duoc duyet OK (dong bi "Bỏ" thi loai khoi FAQ).

Chay:  py -3.12 _scripts/faq_sheet_push.py           # dry-run
       py -3.12 _scripts/faq_sheet_push.py --go      # day that
"""
import argparse
import sys
from collections import OrderedDict
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
import haravan_blog as hb
from faq_gen import render_block
from faq_push import insert_block

SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB = "FAQ Blog (duyệt)"
BACKUP_DIR = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_backup")

OK_WORDS = {"ok", "x", "v", "yes", "duyet", "duyệt", "dong y", "đồng ý", "co", "có"}
NO_WORDS = {"bo", "bỏ", "skip", "khong", "không", "no"}


def read_sheet():
    svc = gsheet_client.get_service()
    res = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{TAB}'!A2:K").execute()
    arts = OrderedDict()
    title = url = handle = aid = bid = None
    for r in res.get("values", []):
        r = r + [""] * (11 - len(r))
        if r[1].strip():          # dong dau cua 1 bai (cot B = ten bai; cot A = STT)
            title, url = r[1].strip(), r[2].strip()
        h, q, a, duyet = r[8].strip(), r[5].strip(), r[6].strip(), r[7].strip().lower()
        if not h or not q or not a:
            continue
        if h not in arts:
            arts[h] = {"title": title, "url": url, "handle": h,
                       "id": int(r[9]), "blog_id": int(r[10]), "faqs": [], "n_row": 0}
        arts[h]["n_row"] += 1
        if duyet in OK_WORDS:
            arts[h]["faqs"].append({"q": q, "a": a})
    return arts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    dry = not a.go

    arts = read_sheet()
    ready = {h: v for h, v in arts.items() if len(v["faqs"]) >= faq_schema.MIN_QUESTIONS}
    print(f"=== {'DRY RUN' if dry else 'PUT THAT'} ===")
    print(f"Bai trong sheet   : {len(arts)}")
    print(f"Bai da duyet (>=2 cau OK): {len(ready)}\n")
    if not ready:
        print("Chua co bai nao duoc duyet. Vo dien 'OK' vao cot Duyệt roi chay lai.")
        return 0

    done = skip = fail = 0
    for h, v in ready.items():
        art = hb.get_article(v["blog_id"], v["id"])
        body = art.get("body_html") or ""
        if len(faq_schema.extract_faq(body)) >= faq_schema.MIN_QUESTIONS:
            print(f"  BO QUA (da co FAQ): {h}")
            skip += 1
            continue

        block = render_block(v["title"], v["faqs"])   # cau chu LAY TU SHEET
        new_body, n = faq_schema.attach(insert_block(body, block))
        if n < len(v["faqs"]):
            print(f"  LOI boc lai {n}/{len(v['faqs'])} cau: {h}")
            fail += 1
            continue
        if dry:
            print(f"  SE DAY {n}/{v['n_row']} cau duyet: {h}")
            done += 1
            continue

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (BACKUP_DIR / f"{v['id']}_{h}_{stamp}.html").write_text(body, encoding="utf-8")

        # Haravan hay tra 500 nhung VAN GHI -> GET lai kiem chung, dung tin status code
        try:
            hb.update_article(v["blog_id"], v["id"], {"body_html": new_body})
            err = None
        except Exception as e:
            err = e
        got = len(faq_schema.extract_faq(hb.get_article(v["blog_id"], v["id"]).get("body_html") or ""))
        if got >= faq_schema.MIN_QUESTIONS:
            print(f"  DA DAY {got} cau: {h}" + ("  (API bao loi nhung DA GHI)" if err else ""))
            done += 1
        else:
            print(f"  LOI THAT: {h} — {str(err)[:70]}")
            fail += 1

    print(f"\n[XONG] day={done} bo_qua={skip} loi={fail}")
    if not dry and done:
        print("  -> Verify: py -3.12 _scripts/faq_verify.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
