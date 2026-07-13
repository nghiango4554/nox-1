"""Day khoi FAQ da DUYET len Haravan (buoc sau faq_gen.py).

Doc file JSON do faq_gen sinh -> chen khoi FAQ vao CUOI bai (truoc phan signature neu co)
-> gan comment FAQJSON -> PUT. Theme article.liquid tu in JSON-LD FAQPage.

Body cu LUON backup ra nox-outputs/faq_backup/ truoc khi PUT.
Idempotent: bai da co khoi FAQ roi thi BO QUA (khong chen 2 lan).

Chay:
    py -3.12 _scripts/faq_push.py <file.json> --dry     # xem truoc
    py -3.12 _scripts/faq_push.py <file.json> --go      # day that
"""
import argparse
import json
import re
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

BACKUP_DIR = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_backup")
# Signature/blockquote phai o CUOI bai -> khoi FAQ chen TRUOC chung
TAIL_RE = re.compile(r"(<blockquote|<p[^>]*>\s*<em>\s*Tư vấn|<p[^>]*>\s*<em>\s*Bài viết)", re.I)


def insert_block(body: str, block: str) -> str:
    """Chen khoi FAQ truoc signature/blockquote cuoi bai; khong co thi noi vao cuoi."""
    body = faq_schema.strip_comment(body)
    m = TAIL_RE.search(body)
    if m:
        return body[:m.start()] + "\n" + block + "\n" + body[m.start():]
    return body + "\n" + block


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file")
    ap.add_argument("--go", action="store_true", help="PUT that (mac dinh chi dry-run)")
    ap.add_argument("--only", type=str, default=None, help="Chi day 1 handle")
    a = ap.parse_args()
    dry = not a.go

    rows = json.loads(Path(a.json_file).read_text(encoding="utf-8"))
    if a.only:
        rows = [r for r in rows if r["handle"] == a.only]

    print(f"=== {'DRY RUN (khong PUT)' if dry else 'PUT THAT'} — {len(rows)} bai ===\n")
    done = skip = fail = 0
    for r in rows:
        art = hb.get_article(r["blog_id"], r["id"])
        body = art.get("body_html") or ""

        if len(faq_schema.extract_faq(body)) >= faq_schema.MIN_QUESTIONS:
            print(f"  BO QUA (da co FAQ): {r['handle']}")
            skip += 1
            continue

        new_body = insert_block(body, r["block_html"])
        new_body, n = faq_schema.attach(new_body)
        if n < len(r["faqs"]):
            print(f"  LOI: chen xong chi boc lai duoc {n}/{len(r['faqs'])} cau — {r['handle']}")
            fail += 1
            continue

        if dry:
            print(f"  SE DAY {n} cau: {r['handle']}")
            done += 1
            continue

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (BACKUP_DIR / f"{r['id']}_{r['handle']}_{stamp}.html").write_text(body, encoding="utf-8")
        hb.update_article(r["blog_id"], r["id"], {"body_html": new_body})
        print(f"  DA DAY {n} cau: {r['handle']}")
        done += 1

    print(f"\n[XONG] day={done} bo_qua={skip} loi={fail}")
    if not dry and done:
        print("  -> Verify: py -3.12 _scripts/faq_verify.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
