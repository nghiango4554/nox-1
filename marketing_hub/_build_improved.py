# -*- coding: utf-8 -*-
"""Cải thiện bài Build PC (TOC anchor + build mẫu + gom câu lặp) → ghi DB pc-gaming (KHÔNG sync)."""
import re, sqlite3, unicodedata, time
from pathlib import Path
from bs4 import BeautifulSoup

clean = Path("state/_build_clean.html").read_text(encoding="utf-8")
soup = BeautifulSoup(clean, "lxml")
root = soup.body or soup


def slug(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:50]


# 1. bỏ H2 tiêu đề đầu + gắn id cho H2, gom heading làm TOC
nodes = list(root.children)
out = []
toc_items = []
seen_title = False
for n in nodes:
    if getattr(n, "name", None) == "h2":
        ht = n.get_text().strip()
        if not seen_title and "Build PC online theo nhu cầu" in ht:
            seen_title = True
            continue  # bỏ H2 tiêu đề
        sid = slug(ht)
        n["id"] = sid
        toc_items.append((sid, ht))
    out.append(n)

# 2. section "Build mẫu" — chèn sau "Tự build PC giá rẻ..."
BUILD_MAU = """
<h2 id="build-mau-tham-khao">3 build mẫu tham khảo theo ngân sách</h2>
<p>Dưới đây là vài cấu hình mẫu để bạn hình dung cách chia ngân sách. Đây là ví dụ tham khảo — giá và tồn kho thay đổi theo thời điểm, hãy mở công cụ Build PC để chọn chính xác.</p>
<table>
<tbody>
<tr><td><strong>Ngân sách</strong></td><td><strong>Nhu cầu</strong></td><td><strong>Cấu hình gợi ý</strong></td></tr>
<tr><td>~10-12 triệu</td><td>Văn phòng, học tập, giải trí nhẹ</td><td>CPU Intel i3-12100 (có iGPU) hoặc Ryzen 5 5600G · RAM 16GB · SSD 500GB NVMe · Nguồn 450-500W · Case mATX thoáng — chưa cần VGA rời</td></tr>
<tr><td>~16-19 triệu</td><td>Gaming Full HD 144Hz</td><td>CPU i5-12400F · VGA RTX 3060 / RTX 4060 · RAM 16GB · SSD 500GB-1TB · Nguồn 550-650W 80+ · Case mid-tower 2-3 fan</td></tr>
<tr><td>~28-33 triệu</td><td>Gaming 2K / đồ họa bán chuyên</td><td>CPU i5-13400F / Ryzen 5 7600 · VGA RTX 4060 Ti / RTX 4070 · RAM 32GB · SSD 1TB · Nguồn 650-750W 80+ Gold · tản AIO 240 hoặc khí cao cấp</td></tr>
</tbody>
</table>
<p>Bạn có thể bắt đầu từ một mẫu gần nhất rồi tăng/giảm từng nhóm cho khớp nhu cầu và ngân sách thật.</p>
"""
final = []
inserted_bm = False
for n in out:
    final.append(n)
    if not inserted_bm and getattr(n, "name", None) == "h2" and "Tự build PC giá rẻ" in n.get_text():
        # chèn sau khi hết đoạn của section này: chèn ngay sau heading + 2 đoạn kế (đơn giản: chèn ngay sau heading-section kết thúc)
        pass
# chèn build-mẫu sau toàn bộ section "Tự build giá rẻ" = trước H2 kế tiếp ("Build PC theo yêu cầu...")
tmp = []
for n in final:
    if (not inserted_bm and getattr(n, "name", None) == "h2"
            and "Build PC theo yêu cầu khác gì" in n.get_text()):
        for el in BeautifulSoup(BUILD_MAU, "lxml").body.children:
            tmp.append(el)
        inserted_bm = True
    tmp.append(n)
final = tmp

# 3. ráp TOC
toc_html = ['<h2 id="muc-luc">Mục lục</h2>', '<ul>']
for sid, ht in toc_items:
    toc_html.append(f'<li><a href="#{sid}">{ht}</a></li>')
toc_html.append('<li><a href="#build-mau-tham-khao">3 build mẫu tham khảo theo ngân sách</a></li>')
toc_html.append('</ul>')
toc = "".join(toc_html)

body_html = "".join(str(n) for n in final).strip()

# 4. gom câu lặp "nhờ kỹ thuật rà/kiểm tra" — giữ 3 lần đầu, các lần sau bỏ riêng câu đó (giữ internal link)
SENT = re.compile(r'(Khi chưa chắc[^.]*\.|hãy lưu cấu hình rồi nhờ kỹ thuật[^.]*\.|[^.]*nhờ kỹ thuật (?:rà|kiểm tra) lại[^.]*\.)', re.I)
cnt = [0]
def trim(m):
    cnt[0] += 1
    return m.group(0) if cnt[0] <= 3 else ''
body_html = SENT.sub(trim, body_html)

# TOC đặt sau đoạn intro đầu tiên
parts = re.split(r'(</p>)', body_html, maxsplit=1)
if len(parts) >= 3:
    body_html = parts[0] + parts[1] + toc + "".join(parts[2:])
else:
    body_html = toc + body_html

print("BÀI CẢI THIỆN: %d ký tự · h2=%d · table=%d · TOC items=%d · còn 'kỹ thuật rà': %d" %
      (len(body_html), body_html.count("<h2"), body_html.count("<table"),
       len(toc_items) + 1, len(re.findall(r'kỹ thuật (rà|kiểm tra)', body_html))))

# 5. backup DB pc-gaming + ghi (KHÔNG sync)
conn = sqlite3.connect("data/posts.db")
old = conn.execute("SELECT edited_body_html FROM collection_jobs WHERE id=1").fetchone()[0] or ""
Path("data/_pcgaming_DBbackup_%s.html" % time.strftime("%Y%m%d_%H%M%S")).write_text(old, encoding="utf-8")
conn.execute("UPDATE collection_jobs SET edited_body_html=?, updated_at=datetime('now') WHERE id=1", (body_html,))
conn.commit(); conn.close()
print("Đã backup DB pc-gaming cũ (%d ký tự) + ghi bản build cải thiện vào collection_jobs id=1. KHÔNG sync." % len(old))
