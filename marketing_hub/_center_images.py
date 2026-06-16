# -*- coding: utf-8 -*-
"""Fix: căn giữa ảnh lại — mọi <p> chứa <img> thêm text-align:center (giữ nguyên còn lại)."""
import sys, io, json, sqlite3, re, time, html as _html
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from bs4 import BeautifulSoup
import collection_content_writer as ccw

canon = json.loads(open('_canon_style.json', encoding='utf-8').read())
P_CENTER = canon['p'].rstrip(';') + '; text-align: center;'

def vis(h):
    t = re.sub(r'<[^>]+>', ' ', h or ''); t = _html.unescape(t)
    return re.sub(r'\s+', ' ', t).strip()

def fix(body):
    soup = BeautifulSoup(body, 'lxml')
    n = 0
    for p in soup.find_all('p'):
        if p.find('img'):
            p['style'] = P_CENTER
            # ảnh: block + margin auto cho chắc căn giữa
            for img in p.find_all('img'):
                st = img.get('style', '')
                if 'margin' not in st:
                    img['style'] = (st.rstrip(';') + '; display: block; margin: 0 auto;').lstrip('; ')
            n += 1
    b = soup.body
    return (''.join(str(x) for x in b.children).strip() if b else str(soup)), n

c = sqlite3.connect('data/posts.db', timeout=30)
rows = c.execute("select handle, haravan_id, edited_title, edited_meta, edited_body_html from collection_jobs where status='synced' and edited_body_html like '%<img%'").fetchall()
print(f"collection có ảnh: {len(rows)}")
ok = fail = 0
for handle, hid, title, meta, body in rows:
    new, n = fix(body)
    if vis(new) != vis(body) or new.count('<table') != body.count('<table'):
        print(f"  ⚠️ {handle}: lệch nội dung — BỎ QUA"); continue
    for attempt in range(3):
        try:
            res = ccw.sync_collection_to_haravan(hid, title, meta, new)
            if res.get('ok'):
                c.execute("update collection_jobs set edited_body_html=?, updated_at=datetime('now') where handle=?", (new, handle))
                c.commit(); ok += 1
                if ok % 20 == 0: print(f"  ...synced {ok}")
                break
            else: fail += 1; print(f"  ✗ {handle}: {res.get('error','?')[:40]}"); break
        except Exception as e:
            if attempt == 2: fail += 1; print(f"  ✗ {handle}: {str(e)[:40]}")
            else: time.sleep(3)
print(f"\nXONG căn giữa ảnh: ok={ok} fail={fail}")
