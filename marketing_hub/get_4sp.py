import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3, json
from bs4 import BeautifulSoup

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

handles = [
    'chuot-gaming-aula-sc580-co-ket-noi-3-mode-trang-den-do',
    'ban-phim-co-gaming-co-day-aula-f75-red-switch',
    'tai-nghe-choi-game-e-dra-eh416pro',
    'man-hinh-phang-gaming-ktc-h27t22s-27-inch-2k-fast-ips-180hz-1ms',
]

for h in handles:
    r = conn.execute("SELECT title, vendor, product_type, price_min, tags, body_html, images FROM haravan_products WHERE handle=?", (h,)).fetchone()
    if r:
        soup = BeautifulSoup(r['body_html'] or '', 'html.parser')
        text = soup.get_text(' ', strip=True)[:800]
        try:
            imgs = json.loads(r['images']) if r['images'] else []
            img_urls = [img.get('src','') if isinstance(img,dict) else str(img) for img in imgs[:3]]
        except: img_urls = []
        p = int(r['price_min']/1000)
        price = f"{p}K" if p < 1000 else f"{p/1000:.1f}tr".replace('.0tr','tr')
        print(f"=== {r['title']} | {price} ===")
        print(f"Tags: {r['tags']}")
        print(f"Body: {text}")
        print(f"Imgs: {img_urls}")
        print()
conn.close()
