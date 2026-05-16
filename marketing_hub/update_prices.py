"""Fetch giá thật từ sintech.vn (Haravan JSON) → censor → rewrite caption 14 bài.

Rule che giá (theo vợ yêu cầu):
- < 100,000:        x.xxx
- 100K-999K:        xxx.xxx → giữ 2 chữ đầu, che chữ 3, giữ ".000"  vd 179.000 → 17x.000
- 10K-99K:          xx.xxx  → giữ 1 chữ đầu  vd 79.000 → 7x.xxx
- 1tr-9tr:          XTrxxx          vd 1.500.000 → 1Trxxx
- 10tr-99tr:        XXTrxxx         vd 14.990.000 → 14Trxxx
- 100tr+:           XXXTrxxx
"""
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import db

HEADERS = {"User-Agent": "Mozilla/5.0"}

PRODUCTS = [
    ("FB0003", "cpu-amd-ryzen-9-9800x3d-4-7ghz-boost-5-2ghz-8-nhan-16-luong"),
    ("FB0004", "card-man-hinh-vga-colorful-igame-geforce-rtx-5070-ti-vulcan-oc-16gb-v"),
    ("FB0005", "card-man-hinh-asus-prime-geforce-rtx-5060-ti-16gb-gddr7-oc-edition"),
    ("FB0006", "ram-pc-ddr5-kingston-fury-beast-32gb-32gbx1-6000mhz-kf560c40bb-32"),
    ("FB0007", "o-cung-ssd-samsung-990-pro-2tb-pcie-gen-4-0-x4-nvme-r-7450-w-6900"),
    ("FB0008", "tan-nhiet-khi-deepcool-ag500-digital-argb-den"),
    ("FB0009", "vo-case-asus-prime-ap201-white-mesh"),
    ("FB0010", "nguon-corsair-rm850e-850w-atx-3-0-pcie-5-0-80-plus-gold-full-modular-cp-9020263-na"),
    ("FB0011", "mainboard-asus-tuf-gaming-b850m-plus"),
    ("FB0012", "mainboard-colorful-battle-ax-z890m-plus-v20-new-ddr5"),
    ("FB0013", "cpu-intel-core-ultra-7-265kf-5-5ghz-20-nhan-20-luong-tray-new"),
    ("FB0014", "man-hinh-asus-tuf-gaming-vg279q1a-27-inch-ips-165hz-g-sync"),
    ("FB0015", "ban-phim-co-aula-f75-phien-ban-xanh-duong-trang-tim-reaper-switch-khong-day"),
    ("FB0016", "chuot-aula-gaming-sc560-3-mode-hong"),
]


def fetch_price(handle: str) -> int | None:
    url = f"https://sintech.vn/products/{handle}.json"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
    except Exception as e:
        print(f"  ! fetch fail: {e}")
        return None
    p = data.get("product", {})
    variants = p.get("variants") or []
    if not variants:
        return None
    return int(variants[0].get("price", 0)) or None


