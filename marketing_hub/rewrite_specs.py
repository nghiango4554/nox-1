"""One-shot: rewrite spec block tối giản cho FB0001 + FB0002 qua /posts/X/update."""
import requests

BASE = "http://127.0.0.1:5055"

CAPTION_FB0001 = """🔥 Zotac RTX 2060 SUPER 8GB – cân full HD max setting, 2K vẫn ngon

Build PC tầm trung mà muốn chiến game AAA mượt + có Ray Tracing + DLSS 2 thì 2060 Super là deal cực ổn áp 💪

⚙️ THÔNG SỐ NỔI BẬT
🎮 GPU: RTX 2060 SUPER 8GB GDDR6
⚡ Bus 256-bit – băng thông khoẻ
✨ Có Ray Tracing + DLSS 2
🔌 3x DisplayPort + 1x HDMI
❄️ Tản 2 fan êm, lắp vừa case mid-tower
🔋 Nguồn đề nghị: 550W (cắm 1x 8-pin)

💸 Giá: 4.190.000đ (web Sintech)

👉 Hợp cho: build PC chiến Valorant/CS2/PUBG max FPS, LoL/DOTA mượt rần rần, GTA V/Cyberpunk full HD bật DLSS ngon, edit Premiere/Photoshop ổn áp
👉 Điểm ăn tiền: 8GB VRAM + bus 256-bit hiếm trong tầm giá, có Ray Tracing + DLSS, tản 2 fan êm, dễ lắp

📩 Inbox ngay
📞 Hotline: 0911 713 000
📍 457 Trần Xuân Soạn, Q7

#Sintech #PCGaming #BuildPC #RTX2060 #RTX2060Super #VGA #Zotac #GamingPC"""

CAPTION_FB0002 = """🔥 TẢN NHIỆT NƯỚC AIO CENTAUR CT-H500-360 TRẮNG – chỉ từ 1Tr8xx (giảm 35%)

Build PC trắng đẹp mà muốn CPU mát rượi + LED RGB sync + có cả màn hình LCD theo dõi nhiệt độ thì CT-H500-360 là kèo cực ngon trong tầm giá 💪

⚙️ THÔNG SỐ NỔI BẬT
❄️ Radiator 360mm – 3 fan
📺 Có màn LCD 1.54" – hiện nhiệt độ, tốc độ
💡 10 đèn RGB sync
⚙️ Pump 200–2600 RPM
🔧 Lắp được Intel & AMD đời mới
🛡️ Bảo hành 60 tháng

💸 Giá: 1Tr8xx (giảm 35% từ 2Tr9xx – tiết kiệm hơn 1 triệu)

👉 Điểm ăn tiền: AIO 360mm dưới 2tr hiếm có, có màn hình LCD theo dõi realtime, RGB sync chuẩn, bảo hành tới 60 tháng

👉 Xem thêm thông tin sản phẩm tại đây:
https://sintech.vn/products/tan-nhiet-nuoc-centaur-ct-h500-360-trang

📩 Inbox ngay để chốt giá tốt nhất
📞 Hotline: 0911 713 000
📍 457 Trần Xuân Soạn, Q7

#Sintech #TanNhiet #AIO #BuildPC #PCGaming #PCTrang #Centaur #SetupDep"""

UPDATES = [
    {
        "id": 1,
        "data": {
            "scheduled_date": "2026-05-03",
            "scheduled_time": "20:55",
            "type": "product",
            "status": "posted",
            "caption": CAPTION_FB0001,
            "link": "https://sintech.vn/products/card-man-hinh-vga-zotac-rtx-2060-super-8gb",
            "images_order": "20260503_134926_934916_FB0002_-_AIO_Centaur_CT-H500-360_Trang_centaur-ct-h500-360-trang-01.jpg,20260503_134926_938075_FB0002_-_AIO_Centaur_CT-H500-360_Trang_centaur-ct-h500-360-trang-02.jpg",
        },
    },
    {
        "id": 2,
        "data": {
            "scheduled_date": "2026-05-03",
            "scheduled_time": "13:58",
            "type": "product",
            "status": "posted",
            "caption": CAPTION_FB0002,
            "link": "https://sintech.vn/products/tan-nhiet-nuoc-centaur-ct-h500-360-trang",
            "images_order": "20260503_135228_239275_FB0002_-_AIO_Centaur_CT-H500-360_Trang_centaur-ct-h500-360-trang-01.jpg,20260503_135222_804609_FB0002_-_AIO_Centaur_CT-H500-360_Trang_centaur-ct-h500-360-trang-02.jpg",
        },
    },
]

for u in UPDATES:
    r = requests.post(
        f"{BASE}/posts/{u['id']}/update",
        data=u["data"],
        allow_redirects=False,
        timeout=10,
    )
    print(f"FB000{u['id']}: HTTP {r.status_code}")
