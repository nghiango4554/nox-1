"""Bổ sung ảnh từ brand cho FB0010 (Corsair) + FB0011 (ASUS)."""
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import db

UPLOAD = ROOT / "uploads"

EXTRA_URLS = {
    "FB0010": [
        "https://assets.corsair.com/image/upload/c_pad,q_85,h_1100,w_1100,f_auto/v1680126575/products/Power-Supply-Units/base-rme-series-2023-psu-config/Gallery/850W/RM850e_01.webp",
        "https://assets.corsair.com/image/upload/f_auto/q_auto/v1680126573/products/Power-Supply-Units/base-rme-series-2023-psu-config/Gallery/850W/RM850e_16.png",
        "https://assets.corsair.com/image/upload/f_auto/q_auto/v1680126574/products/Power-Supply-Units/base-rme-series-2023-psu-config/Gallery/850W/RM850e_17.png",
    ],
    "FB0011": [
        "https://dlcdnwebimgs.asus.com/files/media/4e35a877-1cf3-4745-b416-29a214a011df/V1/img/kv/kv-main.webp",
        "https://dlcdnwebimgs.asus.com/files/media/4e35a877-1cf3-4745-b416-29a214a011df/V1/img/spec/spec-performance.webp",
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
}


def download(url: str, dest: Path) -> bool:
    if url.startswith("//"):
        url = "https:" + url
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if len(data) < 500:
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"   ✗ {e}")
        return False


for code, urls in EXTRA_URLS.items():
    # đọc images hiện có từ DB
    conn = db.get_conn()
    row = conn.execute("SELECT images FROM posts WHERE code=?", (code,)).fetchone()
    conn.close()
    current = json.loads(row["images"]) if row and row["images"] else []
    next_idx = len(current) + 1
    needed = 4 - len(current)
    print(f"\n{code}: hiện {len(current)} ảnh, thêm tối đa {needed}")
    for url in urls[:needed]:
        ext = url.rsplit(".", 1)[-1].split("?")[0].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"
        fname = f"{code.lower()}-product-{next_idx}.{ext}"
        dest = UPLOAD / fname
        if download(url, dest):
            current.append(fname)
            next_idx += 1
            kb = dest.stat().st_size // 1024
            print(f"  ✓ {fname} ({kb} KB)")
        else:
            print(f"  ✗ {fname}")

    if current:
        conn = db.get_conn()
        conn.execute(
            "UPDATE posts SET image_path=?, images=?, updated_at=datetime('now') WHERE code=?",
            (current[0], json.dumps(current), code),
        )
        conn.commit()
        conn.close()
        print(f"  → DB updated: {len(current)} ảnh")
