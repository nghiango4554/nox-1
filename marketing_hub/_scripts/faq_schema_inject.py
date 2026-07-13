"""Boc khoi FAQ san co trong body_html bai blog -> sinh JSON-LD FAQPage -> PUT len Haravan.

Chi gan schema cho bai DA CO FAQ hien thi (dung luat Google: schema phai khop noi dung nhin thay).
Body cu luon backup ra nox-outputs/faq_backup/<article_id>.html truoc khi PUT.

Chay:
    py -3.12 _scripts/faq_schema_inject.py --dry            # xem truoc, khong PUT
    py -3.12 _scripts/faq_schema_inject.py --only <handle>  # lam 1 bai
    py -3.12 _scripts/faq_schema_inject.py --go             # PUT that, toan bo
"""
import argparse
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

BLOG_IDS = [1000906526, 1000960873]  # news, huong-dan
BACKUP_DIR = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_backup")
def process(blog_id: int, art: dict, dry: bool) -> dict:
    aid, handle = art["id"], art.get("handle")
    body = art.get("body_html") or ""
    if faq_schema.MARK_OPEN in body:
        return {"handle": handle, "status": "skip_da_co_schema"}
    new_body, n = faq_schema.attach(body)
    if n < faq_schema.MIN_QUESTIONS:
        return {"handle": handle, "status": "skip_khong_co_faq", "n": n}
    if dry:
        return {"handle": handle, "status": "SE_GAN", "n": n}

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (BACKUP_DIR / f"{aid}_{handle}_{stamp}.html").write_text(body, encoding="utf-8")

    hb.update_article(blog_id, aid, {"body_html": new_body})
    return {"handle": handle, "status": "DA_GAN", "n": n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="Xem truoc, khong PUT")
    ap.add_argument("--go", action="store_true", help="PUT that")
    ap.add_argument("--only", type=str, default=None, help="Chi lam 1 handle")
    a = ap.parse_args()
    dry = not a.go

    rows = []
    for bid in BLOG_IDS:
        page = 1
        while True:
            arts = hb.list_articles(bid, limit=50, page=page)
            if not arts:
                break
            for art in arts:
                if a.only and art.get("handle") != a.only:
                    continue
                rows.append(process(bid, art, dry))
            page += 1

    print(f"=== {'DRY RUN (khong PUT)' if dry else 'PUT THAT'} ===")
    cnt = {}
    for r in rows:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1
    for k, v in sorted(cnt.items()):
        print(f"  {k:24s} {v}")
    for r in rows:
        if r["status"] in ("SE_GAN", "DA_GAN"):
            print(f"  [{r['n']} cau] {r['handle']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
