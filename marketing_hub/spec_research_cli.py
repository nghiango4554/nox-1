"""Chạy research thông số cho phần SP CÒN LẠI — gọi 1 lệnh là xong.

    python spec_research_cli.py --max 700            # chạy tiếp, trần 700 query Serper
    python spec_research_cli.py --max 700 --ddg      # hết Serper thì rơi sang DuckDuckGo
    python spec_research_cli.py --status             # chỉ xem còn bao nhiêu SP chưa tra

Chỉ TRA và LƯU NGUỒN, tuyệt đối KHÔNG đẩy gì lên Haravan.
"""

import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace",
                              line_buffering=True)

import db  # noqa: E402
import spec_research_runner as rr  # noqa: E402


def status():
    conn = db.get_conn()
    tot = conn.execute("""SELECT COUNT(*) FROM product_spec_index WHERE condition_kind='new'
        AND COALESCE(is_service,0)=0 AND COALESCE(skipped,0)=0""").fetchone()[0]
    tra = conn.execute("SELECT COUNT(DISTINCT haravan_id) FROM spec_research_source").fetchone()[0]
    ok = conn.execute("SELECT COUNT(DISTINCT haravan_id) FROM spec_research_source "
                      "WHERE status='dung'").fetchone()[0]
    conn.close()
    print(f"SP trong phạm vi: {tot} · đã tra: {tra} · có nguồn dùng được: {ok} "
          f"· CHƯA TRA: {tot - tra}")
    return tot - tra


if "--status" in sys.argv:
    status()
    sys.exit()

MAX_Q = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 700
if "--ddg" in sys.argv:
    import free_search as fs
    import serper_search as ss
    import spec_research as sr
    _orig, state = ss.search_google, {"dead": False, "serper": 0, "ddg": 0}

    def hybrid(q, num=10):
        if not state["dead"]:
            try:
                r = _orig(q, num=num)
                if r:
                    state["serper"] += 1
                    return r
                state["dead"] = True
                print("⚠️ Serper hết/không trả kết quả → chuyển sang DuckDuckGo (chậm hơn)")
            except Exception as e:  # noqa: BLE001
                state["dead"] = True
                print(f"⚠️ Serper lỗi: {str(e)[:60]} → chuyển sang DuckDuckGo")
        state["ddg"] += 1
        return fs.search(q, num=num)

    ss.search_google = sr.ss.search_google = hybrid

print("=== TRƯỚC KHI CHẠY ===")
status()
t0 = time.time()
st = rr.run(max_queries=MAX_Q, workers=8)
print(f"\n=== XONG sau {round((time.time()-t0)/60, 1)} phút ===")
print(f"tra {st['done']} SP · ra spec {st['found']} · không ra {st['empty']}")
status()
