# -*- coding: utf-8 -*-
"""Chuẩn hoá style mọi collection về khuôn pc-gaming (giữ nội dung + bảng).
DRY=True: chỉ test, không sync. DRY=False: sync toàn bộ lên Haravan."""
import sys, io, json, sqlite3, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from bs4 import BeautifulSoup
import collection_content_writer as ccw

DRY = False
ONLY = None  # list handle để test, None = tất cả
canon = json.loads(open('_canon_style.json', encoding='utf-8').read())
FB = {'h4': canon.get('h3'), 'ol': canon.get('ul')}  # fallback

def restyle(body):
    soup = BeautifulSoup(body, 'lxml')
    for t, style in canon.items():
        for e in soup.find_all(t):
            e['style'] = style
    for t, style in FB.items():
        if style:
            for e in soup.find_all(t):
                if not e.get('style') or t in ('h4', 'ol'):
                    e['style'] = style
    b = soup.body
    return ''.join(str(x) for x in b.children).strip() if b else str(soup)

import html as _html
def vis(h):  # text thuần: bỏ tag + decode entity + gộp space → so nội dung THẬT
    t = re.sub(r'<[^>]+>', ' ', h or ''); t = _html.unescape(t)
    return re.sub(r'\s+', ' ', t).strip()

c = sqlite3.connect('data/posts.db', timeout=30)
q = "select handle, haravan_id, edited_title, edited_meta, edited_body_html from collection_jobs where status='synced' and length(coalesce(edited_body_html,''))>500"
rows = c.execute(q).fetchall()
if ONLY:
    rows = [r for r in rows if r[0] in ONLY]
print(f"{'[DRY] ' if DRY else ''}xử lý {len(rows)} collection")

ok = fail = skip = 0
for handle, hid, title, meta, body in rows:
    new = restyle(body)
    # an toàn: nội dung THẬT (visible) + số bảng KHÔNG đổi
    if vis(new) != vis(body) or new.count('<table') != body.count('<table'):
        print(f"  ⚠️ {handle}: ĐỔI nội dung/bảng — BỎ QUA (an toàn)")
        skip += 1
        continue
    if DRY:
        if handle in (rows[0][0], rows[1][0], rows[2][0]):
            sp = BeautifulSoup(new, 'lxml')
            pst = (sp.find('p').get('style') or '')[:60] if sp.find('p') else '-'
            print(f"  ✓ {handle}: table giữ {new.count('<table')} | p.style={pst}")
        ok += 1
    else:
        for attempt in range(3):
            try:
                res = ccw.sync_collection_to_haravan(hid, title, meta, new)
                if res.get('ok'):
                    c.execute("update collection_jobs set edited_body_html=?, updated_at=datetime('now') where handle=?", (new, handle))
                    c.commit(); ok += 1
                    if ok % 20 == 0: print(f"  ...synced {ok}")
                    break
                else:
                    fail += 1; print(f"  ✗ {handle}: {res.get('error','?')[:50]}"); break
            except Exception as e:
                if attempt == 2: fail += 1; print(f"  ✗ {handle}: {str(e)[:50]}")
                else: time.sleep(3)
print(f"\nXONG: ok={ok} fail={fail} skip(lệch)={skip}")
