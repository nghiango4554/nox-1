"""Process ảnh SP từ Haravan: vuông → 600x388 với white background.

Flow:
1. Download ảnh gốc từ Haravan CDN.
2. PIL resize giữ tỉ lệ → fit theo target (max-fit không crop).
3. Tạo canvas 600x388 trắng → paste ảnh đã resize CHÍNH GIỮA.
4. Save JPEG → return bytes.

Sau đó upload qua `haravan_client.upload_to_asset_storage()` để có URL CDN
public chèn vào body_html.
"""
from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path
from typing import Tuple

import requests
from PIL import Image


TARGET_SIZE = (600, 388)
WHITE = (255, 255, 255)
DEFAULT_TIMEOUT = 20

# Cache local cho ảnh đã download + resize — pre-warmer thread cache trước,
# image worker đọc cache khi process. Save ~10-15s/bài.
CACHE_DIR = Path(__file__).parent.parent / "state" / "img_cache"


def _cache_path(handle: str, idx: int) -> Path:
    """Path file cache cho 1 ảnh đã process. Format: <handle>_<idx>.jpg"""
    safe_handle = re.sub(r"[^a-zA-Z0-9_-]", "_", handle)[:80] if handle else "unknown"
    return CACHE_DIR / f"{safe_handle}_{idx}.jpg"


def cache_get(handle: str, idx: int):
    """Đọc bytes từ cache. Trả None nếu không có."""
    p = _cache_path(handle, idx)
    if p.exists():
        try:
            return p.read_bytes()
        except Exception:
            return None
    return None


def cache_save(handle: str, idx: int, img_bytes: bytes):
    """Save bytes vào cache."""
    p = _cache_path(handle, idx)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(img_bytes)


def cache_exists(handle: str, idx: int) -> bool:
    return _cache_path(handle, idx).exists()


def _normalize_url(url: str) -> str:
    """Haravan trả URL dạng `//cdn.hstatic.net/...` — thiếu scheme. Add https."""
    if not url:
        return url
    if url.startswith("//"):
        return "https:" + url
    return url


def fetch_image_bytes(src_url: str, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    """Download ảnh từ URL. Trả raw bytes."""
    src = _normalize_url(src_url)
    r = requests.get(src, timeout=timeout, headers={"User-Agent": "SintechHubBot/1.0"})
    r.raise_for_status()
    return r.content


def process_to_600x388(img_bytes: bytes, target: Tuple[int, int] = TARGET_SIZE,
                       bg: Tuple[int, int, int] = WHITE,
                       quality: int = 88) -> bytes:
    """Process ảnh vuông → 600x388 với white background, GIỮ NGUYÊN ảnh SP gốc.

    Strategy: contain-fit (resize ảnh sao cho vừa hết khung target,
    paste vào giữa canvas trắng).
    """
    src = Image.open(io.BytesIO(img_bytes))
    if src.mode in ("RGBA", "LA", "P"):
        src = src.convert("RGB")
    target_w, target_h = target
    src_w, src_h = src.size
    # Scale fit (giữ tỉ lệ, không crop)
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = src.resize((new_w, new_h), Image.LANCZOS)
    # Canvas trắng + paste center
    canvas = Image.new("RGB", target, bg)
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y))
    # Save JPEG
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def process_haravan_image(src_url: str, target: Tuple[int, int] = TARGET_SIZE) -> bytes:
    """Convenience: download + process trong 1 call."""
    raw = fetch_image_bytes(src_url)
    return process_to_600x388(raw, target=target)


def process_blog_image(img_bytes: bytes, max_w: int = 1200,
                       bg: Tuple[int, int, int] = WHITE,
                       quality: int = 85) -> bytes:
    """Auto fix scale cho ảnh AI/blog: chỉ THU NHỎ về chiều rộng tối đa max_w
    (giữ tỉ lệ, không phóng to, không crop, không padding), flatten nền trong suốt
    → trắng, nén JPEG. Trả bytes JPEG. Khác process_to_600x388 (canvas cố định cho ảnh SP).
    """
    src = Image.open(io.BytesIO(img_bytes))
    # Flatten alpha (PNG/WebP trong suốt) lên nền trắng
    if src.mode in ("RGBA", "LA") or (src.mode == "P" and "transparency" in src.info):
        src = src.convert("RGBA")
        base = Image.new("RGB", src.size, bg)
        base.paste(src, mask=src.split()[-1])
        src = base
    elif src.mode != "RGB":
        src = src.convert("RGB")
    w, h = src.size
    if w > max_w:
        new_h = max(1, round(h * max_w / w))
        src = src.resize((max_w, new_h), Image.LANCZOS)
    buf = io.BytesIO()
    src.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def img_to_base64(img_bytes: bytes) -> str:
    """Encode bytes → base64 string cho Haravan upload `attachment` field."""
    return base64.b64encode(img_bytes).decode()


# CLI smoke test
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python image_processor.py <haravan_image_url>")
        sys.exit(1)
    src = sys.argv[1]
    out_path = Path("test_processed.jpg")
    bytes_out = process_haravan_image(src)
    out_path.write_bytes(bytes_out)
    print(f"Saved {len(bytes_out)} bytes → {out_path.resolve()}")
