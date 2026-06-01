# -*- coding: utf-8 -*-
"""
Build curated SEO tier map (Tầng 1 → Tầng 2 → Tầng 3) → data/seo_tiers.json

Nguồn gốc: Google Sheet mindmap bộ lọc
(1B0WtpBeeST0Pyw5Z9R08r00A_MUMbdi9YDqnJGKkdyM gid 1825518453).

Đã re-tier (curate) thủ công:
  - Gộp cụm "🆕 Chưa phân tầng (Haravan mới)" ~60 collection về đúng T1/T2.
  - Sửa link gãy trong mindmap cũ (Laptop>hãng trỏ man-hinh-*, bàn di chuột trỏ
    chuot-may-tinh, bàn gaming chữ trỏ ban-2...) → dùng handle sạch.
  - Thêm T1 "Dịch vụ" gom Cài đặt Windows / Vệ sinh / Sửa chữa / Nâng cấp.

Node schema:
  T1: {name, icon, handle|null, children:[T2...]}
  T2: {name, handle|null, children:[T3...]}
  T3: {name, handle}
handle = slug collection Haravan (/collections/<handle>). null = node gom nhóm
thuần (không phải 1 collection thật) → SP = union các con.

Re-gen: py -3.12 _scripts/build_seo_tiers.py
"""
import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"


def t3(name, handle):
    return {"name": name, "handle": handle}


# Ghi lại các link đã sửa so với mindmap gốc (để báo cáo + audit)
FIXES = [
    "Laptop > Theo hãng > Asus: man-hinh-asus → laptop-asus",
    "Laptop > Theo hãng > MSI: man-hinh-msi → laptop-msi",
    "Laptop > Theo hãng > Lenovo: may-bo-lenovo → laptop-lenovo",
    "Laptop > Theo hãng > Dell: man-hinh-dell → laptop-dell",
    "Laptop > Theo hãng > HP: may-bo-hp → laptop-hp",
    "Laptop > Văn phòng: pc-van-phong-build-san → laptop-van-phong",
    "Laptop > Đồ họa: pc-do-hoa-ai-build-san → laptop-do-hoa",
    "Laptop > Gaming: pc-gaming → laptop-gaming",
    "Màn hình > Theo hãng: laptop-theo-hang (link gốc sai) → node gom nhóm",
    "Gaming Gear > Bàn di chuột Nhỏ/Lớn: chuot-may-tinh → ban-di-chuot-nho/lon",
    "Gaming Gear > Bàn Chữ Z/K/Y: ban-2 → ban-gaming-chu-z/k/yn",
]

