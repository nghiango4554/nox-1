import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

# Exclude 2 bài đã chọn + nhóm đã gợi ý lần trước
exclude_handles = [
    'ghe-gaming-centaur-gundam-universe-den',
    'vo-case-magic-aqua-m-ultra-trang',
    'nguon-may-tinh-segotep-u6-650w-sg-d750a',
    'o-cung-ssd-great-wall-256gb-2-5-sata-iii',
    'mainboard-asrock-b760m-pro-rs-ddr4',
    'fan-case-centaur-ct-8500-argb-trang-sync-hub',
    'bo-chuyen-doi-usb-type-c-sang-hdmi-3xusb-3-0-pd-veggieg-v-tc05h',
    'phim-co-aula-win68he-max-wing-chun-magnetic-switch-den-do-co-day',
    'man-hinh-cong-gaming-ktc-h32s17f-32-inch-fhd-hva-240hz-1ms',
    'cpu-intel-core-i5-12400-4-4ghz-6-nhan-12-luong-tray',
]
placeholders = ','.join('?' * len(exclude_handles))

rows = conn.execute(f"""
    SELECT handle, title, vendor, product_type, price_min, price_max,
           inventory_total, images_count, tags
    FROM haravan_products
    WHERE status = 'active'
      AND inventory_total > 2
      AND price_min > 200000
      AND images_count > 1
      AND handle NOT IN ({placeholders})
    ORDER BY RANDOM()
    LIMIT 60
""", exclude_handles).fetchall()

# Lấy đa dạng loại, tránh trùng product_type
seen = set()
picks = []
priority_types = ['CHUỘT', 'BÀN PHÍM CƠ', 'TAI NGHE', 'MÀN HÌNH', 'RAM', 'SSD', 'VGA', 'LAPTOP', 'CPU', 'TẢN NHIỆT', 'LOA', 'NGUỒN']

# Ưu tiên loại chưa có
for pt in priority_types:
    for r in rows:
        if (r['product_type'] or '').upper() == pt and pt not in seen:
            picks.append(r)
            seen.add(pt)
            break

# Điền thêm nếu chưa đủ 4
for r in rows:
    pt = r['product_type'] or 'Khác'
    if pt not in seen and len(picks) < 6:
        picks.append(r)
        seen.add(pt)

picks = picks[:4]

for i, r in enumerate(picks, 1):
    price_k = int(r['price_min'] / 1000)
    price_str = f"{price_k}K" if price_k < 1000 else f"{price_k/1000:.1f}tr".replace('.0tr','tr')
    print(f"{i}. [{r['product_type']}] {r['title']}")
    print(f"   Giá: {price_str} | Tồn: {r['inventory_total']} | Hãng: {r['vendor']}")
    print(f"   Link: https://sintech.vn/products/{r['handle']}")
    print()

conn.close()
