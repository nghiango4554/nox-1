"""Canva Connect API client — OAuth 2.0 + PKCE + token refresh + design autofill.

Reference: https://www.canva.dev/docs/connect/

Public API:
  - load_credentials() / save_tokens() / load_tokens()
  - build_auth_url(state) -> (url, code_verifier)
  - exchange_code(code, code_verifier) -> tokens dict
  - refresh_access_token() -> new tokens (auto-call khi token sắp hết hạn)
  - api_request(method, path, **kw) -> requests.Response — auto-attach Bearer
  - list_brand_templates() / get_brand_template_dataset(id) / create_autofill_design(...)
  - export_design(design_id, format='png') -> URL ảnh export
"""
import base64
import hashlib
import json
import os
import secrets as _secrets
import time
from pathlib import Path
import requests

HERE = Path(__file__).parent
WORKSPACE = HERE.parent
STATE_DIR = WORKSPACE / "state"
CREDS_PATH = STATE_DIR / "canva_credentials.json"
TOKENS_PATH = STATE_DIR / "canva_tokens.json"

AUTH_BASE = "https://www.canva.com/api/oauth/authorize"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
API_BASE = "https://api.canva.com/rest/v1"


class CanvaError(Exception):
    pass


def load_credentials() -> dict:
    if not CREDS_PATH.exists():
        raise CanvaError(f"Thiếu file credentials: {CREDS_PATH}")
    return json.loads(CREDS_PATH.read_text(encoding="utf-8"))


def load_tokens() -> dict | None:
    if not TOKENS_PATH.exists():
        return None
    try:
        return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_tokens(tokens: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Compute expires_at (epoch seconds)
    if "expires_in" in tokens and "expires_at" not in tokens:
        tokens["expires_at"] = int(time.time()) + int(tokens["expires_in"]) - 60
    TOKENS_PATH.write_text(json.dumps(tokens, indent=2, ensure_ascii=False), encoding="utf-8")


def clear_tokens():
    if TOKENS_PATH.exists():
        TOKENS_PATH.unlink()


# ─────────────────────────── PKCE ───────────────────────────

def _gen_code_verifier() -> str:
    return _secrets.token_urlsafe(64)[:96]


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ─────────────────────────── OAUTH FLOW ───────────────────────────

def build_auth_url(state: str) -> tuple:
    """Trả về (auth_url, code_verifier). Lưu code_verifier vào session để dùng ở callback."""
    creds = load_credentials()
    verifier = _gen_code_verifier()
    challenge = _code_challenge(verifier)
    from urllib.parse import urlencode
    params = {
        "client_id": creds["client_id"],
        "redirect_uri": creds["redirect_uri"],
        "response_type": "code",
        "scope": " ".join(creds["scopes"]),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_BASE}?{urlencode(params)}", verifier


def exchange_code(code: str, code_verifier: str) -> dict:
    """Đổi authorization code → access_token + refresh_token."""
    creds = load_credentials()
    auth = (creds["client_id"], creds["client_secret"])
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": creds["redirect_uri"],
    }
    r = requests.post(TOKEN_URL, auth=auth, data=data, timeout=20)
    if r.status_code >= 400:
        raise CanvaError(f"Token exchange HTTP {r.status_code}: {r.text[:300]}")
    tokens = r.json()
    save_tokens(tokens)
    return tokens


def refresh_access_token() -> dict:
    """Refresh khi token sắp hết hạn."""
    tokens = load_tokens()
    if not tokens or "refresh_token" not in tokens:
        raise CanvaError("Chưa connect Canva (thiếu refresh_token). Vào /canva để connect.")
    creds = load_credentials()
    auth = (creds["client_id"], creds["client_secret"])
    r = requests.post(TOKEN_URL, auth=auth, data={
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
    }, timeout=20)
    if r.status_code >= 400:
        raise CanvaError(f"Refresh token HTTP {r.status_code}: {r.text[:300]}")
    new_tokens = r.json()
    # Canva có thể giữ nguyên refresh_token hoặc trả về mới — merge cho an toàn
    if "refresh_token" not in new_tokens and "refresh_token" in tokens:
        new_tokens["refresh_token"] = tokens["refresh_token"]
    save_tokens(new_tokens)
    return new_tokens


