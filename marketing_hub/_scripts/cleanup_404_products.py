"""Soft cleanup 8 SP bi 404 phat hien tu Phase 4C schema audit (30/5/2026).

Approach: KHONG hard delete khoi seo_pages (giu lich su 261-269 inbound link +
seo_cwv + content_jobs). Chi UPDATE status_code=404 + indexable=0 -> 8 SP
bien mat khoi schema audit list (query co indexable=1), reversible.

Verify 2 buoc:
1. Pre-check: DB co schema_errors LIKE %HTTP 404% (snapshot tu Phase 4C audit).
2. Live re-fetch confirm: gui HEAD request, neu KHONG 404 thi skip (du phong
   Sintech khoi phuc SP trong khoang thoi gian giua audit va cleanup).

Chay tay: py -3.12 _scripts/cleanup_404_products.py [--dry-run]
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import db

USER_AGENT = "SintechHubSEOBot/1.0 (+marketing_hub cleanup)"
TIMEOUT = 10


def _verify_404(url: str) -> tuple:
    """Re-fetch URL. Return (is_404, actual_status_or_err)."""
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        return (r.status_code == 404, str(r.status_code))
    except requests.RequestException as e:
        return (False, f"{type(e).__name__}: {str(e)[:60]}")


def main():
    parser = argparse.ArgumentParser(description="Soft cleanup 404 SP")
    parser.add_argument("--dry-run", action="store_true", help="Khong UPDATE, chi log")
    args = parser.parse_args()

    conn = db.get_conn()
    rows = conn.execute("""
        SELECT id, url, url_type FROM seo_pages
        WHERE schema_errors LIKE '%HTTP 404%'
          AND status_code=200 AND indexable=1
    """).fetchall()
    conn.close()
    targets = [dict(r) for r in rows]
    total = len(targets)

    if total == 0:
        print("[INFO] Khong co URL 404 nao trong DB.")
        return 0

    print(f"=== Cleanup 404 SP ({'DRY RUN' if args.dry_run else 'LIVE'}) ===")
    print(f"Target: {total} URL")
    print("---")

    updated = 0
    skipped_not_404 = 0
    now = datetime.now().isoformat(timespec="seconds")

    for t in targets:
        url = t["url"]
        is_404, actual = _verify_404(url)
        if not is_404:
            print(f"  [SKIP id={t['id']}] {url[:60]}")
            print(f"         actual status: {actual} -> KHONG cleanup, co the Sintech da khoi phuc")
            skipped_not_404 += 1
            continue

        if args.dry_run:
            print(f"  [DRY id={t['id']}] {url[:60]} -> would UPDATE status_code=404, indexable=0")
        else:
            conn = db.get_conn()
            conn.execute("""
                UPDATE seo_pages
                SET status_code=404, indexable=0, indexability_reason='not_found_404',
                    last_crawled=?
                WHERE id=?
            """, (now, t["id"]))
            conn.commit()
            conn.close()
            print(f"  [OK  id={t['id']}] {url[:60]} -> indexable=0, status_code=404")
        updated += 1

    print("---")
    print(f"Summary: {updated} updated, {skipped_not_404} skipped (re-fetch khong 404)")
    if args.dry_run:
        print("DRY RUN - khong co thay doi thuc te.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
