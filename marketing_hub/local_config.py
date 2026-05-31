"""Load local machine config từ config.local.json (gitignored).

Dùng để tránh hard-code path Windows vào source code.
Nếu key không có trong file, trả về default.
"""
import json
from pathlib import Path

_cfg_path = Path(__file__).parent / "config.local.json"
_cfg: dict = {}
if _cfg_path.exists():
    try:
        _cfg = json.loads(_cfg_path.read_text(encoding="utf-8"))
    except Exception:
        pass


def get(key: str, default=None):
    return _cfg.get(key, default)
