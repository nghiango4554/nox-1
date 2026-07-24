"""Chạy research thông số CHỈ bằng nguồn miễn phí (DuckDuckGo), KHÔNG đụng quota Serper.

    python spec_research_free.py --max 20        # chạy thử 20 SP
    python spec_research_free.py --max 700       # chạy tiếp phần còn lại

Chỉ TRA và LƯU NGUỒN, tuyệt đối KHÔNG đẩy gì lên Haravan.
"""

import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace",
                              line_buffering=True)

import db  # noqa: E402
import free_search as fs  # noqa: E402
import serper_search as ss  # noqa: E402
import spec_research as sr  # noqa: E402
import spec_research_runner as rr  # noqa: E402

_stat = {"n": 0}


def ddg_only(q, num=10):
    """Ép mọi truy vấn đi qua DuckDuckGo. Serper không bị gọi lần nào."""
    _stat["n"] += 1
    try:
        return fs.search(q, num=num)
    except Exception as e:  # noqa: BLE001
        print(f"  ddg lỗi: {str(e)[:70]}")
        return []


ss.search_google = sr.ss.search_google = ddg_only

MAX_Q = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 700


def status():
    conn = db.get_conn()
    tot = conn.execute("""SELECT COUNT(*) FROM product_spec_index WHERE condition_kind='new'
        AND COALESCE(is_service,0)=0 AND COALESCE(skipped,0)=0
        AND COALESCE(published,1)=1""").fetchone()[0]
    SCOPE = """ AND haravan_id IN (SELECT haravan_id FROM product_spec_index
        WHERE condition_kind='new' AND COALESCE(is_service,0)=0
          AND COALESCE(skipped,0)=0 AND COALESCE(published,1)=1)"""
    tra = conn.execute("SELECT COUNT(DISTINCT haravan_id) FROM spec_research_source "
                       "WHERE 1=1" + SCOPE).fetchone()[0]
    ok = conn.execute("SELECT COUNT(DISTINCT haravan_id) FROM spec_research_source "
                      "WHERE status='dung'" + SCOPE).fetchone()[0]
    conn.close()
    print(f"SP trong phạm vi: {tot} · đã tra: {tra} · có nguồn dùng được: {ok} "
          f"· CHƯA TRA: {tot - tra}")
    return tot - tra


print("=== TRƯỚC KHI CHẠY (nguồn: DuckDuckGo, Serper KHÔNG dùng) ===")
status()
t0 = time.time()
st = rr.run(max_queries=MAX_Q, workers=4)
print(f"\n=== XONG sau {round((time.time() - t0) / 60, 1)} phút ===")
print(f"tra {st['done']} SP · ra spec {st['found']} · không ra {st['empty']} "
      f"· tổng truy vấn ddg {_stat['n']}")
status()
