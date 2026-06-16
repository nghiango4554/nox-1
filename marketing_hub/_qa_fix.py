# -*- coding: utf-8 -*-
"""Cleanup QA toàn bộ bài ✅: bóc class="cN" (Google Docs sót), bóc utm_*, decode google.com/url?q= còn sót.
Body-only PUT (product/blog/page/smart-compress)."""
import sqlite3, sys, re, json, urllib.parse
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import haravan_client as hc, blog_rewrite_apply as ap
sys.path.insert(0, r'C:/Users/NGHIANGO/.openclaw/workspace')
from gsheet_client import get_service, read_range

SID = '13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU'
svc = get_service()
rows = read_range(svc, SID, "'Lịch sử Audit bài'!B2:E60")
audited = [r[0] for r in rows if len(r) > 3 and r[3].strip().startswith('✅')]
conn = sqlite3.connect('data/posts.db'); conn.row_factory = sqlite3.Row
CFG = json.loads(Path('../state/haravan_token.json').read_text(encoding='utf-8'))
HUP = {'Authorization': 'Bearer %s' % CFG['access_token'], 'Content-Type': 'application/json'}
LK = "color:#e74c3c;font-weight:700;text-decoration:underline"


def clean_href(href):
    # decode google url?q=
    m = re.search(r'[?&]q=([^&]+)', href)
    if 'google.com/url' in href and m:
        href = urllib.parse.unquote(m.group(1))
    # strip utm_* + gclid + fbclid params
    if '?' in href:
        base, q = href.split('?', 1)
        keep = [kv for kv in q.split('&') if kv and not re.match(r'(utm_[a-z]+|gclid|fbclid|sa|source|ust|usg|ved)=', kv)]
        href = base + ('?' + '&'.join(keep) if keep else '')
    return href


def clean_body(body):
    soup = BeautifulSoup(body, "lxml")
    cont = soup.body or soup
    changed = {}
    # 1. strip class on all elements
    n_cls = 0
    for el in cont.find_all(True):
        if el.has_attr('class'):
            del el['class']; n_cls += 1
    if n_cls:
        changed['class'] = n_cls
    # 2. clean hrefs
    n_href = 0
    for a in cont.find_all('a', href=True):
        new = clean_href(a['href'])
        if new != a['href']:
            a['href'] = new; n_href += 1
    if n_href:
        changed['href'] = n_href
    out = "".join(str(x) for x in (soup.body.contents if soup.body else soup.contents)).strip()
    return out, changed


def page_get(handle):
    r = requests.get('https://apis.haravan.com/web/pages.json?handle=%s' % handle, headers=HUP, timeout=30)
    ps = r.json().get('pages') or []
    return (ps[0]['id'], ps[0].get('body_html') or '') if ps else (None, None)


fixed = 0
for url in audited:
    m = re.search(r'sintech\.vn/(products|blogs|pages|collections)/(.+?)/?$', url)
    if not m:
        continue
    kind, rest = m.group(1), m.group(2)
    short = re.sub(r'^https?://sintech\.vn', '', url)[:44]
    try:
        if kind == 'products':
            r = conn.execute('SELECT haravan_id FROM haravan_products WHERE handle=?', (rest,)).fetchone()
            if not r: continue
            pid = r['haravan_id']
            b = hc._request('GET', '/products/%d.json' % pid)['product'].get('body_html') or ''
            nb, ch = clean_body(b)
            if ch: hc._request('PUT', '/products/%d.json' % pid, payload={'product': {'id': pid, 'body_html': nb}})
        elif kind == 'blogs':
            r = conn.execute('SELECT blog_id,article_id FROM blog_rewrite_candidates WHERE handle=?', (rest.split('/')[-1],)).fetchone()
            if not r: continue
            b = ap._fetch_live_article(r['blog_id'], r['article_id'])[1].get('body_html') or ''
            nb, ch = clean_body(b)
            if ch: ap._put_article(r['blog_id'], r['article_id'], {'id': r['article_id'], 'body_html': nb})
        elif kind == 'pages':
            pid, b = page_get(rest)
            if not pid: continue
            nb, ch = clean_body(b)
            if ch:
                requests.put('https://apis.haravan.com/web/pages/%d.json' % pid, headers=HUP, json={'page': {'id': pid, 'body_html': nb}}, timeout=60)
        elif kind == 'collections':
            sid = None
            for ep, key in (('smart_collections', 'smart_collections'), ('custom_collections', 'custom_collections')):
                for c in hc._request('GET', '/%s.json?handle=%s' % (ep, rest)).get(key, []):
                    sid, b, ck, ekey = c['id'], c.get('body_html') or '', key[:-1], ep
            if not sid: continue
            nb, ch = clean_body(b)
            if ch:
                import collection_content_writer as ccw
                comp = ccw.compress_html(nb)
                try:
                    hc._request('PUT', '/%s/%d.json' % (ekey, sid), payload={ck: {'id': sid, 'body_html': comp}})
                except Exception as e:
                    print('  ⚠️ coll %s PUT fail: %s' % (rest, str(e)[-25:])); continue
        else:
            continue
        if ch:
            print('  ✓ %-44s %s' % (short, ch)); fixed += 1
    except Exception as e:
        print('  ✗ %-44s ERR %s' % (short, str(e)[:35]))
conn.close()
print('--- fixed %d bài ---' % fixed)
