# -*- coding: utf-8 -*-
"""GSC API client — Google Search Console (Search Analytics) qua OAuth webmasters.readonly.

source_mode = search_console_api · coverage_mode = api_top_rows · coverage_complete = false.
Search Analytics API có pagination NHƯNG vẫn là top rows (giới hạn nội bộ) — KHÔNG full export.
Token canonical: .secrets/gsc_api_token.json. KHÔNG đụng google_token.json / ga4_token.json.
"""
import json
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parent.parent           # marketing_hub/
SECRETS = ROOT.parent / ".secrets"
STATE_DIR = ROOT.parent / "state"
TOKEN_PATH = SECRETS / "gsc_api_token.json"
CONFIG_PATH = STATE_DIR / "gsc_api_config.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

SOURCE_MODE = "search_console_api"
COVERAGE_MODE = "api_top_rows"

DEFAULTS = {
    "enabled": False, "site_url": "sc-domain:sintech.vn", "search_types": ["web"],
    "initial_backfill_days": 90, "incremental_lookback_days": 7,
    "row_limit": 25000, "max_rows_per_day_per_type": 50000,
    "sync_timeout_seconds": 300, "fallback_to_sheet": True,
    "seo_join_channel_groups": ["Organic Search"], "seo_join_initial_backfill_days": 90,
    "seo_join_incremental_lookback_days": 7, "seo_join_version": "daily-organic-v1",
}


class GSCError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code        # token_expired | reconnect_required | permission_denied |
        self.message = message  # wrong_property | quota_exceeded | temporary_network | api_error | token_missing


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return cfg


def config_state() -> dict:
    cfg = load_config()
    has_site = bool(str(cfg.get("site_url") or "").strip())
    return {"config_exists": CONFIG_PATH.exists(), "enabled": bool(cfg.get("enabled")),
            "site_url": cfg.get("site_url") or "", "has_site_url": has_site,
            "configured": CONFIG_PATH.exists() and bool(cfg.get("enabled")) and has_site}


def token_present() -> bool:
    return TOKEN_PATH.exists()


def _credentials():
    if not TOKEN_PATH.exists():
        raise GSCError("token_missing", "Chưa có token GSC API (.secrets/gsc_api_token.json).")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        except Exception:
            raise GSCError("reconnect_required", "Refresh token GSC API thất bại — cần reconnect OAuth.")
    return creds


def get_service():
    return build("searchconsole", "v1", credentials=_credentials(), cache_discovery=False)


def classify_error(exc) -> GSCError:
    if isinstance(exc, GSCError):
        return exc
    if isinstance(exc, HttpError):
        status = getattr(getattr(exc, "resp", None), "status", None)
        body = ""
        try:
            body = exc.content.decode("utf-8") if isinstance(exc.content, bytes) else str(exc.content)
        except Exception:
            body = str(exc)
        low = body.lower()
        if status == 401:
            return GSCError("token_expired", "Token hết hạn — reconnect OAuth GSC.")
        if status == 403:
            if "quota" in low or "exhausted" in low or "rate" in low:
                return GSCError("quota_exceeded", "Vượt quota GSC API.")
            if "permission" in low or "does not have" in low:
                return GSCError("permission_denied", "Thiếu quyền trên property GSC.")
            return GSCError("permission_denied", "403 — thiếu quyền hoặc API chưa bật.")
        if status == 429:
            return GSCError("quota_exceeded", "Rate limit GSC API.")
        if status in (500, 502, 503, 504):
            return GSCError("temporary_network", f"Lỗi tạm thời phía Google ({status}).")
        if status in (400, 404):
            if "permission" in low or "not found" in low or "does not" in low:
                return GSCError("wrong_property", "Property sai hoặc không truy cập được.")
            return GSCError("api_error", f"GSC API {status}: {body[:120]}")
        return GSCError("api_error", f"GSC API status={status}.")
    name = type(exc).__name__.lower()
    if any(k in name for k in ("timeout", "connection", "ssl", "socket")):
        return GSCError("temporary_network", f"Lỗi mạng: {type(exc).__name__}")
    return GSCError("api_error", f"{type(exc).__name__}: {str(exc)[:120]}")


def property_probe(cfg=None):
    """Kiểm tra property access. Trả permissionLevel hoặc raise GSCError."""
    cfg = cfg or load_config()
    site = cfg["site_url"]
    try:
        sites = get_service().sites().list().execute().get("siteEntry", [])
    except Exception as e:
        raise classify_error(e)
    for s in sites:
        if s.get("siteUrl") == site:
            return s.get("permissionLevel")
    raise GSCError("wrong_property", "Property %s không có trong tài khoản." % site)


def _execute_with_retry(req, max_retry=3):
    """Retry hợp lý cho temporary error. KHÔNG retry vô hạn, KHÔNG retry lỗi auth/permission."""
    for attempt in range(max_retry):
        try:
            return req.execute()
        except Exception as e:
            err = classify_error(e)
            if err.code == "temporary_network" and attempt < max_retry - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise err


def query_search_analytics(start_date, end_date, dimensions, search_type="web",
                           row_limit=None, max_rows=None, cfg=None):
    """Query Search Analytics có pagination (rowLimit + startRow). Trả list rows raw.
    Stop khi page rỗng / rows < limit / chạm max_rows guard."""
    cfg = cfg or load_config()
    site = cfg["site_url"]
    row_limit = int(row_limit or cfg.get("row_limit", 25000))
    max_rows = int(max_rows or cfg.get("max_rows_per_day_per_type", 50000))
    svc = get_service()
    out, start_row = [], 0
    while True:
        body = {"startDate": start_date, "endDate": end_date, "rowLimit": row_limit, "startRow": start_row}
        if dimensions:
            body["dimensions"] = dimensions
        if search_type:
            body["type"] = search_type
        rows = _execute_with_retry(svc.searchanalytics().query(siteUrl=site, body=body))
        rows = rows.get("rows", []) if isinstance(rows, dict) else []
        if not rows:
            break
        out.extend(rows)
        if len(rows) < row_limit:          # trang cuối
            break
        start_row += row_limit
        if len(out) >= max_rows:           # guard chống phình
            break
    return out[:max_rows]


def status(probe=True) -> dict:
    st = config_state()
    out = {"source_mode": SOURCE_MODE, "coverage_mode": COVERAGE_MODE, "coverage_complete": False,
           "configured": st["configured"], "config_exists": st["config_exists"],
           "enabled": st["enabled"], "site_url": st["site_url"],
           "token_present": token_present(), "api_status": "unknown",
           "permission_level": None, "error_code": None, "error_message": None}
    if not st["configured"]:
        out["api_status"] = "not_configured"
        return out
    if not token_present():
        out["api_status"] = "token_missing"
        out["error_code"] = "token_missing"
        return out
    if not probe:
        out["api_status"] = "ready"
        return out
    try:
        out["permission_level"] = property_probe()
        out["api_status"] = "ok"
    except GSCError as e:
        out["api_status"] = "error"
        out["error_code"] = e.code
        out["error_message"] = e.message
    except Exception as e:
        out["api_status"] = "error"
        out["error_code"] = "api_error"
        out["error_message"] = str(e)[:160]
    return out
