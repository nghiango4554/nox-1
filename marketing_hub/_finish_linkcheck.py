# -*- coding: utf-8 -*-
"""Làm nốt link-check: check mọi target_url chưa có status (lock-free, đa luồng) → ghi DB theo lô.
Dùng đúng seo._check_link (HEAD + per-host semaphore + classify) → data nhất quán với job gốc."""
import sys, io, time, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import seo, db

# Bump per-host cho web nhà mình (sintech.vn) — an toàn dưới ngưỡng Haravan ~20 → nhanh hơn
for h in ('sintech.vn', 'www.sintech.vn'):
    seo.HOST_CONCURRENCY_OVERRIDES[h] = 12

c = sqlite3.connect('data/posts.db', timeout=30)
urls = [r[0] for r in c.execute("select distinct target_url from seo_links where status_code is null")]
c.close()
print(f"URL chưa check: {len(urls)} | workers={seo.LINK_CHECK_WORKERS}", flush=True)

pending = []   # (status_code, error_kind, target_url) — batch func tự thêm last_checked
written = 0
checked = 0
broken = 0

def flush(rows):
    global written
    if not rows: return
    last = None
    for attempt in range(15):
        try:
            db.seo_link_status_update_batch(rows); written += len(rows); return
        except Exception as e:
            last = e
            if "lock" in str(e).lower():
                time.sleep(3); continue
            break   # lỗi không phải lock → dừng retry, lộ ra
    print(f"  [WARN] ghi {len(rows)} dòng fail: {type(last).__name__}: {last}", flush=True)

t0 = time.time()
with ThreadPoolExecutor(max_workers=seo.LINK_CHECK_WORKERS) as ex:
    futs = [ex.submit(seo._check_link, u) for u in urls]
    for f in as_completed(futs):
        target, sc, ek = f.result()
        pending.append((sc, ek, target))
        checked += 1
        if sc in (404, 410): broken += 1
        if len(pending) >= 800:        # flush lô ~800 (1 transaction ngắn)
            flush(pending); pending = []
        if checked % 1000 == 0:
            rate = checked / max(1, time.time() - t0)
            print(f"  checked {checked}/{len(urls)} | ghi {written} | ~{rate:.0f}/s | 404/410={broken}", flush=True)
flush(pending)

c = sqlite3.connect('data/posts.db', timeout=30)
left = c.execute("select count(distinct target_url) from seo_links where status_code is null").fetchone()[0]
c.close()
print(f"XONG: checked {checked}, ghi {written}, còn unchecked distinct={left}, mất {time.time()-t0:.0f}s", flush=True)
