"""Bulk re-sync SEO metafields (global.title_tag + global.description_tag) cho:
- content_jobs đã synced (sản phẩm)
- collection_jobs đã synced (cate)

LÝ DO: trước 15/5/2026 sync_*_to_haravan dùng flat field
`metafields_global_title_tag`/`metafields_global_description_tag` — Haravan trả 200
nhưng KHÔNG persist. Đã chuyển sang explicit `/{resource}/{id}/metafields.json` —
script này push lại cho tất cả bài đã sync trước fix.

Chỉ push metafields, KHÔNG động body. Idempotent: upsert (PUT nếu existing, POST nếu chưa).
"""
import sys
import io
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import db
import haravan_client as hc


def resync_table(table: str, resource_type: str, label: str):
    conn = db.get_conn()
    rows = conn.execute(f"""
        SELECT id, haravan_id, edited_title, edited_meta, handle
        FROM {table}
        WHERE status='synced' AND haravan_id IS NOT NULL
          AND edited_title IS NOT NULL AND edited_title != ''
        ORDER BY id
    """).fetchall()
    conn.close()

    total = len(rows)
    print(f"\n{'=' * 60}")
    print(f"RE-SYNC {label}: {total} bài")
    print(f"{'=' * 60}")

    ok = fail = 0
    errors = []
    t_start = time.time()

    for i, r in enumerate(rows, 1):
        jid = r["id"]
        hid = r["haravan_id"]
        title = (r["edited_title"] or "").strip()
        meta = (r["edited_meta"] or "").strip()
        handle = (r["handle"] or "")[:35]

        try:
            try:
                seo = hc.upsert_seo_metafields(resource_type, int(hid),
                                                title=title, description=meta)
            except hc.HaravanError as e_primary:
                # Collection có thể là custom thay vì smart — fallback
                if resource_type == "smart_collections" and "404" in str(e_primary):
                    seo = hc.upsert_seo_metafields("custom_collections", int(hid),
                                                    title=title, description=meta)
                else:
                    raise
            ok += 1
            if i % 20 == 0 or i == total:
                elapsed = time.time() - t_start
                rate = i / elapsed if elapsed > 0 else 0
                eta = (total - i) / rate if rate > 0 else 0
                print(f"  [{i:>4}/{total}] ok={ok} fail={fail} · {rate:.1f}/s · ETA {eta:.0f}s · #{jid:>5} {handle}")
        except Exception as e:
            fail += 1
            err_short = str(e)[:120]
            errors.append(f"#{jid} {handle}: {err_short}")
            print(f"  [{i:>4}/{total}] FAIL #{jid} {handle}: {err_short}")
        time.sleep(0.15)  # rate limit ~6/s, dưới ngưỡng Haravan 40/s

    elapsed = time.time() - t_start
    print(f"\n{label} done: OK {ok}/{total}, FAIL {fail}, time {elapsed:.0f}s")
    if errors[:10]:
        print(f"\nFirst {min(10, len(errors))} errors:")
        for e in errors[:10]:
            print(f"  {e}")
    return ok, fail


def main():
    print("Bulk re-sync SEO metafields — Sintech marketing_hub")
    print("Push global.title_tag + global.description_tag qua explicit endpoint")

    ok_col, fail_col = resync_table("collection_jobs", "smart_collections", "COLLECTIONS")
    ok_prod, fail_prod = resync_table("content_jobs", "products", "PRODUCTS")

    print(f"\n{'=' * 60}")
    print(f"TOTAL: collections OK {ok_col} fail {fail_col} · products OK {ok_prod} fail {fail_prod}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
