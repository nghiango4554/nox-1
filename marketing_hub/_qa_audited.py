# -*- coding: utf-8 -*-
"""QA quét toàn bộ bài ✅ đã audit — tìm bất thường trong body."""
import sqlite3, sys, re, json
from pathlib import Path
import requests
import haravan_client as hc, blog_rewrite_apply as ap
sys.path.insert(0, r'C:/Users/NGHIANGO/.openclaw/workspace')
from gsheet_client import get_service, read_range

SID = '13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU'
svc = get_service()
rows = read_range(svc, SID, "'Lịch sử Audit bài'!B2:E60")
audited = [r[0] for r in rows if len(r) > 3 and r[3].strip().startswith('✅')]
conn = sqlite3.connect('data/posts.db'); conn.row_factory = sqlite3.Row
CFG = json.loads(Path('../state/haravan_token.json').read_text(encoding='utf-8'))


def smart_by_handle(h):
    for ep, key in (('smart_collections', 'smart_collections'), ('custom_collections', 'custom_collections')):
        try:
            for c in hc._request('GET', '/%s.json?handle=%s' % (ep, h)).get(key, []):
                return c.get('body_html') or ''
        except Exception:
            pass
    return None


def get_body(url):
    m = re.search(r'sintech\.vn/(products|blogs|pages|collections)/(.+?)/?$', url)
    if not m:
        return None, '?'
    kind, rest = m.group(1), m.group(2)
    try:
        if kind == 'products':
            r = conn.execute('SELECT haravan_id FROM haravan_products WHERE handle=?', (rest,)).fetchone()
            return (hc._request('GET', '/products/%d.json' % r['haravan_id'])['product'].get('body_html') or '', 'product') if r else (None, 'product?')
        if kind == 'blogs':
            r = conn.execute('SELECT blog_id,article_id FROM blog_rewrite_candidates WHERE handle=?', (rest.split('/')[-1],)).fetchone()
            return (ap._fetch_live_article(r['blog_id'], r['article_id'])[1].get('body_html') or '', 'blog') if r else (None, 'blog?')
        if kind == 'collections':
            return smart_by_handle(rest), 'coll'
        if kind == 'pages':
            rr = requests.get('https://apis.haravan.com/web/pages.json?handle=%s' % rest, headers={'Authorization': 'Bearer %s' % CFG['access_token']}, timeout=30)
            ps = rr.json().get('pages') or []
            return (ps[0].get('body_html') or '', 'page') if ps else (None, 'page?')
    except Exception as e:
        return None, 'ERR:%s' % str(e)[:25]
    return None, '?'


def anomalies(b):
    issues = []
    if b.count('&lt;a') > 0:
        issues.append('escaped<a×%d' % b.count('&lt;a'))
    if 'chatgpt' in b:
        issues.append('chatgpt×%d' % b.count('chatgpt'))
    dr = re.findall(r'[—–\-_=]{3,}', b)
    if dr:
        issues.append('dash×%d' % len(dr))
    if re.search(r'>\s*Paste\s*<', b):
        issues.append('Paste')
    if 'google.com/url' in b:
        issues.append('googleurl×%d' % b.count('google.com/url'))
    if re.search(r'class="c\d', b):
        issues.append('gdoc-class×%d' % len(re.findall(r'class="c\d', b)))
    if 'utm_source' in b:
        issues.append('utm×%d' % b.count('utm_source'))
    imgs = b.count('<img')
    nonr6 = imgs - b.count('/r6-') - b.count('cdn.hstatic.net/products') - b.count('product.hstatic.net') - b.count('file.hstatic.net')
    # flag images that are NOT r6 and NOT native product/file CDN (i.e., external leftovers)
    ext = len(re.findall(r'<img[^>]+src="(?!https://cdn\.hstatic|//cdn\.hstatic|https://product\.hstatic|https://file\.hstatic)', b))
    if ext:
        issues.append('img-ngoài×%d' % ext)
    hot = b.count('0911 713 000')
    if hot == 0:
        issues.append('hotline=0')
    elif hot >= 3:
        issues.append('hotline=%d' % hot)
    # visible raw entity tags
    if re.search(r'&lt;(h[1-6]|p|div|table|strong)\b', b):
        issues.append('raw-tag-lộ')
    return issues, imgs


print('Quét %d bài ✅:' % len(audited))
flagged = 0
for url in audited:
    b, kind = get_body(url)
    short = re.sub(r'^https?://sintech\.vn', '', url)[:46]
    if b is None:
        print('  ⚠️ %-46s [%s] KHÔNG LẤY ĐƯỢC' % (short, kind)); flagged += 1; continue
    iss, imgs = anomalies(b)
    if iss:
        print('  🔴 %-46s [%s] %s' % (short, kind, ' · '.join(iss))); flagged += 1
print('--- %d bài có cảnh báo / %d tổng ---' % (flagged, len(audited)))
conn.close()
