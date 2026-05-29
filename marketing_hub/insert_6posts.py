import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/posts.db')
now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

posts = [
    {
        'scheduled_date': '2026-05-29',
        'scheduled_time': '09:00',
        'title': 'Ghế Gaming Centaur Gundam Universe | Đen',
        'link': 'https://sintech.vn/products/ghe-gaming-centaur-gundam-universe-den',
        'images': 'https://product.hstatic.net/200000860097/product/den_04bdc62c973e441698ddd2a5389d21b7.png',
        'caption': '''🎮 NGỒI CHƠI GAME CẢ NGÀY — KHÔNG ĐAU LƯNG!
Ghế Gaming Centaur Gundam Universe | Đen
Giá chỉ 1Tr7xx — inbox Sintech để nhận ưu đãi!

✅ Lưng tựa mesh thoáng khí, không bí bức dù ngồi lâu
✅ Gối cổ + gối thắt lưng hỗ trợ cột sống
✅ Tay vịn 4D điều chỉnh linh hoạt theo tư thế
✅ Nâng hạ độ cao, ngả lưng 90°–135°
✅ Chịu tải 150kg, khung thép bền chắc

Thiết kế Gundam Universe — cá tính, khác biệt 🤖

Xem thêm thông tin sản phẩm tại đây:
https://sintech.vn/products/ghe-gaming-centaur-gundam-universe-den

📞 Hotline: 0911 713 000
📍 457 Trần Xuân Soạn, Q7, TP.HCM
#gheGaming #Centaur #Gundam #gheChơiGame #gheCơ #SintechGaming #PCGaming #gear''',
    },
    {
        'scheduled_date': '2026-05-29',
        'scheduled_time': '15:00',
        'title': 'Vỏ Case MAGIC Aqua M Ultra Trắng',
        'link': 'https://sintech.vn/products/vo-case-magic-aqua-m-ultra-trang',
        'images': 'https://cdn.hstatic.net/products/200000860097/83308_vo_case_magic_aqua_m_white_ultra_matx_mid_tower_mau_trang__4__97a741',
        'caption': '''🤍 BUILD PC TRẮNG MUỐT — CASE MAGIC AQUA M ULTRA
Vỏ Case MAGIC Aqua M Ultra Trắng
Giá chỉ 5xxK — inbox để đặt hàng ngay!

✅ Mặt trước kính cường lực + tấm hông trong suốt khoe nội thất
✅ Hỗ trợ Micro-ATX / ITX — gọn nhẹ, tiết kiệm không gian
✅ Sẵn khe tản nhiệt nước AIO 240/280mm
✅ Quản lý cáp gọn, thoáng gió tốt
✅ Màu trắng sạch — đẹp với mọi bộ RGB

Dành cho ae thích build PC trắng tinh tế ✨

Xem thêm thông tin sản phẩm tại đây:
https://sintech.vn/products/vo-case-magic-aqua-m-ultra-trang

📞 Hotline: 0911 713 000
📍 457 Trần Xuân Soạn, Q7, TP.HCM
#voCase #MAGIC #casePC #buildPC #PCTrắng #SintechGaming #PCGear #gaming''',
    },
    {
        'scheduled_date': '2026-05-30',
        'scheduled_time': '09:00',
        'title': 'Chuột Gaming Aula SC580 3 Mode',
        'link': 'https://sintech.vn/products/chuot-gaming-aula-sc580-co-ket-noi-3-mode-trang-den-do',
        'images': 'https://product.hstatic.net/200000860097/product/aula-sc580-chuot-aula-gaming_202310311452123_d3ae0d4ddd204c9e9a573f5c01',
        'caption': '''🖱️ 1 CHUỘT — 3 CÁI DÙNG! AULA SC580
Chuột Gaming Aula SC580 | 3 Mode kết nối
Giá chỉ 4xxK — quá hời cho tính năng này!

✅ Bluetooth / USB Wireless 2.4G / Có dây — chuyển đổi tức thì
✅ Cảm biến 3600 DPI chính xác cao
✅ Pin sạc, dùng được cả ngày không lo hết pin
✅ Thiết kế ergonomic vừa tay, thoải mái dài hơi
✅ Có 3 màu: Trắng | Đen | Đỏ tùy chọn

Làm việc hay chiến game đều ổn với SC580 💪

Xem thêm thông tin sản phẩm tại đây:
https://sintech.vn/products/chuot-gaming-aula-sc580-co-ket-noi-3-mode-trang-den-do

📞 Hotline: 0911 713 000
📍 457 Trần Xuân Soạn, Q7, TP.HCM
#chuotGaming #Aula #SC580 #chuotKhôngDây #chuot3Mode #SintechGaming #PCGear #gaming''',
    },
    {
        'scheduled_date': '2026-05-30',
        'scheduled_time': '15:00',
        'title': 'Phím Cơ Aula F75 Red Switch Đen Có Dây',
        'link': 'https://sintech.vn/products/ban-phim-co-gaming-co-day-aula-f75-red-switch',
        'images': 'https://cdn.hstatic.net/products/200000860097/f75__1__f1ebadfb60004b12913de828f34aeb75.png',
        'caption': '''⌨️ GÕ NHẸ — PHÍM CƠ AULA F75 RED SWITCH
Bàn phím cơ Aula F75 | Red Switch | 75% Layout | Có dây
Giá chỉ 6xxK — phím cơ xịn không cần chi nhiều!

✅ Red Switch gõ nhẹ, trơn mượt — lý tưởng cho game và code
✅ Layout 75% gọn nhẹ, tiết kiệm diện tích bàn
✅ LED RGB mỗi phím, hiệu ứng sáng đẹp
✅ Hotswap switch — thay switch tự do không hàn
✅ Keycap PBT dày, bền, không bóng dầu

Compact mà đủ phím — lựa chọn đỉnh trong tầm giá 🔥

Xem thêm thông tin sản phẩm tại đây:
https://sintech.vn/products/ban-phim-co-gaming-co-day-aula-f75-red-switch

📞 Hotline: 0911 713 000
📍 457 Trần Xuân Soạn, Q7, TP.HCM
#phimCo #Aula #F75 #RedSwitch #bànPhímCơ #hotswap #SintechGaming #PCGear #gaming''',
    },
    {
        'scheduled_date': '2026-05-31',
        'scheduled_time': '09:00',
        'title': 'Tai nghe E-DRA EH416PRO Có Dây',
        'link': 'https://sintech.vn/products/tai-nghe-choi-game-e-dra-eh416pro',
        'images': 'https://product.hstatic.net/200000860097/product/558_z6232902804865_fbab37dc2033689df3ed0eac567ba915_bb63f4a4e3034af0830',
        'caption': '''🎧 NGHE RÕ TỪNG BƯỚC CHÂN — TAI NGHE E-DRA EH416PRO
Tai nghe gaming có dây E-DRA EH416PRO
Giá chỉ 3xxK — âm thanh vượt tầm giá!

✅ Driver 50mm cho âm bass dày, treble sắc nét
✅ Âm thanh 7.1 Surround ảo — nghe hướng kẻ địch cực rõ
✅ Mic có thể gập lên, lọc tạp âm tốt
✅ Đệm tai mềm, đeo lâu không đau tai
✅ Tương thích PC, PS4, Switch, điện thoại

Chiến game hay họp online đều ổn với EH416PRO 🎮

Xem thêm thông tin sản phẩm tại đây:
https://sintech.vn/products/tai-nghe-choi-game-e-dra-eh416pro

📞 Hotline: 0911 713 000
📍 457 Trần Xuân Soạn, Q7, TP.HCM
#taiNghe #EDRA #EH416PRO #taiNgheGaming #headset #SintechGaming #PCGear #gaming''',
    },
    {
        'scheduled_date': '2026-05-31',
        'scheduled_time': '15:00',
        'title': 'Màn hình KTC H27T22S 27" 2K Fast IPS 180Hz 1ms',
        'link': 'https://sintech.vn/products/man-hinh-phang-gaming-ktc-h27t22s-27-inch-2k-fast-ips-180hz-1ms',
        'images': 'https://product.hstatic.net/200000860097/product/5-4_ee1133819e274fa0b654123438b02d6c.png',
        'caption': '''🖥️ 2K + 180Hz + 1ms — MÀN HÌNH KTC H27T22S ĐỈNH TẦNG
Màn hình Gaming KTC H27T22S | 27" | 2K | Fast IPS | 180Hz | 1ms
Giá chỉ 4Tr9xx — inbox Sintech để nhận báo giá tốt nhất!

✅ Tấm nền Fast IPS: màu sắc sống động, góc nhìn rộng 178°
✅ Độ phân giải 2K (2560×1440) — sắc nét hơn Full HD 77%
✅ 180Hz + 1ms — chuyển động mượt, không bóng ma, phản hồi tức thì
✅ FreeSync Premium chống xé hình khi chiến game
✅ Viền mỏng 3 cạnh, thiết kế gọn đẹp cho setup bất kỳ

Muốn lên 2K mà không phá vỡ ngân sách — đây là lựa chọn! 💪

Xem thêm thông tin sản phẩm tại đây:
https://sintech.vn/products/man-hinh-phang-gaming-ktc-h27t22s-27-inch-2k-fast-ips-180hz-1ms

📞 Hotline: 0911 713 000
📍 457 Trần Xuân Soạn, Q7, TP.HCM
#mànHình #KTC #H27T22S #2K #180Hz #FastIPS #màn27inch #SintechGaming #PCGaming #gaming''',
    },
]

cursor = conn.cursor()
for p in posts:
    cursor.execute("""
        INSERT INTO posts (scheduled_date, scheduled_time, type, status, title, caption, link, images, notes, created_at, updated_at)
        VALUES (?, ?, 'facebook', 'pending', ?, ?, ?, ?, 'Auto-created 6-post batch T6-CN', ?, ?)
    """, (
        p['scheduled_date'], p['scheduled_time'],
        p['title'], p['caption'], p['link'], p['images'],
        now, now
    ))
    print('Inserted: [%s %s] %s' % (p['scheduled_date'], p['scheduled_time'], p['title']))

conn.commit()
conn.close()
print('\nDone! 6 bai da insert.')
