"""Viec 3 + 4: bom noi dung & link noi bo cho 2 TRANG DICH cua 301.

Boi canh: 224 bai crack da 301 ve 2 trang nay -> chung dang HUNG TOAN BO suc manh (37k click).
NHUNG ca 2 bai deu co 0 INTERNAL LINK -> suc dong lai, khach doc xong khong co duong sang SP.

- Bai Office (1002989389): them muc "Office ban quyen vinh vien, 365 hay cho cong ty"
  (bam cum 'office ban quyen vinh vien gia bao nhieu' — Autocomplete) + bang chon goi co link SP.
- Bai Build PC Do Hoa (1003016123): them bang "chon may theo phan mem" co link SP
  + link sang bai AutoCAD 2026 moi.

Khoi moi chen TRUOC muc FAQ (de FAQ van nam cuoi -> theme sinh FAQPage tu do).
Luat: khong neu gia cu the · link SP nam TRONG BANG · style chuan BLOG.

Chay:  py -3.12 _scripts/b3_boost_targets.py --dry
       py -3.12 _scripts/b3_boost_targets.py --go
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import ai_provider
import faq_schema
import haravan_blog as hb
from faq_gen import H2, H3, P

BLOG = 1000960873
BACKUP = Path(r"C:\Users\NGHIANGO\.openclaw\workspace\nox-outputs\faq_backup")
TB = ('border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; font-size: 12pt; '
      'border: 2px solid #555; margin: 14px 0px;')
TH = 'border: 1px solid #999; background: #f4f4f4; padding: 8px; font-weight: 700; text-align: left;'
TD = 'border: 1px solid #999; padding: 8px;'
A = 'color: rgb(231, 76, 60); text-decoration: underline; font-weight: 700;'

TASKS = [
    {
        "id": 1002989389, "name": "Office bản quyền",
        "brief": """Viết THÊM 1 mục cho bài "Office 2021 bản quyền khác gì Office crack".
Mục mới bám cụm người thật gõ: "office bản quyền vĩnh viễn", "office bản quyền vĩnh viễn giá bao nhiêu",
"office bản quyền giá rẻ", "office bản quyền cho công ty", "office bản quyền 365".

NỘI DUNG mục mới:
- Giải thích 2 kiểu giấy phép: mua đứt dùng vĩnh viễn (Office 2021/2024 Home, Home & Business)
  vs thuê bao theo năm (Microsoft 365 Personal/Family/Business) — khác nhau ở quyền dùng lâu dài,
  cập nhật tính năng, dung lượng đám mây, số máy được cài.
- Trả lời "giá phụ thuộc gì": bản nào, mua đứt hay thuê bao, 1 máy hay nhiều máy, cá nhân hay công ty.
  TUYỆT ĐỐI KHÔNG viết con số giá.
- BẢNG "chọn gói Office theo nhu cầu": cột Nhu cầu | Nên chọn kiểu giấy phép | Gói gợi ý (chứa link SP).""",
        "links": [
            # ⚠️ handle DAI — go tay tu tri nho la 404. Lay tu API collection.
            ("/products/phan-mem-microsoft-office-home-2024-all-lng-apac-em-retail-online-esd-ep2-06796",
             "Office Home 2024 mua đứt dùng lâu dài"),
            ("/products/microsoft-office-365-personal-key-online", "Microsoft 365 Personal thuê bao 1 năm"),
            ("/products/microsoft-office-365-family-key-online-6gq-00083", "Microsoft 365 Family cho nhiều người"),
            ("/collections/phan-mem-ban-quyen", "danh mục phần mềm bản quyền"),
            ("/blogs/huong-dan/windows-ban-quyen-oem-retail-khac-gi-ban-crack", "Windows bản quyền OEM và Retail"),
        ],
    },
    {
        "id": 1003016123, "name": "Build PC Đồ Họa",
        "brief": """Viết THÊM 1 mục cho bài "Build PC Đồ Họa Photoshop, Premiere, AutoCAD".
Mục mới: "Chọn máy theo phần mềm bạn dùng" — giúp người đọc đi thẳng tới máy phù hợp.

NỘI DUNG:
- 2-3 câu dẫn: mỗi phần mềm ăn linh kiện khác nhau, chọn sai là tiền đổ vào chỗ không cần.
- BẢNG "chọn máy theo phần mềm": cột Phần mềm chính | Linh kiện cần ưu tiên | Máy gợi ý (chứa link SP).
  · AutoCAD 2D thuần → CPU xung cao, không cần VGA rời mạnh → PC Văn Phòng IT06
  · Photoshop, Illustrator, AutoCAD 2D nặng → CPU + RAM rộng → PC AI AI01
  · Premiere, dựng 3D, render, AI → CPU + VGA + RAM → PC AI AI02
