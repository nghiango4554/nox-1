# -*- coding: utf-8 -*-
"""GA4 config loader — theo convention state/*.json hiện tại (giống psi_config.json).

KHÔNG dùng python-dotenv. Property ID không hard-code trong Python.
Cho phép override bằng os.getenv() nếu cần production sau này.
"""
import os
import json
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent.parent / "state"   # nox-1/state
CONFIG_PATH = STATE_DIR / "ga4_config.json"
EXAMPLE_PATH = STATE_DIR / "ga4_config.example.json"

DEFAULTS = {
    "enabled": False,
    "property_id": "",
    "auth_mode": "oauth_user",            # oauth_user | service_account
    "timezone": "Asia/Ho_Chi_Minh",
    "cache_ttl_minutes": 30,
    "realtime_cache_ttl_seconds": 60,
    "sync_lookback_days": 3,
    "initial_backfill_days": 90,
    "compare_period_enabled": True,
    "gsc_join_stale_days": 7,
}

# env override (optional, không thêm dotenv loader)
_ENV_OVERRIDES = {
    "property_id": "GA4_PROPERTY_ID",
    "auth_mode": "GA4_AUTH_MODE",
    "enabled": "GA4_ENABLED",
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    for key, env in _ENV_OVERRIDES.items():
        val = os.getenv(env)
        if val is not None and val != "":
            if key == "enabled":
                cfg[key] = val.strip().lower() in ("1", "true", "yes", "on")
            else:
                cfg[key] = val
    return cfg


def config_state() -> dict:
    """Trạng thái cấu hình (KHÔNG gọi API). Dùng cho trang setup/empty."""
    cfg = load_config()
    has_property = bool(str(cfg.get("property_id") or "").strip())
    return {
        "config_exists": CONFIG_PATH.exists(),
        "enabled": bool(cfg.get("enabled")),
        "has_property_id": has_property,
        "property_id": cfg.get("property_id") or "",
        "auth_mode": cfg.get("auth_mode") or "oauth_user",
        "timezone": cfg.get("timezone"),
        "configured": CONFIG_PATH.exists() and bool(cfg.get("enabled")) and has_property,
    }
