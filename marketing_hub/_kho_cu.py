# -*- coding: utf-8 -*-
import os, sys, re, json
sys.path.insert(0, r'C:\Users\NGHIANGO\.openclaw\workspace\gsc')
sys.path.insert(0, r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
os.chdir(r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
from _scope_full import build
D = build()
live = [p for p in D['products'] if p['live']]
cu = [p for p in live if re.search(r'\bcũ\b', p['title'], re.I)]
print('SP cũ đang bán: %d' % len(cu))
for p in sorted(cu, key=lambda x: x['title'])[:34]:
    print('   %-64s %s' % (p['title'][:64], p['path']))
col = [c for c in D['collections'] if c['path'].endswith('/hang-cu')]
print('\ndanh mục hàng cũ:', col[0]['path'] if col else 'không có', '| mô tả:', len(col[0]['body']) if col else 0, 'ký tự')
