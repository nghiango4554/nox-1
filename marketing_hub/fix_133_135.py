import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3
from bs4 import BeautifulSoup
import copy

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

# ---- FIX id=133 ve-sinh-laptop ----
# Replace fake price table (300k-5tr tiers) with real service prices:
# Laptop Văn Phòng: 250,000đ | Laptop Gaming/Đồ Họa: 350,000đ

row = conn.execute('SELECT id, handle, edited_body_html FROM collection_jobs WHERE id=133').fetchone()
soup = BeautifulSoup(row['edited_body_html'], 'html.parser')
tables = soup.find_all('table')

# Table 0 is the price table with 5 rows (header + 4 fake tiers)
price_table = tables[0]
tbody = price_table.find('tbody') or price_table

# Remove all data rows (keep header row only)
rows = price_table.find_all('tr')
header_row = rows[0]  # ['Phân khúc giá', 'Gói xử lý tiêu biểu', 'Phù hợp với ai']

# Remove all existing rows from table
for r in rows[1:]:
    r.decompose()

# Add 2 real service rows
new_rows_data = [
    ('Laptop Văn Phòng – 250,000đ', 'Vệ sinh toàn bộ bên trong, làm sạch quạt, khe gió, thay keo tản nhiệt nếu cần', 'Laptop văn phòng, học tập, máy mỏng nhẹ'),
    ('Laptop Gaming/Đồ Họa – 350,000đ', 'Vệ sinh sâu, xử lý keo tản nhiệt, kiểm tra quạt và hệ thống tản khi tải nặng', 'Laptop gaming, đồ họa, máy nóng khi chạy phần mềm nặng'),
]

parent = header_row.parent
for row_data in new_rows_data:
    new_tr = soup.new_tag('tr')
    for cell_text in row_data:
        td = soup.new_tag('td')
        td.string = cell_text
        new_tr.append(td)
    parent.append(new_tr)

new_html = str(soup)
conn.execute('UPDATE collection_jobs SET edited_body_html=? WHERE id=133', (new_html,))
conn.commit()
print("id=133: price table fixed (250k/350k real prices)")

# Verify
row2 = conn.execute('SELECT edited_body_html FROM collection_jobs WHERE id=133').fetchone()
soup2 = BeautifulSoup(row2['edited_body_html'], 'html.parser')
t = soup2.find_all('table')[0]
for r in t.find_all('tr'):
    cells = [td.get_text(strip=True) for td in r.find_all(['th','td'])]
    print(f"  {cells}")

# ---- FIX id=135 nang-cap-pc ----
# Add service fee note (50k) to the intro/price table section

row = conn.execute('SELECT id, handle, edited_body_html FROM collection_jobs WHERE id=135').fetchone()
soup = BeautifulSoup(row['edited_body_html'], 'html.parser')

# Find the first h2 (likely intro section or price table heading) and add a note about service fee
# Strategy: find where the price table is, add a paragraph before it about 50k fee

tables = soup.find_all('table')
price_table_135 = tables[0]

# Insert a note paragraph before the price table
note_p = soup.new_tag('p')
note_p.string = 'Phí công nâng cấp tại Sintech: 50,000đ/lần (chưa bao gồm linh kiện). Giá linh kiện thực tế xem bên dưới.'
price_table_135.insert_before(note_p)

new_html = str(soup)
conn.execute('UPDATE collection_jobs SET edited_body_html=? WHERE id=135', (new_html,))
conn.commit()
print("\nid=135: service fee note (50k) added before price table")

# Verify
row2 = conn.execute('SELECT edited_body_html FROM collection_jobs WHERE id=135').fetchone()
soup2 = BeautifulSoup(row2['edited_body_html'], 'html.parser')
# Find our paragraph
for p in soup2.find_all('p'):
    if '50,000' in p.get_text():
        print(f"  Found: {p.get_text()}")
        break

conn.close()
print("\nAll fixes applied.")
