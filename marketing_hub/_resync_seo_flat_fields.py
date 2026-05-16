"""Bulk re-sync SEO title/description qua FLAT FIELD vào resource endpoint
(/products/{id}.json, /smart_collections/{id}.json, /blogs/{bid}/articles/{aid}.json).

LÝ DO: Trước đó `_resync_seo_metafields.py` push vào endpoint
`/{resource}/{id}/metafields.json` với namespace=global. Haravan lưu data thật
vào DB metafield, NHƯNG theme Sintech KHÔNG render từ đó — theme đọc field flat
`metafields_global_title_tag` / `metafields_global_description_tag` ở chỗ khác.

Test 15/5: PUT flat field qua /products/{id}.json → web render title+meta mới
sau 3 giây (verified HTML render). Field flat KHÔNG echo back ở GET nhưng theme
vẫn đọc được.

Chỉ push title/meta flat field, KHÔNG động body_html, KHÔNG động field khác.
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


def _put_flat_seo(resource_type: str, rid: int, title: str, meta: str) -> dict:
    """PUT flat SEO field qua resource endpoint chính."""
    flat = {
        "id": rid,
        "metafields_global_title_tag": title,
        "metafields_global_description_tag": meta,
    }
    if resource_type == "products":
        return hc._request("PUT", f"/products/{rid}.json", payload={"product": flat})
    if resource_type == "smart_collections":
        return hc._request("PUT", f"/smart_collections/{rid}.json",
                           payload={"smart_collection": flat})
    if resource_type == "custom_collections":
        return hc._request("PUT", f"/custom_collections/{rid}.json",
                           payload={"custom_collection": flat})
    raise ValueError(f"Unsupported resource_type: {resource_type}")


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
    print(f"RE-SYNC FLAT FIELD {label}: {total} bài")
    print(f"{'=' * 60}")

    ok = fail = 0
    errors = []
    t_start = time.time()

    for i, r in enumerate(rows, 1):
        jid = r["id"]
        hid = int(r["haravan_id"])
        title = (r["edited_title"] or "").strip()
        meta = (r["edited_meta"] or "").strip()
        handle = (r["handle"] or "")[:35]

        try:
            try:
                _put_flat_seo(resource_type, hid, title, meta)
            except hc.HaravanError as e_primary:
                if resource_type == "smart_collections" and "404" in str(e_primary):
                    _put_flat_seo("custom_collections", hid, title, meta)
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
        time.sleep(0.15)

    elapsed = time.time() - t_start
    print(f"\n{label} done: OK {ok}/{total}, FAIL {fail}, time {elapsed:.0f}s")
    if errors[:10]:
        print(f"\nFirst {min(10, len(errors))} errors:")
        for e in errors[:10]:
            print(f"  {e}")
    return ok, fail


def main():
    print("Bulk re-sync SEO FLAT FIELD — Sintech marketing_hub")
    print("PUT metafields_global_title_tag + metafields_global_description_tag")
    print("qua resource endpoint chính (theme đọc field flat, không phải /metafields)")

    ok_col, fail_col = resync_table("collection_jobs", "smart_collections", "COLLECTIONS")
    ok_prod, fail_prod = resync_table("content_jobs", "products", "PRODUCTS")

    print(f"\n{'=' * 60}")
    print(f"TOTAL: collections OK {ok_col} fail {fail_col} · products OK {ok_prod} fail {fail_prod}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
