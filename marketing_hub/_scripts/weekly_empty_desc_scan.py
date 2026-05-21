"""Quet SP thieu mo ta (empty-desc) — chay standalone, ghi thang DB.

Khong phu thuoc Flask dang chay (import seo + goi run_empty_desc_scan truc tiep).
Dang ky Task Scheduler "Marketing Hub Weekly EmptyDesc Scan" chay hang tuan
de so lieu "thieu mo ta" luon moi.

Chay tay:  python _scripts/weekly_empty_desc_scan.py
"""
import sys
from pathlib import Path

# UTF-8 stdout (tranh UnicodeEncodeError khi log tieng Viet ra console cp1252)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import seo

if __name__ == "__main__":
    print("Bat dau quet empty-desc (threshold=800)...", flush=True)
    seo.run_empty_desc_scan(threshold=800)
    st = seo.empty_desc_state()
    print("Xong: " + str(st.get("message", "")), flush=True)