def censor(price: int) -> str:
    """Che giá theo rule vợ — giữ phần đầu, che phần đuôi."""
    if price <= 0:
        return "x.xxx"
    if price < 10_000:
        # 1-9999, hiếm gặp
        return "x.xxx"
    if price < 100_000:
        # xx.xxx → giữ chữ đầu  vd 79000 → "7x.xxx"
        s = str(price // 1000)  # "79"
        return f"{s[0]}x.xxx"
    if price < 1_000_000:
        # xxx.xxx → giữ 2 chữ đầu, che chữ 3, giữ ".000"  vd 179000 → "17x.000"
        s = str(price // 1000)  # "179"
        return f"{s[:2]}x.000"
    # >= 1tr
    tr = price // 1_000_000
    return f"{tr}Trxxx"


# Caption templates — placeholder {PRICE_TITLE} ở dòng đầu, {PRICE_BODY} ở "💸 Giá:"
TEMPLATES = {
    "FB0003": (
        "CPU AMD RYZEN 7 9800X3D",
        "Con CPU mà mọi PC gaming high-end đều thèm khát, cân tất tần tật từ AAA đồ hoạ khủng, esports khung hình max settings tới stream + render song song mượt mà 💪",
        ["• Kiến trúc: Zen 5 (3D V-Cache thế hệ mới)",
         "• Nhân/Luồng: 8 nhân – 16 luồng",
         "• Xung: 4.7GHz base / 5.2GHz boost",
         "• Cache: 96MB L3 (3D V-Cache) + 8MB L2",
         "• Socket: AM5 – TDP 120W",
         "• iGPU: AMD Radeon Graphics tích hợp"],
        "ưu đãi đặc biệt tại Sintech",
        "vua gaming 2026 — vượt cả i9 14900K trong hầu hết game AAA, công suất thấp mát mẻ, lên đời PC AM5 dùng được nhiều năm",
        "https://sintech.vn/products/cpu-amd-ryzen-9-9800x3d-4-7ghz-boost-5-2ghz-8-nhan-16-luong",
        "#Sintech #Ryzen9800X3D #AMD #PCGaming #BuildPC #CPUGaming #X3D #SetupDep",
    ),
    "FB0004": (
        "VGA COLORFUL iGAME RTX 5070 Ti VULCAN OC 16GB",
        "Quái vật đồ hoạ cho PC 2K max setting và 4K mượt mà, kèm DLSS 4 + Frame Generation cho khung hình bay vút 🤤",
        ["• GPU: NVIDIA GeForce RTX 5070 Ti (Blackwell)",
         "• VRAM: 16GB GDDR7 256-bit",
         "• CUDA cores: 8.960 – Boost OC sẵn từ nhà máy",
         "• Tản: 3 fan Storm-X kèm Vapor Chamber, fan-stop khi idle",
         "• Cổng: 1× HDMI 2.1b + 3× DisplayPort 2.1b",
         "• Nguồn đề nghị: 750W trở lên"],
        "tặng kèm decal LED + bảo hành 36 tháng",
        "bản Vulcan top tier của Colorful — OC sẵn, thiết kế ARGB cực ngầu, quây gọn trong case mid-tower",
        "https://sintech.vn/products/card-man-hinh-vga-colorful-igame-geforce-rtx-5070-ti-vulcan-oc-16gb-v",
        "#Sintech #RTX5070Ti #Colorful #iGame #PCGaming #BuildPC #VGAGaming #SetupDep",
    ),
    "FB0005": (
        "VGA ASUS PRIME RTX 5060 Ti 16GB OC EDITION",
        "VRAM 16GB GDDR7 cân Cyberpunk, Black Myth Wukong, Helldivers 2 ở 2K ngon ơ — best buy 2026 cho gamer Full HD/2K 🔥",
        ["• GPU: NVIDIA GeForce RTX 5060 Ti (Blackwell)",
         "• VRAM: 16GB GDDR7 128-bit",
         "• CUDA cores: 4.608 – Boost OC sẵn",
         "• Tản: 2 fan Axial-tech + thiết kế Auto-Extreme bền bỉ",
         "• Cổng: 1× HDMI 2.1b + 3× DisplayPort 2.1",
         "• Nguồn đề nghị: 600W"],
        "giảm sốc đầu tháng – bảo hành 36 tháng",
        "16GB VRAM dư xài 4-5 năm tới, hỗ trợ DLSS 4 + Frame Generation, ASUS Prime build tốt giá vừa tầm",
        "https://sintech.vn/products/card-man-hinh-asus-prime-geforce-rtx-5060-ti-16gb-gddr7-oc-edition",
        "#Sintech #RTX5060Ti #ASUSPrime #PCGaming #BuildPC #VGAGaming #DLSS4 #SetupDep",
    ),
    "FB0006": (
        "RAM KINGSTON FURY BEAST DDR5 32GB 6000MHz",
        "Thanh RAM 32GB chuẩn bus vàng cho dàn Ryzen 7000/9000 và Intel Core Ultra — đa nhiệm gaming + stream + chrome 50 tab vẫn mướt 🌊",
        ["• Dung lượng: 32GB (1× 32GB single module)",
         "• Bus: 6000MHz – Latency CL40",
         "• Chuẩn: DDR5 PC5-48000",
         "• Voltage: 1.35V (hỗ trợ Intel XMP 3.0)",
         "• Tản nhôm dày low-profile, hợp mọi case",
         "• Bảo hành: trọn đời chính hãng Kingston"],
        "combo 64GB 2 thanh giảm thêm",
        "32GB single module dễ nâng cấp lên 64GB sau, bus 6000 sweet spot cho AM5 + LGA 1851, ép xung dễ",
        "https://sintech.vn/products/ram-pc-ddr5-kingston-fury-beast-32gb-32gbx1-6000mhz-kf560c40bb-32",
        "#Sintech #KingstonFury #FuryBeast #DDR5 #RAM6000 #BuildPC #PCGaming #SetupDep",
    ),
    "FB0007": (
        "SSD SAMSUNG 990 PRO 2TB PCIe Gen4 NVMe",
        "SSD đỉnh chóp gen 4, đọc 7450 MB/s — load Windows + game AAA nhanh như chớp, đủ chỗ cài nguyên thư viện Steam 🧊",
        ["• Dung lượng: 2TB",
         "• Chuẩn: M.2 2280 PCIe Gen4 x4 NVMe",
         "• Tốc độ đọc/ghi tuần tự: 7450 / 6900 MB/s",
         "• Random IOPS: 1.400K read / 1.550K write",
         "• Chip nhớ: V-NAND TLC + controller Pascal",
         "• Bảo hành: 5 năm hoặc 1.200 TBW"],
        "sale tháng 5 – bảo hành 5 năm chính hãng",
        "top hiệu năng PCIe Gen4 trên thị trường, phần mềm Magician quản lý + DirectStorage chuẩn cho game next-gen",
        "https://sintech.vn/products/o-cung-ssd-samsung-990-pro-2tb-pcie-gen-4-0-x4-nvme-r-7450-w-6900",
        "#Sintech #Samsung990Pro #SSDNVMe #PCIeGen4 #BuildPC #PCGaming #SSD2TB #SetupDep",
    ),
    "FB0008": (
        "TẢN KHÍ DEEPCOOL AG500 DIGITAL ARGB ĐEN",
        "Tản khí \"ngon bổ rẻ\" cho dàn Ryzen / Core Ultra, mát ngang AIO 240 mà giá chỉ bằng nửa — có cả màn LED Digital hiển thị nhiệt độ 🔥",
        ["• Loại: Tản tháp single tower",
         "• Heatpipe: 5 ống đồng tiếp xúc trực tiếp CPU",
         "• Fan: 1× 120mm PWM ARGB (500-1.850 RPM)",
         "• Màn LED Digital hiển thị nhiệt CPU realtime",
         "• TDP support: tới 220W",
         "• Socket: AM5/AM4 · LGA 1851/1700/1200/115x"],
        "giá tốt cuối tuần – BH 12 tháng",
        "tản khí có màn LED hiếm có trong tầm giá, ARGB sync chuẩn 5V 3-pin, lắp gọn không đụng RAM cao",
        "https://sintech.vn/products/tan-nhiet-khi-deepcool-ag500-digital-argb-den",
        "#Sintech #Deepcool #AG500 #TanKhi #ARGB #BuildPC #PCGaming #SetupDep",
    ),
    "FB0009": (
        "CASE ASUS PRIME AP201 WHITE MESH",
        "Case mid-tower mesh trắng tinh khôi 4 mặt — airflow đỉnh cho dàn PC nóng, nhìn cực sang chuẩn aesthetic gaming 2026 ✨",
        ["• Form factor: Mid-Tower (M-ATX / Mini-ITX)",
         "• Mặt: lưới mesh kim loại 4 phía",
         "• Hỗ trợ VGA: tới 338mm",
         "• Hỗ trợ tản AIO: 360mm trên / 280mm trước",
         "• Khe ổ: 2× 3.5\" + 2× 2.5\"",
         "• Cổng I/O: USB 3.2 Gen 2 Type-C + 2× USB 3.0 + Audio",
         "• Có sẵn 2 phiên bản: Trắng / Đen"],
        "deal sốc – có cả bản đen",
        "airflow mesh đỉnh, dây gọn dễ build, chứa tản AIO 360 + VGA 5070 Ti vô tư, giá mềm cho case ASUS",
        "https://sintech.vn/products/vo-case-asus-prime-ap201-white-mesh",
        "#Sintech #ASUSPrime #AP201 #CaseGaming #PCTrang #BuildPC #PCGaming #SetupDep",
    ),
    "FB0010": (
        "NGUỒN CORSAIR RM850e 850W ATX 3.0 PCIe 5.0 80+ GOLD",
        "Nguồn vàng full modular sẵn sàng cho RTX 50 series, dư công suất cho build 9800X3D + 5070 Ti, im ru kể cả load nặng 🔇",
        ["• Công suất: 850W liên tục",
         "• Chuẩn: ATX 3.0 + PCIe 5.0 (cáp 12V-2x6 sẵn)",
         "• Hiệu suất: 80 Plus Gold ≥ 90%",
         "• Modular: Full modular đi dây gọn",
         "• Quạt: 120mm Fluid Dynamic Bearing – Zero RPM mode",
         "• Bảo vệ: OVP / UVP / OCP / OPP / SCP / OTP",
         "• Bảo hành: 7 năm chính hãng Mai Hoàng"],
        "deal đầu tháng – BH 7 năm",
        "chuẩn ATX 3.0 + cáp 12VHPWR sẵn, dư công suất nâng cấp, im ru chế độ Zero RPM khi tải nhẹ",
        "https://sintech.vn/products/nguon-corsair-rm850e-850w-atx-3-0-pcie-5-0-80-plus-gold-full-modular-cp-9020263-na",
        "#Sintech #Corsair #RM850e #PSU850W #ATX30 #BuildPC #PCGaming #SetupDep",
    ),
    "FB0011": (
        "MAINBOARD ASUS TUF GAMING B850M-PLUS",
        "Main AMD chipset đời mới 2026 cho Ryzen 7000/9000 (cả 9800X3D), VRM TUF chuẩn quân đội — chiến CPU đầu bảng vô tư 🛡️",
        ["• Chipset: AMD B850 (socket AM5)",
         "• Form: Micro-ATX",
         "• VRM: 12+2+1 phase Dr.MOS",
         "• RAM: 4 khe DDR5 lên tới 8000+ MHz EXPO",
         "• M.2: 2 khe (1 khe Gen5 + 1 khe Gen4)",
         "• Mạng: 2.5G LAN + Wi-Fi 6E + Bluetooth 5.3",
         "• I/O: USB4 Type-C, HDMI 2.1, DisplayPort 1.4"],
        "combo CPU + Main + RAM giảm thêm",
        "B850 đời mới hỗ trợ M.2 Gen5 + Wi-Fi 6E, VRM dư cân 9800X3D, BIOS Q-Flash dễ update",
        "https://sintech.vn/products/mainboard-asus-tuf-gaming-b850m-plus",
        "#Sintech #ASUSTUF #B850M #MainboardAMD #AM5 #BuildPC #PCGaming #SetupDep",
    ),
    "FB0012": (
        "MAINBOARD COLORFUL BATTLE-AX Z890M-PLUS V20 DDR5",
        "Main Intel chipset Z890 đầu bảng cho Core Ultra (Arrow Lake), socket LGA 1851 mới toanh — chipset Z mà giá ngang B-series ⚡",
        ["• Chipset: Intel Z890 (socket LGA 1851)",
         "• Form: Micro-ATX",
         "• VRM: 14 phase Dr.MOS – tản dày",
         "• RAM: 4 khe DDR5 lên tới 7200+ MHz",
         "• M.2: 3 khe (1 khe Gen5 + 2 khe Gen4)",
         "• Mạng: 2.5G LAN + Wi-Fi 6E + Bluetooth 5.3",
         "• I/O: USB 3.2 Gen 2x2 Type-C, HDMI 2.1, DP"],
        "BH 36 tháng – Colorful chính hãng",
        "chipset Z OC tới max, cân được Core Ultra 9 285K, M.2 Gen5 sẵn cho SSD next-gen, giá hợp lý hơn ASUS/MSI cùng phân khúc",
        "https://sintech.vn/products/mainboard-colorful-battle-ax-z890m-plus-v20-new-ddr5",
        "#Sintech #Colorful #Z890 #IntelCoreUltra #LGA1851 #BuildPC #PCGaming #SetupDep",
    ),
    "FB0013": (
        "CPU INTEL CORE ULTRA 7 265KF (Tray)",
        "CPU Intel thế hệ Arrow Lake mới toanh, 20 nhân hiệu năng đa nhiệm vượt trội — gaming, render, code đều cân, tiết kiệm điện 30% so với gen 14 🎯",
        ["• Kiến trúc: Intel Arrow Lake (Intel 8 process)",
         "• Nhân/Luồng: 20 nhân (8P + 12E) – 20 luồng",
         "• Xung: 3.9GHz base / 5.5GHz Max Turbo",
         "• Cache: 36MB L3 + 36MB L2",
         "• Socket: LGA 1851 – TDP 125W",
         "• iGPU: Không có (bản KF)"],
        "bản tray giá hời – BH 36 tháng",
        "20 nhân cân stream + render thoải mái, bản KF rẻ hơn cho ai đã có VGA rời, chuẩn LGA 1851 nâng cấp dài hạn",
        "https://sintech.vn/products/cpu-intel-core-ultra-7-265kf-5-5ghz-20-nhan-20-luong-tray-new",
        "#Sintech #CoreUltra7 #265KF #IntelArrowLake #LGA1851 #BuildPC #PCGaming #SetupDep",
    ),
    "FB0014": (
        "MÀN HÌNH ASUS TUF GAMING VG279Q1A 27\" IPS 165Hz G-SYNC",
        "Tấm IPS 27\" Full HD 165Hz, 1ms response — phản xạ siêu nhanh cho FPS như Valorant, CS2, PUBG, kèm G-Sync loại bỏ xé hình ✨",
        ["• Kích thước: 27 inch – tấm IPS",
         "• Độ phân giải: 1920×1080 Full HD",
         "• Tần số quét: 165Hz (overclock từ 144Hz)",
         "• Response: 1ms MPRT – G-Sync Compatible",
         "• Độ sáng: 250 nits – Contrast 1000:1",
         "• Cổng: 2× HDMI + 1× DisplayPort + Audio out",
         "• Loa tích hợp 2W, kê chân ergonomic xoay/nghiêng/cao thấp"],
        "BH 36 tháng ASUS",
        "thương hiệu ASUS TUF bền bỉ, ergonomic stand chỉnh đa hướng, hợp setup gaming + làm việc cả ngày không mỏi mắt",
        "https://sintech.vn/products/man-hinh-asus-tuf-gaming-vg279q1a-27-inch-ips-165hz-g-sync",
        "#Sintech #ASUSTUF #VG279Q1A #ManHinhGaming #IPS165Hz #BuildPC #PCGaming #SetupDep",
    ),
    "FB0015": (
        "BÀN PHÍM CƠ AULA F75 3 MODE WIRELESS",
        "Phím cơ hot trend 2026 — kết nối 3 kiểu (dây / Bluetooth / 2.4GHz), switch Reaper gõ đã tay, RGB ảo diệu, núm xoay tiện lợi 🎨",
        ["• Layout: 75% (82 phím)",
         "• Kết nối: 3 mode – Type-C / Bluetooth 5.0 / 2.4GHz",
         "• Switch: Reaper (linear, hot-swap 5-pin)",
         "• Keycap: PBT Double-shot bền không mờ chữ",
         "• Đèn: RGB per-key 16,8 triệu màu",
         "• Pin: 4.000 mAh – dùng tới 1 tuần",
         "• Núm xoay đa năng + màn OLED nhỏ"],
        "đa dạng màu: xanh, trắng tím, đen",
        "phím cơ wireless 3 mode trong tầm giá học sinh, hot-swap đổi switch dễ, layout 75% gọn cho setup nhỏ",
        "https://sintech.vn/products/ban-phim-co-aula-f75-phien-ban-xanh-duong-trang-tim-reaper-switch-khong-day",
        "#Sintech #AULA #F75 #BanPhimCo #Wireless #SetupDep #PCGaming #GamingGear",
    ),
    "FB0016": (
        "CHUỘT AULA GAMING SC560 3 MODE",
        "Chuột wireless nhiều màu cực hot, sensor 26000 DPI siêu nhạy, pin xài cả tuần — cân FPS lẫn MOBA, văn phòng đa năng 💕",
        ["• Kết nối: 3 mode – có dây / Bluetooth / 2.4GHz",
         "• Sensor: PAW3395 26.000 DPI",
         "• Polling rate: 1.000Hz",
         "• Phím: 6 nút lập trình được",
         "• Pin: tới 100h sử dụng liên tục",
         "• Trọng lượng: 79g – công thái học ôm tay",
         "• Màu: Hồng / Xanh lá / Đen"],
        "BH 12 tháng chính hãng",
        "sensor PAW3395 ngang chuột cao cấp, wireless 1000Hz mượt, nhiều màu cute hợp setup nữ + nam",
        "https://sintech.vn/products/chuot-aula-gaming-sc560-3-mode-hong",
        "#Sintech #AULA #SC560 #ChuotGaming #Wireless #SetupDep #PCGaming #GamingGear",
    ),
}


def build_caption(name, hook, specs, price_note, usp, link, hashtags, censored_price):
    specs_str = "\n".join(specs)
    return (
        f"🔥 {name} – chỉ từ {censored_price}\n\n"
        f"{hook}\n\n"
        f"⚙️ THÔNG SỐ NỔI BẬT\n{specs_str}\n\n"
        f"💸 Giá: {censored_price} ({price_note})\n\n"
        f"👉 Điểm ăn tiền: {usp}\n\n"
        f"👉 Xem thêm thông tin sản phẩm tại đây:\n{link}\n\n"
        f"📩 Inbox ngay để chốt giá tốt nhất\n"
        f"📞 Hotline: 0911 713 000\n"
        f"📍 457 Trần Xuân Soạn, Q7\n\n"
        f"{hashtags}"
    )


print("Fetching prices từ sintech.vn...")
results = []
for code, handle in PRODUCTS:
    price = fetch_price(handle)
    if price:
        cen = censor(price)
        results.append((code, price, cen))
        print(f"  {code}: {price:>12,}đ → {cen}")
    else:
        results.append((code, None, "x.xxx.xxx"))
        print(f"  {code}: ✗ no price")

print("\nUpdating captions...")
conn = db.get_conn()
for code, price, cen in results:
    if code not in TEMPLATES:
        continue
    name, hook, specs, price_note, usp, link, hashtags = TEMPLATES[code]
    caption = build_caption(name, hook, specs, price_note, usp, link, hashtags, cen)
    conn.execute(
        "UPDATE posts SET caption=?, updated_at=datetime('now') WHERE code=?",
        (caption, code),
    )
    print(f"  ✓ {code}")
conn.commit()
conn.close()

print(f"\nDone. Updated {len(TEMPLATES)} captions.")
