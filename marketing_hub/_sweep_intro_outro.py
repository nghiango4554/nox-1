# -*- coding: utf-8 -*-
"""Rà các bài ✅ đã audit, gỡ:
 - <p> đầu nếu là intro Nox tự chèn (bắt đầu 'Sintech ' hoặc chứa 'đang có tại Sintech')
 - <p> cuối chứa hotline NẾU bài có >=2 hotline (tức còn footer gốc 'Tư vấn cấu hình...')
Bỏ qua /pages/thuamualinhkiencu (soi tay riêng)."""
import sqlite3, json, re, sys
from pathlib import Path
from bs4 import BeautifulSoup
import requests
import haravan_client as hc, blog_rewrite_apply as ap
sys.path.insert(0, r'C:/Users/NGHIANGO/.openclaw/workspace')
from gsheet_client import get_service, read_range

SID = '13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU'
SKIP = {'thuamualinhkiencu'}
svc = get_service()
rows = read_range(svc, SID, "'Lịch sử Audit bài'!B2:E60")
audited = [r[0] for r in rows if len(r) > 3 and r[3].strip().startswith('✅')]
conn = sqlite3.connect('data/posts.db'); conn.row_factory = sqlite3.Row
CFG = json.loads(Path('../state/haravan_token.json').read_text(encoding='utf-8'))
HUP = {'Authorization': 'Bearer %s' % CFG['access_token'], 'Content-Type': 'application/json'}
HOT = '0911 713 000'


def is_injected_top(p):
    t = re.sub(r'\s+', ' ', p.get_text()).strip()
    return t.startswith('Sintech ') or ('đang có tại Sintech' in t)


def fix(body):
    soup = BeautifulSoup(body, 'lxml')
    cont = soup.body or soup
    n_hot = body.count(HOT)
    removed = []
    ps = cont.find_all('p')
    if ps and is_injected_top(ps[0]):
        ps[0].decompose(); removed.append('top')
    if n_hot >= 2:
        ps2 = [p for p in cont.find_all('p') if HOT in p.get_text()]
        if ps2:
            ps2[-1].decompose(); removed.append('bot')
    new = ''.join(str(x) for x in (soup.body.contents if soup.body else soup.contents)).strip()
    new = re.sub(r'^(\s*<p[^>]*>\s*(&nbsp;|\s)*</p>\s*)+', '', new)
    return new, removed, n_hot


for url in audited:
    m = re.search(r'sintech\.vn/(products|blogs|pages)/(.+?)/?$', url)
    if not m:
        continue
    kind, rest = m.group(1), m.group(2)
    short = url.replace('https://sintech.vn', '')[:50]
    if kind == 'pages' and rest in SKIP:
        print('%-52s SKIP (soi tay)' % short); continue
    try:
        if kind == 'products':
            row = conn.execute('SELECT haravan_id FROM haravan_products WHERE handle=?', (rest,)).fetchone()
            if not row: print('%-52s NO PID' % short); continue
            pid = row['haravan_id']
            body = hc._request('GET', '/products/%d.json' % pid)['product'].get('body_html') or ''
            new, rm, nh = fix(body)
            if rm:
                hc._request('PUT', '/products/%d.json' % pid, payload={'product': {'id': pid, 'body_html': new}})
        elif kind == 'blogs':
            h = rest.split('/')[-1]
            row = conn.execute('SELECT blog_id,article_id FROM blog_rewrite_candidates WHERE handle=?', (h,)).fetchone()
            if not row: print('%-52s NO ART' % short); continue
            body = ap._fetch_live_article(row['blog_id'], row['article_id'])[1].get('body_html') or ''
            new, rm, nh = fix(body)
            if rm:
                ap._put_article(row['blog_id'], row['article_id'], {'id': row['article_id'], 'body_html': new})
        else:
            continue
        print('%-52s hot %d->%d | gỡ: %s' % (short, nh, new.count(HOT), '+'.join(rm) or 'không'))
    except Exception as e:
        print('%-52s ERR %s' % (short, str(e)[:40]))
conn.close()
