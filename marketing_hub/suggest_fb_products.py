import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

# Lấy SP còn hàng, active, có giá, chưa đăng gần đây
# Ưu tiên: price_min > 0, inventory > 0, có ảnh
rows = conn.execute("""
    SELECT handle, title, vendor, product_type, price_min, price_max,
           inventory_total, images_count
    FROM haravan_products
    WHERE status = 'active'
      AND inventory_total > 0
      AND price_min > 0
      AND images_count > 0
    ORDER BY RANDOM()
    LIMIT 30
""").fetchall()

# Filter ra các nhóm thú vị để post FB
from collections import defaultdict
by_type = defaultdict(list)
for r in rows:
    by_type[r['product_type']].append(r)

# Print gợi ý đa dạng loại SP
seen_types = set()
picks = []
for r in rows:
    pt = r['product_type'] or 'Khác'
    if pt not in seen_types:
        picks.append(r)
        seen_types.add(pt)
    if len(picks) >= 10:
        break

print("Gợi ý SP đăng FB (còn hàng, đa dạng loại):\n")
for i, r in enumerate(picks, 1):
    price_k = int(r['price_min'] / 1000)
    price_str = f"{price_k}K" if price_k < 1000 else f"{price_k/1000:.1f}tr".replace('.0tr', 'tr')
    print(f"{i}. [{r['product_type']}] {r['title']}")
    print(f"   Giá: {price_str} | Tồn: {r['inventory_total']} | Hãng: {r['vendor']}")
    print(f"   Link: https://sintech.vn/products/{r['handle']}")
    print()

conn.close()
