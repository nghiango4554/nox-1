"""Bulk audit JSON-LD schema cho toan bo URL trong seo_pages.

Phase 4C cua Task 4 SEO Crawl Optimization. Loop seo_pages indexable=1 + 200,
goi schema_scanner.scan_url() qua thread pool, upsert DB. Idempotent: skip URL
co schema_scanned_at < 7 ngay (re-audit weekly).

Chay tay:        py -3.12 _scripts/audit_schema_all.py
Dev test:        py -3.12 _scripts/audit_schema_all.py --limit 50
Force full:      py -3.12 _scripts/audit_schema_all.py --force
Filter type:     py -3.12 _scripts/audit_schema_all.py --url-type product
"""
import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import schema_scanner

WORKERS = 5
DELAY_PER_WORKER = 0.5
RE_AUDIT_DAYS = 7


def _pick_targets(url_type: str = None, limit: int = None, force: bool = False) -> list:
    """Pick URL can audit: indexable 200, chua scan hoac scan qua 7 ngay."""
    conn = db.get_conn()
    sql = """SELECT url, url_type FROM seo_pages
             WHERE status_code=200 AND indexable=1"""
    args = []
    if url_type:
        sql += " AND url_type=?"
        args.append(url_type)
    if not force:
        cutoff = (datetime.now() - timedelta(days=RE_AUDIT_DAYS)).isoformat(timespec="seconds")
        sql += " AND (schema_scanned_at IS NULL OR schema_scanned_at < ?)"
        args.append(cutoff)
    sql += " ORDER BY url_type, url"
    if limit:
        sql += " LIMIT ?"
        args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [(r["url"], r["url_type"]) for r in rows]


def _scan_one(url: str) -> tuple:
    """Wrap scan + upsert + delay. Return (url, ok, types, error)."""
    try:
        data = schema_scanner.scan_url(url)
        db.seo_schema_upsert(url, data)
        time.sleep(DELAY_PER_WORKER)
        if data.get("fetch_error"):
            return (url, False, [], data["fetch_error"])
        types_json = data.get("schema_types") or "[]"
        import json
        try:
            types = json.loads(types_json)
        except Exception:
            types = []
        return (url, True, types, None)
    except Exception as e:
        return (url, False, [], f"{type(e).__name__}: {str(e)[:80]}")


def main():
    parser = argparse.ArgumentParser(description="Bulk audit JSON-LD schema")
    parser.add_argument("--limit", type=int, default=None, help="Max URL audit (dev test)")
    parser.add_argument("--url-type", type=str, default=None, help="Filter url_type")
    parser.add_argument("--force", action="store_true", help="Force re-audit kê cả scan <7 ngày")
    parser.add_argument("--workers", type=int, default=WORKERS, help=f"Thread workers (default {WORKERS})")
    args = parser.parse_args()

    db.init_db()
    targets = _pick_targets(url_type=args.url_type, limit=args.limit, force=args.force)
    total = len(targets)
    if total == 0:
        print("[INFO] Khong co URL nao can audit. Tat ca da scan trong 7 ngay qua.")
        return 0

    type_counts = {}
    for _, ut in targets:
        type_counts[ut] = type_counts.get(ut, 0) + 1

    print(f"=== Bulk schema audit ===", flush=True)
    print(f"Target: {total} URL ({args.workers} workers, delay {DELAY_PER_WORKER}s/req)", flush=True)
    print(f"Per url_type: {type_counts}", flush=True)
    print(f"Re-audit cutoff: >{RE_AUDIT_DAYS} days {'(IGNORED, force=on)' if args.force else ''}", flush=True)
    print(f"---", flush=True)

    start = time.time()
    done = 0
    success = 0
    fail = 0
    aggregate_types = {}
    has_product = 0
    has_faq = 0
    has_article = 0

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_scan_one, url): url for url, _ in targets}
        for f in as_completed(futures):
            url, ok, types, err = f.result()
            done += 1
            if ok:
                success += 1
                for t in types:
                    aggregate_types[t] = aggregate_types.get(t, 0) + 1
                if "Product" in types:
                    has_product += 1
                if "FAQPage" in types:
                    has_faq += 1
                if any(t in types for t in ("Article", "NewsArticle", "BlogPosting", "TechArticle")):
                    has_article += 1
            else:
                fail += 1
            if done % 50 == 0 or done == total:
                elapsed = time.time() - start
                rate = done / elapsed if elapsed else 0
                eta = (total - done) / rate if rate else 0
                print(
                    f"  [{done}/{total}] ok={success} fail={fail} | "
                    f"{rate:.1f} req/s | ETA {int(eta)}s",
                    flush=True,
                )

    elapsed = time.time() - start
    print(f"---", flush=True)
    print(f"[DONE] {success}/{total} success, {fail} fail in {int(elapsed)}s", flush=True)
    print(f"Aggregate @type counts (top 10):", flush=True)
    top = sorted(aggregate_types.items(), key=lambda kv: -kv[1])[:10]
    for t, n in top:
        print(f"  {t:24s} {n:>6d}", flush=True)
    print(f"Flag breakdown (out of {success} success):", flush=True)
    print(f"  has_product: {has_product} ({100.0*has_product/success:.1f}%)" if success else "  has_product: 0", flush=True)
    print(f"  has_faq:     {has_faq} ({100.0*has_faq/success:.1f}%)" if success else "  has_faq: 0", flush=True)
    print(f"  has_article: {has_article} ({100.0*has_article/success:.1f}%)" if success else "  has_article: 0", flush=True)

    # Auto-snapshot schema gap timeline (Phase H3 SEO History Hub)
    try:
        rid = db.seo_schema_history_capture()
        print(f"[OK] seo_schema_history snapshot id={rid} (auto-capture sau bulk audit)", flush=True)
    except Exception as e:
        print(f"[WARN] seo_schema_history_capture fail: {e}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
