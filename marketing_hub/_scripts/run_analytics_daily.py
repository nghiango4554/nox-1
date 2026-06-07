# -*- coding: utf-8 -*-
"""CLI entry: chạy Analytics Daily orchestration (cho Windows Task Scheduler / manual).

Dùng:  py -3.12 marketing_hub/_scripts/run_analytics_daily.py
Chạy 1 lần, in tóm tắt JSON, exit 0 nếu success / 1 nếu có step lỗi. KHÔNG log token.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # marketing_hub/

from services import analytics_daily_service as ops  # noqa: E402


def main():
    res = ops.run_orchestration(trigger="scheduler")
    summary = {"status": res["status"], "failed_steps": res["failed_steps"],
               "new_p0": res["new_p0"], "new_p1": res["new_p1"],
               "alert_sent": res["alert_sent"], "duration_seconds": res["duration_seconds"],
               "steps": [{"step": s["step"], "status": s["status"]} for s in res["steps"]]}
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
