"""Snapshot CWV data tuan hien tai vao bang seo_cwv_history.

Chay standalone, khong phu thuoc Flask. Dang ky Task Scheduler "Marketing Hub Weekly CWV Snapshot"
chay Chu Nhat 02:00 hang tuan. Idempotent: chay lai cung tuan -> skip.

Chay tay:  py -3.12 _scripts/weekly_cwv_snapshot.py
Override:  py -3.12 _scripts/weekly_cwv_snapshot.py --week 22 --year 2026
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db


def main():
    parser = argparse.ArgumentParser(description="Snapshot CWV tuan hien tai")
    parser.add_argument("--week", type=int, default=None, help="ISO week number (1-53). Default: tuan hien tai")
    parser.add_argument("--year", type=int, default=None, help="ISO year. Default: nam hien tai")
    args = parser.parse_args()

    iso = datetime.now().isocalendar()
    week_no = args.week if args.week is not None else iso.week
    year = args.year if args.year is not None else iso.year

    db.init_db()

    if db.cwv_history_has_week(week_no, year):
        print(f"[SKIP] Tuan {week_no}/{year} da snapshot truoc do.", flush=True)
        return 0

    conn = db.get_conn()
    total_cwv = conn.execute("SELECT COUNT(*) FROM seo_cwv").fetchone()[0]
    conn.close()
    if total_cwv == 0:
        print(f"[WARN] Bang seo_cwv rong, khong co data de snapshot.", flush=True)
        return 1

    print(f"Bat dau snapshot tuan {week_no}/{year} ({total_cwv} rows seo_cwv)...", flush=True)
    snapshot_at = datetime.now().isoformat(timespec="seconds")
    n = db.cwv_history_snapshot(week_no, year, snapshot_at=snapshot_at)
    print(f"[OK] Snapshot tuan {week_no}/{year}: {n} rows ({snapshot_at}).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
