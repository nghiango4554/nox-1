# -*- coding: utf-8 -*-
"""Thêm phần lắp fan LED (ARGB) vào bài gắn quạt tản nhiệt — 27 imp chưa phủ."""
import os, sys, re, json, time
sys.path.insert(0, r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
os.chdir(r'C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub')
import haravan_blog as hb

idx = {}
for b in hb.list_blogs():
    for p in range(1, 20):
        a = hb.list_articles(b['id'], limit=250, page=p)
        if not a: break
        for x in a: idx[x['handle']] = (b['id'], x['id'])
k = [h for h in idx if h.startswith('bat-mi-cach-gan-quat-tan-nhiet')][0]
bid, aid = idx[k]
body = hb.get_article(bid, aid)['body_html']

h2 = re.search(r'<h2([^>]*)>', body).group(1)
p_at = re.search(r'<p([^>]*)>', body).group(1)
li_at = re.search(r'<li([^>]*)>', body)
li_at = li_at.group(1) if li_at else ''

NEW = (
    '<h2%s>Cách lắp fan LED cho PC: khác gì fan thường?</h2>' % h2
    + '<p%s>Fan LED có thêm một sợi dây riêng cho phần đèn, nên khi lắp bạn phải cắm hai đường chứ không '
      'phải một. Dây quạt bốn chân cắm vào cổng SYS_FAN hoặc CHA_FAN trên mainboard để điều khiển tốc độ. '
      'Dây đèn thì tuỳ chuẩn: loại ARGB dùng đầu ba chân 5V, loại RGB thường dùng đầu bốn chân 12V. Hai '
      'chuẩn này không cắm lẫn được, cắm nhầm là hỏng đèn.</p>' % p_at
    + '<p%s>Cách lắp fan LED cho case cũng theo đúng nguyên tắc hướng gió như fan thường: mặt trước và mặt '
      'dưới hút vào, mặt sau và nóc thổi ra. Đèn không ảnh hưởng luồng gió, nên đừng vì muốn nhìn đẹp mà '
      'lắp ngược chiều quạt.</p>' % p_at
    + '<ul>'
    + '<li%s>Mainboard thiếu cổng đèn thì dùng hub điều khiển, cắm chung nhiều quạt vào một đầu.</li>' % li_at
    + '<li%s>Xem kỹ chân trống trên đầu cắm ARGB, cắm lệch một chân là đèn không lên.</li>' % li_at
    + '<li%s>Quạt và đèn nên cùng hãng nếu bạn muốn đồng bộ hiệu ứng bằng phần mềm của mainboard.</li>' % li_at
    + '</ul>')

if 'Cách lắp fan LED cho PC' not in body:
    m = None
    for hm in re.finditer(r'<h2[^>]*>(?:(?!</h2>).)*?</h2>', body, re.S):
        if 'Cắm dây quạt vào đâu' in re.sub('<[^>]+>', '', hm.group(0)):
            m = hm
    nb = (body[:m.start()] + NEW + body[m.start():]) if m else body + NEW
else:
    nb = body

t = re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', nb)).lower()
ok = all(k in t for k in ['cách lắp fan led cho pc', 'cách lắp fan led cho case'])
bal = all(len(re.findall(r'<%s[ >]' % x, nb)) == len(re.findall(r'</%s>' % x, nb))
          for x in ('p', 'li', 'ul', 'h2', 'h3'))
print('cụm vào đủ:', ok, '| thẻ cân:', bal, '| +%d ký tự' % (len(nb) - len(body)))
if '--apply' in sys.argv and ok and bal and nb != body:
    json.dump({'blog_id': bid, 'id': aid, 'body_html': body},
              open(r'C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\_fanled_backup.json', 'w',
                   encoding='utf-8'), ensure_ascii=False)
    hb.update_article(bid, aid, {'body_html': nb}); time.sleep(1.5)
    print('đã ghi | khớp:', len(hb.get_article(bid, aid)['body_html']) == len(nb))