- 1 đoạn dẫn sang bài chuyên sâu về cấu hình AutoCAD (dùng link bài AutoCAD 2026).""",
        "links": [
            ("/products/pc-van-phong-it06-intel-i7-14700-16gb-512gb", "PC Văn Phòng IT06 i7-14700"),
            ("/products/pc-ai-ai01-ryzen-5-5500-32gb-1tb-rtx-3060-12gb", "PC AI AI01 Ryzen 5 + RTX 3060"),
            ("/products/pc-ai-ai02-intel-i5-14400f-32gb-1tb-rtx-4060-8gb", "PC AI AI02 i5-14400F + RTX 4060"),
            ("/blogs/huong-dan/cau-hinh-autocad-2026-chon-cpu-ram-vga", "cấu hình chạy AutoCAD 2026"),
            ("/collections/pc-do-hoa", "danh mục PC đồ họa"),
        ],
    },
]

SYSTEM = f"""Bạn viết bổ sung nội dung cho bài blog Sintech (cửa hàng linh kiện & PC, TP.HCM).

LUẬT CỨNG:
- KHÔNG nêu giá tiền cụ thể. Được nói "tuỳ gói", "tầm phổ thông/cao cấp".
- KHÔNG bịa thông số. Không hướng dẫn crack.
- Xưng "bạn". Không dùng từ: research, SERP, đối thủ, tại đây.
- Không H1. Không in đậm trong thân bài. Không dấu ';'.
- CHỈ dùng link trong danh sách được cấp. LINK SẢN PHẨM PHẢI NẰM TRONG BẢNG (người đọc quét mắt bảng).
- Mỗi link dùng đúng 1 lần.

STYLE (chép nguyên):
h2: style="{H2}"   h3: style="{H3}"   p: style="{P}"
table: style="{TB}"  th: style="{TH}"  td: style="{TD}"
a: style="{A}"

Trả về DUY NHẤT HTML thuần của phần bổ sung (bắt đầu bằng <h2>), không giải thích, không bọc markdown."""


def gen(task, provider=None):
    links = "\n".join(f"- {u} — {t}" for u, t in task["links"])
    msg = f"""{task['brief']}

LINK ĐƯỢC PHÉP DÙNG (dùng hết, link sản phẩm đặt TRONG BẢNG):
{links}

Viết phần bổ sung. HTML thuần."""
    raw = (ai_provider.call_ai_single(provider, SYSTEM, msg, timeout=300) if provider
           else ai_provider.call_ai(SYSTEM, msg, timeout=300))
    return re.sub(r"^```(?:html)?|```$", "", (raw or "").strip(), flags=re.M).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    dry = not a.go

    for t in TASKS:
        art = hb.get_article(BLOG, t["id"])
        body = art["body_html"]
        block = gen(t, provider="claude")

        used = re.findall(r'href="(/[^"]+)"', block)
        allowed = {u for u, _ in t["links"]}
        bad = [u for u in used if u not in allowed]
        in_tb = re.findall(r'href="(/products/[^"]+)"', "".join(re.findall(r"<table.*?</table>", block, re.S)))
        print(f"═══ {t['name']} (id {t['id']})")
        print(f"   khối mới: {len(block)} ký tự · {len(set(used))} link ({len(in_tb)} SP trong bảng)")
        if bad:
            print(f"   ⚠ link lạ (không cho phép): {bad}")
            continue
        if not in_tb:
            print("   ⚠ link SP KHÔNG nằm trong bảng — bỏ qua")
            continue

        # chen TRUOC muc FAQ (giu FAQ o cuoi -> theme van sinh FAQPage)
        m = re.search(r'<h2[^>]*>(?:(?!</h2>).)*(?:Câu hỏi thường gặp|FAQ)', body, re.S | re.I)
        if not m:
            print("   ⚠ không tìm thấy mục FAQ — chèn cuối bài")
            new = body + "\n" + block
        else:
            new = body[:m.start()] + block + "\n" + body[m.start():]
        new, nfaq = faq_schema.attach(new)

        if dry:
            print(f"   SẼ CHÈN trước mục FAQ · FAQ giữ nguyên {nfaq} câu")
            print(f"   preview: {re.sub(r'<[^>]+>', ' ', block)[:150]}...")
            continue

        BACKUP.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        (BACKUP / f"{t['id']}_boost_{stamp}.html").write_text(body, encoding="utf-8")
        try:
            hb.update_article(BLOG, t["id"], {"body_html": new})
        except Exception as e:
            print(f"   API báo: {str(e)[:50]}")
        chk = hb.get_article(BLOG, t["id"])["body_html"]
        n_link = len(set(re.findall(r'href="(/[^"]+)"', chk)))
        print(f"   ✔ ĐÃ CHÈN · link nội bộ giờ: {n_link} · FAQ: {len(faq_schema.extract_faq(chk))} câu")
    return 0


if __name__ == "__main__":
    sys.exit(main())
