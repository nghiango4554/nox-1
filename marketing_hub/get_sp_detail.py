import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3, json

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

for handle in ['ghe-gaming-centaur-gundam-universe-den', 'vo-case-magic-aqua-m-ultra-trang']:
    r = conn.execute("""
        SELECT title, vendor, product_type, price_min, price_max,
               body_html, images, tags, variants_count
        FROM haravan_products WHERE handle=?
    """, (handle,)).fetchone()
    if r:
        price_k = int(r['price_min']/1000)
        price_str = f"{price_k/1000:.1f}tr".replace('.0tr','tr')
        print(f"=== {r['title']} ===")
        print(f"Hãng: {r['vendor']} | Loại: {r['product_type']}")
        print(f"Giá: {price_str} ({r['price_min']:,}đ)")
        print(f"Tags: {r['tags']}")
        # Images
        try:
            imgs = json.loads(r['images']) if r['images'] else []
            print(f"Ảnh ({len(imgs)}):")
            for img in imgs[:3]:
                src = img.get('src','') if isinstance(img,dict) else str(img)
                print(f"  {src[:100]}")
        except: pass
        # Body preview
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r['body_html'] or '', 'html.parser')
        text = soup.get_text(' ', strip=True)[:600]
        print(f"Mô tả: {text}")
        print()

conn.close()
