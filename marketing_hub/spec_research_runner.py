"""Chay research HÀNG LOẠT theo từng collection — CHỈ TRA, KHÔNG SYNC.

Vợ chốt 22/7: research toàn bộ SP theo collection, ghi rõ vì sao lấy / vì sao bỏ nguồn nào.
- Tầng 1: HTTP thuần (nhanh, chạy song song nhiều luồng).
- Tầng 2: Chrome THẬT chạy từ script cho SP mà tầng 1 không ra gì (không dùng Chrome-MCP).
- Có TRẦN QUERY để không đốt hết hạn mức Serper (2.500/tháng).
- Kết quả lưu bảng `spec_research_source`, xem trong tab /spec → nút "🔎 Nguồn spec".
"""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import db
import spec_index as si
import spec_research as sr

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state",
                          "spec_research_progress.json")
_LOCK = threading.Lock()


def _save_state(st: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)


def load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def targets_by_collection(only_missing: bool = True) -> list[dict]:
    """Danh sách SP cần tra, gom theo collection (theo thứ tự menu live)."""
    conn = db.get_conn()
    colls = conn.execute("SELECT handle, tag_filter, title, root FROM spec_menu_collections "
                         "ORDER BY sort_order").fetchall()
    done = {r[0] for r in conn.execute(
        "SELECT DISTINCT haravan_id FROM spec_research_source")} if only_missing else set()
    seen, out = set(), []
    for c in colls:
        rows = conn.execute("""SELECT p.haravan_id, p.title, p.product_type
            FROM product_spec_index p JOIN spec_group_products g ON g.haravan_id = p.haravan_id
            WHERE g.handle=? AND g.tag_filter=? AND p.condition_kind='new'
              AND COALESCE(p.is_service,0)=0 AND COALESCE(p.skipped,0)=0
            ORDER BY p.title""", (c["handle"], c["tag_filter"])).fetchall()
        items = [dict(r) for r in rows if r["haravan_id"] not in done
                 and r["haravan_id"] not in seen]
        seen |= {r["haravan_id"] for r in rows}
        if items:
            out.append({"handle": c["handle"], "tag": c["tag_filter"], "title": c["title"],
                        "root": c["root"], "items": items})
    # SP không thuộc collection nào
    rest = [dict(r) for r in conn.execute("""SELECT haravan_id, title, product_type
        FROM product_spec_index WHERE condition_kind='new' AND COALESCE(is_service,0)=0
          AND COALESCE(skipped,0)=0
          AND haravan_id NOT IN (SELECT haravan_id FROM spec_group_products)
        ORDER BY title""").fetchall() if r["haravan_id"] not in done]
    conn.close()
    if rest:
        out.append({"handle": "__ungrouped__", "tag": "", "title": "SP chưa phân loại",
                    "root": "Khác", "items": rest})
    return out


def _why_picked(res: dict) -> str:
    n = len(res.get("rows") or [])
    conf = res.get("confirmed", 0)
    bits = [f"nhiều dòng nhất ({n})", res.get("evidence", "")]
    if conf:
        bits.append(f"{conf} dòng trùng khớp với nguồn thứ hai")
    return " · ".join(b for b in bits if b)


def run(max_queries: int = 400, workers: int = 6, log=print) -> dict:
    """Tra theo từng collection tới khi hết SP hoặc chạm trần query."""
    started = datetime.now().isoformat(timespec="seconds")
    groups = targets_by_collection()
    total = sum(len(g["items"]) for g in groups)
    st = {"started": started, "total_targets": total, "done": 0, "queries": 0,
          "collections_done": [], "current": "", "finished": False,
          "found": 0, "empty": 0, "blocked": 0}
    _save_state(st)
    log(f"CẦN TRA: {total} SP trong {len(groups)} danh mục · trần {max_queries} query")

    stop = False
    for g in groups:
        if stop:
            break
        st["current"] = f"{g['root']} › {g['title']}"
        _save_state(st)
        t0 = time.time()
        res_count = {"found": 0, "empty": 0, "blocked": 0}

        def work(it):
            nonlocal stop
            with _LOCK:
                if st["queries"] >= max_queries:
                    stop = True
                    return None
                st["queries"] += 1
            try:
                res = sr.research(it["title"], it["product_type"] or "")
            except Exception as e:  # noqa: BLE001
                return ("blocked", it, str(e))
            # ghi rõ vì sao lấy nguồn này
            for c in res.get("candidates") or []:
                if c.get("picked"):
                    c["why"] = f"ĐÃ DÙNG vì {_why_picked(res)}"
                else:
                    c["why"] = (f"đạt cổng kiểm ({c.get('why','')}) nhưng ít dòng hơn "
                                f"({len(c.get('rows') or [])} dòng) → chỉ dùng để đối chiếu")
            si.save_research_sources(it["haravan_id"], res)
            return ("found" if res.get("ok") else "empty", it, res.get("reason", ""))

        with ThreadPoolExecutor(max_workers=workers) as ex:
            for r in ex.map(work, g["items"]):
                if not r:
                    continue
                kind, _it, _msg = r
                res_count[kind] += 1
                with _LOCK:
                    st["done"] += 1
                    st[kind] += 1
        _save_state(st)
        st["collections_done"].append(
            {"title": g["title"], "n": len(g["items"]), **res_count,
             "sec": round(time.time() - t0, 1)})
        log(f"  ✔ {g['title'][:34]:<34} {len(g['items']):3d} SP · "
            f"ra spec {res_count['found']:3d} · rỗng {res_count['empty']:3d} · "
            f"lỗi {res_count['blocked']:2d} · {round(time.time()-t0,1)}s "
            f"[{st['queries']}/{max_queries} query]")
        if stop:
            log("  ⏸ CHẠM TRẦN QUERY — dừng, phần còn lại chạy tiếp lần sau")
            break

    st["finished"] = True
    st["current"] = ""
    _save_state(st)
    return st