def get_valid_access_token() -> str:
    """Trả access_token còn hạn, auto-refresh nếu cần."""
    tokens = load_tokens()
    if not tokens:
        raise CanvaError("Chưa connect Canva. Vào /canva/connect.")
    expires_at = tokens.get("expires_at", 0)
    if expires_at <= int(time.time()):
        tokens = refresh_access_token()
    return tokens["access_token"]


# ─────────────────────────── API WRAPPER ───────────────────────────

def api_request(method: str, path: str, **kwargs) -> requests.Response:
    """Wrapper: auto-attach Bearer token, retry 1 lần nếu 401 (token rotation race)."""
    token = get_valid_access_token()
    headers = kwargs.pop("headers", {}) or {}
    headers["Authorization"] = f"Bearer {token}"
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    r = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    if r.status_code == 401:
        refresh_access_token()
        token = get_valid_access_token()
        headers["Authorization"] = f"Bearer {token}"
        r = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    return r


def get_user_profile() -> dict:
    """GET /users/me — verify connection + get user info."""
    r = api_request("GET", "/users/me")
    if r.status_code >= 400:
        raise CanvaError(f"Get profile HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def list_brand_templates(limit: int = 50) -> list:
    """List brand templates user có thể autofill. Yêu cầu scope brandtemplate:meta:read."""
    r = api_request("GET", "/brand-templates", params={"limit": limit})
    if r.status_code >= 400:
        raise CanvaError(f"List brand templates HTTP {r.status_code}: {r.text[:300]}")
    return r.json().get("items", [])


def get_brand_template_dataset(template_id: str) -> dict:
    """Get list các field autofill trong 1 brand template."""
    r = api_request("GET", f"/brand-templates/{template_id}/dataset")
    if r.status_code >= 400:
        raise CanvaError(f"Get dataset HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def create_autofill_design(template_id: str, autofill_data: dict, title: str = None) -> dict:
    """Create design mới từ brand template với data autofill.

    autofill_data format: {"field_name": {"type": "text", "text": "..."}}
                          {"field_name": {"type": "image", "asset_id": "..."}}
    """
    payload = {
        "brand_template_id": template_id,
        "data": autofill_data,
    }
    if title:
        payload["title"] = title
    r = api_request("POST", "/autofills", json=payload)
    if r.status_code >= 400:
        raise CanvaError(f"Create autofill HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def get_autofill_job(job_id: str) -> dict:
    """Poll status của autofill job (async)."""
    r = api_request("GET", f"/autofills/{job_id}")
    if r.status_code >= 400:
        raise CanvaError(f"Get autofill job HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def export_design(design_id: str, format_type: str = "png") -> dict:
    """Tạo export job cho design → ra URL ảnh tải về."""
    payload = {
        "design_id": design_id,
        "format": {"type": format_type},
    }
    r = api_request("POST", "/exports", json=payload)
    if r.status_code >= 400:
        raise CanvaError(f"Export design HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def get_export_job(job_id: str) -> dict:
    """Poll status của export job."""
    r = api_request("GET", f"/exports/{job_id}")
    if r.status_code >= 400:
        raise CanvaError(f"Get export job HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def upload_asset(file_path: str, name: str = None) -> dict:
    """Upload 1 file (ảnh) lên Canva làm asset, dùng cho autofill type=image."""
    fp = Path(file_path)
    if not fp.exists():
        raise CanvaError(f"File not found: {file_path}")
    metadata = {"name_base64": base64.b64encode((name or fp.name).encode("utf-8")).decode("ascii")}
    headers = {
        "Authorization": f"Bearer {get_valid_access_token()}",
        "Content-Type": "application/octet-stream",
        "Asset-Upload-Metadata": json.dumps(metadata),
    }
    with open(fp, "rb") as f:
        r = requests.post(f"{API_BASE}/asset-uploads", headers=headers, data=f.read(), timeout=60)
    if r.status_code >= 400:
        raise CanvaError(f"Upload asset HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def get_asset_upload_job(job_id: str) -> dict:
    r = api_request("GET", f"/asset-uploads/{job_id}")
    if r.status_code >= 400:
        raise CanvaError(f"Get asset upload HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def is_connected() -> bool:
    tokens = load_tokens()
    return bool(tokens and tokens.get("access_token"))