TIERS = [
    {
        "name": "PC Gaming – Đồ họa – AI", "icon": "🎮", "handle": "pc-gaming-do-hoa-ai",
        "children": [
            {"name": "PC Gaming", "handle": "pc-gaming", "children": [
                t3("Cao cấp", "pc-gaming-cao-cap"),
                t3("Streaming", "pc-streaming-livestream"),
                t3("Esport", "pc-esport"),
            ]},
            {"name": "PC Gaming theo giá", "handle": "pc-gaming-theo-gia", "children": [
                t3("10 - 20 triệu", "pc-gaming-10-20-trieu"),
                t3("20 - 30 triệu", "pc-gaming-20-30-trieu"),
                t3("30 - 50 triệu", "pc-gaming-30-50-trieu"),
                t3("50 - 80 triệu", "pc-gaming-50-80-trieu"),
                t3("80 - 100 triệu", "pc-gaming-80-100-trieu"),
                t3("Trên 100 triệu", "pc-gaming-tren-100-trieu"),
            ]},
            {"name": "PC theo VGA", "handle": "pc-gaming-theo-vga", "children": [
                t3("RTX 3050 / 4050", "pc-rtx-3050-4050"),
                t3("RTX 4060 / 5060", "pc-rtx-4060-5060"),
                t3("RTX 4070 / 5070", "pc-rtx-4070-5070"),
                t3("RTX 4080 / 5080", "pc-rtx-4080-5080"),
                t3("RTX 4090 / 5090", "pc-rtx-4090-5090"),
            ]},
            {"name": "PC Đồ họa", "handle": "pc-do-hoa", "children": [
                t3("Photoshop", "pc-photoshop"),
                t3("Video Editing", "pc-video-editing"),
                t3("3D Rendering", "pc-3d-rendering"),
                t3("AutoCAD", "pc-autocad"),
            ]},
            {"name": "PC AI – Workstation", "handle": "pc-ai-workstation", "children": []},
        ],
    },
    {
        "name": "PC Văn phòng – Máy bộ", "icon": "🏢", "handle": "pc-van-phong-may-bo",
        "children": [
            {"name": "PC Văn phòng", "handle": "pc-van-phong", "children": [
                t3("Giá rẻ", "pc-van-phong-gia-re"),
                t3("Mini PC", "pc-mini-pc"),
                t3("All In One", "all-in-one"),
                t3("Học tập online", "pc-hoc-tap-online"),
                t3("Kế toán", "pc-ke-toan"),
                t3("Doanh nghiệp", "pc-van-phong-doanh-nghiep"),
            ]},
            {"name": "PC Văn phòng theo giá", "handle": "pc-van-phong-theo-gia", "children": [
                t3("Dưới 7 triệu", "pc-duoi-7-trieu"),
                t3("7 - 10 triệu", "pc-7-10-trieu"),
                t3("10 - 15 triệu", "pc-10-15-trieu"),
                t3("15 - 20 triệu", "pc-15-20-trieu"),
                t3("Trên 20 triệu", "pc-tren-20-trieu"),
            ]},
            {"name": "Máy bộ", "handle": "may-tinh-bo", "children": [
                t3("Dell", "may-bo-dell"),
                t3("HP", "may-bo-hp"),
                t3("Lenovo", "may-bo-lenovo"),
                t3("Rosa", "may-bo-rosa"),
            ]},
            {"name": "Máy in", "handle": "may-in", "children": [
                t3("Máy in wifi", "may-in-wifi"),
                t3("Máy in cắm dây", "may-in-cam-day"),
            ]},
        ],
    },
    {
        "name": "Laptop – MacBook", "icon": "💻", "handle": "laptop-macbook",
        "children": [
            {"name": "Laptop theo nhu cầu", "handle": "laptop", "children": [
                t3("Gaming", "laptop-gaming"),
                t3("Văn phòng", "laptop-van-phong"),
                t3("Đồ họa", "laptop-do-hoa"),
                t3("Sinh viên", "laptop-hoc-tap-sinh-vien"),
            ]},
            {"name": "Laptop theo giá", "handle": "laptop-theo-gia", "children": [
                t3("Dưới 15 triệu", "laptop-duoi-15-trieu"),
                t3("15 - 20 triệu", "laptop-15-20-trieu"),
                t3("20 - 25 triệu", "laptop-20-25-trieu"),
                t3("25 - 30 triệu", "laptop-25-30-trieu"),
                t3("30 - 40 triệu", "laptop-30-40-trieu"),
            ]},
            {"name": "Laptop theo hãng", "handle": "laptop-theo-hang", "children": [
                t3("Asus", "laptop-asus"),
                t3("Acer", "laptop-acer"),
                t3("MSI", "laptop-msi"),
                t3("Lenovo", "laptop-lenovo"),
                t3("Dell", "laptop-dell"),
                t3("HP", "laptop-hp"),
            ]},
            {"name": "MacBook", "handle": "macbook", "children": [
                t3("Air", "macbook-air"),
                t3("Pro", "macbook-pro"),
            ]},
            {"name": "Phụ kiện laptop", "handle": "phu-kien-linh-kien-laptop", "children": [
                t3("Sạc laptop", "sac-laptop"),
                t3("Sạc MacBook", "sac-macbook"),
                t3("Pin", "pin-laptop"),
                t3("RAM laptop", "ram-laptop"),
                t3("SSD laptop", "ssd-laptop"),
                t3("Bàn phím laptop", "ban-phim-laptop"),
                t3("Màn hình laptop", "man-hinh-laptop"),
                t3("Đế tản nhiệt", "de-tan-nhiet"),
                t3("Balo / Túi laptop", "balo-tui-laptop"),
            ]},
        ],
    },
    {
        "name": "Màn hình", "icon": "🖥️", "handle": "man-hinh-may-tinh-pc",
        "children": [
            {"name": "Theo nhu cầu", "handle": None, "children": [
                t3("Gaming", "man-hinh-gaming"),
                t3("Đồ họa", "man-hinh-do-hoa"),
                t3("Văn phòng", "man-hinh-van-phong"),
            ]},
            {"name": "Theo hãng", "handle": None, "children": [
                t3("MSI", "man-hinh-msi"),
                t3("VSP", "man-hinh-vsp"),
                t3("Dell", "man-hinh-dell"),
                t3("Asus", "man-hinh-asus"),
                t3("ViewSonic", "man-hinh-viewsonic"),
                t3("Samsung", "man-hinh-samsung"),
                t3("Acer", "man-hinh-acer"),
                t3("AOC", "man-hinh-aoc"),
                t3("AIWA", "man-hinh-aiwa"),
                t3("KTC", "man-hinh-ktc"),
                t3("Các hãng khác", "cac-hang-man-hinh-khac"),
            ]},
            {"name": "Theo kích thước", "handle": None, "children": [
                t3("22 - 25 inch", "man-hinh-22-25-inch"),
                t3("27 - 29 inch", "man-hinh-27-29-inch"),
                t3("30 - 32 inch", "man-hinh-30-32-inch"),
                t3("34 - 35 inch", "man-hinh-34-35-inch"),
                t3("Trên 43 inch", "man-hinh-tren-43-inch"),
            ]},
            {"name": "Theo tần số quét", "handle": None, "children": [
                t3("75Hz trở xuống", "man-hinh-75hz-tro-xuong"),
                t3("100Hz - 144Hz", "man-hinh-100hz-144hz"),
                t3("165Hz - 180Hz", "man-hinh-165hz-180hz"),
                t3("240Hz trở lên", "man-hinh-240hz-tro-len"),
            ]},
            {"name": "Theo độ phân giải", "handle": None, "children": [
                t3("Full HD", "man-hinh-full-hd"),
                t3("2K / QHD", "man-hinh-2k-qhd"),
                t3("4K", "man-hinh-4k"),
            ]},
            {"name": "Theo loại", "handle": None, "children": [
                t3("Màn cong", "man-hinh-cong"),
            ]},
            {"name": "Phụ kiện màn hình", "handle": "gia-treo-man-hinh", "children": [
                t3("Giá treo đơn", "gia-treo-don"),
                t3("Giá treo đôi", "gia-treo-doi"),
            ]},
        ],
    },
    {
        "name": "Linh kiện máy tính", "icon": "🔧", "handle": None,
        "children": [
            {"name": "CPU", "handle": "cpu", "children": [
                t3("Intel", "cpu-intel"), t3("AMD", "cpu-amd"),
            ]},
            {"name": "VGA", "handle": "vga", "children": [
                t3("NVIDIA", "vga-nvidia"), t3("AMD", "vga-amd"),
            ]},
            {"name": "Mainboard", "handle": "mainboard", "children": [
                t3("Intel", "mainboard-intel-1"), t3("AMD", "mainboard-amd"),
            ]},
            {"name": "RAM", "handle": "ram", "children": [
                t3("DDR4", "ram-ddr4"), t3("DDR5", "ram-ddr5"),
            ]},
            {"name": "SSD / HDD", "handle": "ssd-hdd-1", "children": [
                t3("SSD M.2", "ssd-m-2"), t3("SSD SATA", "ssd-sata"), t3("HDD", "hdd"),
            ]},
            {"name": "Nguồn (PSU)", "handle": "psu-nguon", "children": [
                t3("Dưới 550W", "nguon-duoi-550w"),
                t3("600W - 750W", "nguon-600w-750w"),
                t3("850W trở lên", "nguon-850w-tro-len"),
            ]},
            {"name": "Case", "handle": "case", "children": [
                t3("Gaming", "case-gaming-1"), t3("Văn phòng", "case-van-phong-1"),
            ]},
            {"name": "Tản nhiệt", "handle": "tan-nhiet", "children": [
                t3("Tản khí", "tan-khi"),
                t3("Nước AIO", "tan-aio"),
                t3("Fan case", "fan-case"),
                t3("Hub fan / LED", "hub"),
            ]},
        ],
    },
    {
        "name": "Gaming Gear", "icon": "🎧", "handle": None,
        "children": [
            {"name": "Bàn phím", "handle": "ban-phim", "children": [
                t3("Gaming", "ban-phim-gaming"),
                t3("Cơ", "ban-phim-co"),
                t3("Không dây", "ban-phim-khong-day-1"),
                t3("Có dây", "ban-phim-co-day"),
            ]},
            {"name": "Chuột", "handle": "chuot-may-tinh", "children": [
                t3("Gaming", "chuot-gaming"),
                t3("Văn phòng", "chuot-van-phong"),
                t3("Không dây", "chuot-khong-day"),
                t3("Có dây", "chuot-co-day"),
            ]},
            {"name": "Bàn di chuột", "handle": "ban-di-chuot", "children": [
                t3("Nhỏ", "ban-di-chuot-nho"),
                t3("Lớn", "ban-di-chuot-lon"),
            ]},
            {"name": "Tai nghe", "handle": "tai-nghe", "children": [
                t3("Gaming", "tai-nghe-gaming"),
                t3("Bluetooth", "tai-nghe-khong-day"),
                t3("Có dây", "tai-nghe-co-day-1"),
            ]},
            {"name": "Loa", "handle": "loa-1", "children": []},
            {"name": "Bàn", "handle": "ban-2", "children": [
                t3("Chữ Z", "ban-gaming-chu-z"),
                t3("Chữ K", "ban-gaming-chu-k"),
                t3("Chữ Y", "ban-gaming-chu-yn"),
            ]},
            {"name": "Ghế", "handle": "ghe", "children": [
                t3("Gaming", "ghe"),
                t3("Văn phòng", "ghe-van-phong-2"),
            ]},
            {"name": "Bàn & Ghế Gaming (combo)", "handle": "ban-ghe-gaming", "children": []},
        ],
    },
    {
        "name": "Phụ kiện máy tính", "icon": "🔌", "handle": None,
        "children": [
            {"name": "Cáp & chuyển đổi", "handle": "cap-chuyen-doi", "children": [
                t3("HDMI", "cap-hdmi"),
                t3("DisplayPort", "cap-displayport"),
                t3("Type-C", "cap-type-c"),
            ]},
            {"name": "Lưu trữ & Box đọc", "handle": "luu-tru-va-box", "children": [
                t3("BOX SSD M.2", "box-ssd-m-2"),
                t3("Box SSD SATA", "box-ssd-sata"),
                t3("Box HDD", "box-hdd"),
                t3("Thẻ nhớ", "the-nho"),
                t3("USB Flash", "usb-flash"),
            ]},
            {"name": "Cáp nguồn", "handle": "day-nguon", "children": [
                t3("Cáp nguồn PC", "cap-nguon-pc"),
                t3("Cáp sạc laptop", "cap-nguon-laptop"),
            ]},
            {"name": "Hub", "handle": "hub", "children": [
                t3("USB", "hub-usb"),
                t3("Type-C", "hub-type-c"),
            ]},
        ],
    },
    {
        "name": "Thiết bị mạng & Camera", "icon": "📡", "handle": None,
        "children": [
            {"name": "Thiết bị WiFi", "handle": "thiet-bi-wifi", "children": [
                t3("Router WiFi", "router-wifi-1"),
                t3("WiFi Mesh", "wifi-mesh"),
                t3("Bộ phát 4G/LTE", "bo-phat-wifi-4g-lte"),
            ]},
            {"name": "Thu WiFi & Bluetooth", "handle": "thiet-bi-thu-wifi-bluetooth", "children": [
                t3("USB Bluetooth", "usb-bluetooth"),
                t3("USB WiFi", "usb-wifi-1"),
            ]},
            {"name": "Bộ chia & Dây mạng", "handle": "bo-chia-mang-day-mang", "children": [
                t3("Bộ chia mạng", "bo-chia-mang"),
                t3("Dây mạng", "day-mang"),
            ]},
            {"name": "Camera", "handle": "camera", "children": [
                t3("Ngoài trời", "camera-ngoai-troi"),
                t3("Trong nhà", "camera-trong-nha"),
            ]},
            {"name": "Thiết bị mạng khác", "handle": "thiet-bi-mang-1", "children": []},
        ],
    },
    {
        "name": "Dịch vụ", "icon": "🛠️", "handle": None,
        "children": [
            {"name": "Cài đặt Windows – Phần mềm", "handle": "cai-dat-windows-phan-mem", "children": []},
            {"name": "Vệ sinh PC", "handle": "dich-vu-ve-sinh-pc", "children": [
                t3("Tại cửa hàng", "ve-sinh-pc-tai-cua-hang"),
                t3("Tận nhà", "ve-sinh-pc-tan-nha"),
                t3("Vệ sinh laptop", "ve-sinh-laptop"),
            ]},
            {"name": "Sửa chữa & Nâng cấp", "handle": "sua-chua-may-tinh", "children": [
                t3("Nâng cấp PC", "nang-cap-pc"),
                t3("Sửa chữa PC/Laptop", "sua-chua-pc-laptop"),
            ]},
        ],
    },
    {
        "name": "Hàng cũ", "icon": "♻️", "handle": "hang-cu", "children": [],
    },
]


