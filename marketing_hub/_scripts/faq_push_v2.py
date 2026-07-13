"""Day FAQ v2 len Haravan — THAY THE khoi FAQ cu neu bai da co (rework), hoac chen moi.

Khac faq_push.py (v1): v1 chi CHEN khi bai chua co FAQ. v2 co the GO khoi cu roi thay khoi moi
-> dung cho 10 bai da day theo chuan v1 (ep 6 cau, khong bam key GSC, tieu de khoi le the).

Luon backup body cu ra nox-outputs/faq_backup/ truoc khi PUT.
⚠️ Haravan hay tra HTTP 500 NHUNG VAN GHI -> PUT loi thi GET lai kiem chung.

Chay:  py -3.12 _scripts/faq_push_v2.py <file.json>          # dry-run
       py -3.12 _scripts/faq_push_v2.py <file.json> --go
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import faq_schema
import haravan_blog as hb
from faq_gen import render_block
from faq_push import insert_block

BACKUP_DIR = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_backup")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file")
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    dry = not a.go

    rows = json.loads(Path(a.json_file).read_text(encoding="utf-8"))
    print(f"=== {'DRY RUN' if dry else 'PUT THAT'} — {len(rows)} bài ===\n")

    done = fail = 0
    for r in rows:
        art = hb.get_article(r["blog_id"], r["id"])
        body = art.get("body_html") or ""
        cu = len(faq_schema.extract_faq(body))

        clean = faq_schema.strip_faq_block(body)          # go khoi FAQ cu (neu co)
        block = render_block(r["title"], r["faqs"])       # render lai tu faqs (tieu de khoi da fix)
        new_body, n = faq_schema.attach(insert_block(clean, block))

        if n != len(r["faqs"]):
            print(f"  LỖI: bóc lại {n}/{len(r['faqs'])} câu — {r['handle']}")
            fail += 1
            continue

        act = f"THAY {cu} câu → {n} câu" if cu else f"CHÈN {n} câu"
        if dry:
            print(f"  {act}: {r['handle'][:48]}")
            done += 1
            continue

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (BACKUP_DIR / f"{r['id']}_{r['handle']}_v2_{stamp}.html").write_text(body, encoding="utf-8")

        try:
            hb.update_article(r["blog_id"], r["id"], {"body_html": new_body})
            err = None
        except Exception as e:
            err = e
        got = len(faq_schema.extract_faq(hb.get_article(r["blog_id"], r["id"]).get("body_html") or ""))
        if got == n:
            print(f"  {act}: {r['handle'][:48]}" + ("  (API báo lỗi nhưng ĐÃ GHI)" if err else ""))
            done += 1
        else:
            print(f"  LỖI THẬT ({got}/{n} câu): {r['handle']} — {str(err)[:60]}")
            fail += 1

    print(f"\n[XONG] ok={done} lỗi={fail}")
    if not dry and done:
        print("  -> Verify: py -3.12 _scripts/faq_verify.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
