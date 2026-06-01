# -*- coding: utf-8 -*-
"""
Sync collection → product (Haravan) vào DB `collection_products`.

Quét tất cả handle xuất hiện trong data/seo_tiers.json (T1/T2/T3 có handle),
resolve handle→collection_id qua data/haravan_collections.json, gọi Haravan API
lấy SP từng collection rồi ghi DB. Idempotent per collection (replace).

Chạy:
  py -3.12 _scripts/sync_collection_products.py            # full
  py -3.12 _scripts/sync_collection_products.py --limit 3  # test 3 collection
  py -3.12 _scripts/sync_collection_products.py --only cpu # 1 handle
"""
import argparse
import io
import json
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
import haravan_client as hv  # noqa: E402

DATA = ROOT / "data"


def collect_tier_handles():
    d = json.load(open(DATA / "seo_tiers.json", encoding="utf-8"))
    hs = []
    seen = set()
    def add(h):
        if h and h not in seen:
            seen.add(h); hs.append(h)
    for t in d["tiers"]:
        add(t.get("handle"))
        for t2 in t["children"]:
            add(t2.get("handle"))
            for t3 in t2["children"]:
                add(t3.get("handle"))
    return hs


def handle_to_id():
    cols = json.load(open(DATA / "haravan_collections.json", encoding="utf-8"))
    m = {}
    for c in cols:
        if c.get("handle"):
            m[c["handle"]] = {"id": c["id"], "type": c.get("type"),
                              "count": c.get("products_count")}
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="chỉ sync N collection đầu (test)")
    ap.add_argument("--only", type=str, default=None, help="chỉ sync 1 handle")
    ap.add_argument("--delay", type=float, default=0.3, help="nghỉ giữa các collection (s)")
    args = ap.parse_args()

    db.init_db()
    handles = collect_tier_handles()
    hmap = handle_to_id()

    if args.only:
        handles = [args.only]
    elif args.limit:
        handles = handles[:args.limit]

    total = len(handles)
    print(f"▶ Sync {total} collection → product\n")
    t0 = time.time()
    ok = miss = err = 0
    grand = 0
    for i, h in enumerate(handles, 1):
        info = hmap.get(h)
        if not info:
            print(f"  [{i}/{total}] {h:38s} ⚠️ không có trong haravan_collections.json")
            miss += 1
            continue
        try:
            prods = hv.list_products_in_collection(info["id"])
            n = db.collection_products_replace(h, prods)
            grand += n
            ok += 1
            print(f"  [{i}/{total}] {h:38s} ✓ {n:4d} SP  (col_id={info['id']} {info['type']})")
        except Exception as e:
            err += 1
            print(f"  [{i}/{total}] {h:38s} ❌ {str(e)[:80]}")
        if args.delay:
            time.sleep(args.delay)

    dt = time.time() - t0
    st = db.collection_products_stats()
    print(f"\n=== DONE in {dt:.0f}s ===")
    print(f"  collection: ok={ok} miss={miss} err={err}")
    print(f"  rows ghi lần này (tổng cộng dồn): {grand}")
    print(f"  DB stats: {st['collections']} collection · {st['rows']} rows · "
          f"{st['products']} SP distinct · last={st['last_sync']}")


if __name__ == "__main__":
    main()
