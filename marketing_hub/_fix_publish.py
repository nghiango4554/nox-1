# -*- coding: utf-8 -*-
import os, sys, json, time, datetime
sys.path.insert(0, r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
os.chdir(r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
import haravan_blog as hb
d = json.load(open(r'C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\_bai_dungluong.json', encoding='utf-8'))
utc = datetime.datetime.utcnow() - datetime.timedelta(minutes=30)
hb.update_article(d['blog_id'], d['id'], {'published_at': utc.strftime('%Y-%m-%dT%H:%M:%SZ')})
time.sleep(2)
a = hb.get_article(d['blog_id'], d['id'])
print('published_at mới:', a.get('published_at'), '| bây giờ UTC:', datetime.datetime.utcnow().isoformat()[:19])
