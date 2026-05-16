"""Save posted products list to data/posted_products.json + fetch OG images for 14 bài."""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import db

UPLOAD = ROOT / "uploads"
DATA = ROOT / "data"
UPLOAD.mkdir(parents=True, exist_ok=True)
DATA.mkdir(parents=True, exist_ok=True)

PRODUCTS = [
    {"code": "FB0003", "name": "CPU AMD Ryzen 7 9800X3D", "category": "CPU", "url": "https://sintech.vn/products/cpu-amd-ryzen-9-9800x3d-4-7ghz-boost-5-2ghz-8-nhan-16-luong", "scheduled_date": "2026-05-04"},
    {"code": "FB0004", "name": "VGA Colorful iGame RTX 5070 Ti Vulcan OC 16GB", "category": "VGA", "url": "https://sintech.vn/products/card-man-hinh-vga-colorful-igame-geforce-rtx-5070-ti-vulcan-oc-16gb-v", "scheduled_date": "2026-05-04"},
    {"code": "FB0005", "name": "VGA ASUS Prime RTX 5060 Ti 16GB OC", "category": "VGA", "url": "https://sintech.vn/products/card-man-hinh-asus-prime-geforce-rtx-5060-ti-16gb-gddr7-oc-edition", "scheduled_date": "2026-05-05"},
    {"code": "FB0006", "name": "RAM Kingston Fury Beast DDR5 32GB 6000MHz", "category": "RAM", "url": "https://sintech.vn/products/ram-pc-ddr5-kingston-fury-beast-32gb-32gbx1-6000mhz-kf560c40bb-32", "scheduled_date": "2026-05-05"},
    {"code": "FB0007", "name": "SSD Samsung 990 Pro 2TB Gen4 NVMe", "category": "SSD", "url": "https://sintech.vn/products/o-cung-ssd-samsung-990-pro-2tb-pcie-gen-4-0-x4-nvme-r-7450-w-6900", "scheduled_date": "2026-05-06"},
    {"code": "FB0008", "name": "Tản khí Deepcool AG500 Digital ARGB Đen", "category": "Tản nhiệt", "url": "https://sintech.vn/products/tan-nhiet-khi-deepcool-ag500-digital-argb-den", "scheduled_date": "2026-05-06"},
    {"code": "FB0009", "name": "Case ASUS Prime AP201 White Mesh", "category": "Case", "url": "https://sintech.vn/products/vo-case-asus-prime-ap201-white-mesh", "scheduled_date": "2026-05-07"},
    {"code": "FB0010", "name": "PSU Corsair RM850e 850W 80+ Gold", "category": "PSU", "url": "https://sintech.vn/products/nguon-corsair-rm850e-850w-atx-3-0-pcie-5-0-80-plus-gold-full-modular-cp-9020263-na", "scheduled_date": "2026-05-07"},
    {"code": "FB0011", "name": "Mainboard ASUS TUF Gaming B850M-PLUS", "category": "Mainboard", "url": "https://sintech.vn/products/mainboard-asus-tuf-gaming-b850m-plus", "scheduled_date": "2026-05-08"},
    {"code": "FB0012", "name": "Mainboard Colorful BATTLE-AX Z890M-PLUS V20 DDR5", "category": "Mainboard", "url": "https://sintech.vn/products/mainboard-colorful-battle-ax-z890m-plus-v20-new-ddr5", "scheduled_date": "2026-05-08"},
    {"code": "FB0013", "name": "CPU Intel Core Ultra 7 265KF (Tray)", "category": "CPU", "url": "https://sintech.vn/products/cpu-intel-core-ultra-7-265kf-5-5ghz-20-nhan-20-luong-tray-new", "scheduled_date": "2026-05-09"},
    {"code": "FB0014", "name": "Màn hình ASUS TUF Gaming VG279Q1A 27\" 165Hz IPS", "category": "Màn hình", "url": "https://sintech.vn/products/man-hinh-asus-tuf-gaming-vg279q1a-27-inch-ips-165hz-g-sync", "scheduled_date": "2026-05-09"},
    {"code": "FB0015", "name": "Bàn phím cơ AULA F75 3 Mode wireless", "category": "Bàn phím", "url": "https://sintech.vn/products/ban-phim-co-aula-f75-phien-ban-xanh-duong-trang-tim-reaper-switch-khong-day", "scheduled_date": "2026-05-10"},
    {"code": "FB0016", "name": "Chuột AULA Gaming SC560 3 Mode", "category": "Chuột", "url": "https://sintech.vn/products/chuot-aula-gaming-sc560-3-mode-hong", "scheduled_date": "2026-05-10"},
]

# 1. Lưu list SP đã đăng
plist_file = DATA / "posted_products.json"
existing = []
if plist_file.exists():
    try:
        existing = json.loads(plist_file.read_text(encoding="utf-8"))
    except Exception:
        existing = []
existing_urls = {p.get("url") for p in existing}
for p in PRODUCTS:
    if p["url"] not in existing_urls:
        existing.append(p)
plist_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[1/2] Saved {len(existing)} products to {plist_file.name}")

# 2. Fetch OG image cho mỗi SP
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

def fetch_og_image(url: str) -> str | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"   ! fetch fail: {e}")
        return None
    patterns = [
        r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
        r'<meta\s+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1)
    return None


def download(url: str, dest: Path) -> bool:
    if url.startswith("//"):
        url = "https:" + url
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"   ! download fail: {e}")
        return False


print(f"\n[2/2] Fetching images for {len(PRODUCTS)} products...")
ok_count = 0
for p in PRODUCTS:
    print(f"  • {p['code']} — {p['name'][:50]}...")
    img_url = fetch_og_image(p["url"])
    if not img_url:
        print(f"     ✗ no OG image found")
        continue
    if img_url.startswith("//"):
        img_url = "https:" + img_url
    ext = img_url.rsplit(".", 1)[-1].split("?")[0].split("&")[0].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        ext = "jpg"
    fname = f"{p['code'].lower()}-product.{ext}"
    dest = UPLOAD / fname
    if download(img_url, dest):
        size_kb = dest.stat().st_size // 1024
        # update DB
        conn = db.get_conn()
        conn.execute(
            "UPDATE posts SET image_path = ?, images = ?, updated_at = datetime('now') WHERE code = ?",
            (fname, json.dumps([fname]), p["code"]),
        )
        conn.commit()
        conn.close()
        ok_count += 1
        print(f"     ✓ {fname} ({size_kb} KB)")

print(f"\nDone. Fetched {ok_count}/{len(PRODUCTS)} images.")
