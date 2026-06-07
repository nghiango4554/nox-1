"""Fetch GSC data từ 2 Google Sheets export → cache vào local JSON.
Sau này khi có GSC API token thì refactor sang fetch trực tiếp.
"""
import os, sys, json
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Derive từ vị trí file → nox-1/.secrets/ (không hard-code, không phụ thuộc cwd).
TOKEN = str(Path(__file__).resolve().parent.parent / ".secrets" / "google_token.json")
CACHE_PATH = Path(__file__).parent / "data" / "gsc_cache.json"

# Mapping issue Vietnamese label → english key
COVERAGE_KEY_MAP = {
    "Không tìm thấy (404)": "not_found_404",
    "Trang thay thế có thẻ chính tắc thích hợp": "alternate_canonical",
    "Bị loại trừ bởi thẻ 'noindex'": "noindex_excluded",
    "Trang có lệnh chuyển hướng": "redirect",
    "bị chặn bằng tệp robots.txt": "robots_blocked",
    "Đã thu thập dữ liệu – hiện chưa được lập chỉ mục": "crawled_not_indexed",
    "Trang trùng lặp, Google đã chọn một trang chính tắc khác với lựa chọn của người dùng": "duplicate_canonical",
    "Đã phát hiện thấy – hiện chưa được lập chỉ mục": "discovered_not_indexed",
    "Đã lập chỉ mục mặc dù bị chặn bởi robots.txt": "indexed_despite_robots",
}


def parse_pct(s):
    if not s: return 0.0
    return float(str(s).replace("%", "").replace(",", ".").strip())


def parse_float(s):
    if not s: return 0.0
    return float(str(s).replace(",", ".").strip())


def parse_int(s):
    if not s: return 0
    try: return int(str(s).replace(",", "").strip())
    except ValueError: return 0


def fetch_query_sheet(svc, sheet_id):
    out = {"queries": [], "pages": [], "devices": [], "countries": [], "daily": []}

    # Daily (Sơ đồ)
    vals = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Sơ đồ'!A2:E100").execute().get("values", [])
    for row in vals:
        if len(row) >= 5:
            out["daily"].append({
                "date": row[0],
                "click": parse_int(row[1]),
                "imp": parse_int(row[2]),
                "ctr": parse_pct(row[3]),
                "pos": parse_float(row[4]),
            })

    # Queries
    vals = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Cụm từ tìm kiếm'!A2:E2000").execute().get("values", [])
    for row in vals:
        if len(row) >= 5:
            out["queries"].append({
                "query": row[0],
                "click": parse_int(row[1]),
                "imp": parse_int(row[2]),
                "ctr": parse_pct(row[3]),
                "pos": parse_float(row[4]),
            })

    # Pages
    vals = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Trang'!A2:E2000").execute().get("values", [])
    for row in vals:
        if len(row) >= 5:
            out["pages"].append({
                "url": row[0],
                "click": parse_int(row[1]),
                "imp": parse_int(row[2]),
                "ctr": parse_pct(row[3]),
                "pos": parse_float(row[4]),
            })

    # Devices
    vals = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Thiết bị'!A2:E20").execute().get("values", [])
    for row in vals:
        if len(row) >= 5:
            out["devices"].append({
                "device": row[0],
                "click": parse_int(row[1]),
                "imp": parse_int(row[2]),
                "ctr": parse_pct(row[3]),
                "pos": parse_float(row[4]),
            })

    # Countries
    vals = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Quốc gia'!A2:E30").execute().get("values", [])
    for row in vals:
        if len(row) >= 5:
            out["countries"].append({
                "country": row[0],
                "click": parse_int(row[1]),
                "imp": parse_int(row[2]),
                "ctr": parse_pct(row[3]),
                "pos": parse_float(row[4]),
            })

    return out


def fetch_coverage_sheet(svc, sheet_id):
    out = {"critical": {}, "warning": {}, "indexed_daily": []}

    vals = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Sơ đồ'!A2:D200").execute().get("values", [])
    for row in vals:
        if len(row) >= 4:
            out["indexed_daily"].append({
                "date": row[0],
                "not_indexed": parse_int(row[1]),
                "indexed": parse_int(row[2]),
                "imp": parse_int(row[3]),
            })

    vals = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Vấn đề nghiêm trọng'!A2:D20").execute().get("values", [])
    for row in vals:
        if len(row) >= 4:
            label = row[0]
            count = parse_int(row[3])
            key = COVERAGE_KEY_MAP.get(label, label)
            out["critical"][key] = {"label": label, "count": count, "source": row[1], "status": row[2]}

    vals = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range="'Vấn đề không nghiêm trọng'!A2:D20").execute().get("values", [])
    for row in vals:
        if len(row) >= 4:
            label = row[0]
            count = parse_int(row[3])
            key = COVERAGE_KEY_MAP.get(label, label)
            out["warning"][key] = {"label": label, "count": count, "source": row[1], "status": row[2]}

    return out


def main():
    creds = Credentials.from_authorized_user_file(TOKEN, ["https://www.googleapis.com/auth/spreadsheets"])
    if creds.expired and creds.refresh_token: creds.refresh(Request())
    svc = build("sheets", "v4", credentials=creds)

    print("[1] Fetch Query sheet (Performance)...")
    perf = fetch_query_sheet(svc, "14Av9S2wJ_oSvYP3O2NPjRD18z0vCKwItEJgvMULfzSo")
    print(f"    queries={len(perf['queries'])}, pages={len(perf['pages'])}, daily={len(perf['daily'])}")

    print("[2] Fetch Coverage sheet...")
    cov = fetch_coverage_sheet(svc, "1ifGC--bJxvAbr3zaG1qpDj1qh9k2GYoS9LQuZr53OkU")
    print(f"    critical={len(cov['critical'])}, warning={len(cov['warning'])}")

    # Summary
    total_click = sum(q["click"] for q in perf["queries"])
    total_imp = sum(q["imp"] for q in perf["queries"])
    avg_pos = (sum(q["pos"] * q["imp"] for q in perf["queries"]) / total_imp) if total_imp else 0

    cache = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "total_click": total_click,
            "total_imp": total_imp,
            "avg_ctr": round(total_click * 100 / total_imp, 2) if total_imp else 0,
            "avg_position": round(avg_pos, 2),
        },
        "performance": perf,
        "coverage": cov,
    }

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Saved cache: {CACHE_PATH} ({CACHE_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
