"""Push title/meta đề xuất vào Google Sheet 'Meta des + Title Errors'.

Schema sheet (cố định, do vợ setup):
  A: Loại trùng | B: URL | C: Tên hiện tại | D: Title hiện tại | E: Meta hiện tại
  F: Title đề xuất ← cột anh ghi
  G: Meta đề xuất ← cột anh ghi
  H: Trạng thái   ← cột anh ghi (vd "✨ Gen AI 2026-05-16 15:32 | angle=SPEC")
  I: Đã apply (checkbox) | J: Ngày apply | K: Chồng iu tự điền

Token OAuth tái dùng từ `.secrets/google_token.json` (đã có sẵn từ các script GSC + push 269).
KHÔNG tự refresh token expired — caller phải đảm bảo token còn valid.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


# ─── Config ───
TOKEN_PATH = Path(__file__).resolve().parent.parent / ".secrets" / "google_token.json"
SHEET_ID = "13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU"
TAB_NAME = "Meta des + Title Errors"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Cache URL→row idx (sheet có ~1700 row, fetch 1 lần đủ)
_CACHE_TTL_SEC = 300  # 5 phút refresh lại

# ─── State ───
_svc = None
_url_to_row_cache: dict | None = None
_cache_built_at: float | None = None


def _get_svc():
    """Lazy-build Sheets v4 service object. Tự refresh token nếu expired."""
    global _svc
    if _svc is not None:
        return _svc
    if not TOKEN_PATH.exists():
        raise RuntimeError(
            f"Google token chưa tồn tại: {TOKEN_PATH}. "
            f"Chạy `_refresh_google_token_full_scopes.py` trước."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    _svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _svc


def _build_url_to_row_index() -> dict:
    """Đọc cột B (URL) toàn sheet → build dict url → row_idx (1-based, header=row 1)."""
    svc = _get_svc()
    vals = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=SHEET_ID, range=f"'{TAB_NAME}'!B1:B")
        .execute()
        .get("values", [])
    )
    # vals = [[header], [url1], [url2], ...] — index 0 = row 1 (header)
    out = {}
    for idx, row in enumerate(vals, 1):
        if row and row[0]:
            out[row[0].strip()] = idx
    return out


def get_url_row_index(url: str) -> int | None:
    """Cache hết URL→row. Trả row 1-based, None nếu URL không có trong sheet."""
    global _url_to_row_cache, _cache_built_at
    now = time.time()
    if _url_to_row_cache is None or (now - (_cache_built_at or 0)) > _CACHE_TTL_SEC:
        _url_to_row_cache = _build_url_to_row_index()
        _cache_built_at = now
    return _url_to_row_cache.get((url or "").strip())


def invalidate_cache():
    """Force rebuild cache lần sau (gọi sau khi sheet thay đổi nhiều)."""
    global _url_to_row_cache, _cache_built_at
    _url_to_row_cache = None
    _cache_built_at = None


def push_proposal(url: str, title: str, meta: str, status: str | None = None) -> bool:
    """Update F, G, H của row có URL trong sheet. Return True nếu OK,
    False nếu URL không có trong sheet (caller log warning).

    Raise google API exception nếu sheet API fail (caller bọc try/except).
    """
    row_idx = get_url_row_index(url)
    if not row_idx:
        return False
    svc = _get_svc()
    if status is None:
        status = f"✨ Gen AI {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB_NAME}'!F{row_idx}:H{row_idx}",
        valueInputOption="USER_ENTERED",
        body={"values": [[title, meta, status]]},
    ).execute()
    return True


def list_urls_with_proposal() -> set:
    """Đọc toàn sheet, return SET các URL đã có cả F (title) + G (meta) non-empty.
    Dùng để skip gen lại các SP đã gen từ lần trước.

    Read 1 lần ~2-3s cho 1700 row — nhanh hơn check từng cell.
    """
    svc = _get_svc()
    # Batch get B (URL) + F:G (title/meta đề xuất) cùng lúc
    result = (
        svc.spreadsheets()
        .values()
        .batchGet(
            spreadsheetId=SHEET_ID,
            ranges=[
                f"'{TAB_NAME}'!B2:B",
                f"'{TAB_NAME}'!F2:G",
            ],
        )
        .execute()
    )
    ranges = result.get("valueRanges", [])
    urls_col = ranges[0].get("values", []) if len(ranges) > 0 else []
    fg_col = ranges[1].get("values", []) if len(ranges) > 1 else []

    have = set()
    for i, url_row in enumerate(urls_col):
        if not url_row or not url_row[0]:
            continue
        url = url_row[0].strip()
        fg = fg_col[i] if i < len(fg_col) else []
        title = (fg[0] if len(fg) > 0 else "").strip()
        meta = (fg[1] if len(fg) > 1 else "").strip()
        if title and meta:  # cả 2 đều có → coi như đã gen
            have.add(url)
    return have


def read_proposal(url: str) -> dict | None:
    """Đọc lại F/G/H của row chứa URL (verify push). Return None nếu URL không có."""
    row_idx = get_url_row_index(url)
    if not row_idx:
        return None
    svc = _get_svc()
    vals = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=SHEET_ID, range=f"'{TAB_NAME}'!F{row_idx}:H{row_idx}")
        .execute()
        .get("values", [[]])
    )
    row = vals[0] if vals else []
    return {
        "row_idx": row_idx,
        "title": (row[0] if len(row) > 0 else "") or "",
        "meta": (row[1] if len(row) > 1 else "") or "",
        "status": (row[2] if len(row) > 2 else "") or "",
    }


if __name__ == "__main__":
    # Smoke test
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Token: {TOKEN_PATH}")
    print(f"Sheet: {SHEET_ID} tab '{TAB_NAME}'")
    cache = _build_url_to_row_index()
    print(f"URL trong sheet: {len(cache)}")
    if cache:
        sample = list(cache.items())[:3]
        for u, r in sample:
            print(f"  row {r}: {u}")
