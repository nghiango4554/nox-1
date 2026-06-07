# -*- coding: utf-8 -*-
"""GA4 client — Google Analytics Data API v1beta qua OAuth user token.

Token canonical: .secrets/ga4_token.json (KHÔNG đụng .secrets/google_token.json của Sheets/GSC).
Không log token value. Không gọi Admin API / accountSummaries (validate bằng Data API).
Error mapping: 401 reconnect · 403 permission · sai property misconfig · quota exceeded · metric incompatible degrade.

Port logic từ marketing_hub/gsc_live.py (nguồn tạm, sẽ xóa sau).
"""
import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from services import ga4_config

SECRETS_DIR = Path(__file__).resolve().parent.parent.parent / ".secrets"   # nox-1/.secrets
TOKEN_PATH = SECRETS_DIR / "ga4_token.json"
SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

# metric "rủi ro" có thể không tương thích trên 1 số property → drop khi degrade
RISKY_METRICS = {"keyEvents", "eventValue", "userEngagementDuration"}


class GA4Error(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code          # token_expired | permission_denied | wrong_property | quota | metric_incompatible | unknown | token_missing
        self.message = message


def token_present() -> bool:
    return TOKEN_PATH.exists()


def _load_credentials():
    if not TOKEN_PATH.exists():
        raise GA4Error("token_missing", "Chưa có token GA4 (.secrets/ga4_token.json).")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def get_client():
    return build("analyticsdata", "v1beta", credentials=_load_credentials(), cache_discovery=False)


def _classify_http_error(exc: HttpError) -> GA4Error:
    """Phân loại lỗi HTTP GA4 thành code rõ ràng.
    KHÔNG map mọi lỗi limit/validation thành metric_incompatible — chỉ khi message nói rõ incompatible.
    Codes: token_expired | permission_denied | wrong_property | quota |
           metric_incompatible | invalid_request | temporary | unknown
    """
    status = getattr(getattr(exc, "resp", None), "status", None)
    body = ""
    try:
        body = exc.content.decode("utf-8") if isinstance(exc.content, bytes) else str(exc.content)
    except Exception:
        body = str(exc)
    low = body.lower()

    if status == 401:
        return GA4Error("token_expired", "Token hết hạn — cần reconnect OAuth GA4.")
    if status == 403:
        if "quota" in low or "exhausted" in low or "resource_exhausted" in low:
            return GA4Error("quota", "Vượt quota GA4 Data API.")
        return GA4Error("permission_denied", "Thiếu quyền trên GA4 property (cần Viewer).")
    if status == 429:
        return GA4Error("quota", "Vượt quota / rate limit GA4 Data API.")
    if status in (500, 502, 503, 504):
        return GA4Error("temporary", f"Lỗi tạm thời phía Google (status={status}) — thử lại sau.")
    if status == 404:
        return GA4Error("wrong_property", "Property ID không tồn tại.")
    if status == 400:
        if "property" in low and ("not found" in low or "invalid" in low or "permission" in low or "does not" in low):
            return GA4Error("wrong_property", "Property ID sai hoặc không truy cập được.")
        # CHỈ incompatible khi message nói rõ — KHÔNG bắt "limited to N metrics" / validation chung
        if "incompat" in low or "not compatible" in low:
            return GA4Error("metric_incompatible", "Metric/dimension không tương thích với nhau.")
        return GA4Error("invalid_request", f"Request không hợp lệ (400): {body[:120]}")
    return GA4Error("unknown", f"Lỗi GA4 API (status={status}).")


def classify_exception(exc) -> GA4Error:
    """Bọc ngoài: HttpError → phân loại; lỗi transport/network khác → temporary."""
    if isinstance(exc, HttpError):
        return _classify_http_error(exc)
    if isinstance(exc, GA4Error):
        return exc
    name = type(exc).__name__.lower()
    if any(k in name for k in ("timeout", "connection", "transport", "ssl", "socket")):
        return GA4Error("temporary", f"Lỗi mạng tạm thời: {type(exc).__name__}")
    return GA4Error("unknown", f"{type(exc).__name__}: {str(exc)[:120]}")


def _property_path(cfg=None) -> str:
    cfg = cfg or ga4_config.load_config()
    pid = str(cfg.get("property_id") or "").strip()
    if not pid:
        raise GA4Error("wrong_property", "Chưa cấu hình GA4 property_id.")
    return f"properties/{pid}"


_LAST_QUOTA = None   # propertyQuota của request gần nhất (không log token; không dump dài)


def last_quota():
    return _LAST_QUOTA


def dimension_filter_eq(field, value):
    """Helper build dimensionFilter EXACT cho run_report (vd channel group = Organic Search)."""
    return {"filter": {"fieldName": field, "stringFilter": {"matchType": "EXACT", "value": value}}}


def run_report(dimensions, metrics, start_date, end_date,
               limit=None, order_bys=None, keep_empty=False, dimension_filter=None, cfg=None):
    """Chạy runReport (returnPropertyQuota=True). Degrade CHỈ khi metric_incompatible.
    dimension_filter: dict GA4 FilterExpression (optional). Trả (rows, used_metrics, degraded)."""
    global _LAST_QUOTA
    client = get_client()
    prop = _property_path(cfg)

    def _exec(mets):
        global _LAST_QUOTA
        body = {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in mets],
            "keepEmptyRows": keep_empty,
            "returnPropertyQuota": True,
        }
        if dimension_filter:
            body["dimensionFilter"] = dimension_filter
        if limit:
            body["limit"] = limit
        if order_bys:
            body["orderBys"] = order_bys
        resp = client.properties().runReport(property=prop, body=body).execute()
        if resp.get("propertyQuota"):
            _LAST_QUOTA = resp["propertyQuota"]
        return resp

    try:
        resp = _exec(metrics)
        return resp.get("rows", []), list(metrics), False
    except HttpError as e:
        err = _classify_http_error(e)
        if err.code == "metric_incompatible":
            # Hỏi GA4 metric nào COMPATIBLE → chỉ bỏ đúng cái hỏng (giữ keyEvents...)
            safe = None
            try:
                compat = check_compatibility(dimensions, metrics, prop)
                cand = [m for m in metrics if m in compat]
                if cand and len(cand) < len(metrics):
                    safe = cand
            except Exception:
                pass
            if safe is None:                      # fallback: drop RISKY set
                rs = [m for m in metrics if m not in RISKY_METRICS]
                safe = rs if (rs and len(rs) < len(metrics)) else None
            if safe:
                try:
                    resp = _exec(safe)
                    return resp.get("rows", []), safe, True
                except HttpError as e2:
                    raise _classify_http_error(e2)
        raise err


