# -*- coding: utf-8 -*-
import os, sys, re, json, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
os.chdir(r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
import haravan_blog as hb
import warnings; warnings.filterwarnings('ignore')

def norm(s):
    s = unicodedata.normalize('NFD', (s or '').lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip()

ops = json.load(open(r'C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\_content_ops.json', encoding='utf-8'))
allq = sorted({q for v in ops.values() for q in v['q']})
PQ = json.load(open('_pq_28d.json', encoding='utf-8'))
imp = {}
for x in PQ:
    imp[x['q']] = imp.get(x['q'], 0) + x['imp']

# cụm 2: thu mua linh kiện cũ -> trang thuamualinhkiencu
pg = [x for x in hb._req('GET', '/pages.json', params={'limit': 250})['pages']
      if x['handle'] == 'thuamualinhkiencu'][0]
t2 = norm(pg['title'] + ' ' + pg['body_html'])
q2 = [q for q in allq if re.search(r'(bán|thu|bảng giá|định giá|mua).*(cũ|linh kiện)', q, re.I)]
miss2 = [(q, imp.get(q, 0)) for q in q2 if norm(q) not in t2]
print('CỤM THU MUA: %d cụm | chưa phủ %d (%d imp)' % (len(q2), len(miss2), sum(i for _, i in miss2)))
for q, i in sorted(miss2, key=lambda x: -x[1])[:8]:
    print('   %3d imp | %s' % (i, q))

# cụm 3: fan led / fan case -> bài gắn quạt tản nhiệt
idx = {}
for b in hb.list_blogs():
    for p in range(1, 20):
        a = hb.list_articles(b['id'], limit=250, page=p)
        if not a: break
        for x in a: idx[x['handle']] = (b['id'], x['id'], b['handle'])
k = [h for h in idx if h.startswith('bat-mi-cach-gan-quat-tan-nhiet')][0]
body = hb.get_article(idx[k][0], idx[k][1])['body_html']
t3 = norm(body)
q3 = [q for q in allq if re.search(r'fan|quạt', q, re.I)]
miss3 = [(q, imp.get(q, 0)) for q in q3 if norm(q) not in t3]
print('\nCỤM FAN: %d cụm | chưa phủ %d (%d imp)' % (len(q3), len(miss3), sum(i for _, i in miss3)))
for q, i in sorted(miss3, key=lambda x: -x[1])[:8]:
    print('   %3d imp | %s' % (i, q))