def count(tiers):
    n1 = len(tiers)
    n2 = sum(len(t["children"]) for t in tiers)
    n3 = sum(len(t2["children"]) for t in tiers for t2 in t["children"])
    return n1, n2, n3


def collect_handles(tiers):
    hs = set()
    for t in tiers:
        if t.get("handle"):
            hs.add(t["handle"])
        for t2 in t["children"]:
            if t2.get("handle"):
                hs.add(t2["handle"])
            for t3n in t2["children"]:
                if t3n.get("handle"):
                    hs.add(t3n["handle"])
    return hs


def main():
    n1, n2, n3 = count(TIERS)
    handles = collect_handles(TIERS)
    # Validate handles tồn tại trong haravan_collections.json
    known = set()
    hcol = DATA / "haravan_collections.json"
    if hcol.exists():
        for c in json.load(open(hcol, encoding="utf-8")):
            if c.get("handle"):
                known.add(c["handle"])
    missing = sorted(h for h in handles if known and h not in known)

    out = {
        "version": "2026-06-01",
        "source_sheet": "1B0WtpBeeST0Pyw5Z9R08r00A_MUMbdi9YDqnJGKkdyM#gid=1825518453",
        "counts": {"t1": n1, "t2": n2, "t3": n3, "unique_handles": len(handles)},
        "fixes": FIXES,
        "missing_handles": missing,
        "tiers": TIERS,
    }
    DATA.mkdir(exist_ok=True)
    dest = DATA / "seo_tiers.json"
    json.dump(out, open(dest, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✓ Wrote {dest}")
    print(f"  T1={n1} T2={n2} T3={n3} unique_handles={len(handles)}")
    print(f"  fixes={len(FIXES)}")
    if missing:
        print(f"  ⚠️ {len(missing)} handle KHÔNG có trong haravan_collections.json:")
        for h in missing:
            print(f"     - {h}")
    else:
        print("  ✓ Tất cả handle khớp haravan_collections.json")


if __name__ == "__main__":
    main()