def check_compatibility(dimensions, metrics, prop) -> set:
    """Trả set tên metric COMPATIBLE với bộ dimension đã cho (Data API checkCompatibility)."""
    client = get_client()
    body = {
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
    }
    resp = client.properties().checkCompatibility(property=prop, body=body).execute()
    ok = set()
    for mc in resp.get("metricCompatibilities", []):
        if mc.get("compatibility") == "COMPATIBLE":
            name = mc.get("metricMetadata", {}).get("apiName")
            if name:
                ok.add(name)
    return ok


def run_realtime_report(dimensions, metrics, limit=10, minute_ranges=None, cfg=None):
    """runRealtimeReport. Mặc định 30 phút gần nhất; truyền minute_ranges để giới hạn cửa sổ.
    minute_ranges ví dụ: [{"name":"m5","startMinutesAgo":5,"endMinutesAgo":0}]. Trả rows (raw)."""
    client = get_client()
    prop = _property_path(cfg)
    body = {
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
    }
    if limit:
        body["limit"] = limit
    if minute_ranges:
        body["minuteRanges"] = minute_ranges
    resp = client.properties().runRealtimeReport(property=prop, body=body).execute()
    return resp.get("rows", [])


def check_metadata(cfg=None) -> dict:
    """Validate property + token bằng getMetadata (Data API, không phải Admin API)."""
    client = get_client()
    prop = _property_path(cfg)
    meta = client.properties().getMetadata(name=f"{prop}/metadata").execute()
    return {
        "dimensions": len(meta.get("dimensions", [])),
        "metrics": len(meta.get("metrics", [])),
    }


def status(probe: bool = True) -> dict:
    """Trạng thái GA4 cho /api/ga4/status. probe=True mới gọi API (validate).
    Trang render KHÔNG probe (đọc DB/config). KHÔNG log token."""
    cfg = ga4_config.load_config()
    st = ga4_config.config_state()
    out = {
        "configured": st["configured"],
        "config_exists": st["config_exists"],
        "enabled": st["enabled"],
        "has_property_id": st["has_property_id"],
        "property_id": st["property_id"],
        "auth_mode": st["auth_mode"],
        "token_present": token_present(),
        "api_status": "unknown",
        "error_code": None,
        "error_message": None,
        "metadata": None,
    }
    if not st["configured"]:
        out["api_status"] = "not_configured"
        return out
    if not token_present():
        out["api_status"] = "token_missing"
        out["error_code"] = "token_missing"
        out["error_message"] = "Chưa có .secrets/ga4_token.json"
        return out
    if not probe:
        out["api_status"] = "ready"
        return out
    try:
        out["metadata"] = check_metadata(cfg)
        out["api_status"] = "ok"
    except GA4Error as e:
        out["api_status"] = "error"
        out["error_code"] = e.code
        out["error_message"] = e.message
    except HttpError as e:
        err = _classify_http_error(e)
        out["api_status"] = "error"
        out["error_code"] = err.code
        out["error_message"] = err.message
    except Exception as e:
        out["api_status"] = "error"
        out["error_code"] = "unknown"
        out["error_message"] = str(e)[:200]
    return out
