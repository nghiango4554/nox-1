"""Bulk: rewrite spec block tối giản cho FB0003 → FB0016 trong DB."""
import sys, io, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import db

NEW_SPECS = {
    3: """🧠 8 nhân – 16 luồng (Zen 5)
⚡ Xung boost tới 5.2GHz
💎 96MB cache (3D V-Cache)
🔌 Socket AM5 – TDP 120W
🎨 Có iGPU Radeon tích hợp""",

    4: """🎮 RTX 5070 Ti 16GB GDDR7
✨ Có DLSS 4 + Frame Generation
🔥 OC sẵn từ nhà máy
❄️ Tản 3 fan + Vapor Chamber (fan-stop khi idle)
🔌 1x HDMI 2.1 + 3x DisplayPort 2.1
🔋 Nguồn đề nghị: 750W""",

    5: """🎮 RTX 5060 Ti 16GB GDDR7
✨ Có DLSS 4 + Frame Generation
🔥 OC sẵn, build ASUS Prime bền bỉ
❄️ Tản 2 fan Axial-tech
🔌 1x HDMI 2.1 + 3x DisplayPort 2.1
🔋 Nguồn đề nghị: 600W""",

    6: """💾 32GB DDR5 (1 thanh – dễ nâng lên 64GB)
⚡ Bus 6000MHz – CL40
🎯 Hỗ trợ Intel XMP 3.0
❄️ Tản nhôm low-profile, vừa mọi case
🛡️ Bảo hành trọn đời chính hãng""",

    7: """💾 Dung lượng 2TB
⚡ Đọc/ghi 7450 / 6900 MB/s (Gen4 NVMe)
🚀 Hỗ trợ DirectStorage cho game next-gen
🧊 Chip V-NAND TLC bền bỉ
🛡️ Bảo hành 5 năm""",

    8: """❄️ Tản tháp đơn – 5 heatpipe đồng
🌪️ 1 fan 120mm ARGB (500–1850 RPM)
📺 Màn LED Digital hiển thị nhiệt CPU
💪 Cân CPU TDP tới 220W
🔧 Lắp được Intel & AMD đời mới""",

    9: """🏠 Case Mid-tower (M-ATX/Mini-ITX)
💨 Mesh kim loại 4 mặt – airflow đỉnh
🎮 Lắp VGA tới 338mm
❄️ Lắp AIO 360mm thoải mái
🔌 USB Type-C + 2x USB 3.0 mặt trước
🎨 Có cả bản trắng & đen""",

    10: """⚡ Công suất 850W liên tục
🥇 80 Plus Gold (hiệu suất ≥ 90%)
🔌 ATX 3.0 + cáp 12V-2x6 sẵn cho RTX 50
🧩 Full modular – đi dây gọn
🔇 Zero RPM (im ru khi tải nhẹ)
🛡️ Bảo hành 7 năm""",

    11: """🎯 Chipset AMD B850 (socket AM5)
📐 Form Micro-ATX
💾 4 khe RAM DDR5 (tới 8000MHz)
⚡ 2 khe M.2 (1 Gen5 + 1 Gen4)
📶 Wi-Fi 6E + 2.5G LAN + Bluetooth 5.3
🔌 USB4 Type-C + HDMI 2.1""",

    12: """🎯 Chipset Intel Z890 (socket LGA 1851)
📐 Form Micro-ATX
💾 4 khe RAM DDR5 (tới 7200MHz)
⚡ 3 khe M.2 (1 Gen5 + 2 Gen4)
📶 Wi-Fi 6E + 2.5G LAN + Bluetooth 5.3
🔌 USB Type-C + HDMI 2.1""",

    13: """🧠 20 nhân (8P + 12E) – 20 luồng
⚡ Turbo tới 5.5GHz
💎 36MB cache L3
🔌 Socket LGA 1851 – TDP 125W
❌ Không có iGPU (bản KF – cần VGA rời)""",

    14: """📺 27" IPS Full HD (1920x1080)
⚡ 165Hz – Response 1ms
🎯 G-Sync Compatible (chống xé hình)
🔌 2x HDMI + 1x DisplayPort
🔊 Có loa tích hợp 2W
🪑 Chân xoay/nghiêng/lên xuống""",

    15: """⌨️ Layout 75% (82 phím) gọn
🔗 3 mode: dây / Bluetooth / 2.4GHz
🎵 Switch Reaper (linear, hot-swap)
🌈 RGB per-key + keycap PBT bền
🔋 Pin xài tới 1 tuần
🎛️ Có núm xoay + màn OLED""",

    16: """🖱️ 3 mode: dây / Bluetooth / 2.4GHz
🎯 Sensor PAW3395 – 26.000 DPI
⚡ Polling rate 1.000Hz mượt
🔘 6 nút lập trình được
🔋 Pin xài tới 100h
🎨 3 màu: Hồng / Xanh lá / Đen""",
}

# Replace block giữa "⚙️ THÔNG SỐ NỔI BẬT\n" và "\n\n" tiếp theo (kết thúc paragraph)
PATTERN = re.compile(r'(⚙️ THÔNG SỐ NỔI BẬT\n)([\s\S]+?)(\n\n)')

for post_id, new_spec in NEW_SPECS.items():
    p = db.get_post(post_id)
    if not p:
        print(f"FB{post_id:04d}: NOT FOUND")
        continue
    cap = p.get("caption") or ""
    m = PATTERN.search(cap)
    if not m:
        print(f"FB{post_id:04d}: PATTERN NOT MATCHED — skip")
        continue
    new_cap = PATTERN.sub(lambda mo: mo.group(1) + new_spec + mo.group(3), cap, count=1)
    db.update_post(post_id, {"caption": new_cap})
    print(f"FB{post_id:04d}: OK")
