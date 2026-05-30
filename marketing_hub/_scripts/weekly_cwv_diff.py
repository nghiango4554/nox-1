"""Diff CWV 2 tuan gan nhat -> output JSON `data/cwv_weekly_diff.json`.

Chay sau `weekly_cwv_snapshot.py` (cung Chu Nhat 02:00). Auto pick 2 tuan moi nhat
trong `seo_cwv_history`. Output JSON cho dashboard ops-center doc.

Chay tay:  py -3.12 _scripts/weekly_cwv_diff.py
Override:  py -3.12 _scripts/weekly_cwv_diff.py --current 22:2026 --prev 21:2026
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db

TOP_N = 10
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "cwv_weekly_diff.json"


def _parse_wy(s: str) -> tuple:
    a, b = s.split(":", 1)
    return int(a), int(b)


def _latest_two_weeks() -> list:
    """Return [(week_no, year), ...] 2 tuan moi nhat co data trong seo_cwv_history."""
    conn = db.get_conn()
    rows = conn.execute("""
        SELECT DISTINCT week_no, year
        FROM seo_cwv_history
        ORDER BY year DESC, week_no DESC
        LIMIT 2
    """).fetchall()
    conn.close()
    return [(r["week_no"], r["year"]) for r in rows]


def _avg(nums):
    nums = [n for n in nums if n is not None]
    return round(sum(nums) / len(nums), 1) if nums else None


def _diff_strategy(current, prev, strategy: str) -> dict:
    """current/prev = list[dict] tu cwv_history_get_week. Build diff per URL."""
    cur_map = {r["url"]: r for r in current}
    prev_map = {r["url"]: r for r in prev}
    common = sorted(set(cur_map) & set(prev_map))

    deltas = []
    for url in common:
        cs = cur_map[url]["performance_score"]
        ps = prev_map[url]["performance_score"]
        if cs is None or ps is None:
            continue
        deltas.append({
            "url": url,
            "prev_score": ps,
            "current_score": cs,
            "delta": cs - ps,
            "prev_lcp_ms": prev_map[url]["lcp_ms"],
            "current_lcp_ms": cur_map[url]["lcp_ms"],
        })

    improved = sorted([d for d in deltas if d["delta"] > 0], key=lambda d: -d["delta"])
    regressed = sorted([d for d in deltas if d["delta"] < 0], key=lambda d: d["delta"])

    return {
        "strategy": strategy,
        "current_avg_score": _avg([r["performance_score"] for r in current]),
        "prev_avg_score": _avg([r["performance_score"] for r in prev]),
        "avg_change": None,
        "current_count": len(current),
        "prev_count": len(prev),
        "common_count": len(common),
        "improved_count": len(improved),
        "regressed_count": len(regressed),
        "improved_top": improved[:TOP_N],
        "regressed_top": regressed[:TOP_N],
    }


def main():
    parser = argparse.ArgumentParser(description="Diff CWV 2 tuan gan nhat")
    parser.add_argument("--current", type=str, default=None, help="week:year, vi du 22:2026")
    parser.add_argument("--prev", type=str, default=None, help="week:year, vi du 21:2026")
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH), help="Output JSON path")
    args = parser.parse_args()

    db.init_db()

    if args.current and args.prev:
        cur_wy = _parse_wy(args.current)
        prev_wy = _parse_wy(args.prev)
    else:
        weeks = _latest_two_weeks()
        if len(weeks) < 2:
            print(f"[WARN] Can it nhat 2 tuan trong seo_cwv_history. Hien co {len(weeks)} tuan: {weeks}", flush=True)
            return 1
        cur_wy, prev_wy = weeks[0], weeks[1]

    print(f"Diff: current=tuan {cur_wy[0]}/{cur_wy[1]}  vs  prev=tuan {prev_wy[0]}/{prev_wy[1]}", flush=True)

    result = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "current_week": {"week_no": cur_wy[0], "year": cur_wy[1]},
        "prev_week": {"week_no": prev_wy[0], "year": prev_wy[1]},
        "strategies": {},
    }

    for strategy in ("mobile", "desktop"):
        current = db.cwv_history_get_week(cur_wy[0], cur_wy[1], strategy=strategy)
        prev = db.cwv_history_get_week(prev_wy[0], prev_wy[1], strategy=strategy)
        diff = _diff_strategy(current, prev, strategy)
        if diff["current_avg_score"] is not None and diff["prev_avg_score"] is not None:
            diff["avg_change"] = round(diff["current_avg_score"] - diff["prev_avg_score"], 1)
        result["strategies"][strategy] = diff
        print(
            f"  [{strategy}] avg {diff['prev_avg_score']} -> {diff['current_avg_score']} "
            f"(delta {diff['avg_change']}) | improved={diff['improved_count']} regressed={diff['regressed_count']}",
            flush=True,
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Diff written: {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
