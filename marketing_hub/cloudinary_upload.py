"""Upload ảnh lên Cloudinary (signed) → trả secure_url (URL CDN public HTTPS).

Dùng cho ảnh AI Blog Content: scale xong → upload đây → chèn vào body_html.
Key đọc từ state/cloudinary_keys.txt (KEY=VALUE). KHÔNG cần SDK — chỉ requests + hashlib.

    import cloudinary_upload
    src = cloudinary_upload.upload(img_bytes, filename="hero.jpg")  # -> https://res.cloudinary.com/...
"""
import hashlib
import time
from pathlib import Path

import requests

KEYS_PATH = Path(__file__).parent.parent / "state" / "cloudinary_keys.txt"
DEFAULT_FOLDER = "sintech_blog"
TIMEOUT = 60


def _load_keys() -> dict:
    """Parse state/cloudinary_keys.txt (dòng KEY=VALUE, bỏ comment #)."""
    out = {}
    if not KEYS_PATH.exists():
        return out
    for line in KEYS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def is_configured() -> bool:
    k = _load_keys()
    return all(k.get(x) for x in
               ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"))


def upload(img_bytes: bytes, filename: str = "image.jpg",
           folder: str = DEFAULT_FOLDER) -> str:
    """Signed upload → trả secure_url. Raise RuntimeError nếu chưa cấu hình / lỗi API."""
    keys = _load_keys()
    cloud = keys.get("CLOUDINARY_CLOUD_NAME")
    api_key = keys.get("CLOUDINARY_API_KEY")
    api_secret = keys.get("CLOUDINARY_API_SECRET")
    if not (cloud and api_key and api_secret):
        raise RuntimeError("Chưa cấu hình Cloudinary — dán key vào state/cloudinary_keys.txt")

    ts = str(int(time.time()))
    # Chữ ký: các param (trừ file/api_key/resource_type/cloud_name) sort theo tên,
    # nối &, append api_secret → SHA1 hex.
    sign_params = {"folder": folder, "timestamp": ts}
    to_sign = "&".join(f"{k}={sign_params[k]}" for k in sorted(sign_params))
    signature = hashlib.sha1((to_sign + api_secret).encode("utf-8")).hexdigest()

    url = f"https://api.cloudinary.com/v1_1/{cloud}/image/upload"
    resp = requests.post(
        url,
        files={"file": (filename, img_bytes)},
        data={"api_key": api_key, "timestamp": ts, "folder": folder, "signature": signature},
        timeout=TIMEOUT,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Cloudinary HTTP {resp.status_code}: {resp.text[:240]}")
    data = resp.json()
    src = data.get("secure_url")
    if not src:
        raise RuntimeError(f"Cloudinary không trả secure_url: {str(data)[:240]}")
    return src
