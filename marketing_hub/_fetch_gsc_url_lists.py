"""Fetch URL list từ 5 GSC Coverage Drilldown sheet → merge vào cache JSON.

Cấu trúc mỗi sheet:
  Tab 'Bảng' có 2 cột: URL + Lần thu thập dữ liệu cuối cùng
"""
import os, sys, json
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = r"C:\Users\NGHIANGO\.openclaw\workspace\.secrets\google_token.json"
CACHE_PATH = Path(__file__).parent / "data" / "gsc_cache.json"

# Mapping task_id (giống trong seo.py) → sheet_id
TASK_SHEETS = {
    "not_found_404": "1TGMslfSRxFSuWJdHNOi0X-y_BsoGtcyfQL7uBSLS4xc",
    "noindex_excluded": "1T1u7MLWwNfbbdcLlqiRgvD38pX1EUBJW0KLe0KdUjrg",
    "crawled_not_indexed": "1hDVs_oU6zRJbHqzRDX9l7ZW7JMaJjUbbCbJ0E0eZC2c",
    "discovered_not_indexed": "1FL6RRfVBkFHeSYhI3r9pGA3_IeYbfT11QoemgYlSYVI",
    "duplicate_canonical": "1Mnjx1nS2ZlBv8kuxwoKAMbdikB3NAPWxzmhuTHzFRDE",
}


def main():
    creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
    if creds.expired and creds.refresh_token: creds.refresh(Request())
    svc = build("sheets", "v4", credentials=creds)

    # Load cache hiện có
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    cache.setdefault("task_urls", {})

    for task_id, sid in TASK_SHEETS.items():
        print(f"[*] Fetch task '{task_id}' từ sheet {sid[:20]}...")
        try:
            vals = svc.spreadsheets().values().get(
                spreadsheetId=sid, range="'Bảng'!A2:B5000"
            ).execute().get("values", [])
        except Exception as e:
            print(f"  ❌ Lỗi fetch: {e}")
            continue
        urls = []
        for row in vals:
            if not row: continue
            url = (row[0] or "").strip()
            if not url: continue
            urls.append({
                "url": url,
                "last_crawled": row[1] if len(row) > 1 else "",
            })
        cache["task_urls"][task_id] = urls
        print(f"  ✅ {len(urls)} URL")

    cache["task_urls_fetched_at"] = datetime.now().isoformat(timespec="seconds")
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Saved cache: {CACHE_PATH} ({CACHE_PATH.stat().st_size:,} bytes)")
    print(f"   Tasks: {list(cache['task_urls'].keys())}")


if __name__ == "__main__":
    main()
