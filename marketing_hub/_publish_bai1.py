# -*- coding: utf-8 -*-
import os, sys, json, re, time, datetime
sys.path.insert(0, r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
os.chdir(r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
import haravan_blog as hb

d = json.load(open(r'C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\_bai_dungluong.json', encoding='utf-8'))
SEO_TITLE = 'Game nặng bao nhiêu GB? Bảng dung lượng game PC mới nhất'
SEO_META = ('Bảng dung lượng game PC: GTA 5 khoảng 105GB, Delta Force 50GB, Honkai Star Rail 82GB, '
            'Liên Quân 4-6GB. XEM NGAY để biết cần chừa bao nhiêu ổ trống.')
now = datetime.datetime.now().astimezone().isoformat()
hb.update_article(d['blog_id'], d['id'], {
    'page_title': SEO_TITLE, 'meta_description': SEO_META,
    'published': True, 'published_at': now,
})
time.sleep(2)
a = hb.get_article(d['blog_id'], d['id'])
print('published_at:', a.get('published_at'))
print('page_title  :', a.get('page_title'))
print('meta        :', (a.get('meta_description') or '')[:80])
print('handle      :', a.get('handle'))
