"""Helper gen content cho collection landing page qua Codex CLI.

Flow:
  1. fetch_collection_context(url) — scrape HTML thật từ sintech.vn lấy title + description + top SP names
  2. gen_collection_content(url, name, ...) — call Codex sinh title + meta + body HTML
  3. sync_collection_to_haravan(haravan_id, ...) — PUT smart_collection
"""
import re, json, time
from datetime import datetime
from typing import Optional
import requests
from bs4 import BeautifulSoup

import codex_provider
import ai_provider
import sintech_rules
import haravan_client

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}


def fetch_collection_context(url: str) -> dict:
    """Scrape sintech.vn collection page → lấy title + description + top SP names."""
    try:
        r = requests.get(url, headers=HEAD, timeout=20, allow_redirects=True)
        if r.status_code >= 400:
            return {"ok": False, "error": f"HTTP {r.status_code}"}
        soup = BeautifulSoup(r.content, "lxml")

        # Title
        title_tag = soup.find("title")
        page_title = title_tag.get_text().strip() if title_tag else ""
        page_title = re.sub(r"\s*[-–|]\s*Sintech.*$", "", page_title, flags=re.I).strip()

        # H1
        h1_tag = soup.find("h1")
        h1 = h1_tag.get_text().strip() if h1_tag else ""

        # Description (admin description div)
        desc_el = (soup.select_one(".collection-description")
                    or soup.select_one(".rte")
                    or soup.select_one("[class*='collection-desc']"))
        admin_desc = desc_el.get_text(" ", strip=True)[:2000] if desc_el else ""

        # Top SP names trong collection
        sp_names = []
        for a in soup.find_all("a", href=re.compile(r"/products/")):
            text = a.get_text(strip=True)
            if text and len(text) > 5 and text not in sp_names:
                sp_names.append(text)
            if len(sp_names) >= 10: break

        return {
            "ok": True,
            "page_title": page_title,
            "h1": h1,
            "admin_desc": admin_desc,
            "sp_names": sp_names,
            "n_products": len(sp_names),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def fetch_real_products(haravan_collection_id: int, limit: int = 20) -> dict:
    """Gọi Haravan API lấy SP thật + giá thật trong collection → làm giàu prompt gen content."""
    if not haravan_collection_id:
        return {"ok": False, "error": "Thiếu haravan_id"}
    try:
        data = haravan_client._request(
            "GET", "/products.json",
            params={"collection_id": haravan_collection_id, "limit": limit,
                    "fields": "id,title,variants"}
        )
        products = data.get("products", [])
        if not products:
            return {"ok": False, "error": "Collection rỗng hoặc không tìm được SP"}
        names = [p["title"] for p in products if p.get("title")]
        prices = []
        for p in products:
            for v in (p.get("variants") or []):
                try:
                    prices.append(float(v["price"]))
                except Exception:
                    pass
        price_min = round(min(prices) / 1_000_000, 1) if prices else None
        price_max = round(max(prices) / 1_000_000, 1) if prices else None
        return {
            "ok": True, "names": names, "n": len(names),
            "price_min_tr": price_min, "price_max_tr": price_max,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


_SYSTEM_PROMPT = """Bạn là chuyên gia SEO + copywriter cho Sintech.vn — shop PC, laptop, gaming gear tại 457 Trần Xuân Soạn, Q7, TP.HCM. Hotline 0911 713 000. Nền tảng Haravan.
NHIỆM VỤ: Viết content landing page cho 1 COLLECTION (category sản phẩm), tone tư vấn mua hàng, không học thuật, không SEOer.

═══════════════════════════════════════════════════
⚠️ RULE 0 — HTML CLEAN (CỰC QUAN TRỌNG)
═══════════════════════════════════════════════════
Haravan filter strip wrapper lạ → trả về HTML có wrapper là MẤT HẾT NỘI DUNG trên web.

CHỈ ĐƯỢC DÙNG tag: <p> <h2> <h3> <ul> <ol> <li> <a> <strong> <em> <table> <tr> <td> <th> <br>

TUYỆT ĐỐI CẤM:
- <section>, <article>, <div class="markdown">, <div class="prose">, <div class="contents">
- <div class="flex...">, <div class="text-token-...">, <div class="R6Vx5W_...">
- Mọi attribute data-*: data-start, data-end, data-is-last-node, data-turn-id-container, data-is-intersecting, data-message-id, data-writing-block, data-testid
- Class Tailwind: prose, markdown, dark:, hover:, empty:, flex-col, gap-1, scroll-mb-

body_html PHẢI bắt đầu NGAY bằng <p> (intro) — KHÔNG wrap thêm <div> <section> bên ngoài.

═══════════════════════════════════════════════════
⚠️ LIMIT KÝ TỰ — ĐẾM len() TRƯỚC KHI TRẢ
═══════════════════════════════════════════════════
- TITLE: 48-58 ký tự (chặt hơn để chắc ăn). KHÔNG chứa "Sintech" (Haravan auto-suffix " - Sintech"). Format câu phân tích lợi ích, KHÔNG "Chính Hãng" / "Giá Rẻ" / capitalize từng từ. NÊN cài 1-2 tín hiệu tin cậy dạng chữ thường tự nhiên ("chính hãng", "bảo hành chính hãng") để tăng CTR; KHÔNG nhồi >2 cụm lợi ích; CẤM superlative ("rẻ nhất / giá sốc / đáng mua nhất").
- META: NHẮM 148-158 ký tự (đếm len(); tối thiểu 140, tối đa 160 — viết DÀI TAY vì hay bị hụt dưới 140). BẮT BUỘC kết thúc bằng 1 CTA viết HOA: "XEM NGAY tại Sintech" / "THAM KHẢO NGAY tại Sintech" / "CHỌN NGAY mẫu phù hợp tại Sintech" / "KHÁM PHÁ NGAY tại Sintech".
- BODY HTML: 2000-2500 từ. TỐI THIỂU 2000 từ — bài dưới 2000 từ bị tính FAIL, phải viết thêm phân tích cho đủ. Đủ chiều sâu, KHÔNG nhồi heading rỗng để chữa cháy số từ. KHÔNG H1.

═══════════════════════════════════════════════════
⚠️ READABILITY — CÂU NGẮN, ĐOẠN NGẮN
═══════════════════════════════════════════════════
- Mỗi câu TỐI ĐA 20 từ. Câu dài chia thành 2 câu ngắn.
- Mỗi <p> chỉ 2-3 câu, KHÔNG đoạn dài 5+ câu.
- Dùng từ đơn giản, tránh từ Hán Việt phức tạp khi có từ thuần Việt ngắn hơn.
- KHÔNG nhồi nhiều mệnh đề phụ trong 1 câu.
- Target readability score Vietnamese ≥65.

═══════════════════════════════════════════════════
⚠️ BẢNG SO SÁNH — BẮT BUỘC 3-4 BẢNG <table>
═══════════════════════════════════════════════════
Đây là điểm KHÁC BIỆT LỚN của Sintech vs SEO generic — phải có bảng tư vấn thực tế dễ scan.

YÊU CẦU MỖI BẢNG:
- 3 cột (KHÔNG 2, KHÔNG 4+)
- 5-8 hàng tổng (gồm 1 header <th>)
- Đặt trong section H2 phù hợp — CHỈ từ H2 THỨ 3 trở đi (2 H2 đầu sau intro PHẢI text-only), sau 1-2 câu dẫn

4 PATTERN BẢNG (chọn 3-4 cái áp dụng cho collection cụ thể):

PATTERN 1 — Bảng phân khúc nhu cầu:
| Nhu cầu sử dụng | Mức độ phù hợp | Gợi ý chọn nhanh |
| Game esport Full HD FPS cao | Rất hợp | Ưu tiên CPU tốt, RAM 16GB trở lên |
| Văn phòng đa nhiệm | Rất hợp | SSD NVME bắt buộc |
...

PATTERN 2 — Bảng so sánh dòng SP / phiên bản:
| Dòng/phiên bản | Phù hợp với nhu cầu | Khi nào nên chọn |
| [SP1] | Full HD, esport | Tối ưu chi phí |
| [SP2] | 2K nhẹ, đồ họa | Cần dư hiệu năng |
...

PATTERN 3 — Bảng chọn theo input thực tế (màn hình / phần mềm / không gian):
| Màn hình đang dùng | Có hợp [SP] không? | Gợi ý |
| Full HD 75Hz | Hợp, hơi dư | Chọn cấu hình thấp hơn để tiết kiệm |
...

PATTERN 4 — Bảng tiêu chí cấu hình (4 CỘT — range theo phân khúc):
| Linh kiện | Mức cơ bản | Mức tầm trung | Mức cao cấp |
| CPU | i3-12100F / Ryzen 5 5500 | i5-12400F / Ryzen 5 7600 | i7-13700F / Ryzen 7 7800X3D |
| RAM | 8-16GB DDR4-3200 | 16-32GB DDR5-5600 | 32GB+ DDR5-6000/6400 |
| SSD | 256-512GB NVMe Gen3 | 1TB NVMe Gen4 | 2TB+ NVMe Gen4 |
| VGA | iGPU / GTX 1650 / RTX 3050 | RTX 4060 / RX 7600 | RTX 4070 Super+ / RX 7800 XT+ |
| Mainboard | B660/B760/A520 | B760/B850 | Z790/X670 |
| Nguồn | 450-550W 80+ Bronze | 650-750W 80+ Gold | 850W+ 80+ Gold/Platinum |
(Mỗi cell phải có model/spec CỤ THỂ, KHÔNG để chung chung "phổ thông"/"tầm trung".)

PATTERN 5 — BẢNG PHÂN KHÚC GIÁ THEO RANGE (BẮT BUỘC — đặt trong H2 riêng "[Tên collection] có những phân khúc giá nào?" hoặc "Phân khúc giá tham khảo cho [tên collection]"):

BƯỚC 1: Tự xác định loại collection từ tên/URL → chọn range giá phù hợp theo bảng dưới:

| Loại collection | Range giá tham khảo 4 phân khúc |
|---|---|
| PC Gaming / Máy bộ Gaming | Tầm 10-15tr / 15-25tr / 25-40tr / Trên 40tr |
| PC Văn phòng / Máy bộ Văn phòng | Tầm 6-10tr / 10-15tr / 15-22tr / Trên 22tr |
| Laptop Gaming | Tầm 18-25tr / 25-35tr / 35-50tr / Trên 50tr |
| Laptop Văn phòng / Học tập | Tầm 8-15tr / 15-22tr / 22-32tr / Trên 32tr |
| Màn hình máy tính | Tầm 2-4tr / 4-7tr / 7-12tr / Trên 12tr |
| Bàn phím / Chuột / Tai nghe / Loa | Tầm 200k-700k / 700k-1.5tr / 1.5-3tr / Trên 3tr |
| Mainboard / VGA / CPU / RAM / SSD | Tầm 1-3tr / 3-6tr / 6-12tr / Trên 12tr |
| Case / Nguồn / Tản nhiệt / Fan | Tầm 500k-1.5tr / 1.5-3tr / 3-6tr / Trên 6tr |
| Camera / Mạng / Phụ kiện văn phòng | Tầm 300k-1tr / 1-2.5tr / 2.5-5tr / Trên 5tr |

⚠️ Nếu collection có tên chứa giá sẵn (vd "PC Gaming 10-20 Triệu", "PC Gaming 50-80 Triệu") → range trong bảng PHẢI overlap/sát khoảng đó, KHÔNG bịa range khác.
⚠️ Nếu user input có "Giá thật từ Haravan: Xtr – Ytr" → KHÔNG dùng bảng loại collection ở trên. Dùng khoảng X–Y đó làm reference THẬT, chia 4 tầng đều phủ toàn bộ X đến Y.

BƯỚC 2: Format bảng theo template (cấu hình tiêu biểu phải có MODEL/SPEC CỤ THỂ — không chung chung):
| Phân khúc giá | Cấu hình tiêu biểu (CPU · RAM · SSD · VGA) | Phù hợp với ai |
| Tầm 10-15 triệu | i3-12100F · 16GB DDR4-3200 · 256-512GB NVMe Gen3 · iGPU/RTX 3050 6GB | Học sinh, sinh viên, văn phòng nhẹ |
| Tầm 15-25 triệu | i5-12400F / Ryzen 5 7600 · 16GB DDR5-5600 · 512GB-1TB NVMe Gen4 · RTX 3050/4060 8GB | Game Full HD 144Hz, văn phòng đa nhiệm |
| Tầm 25-40 triệu | i7-13700F / Ryzen 7 7700 · 32GB DDR5-6000 · 1TB NVMe Gen4 · RTX 4060 Ti/4070 12GB | Game 2K, stream nhẹ, dựng video Premiere |
| Trên 40 triệu | i9-14900K / Ryzen 7 7800X3D / 9800X3D · 32-64GB DDR5-6400 · 2TB NVMe Gen4 · RTX 4070 Super/4080/5070 | Game 4K cao FPS, render 3D, đồ họa chuyên nghiệp |

⚠️ MỖI CELL specs PHẢI có model thật + thông số kỹ thuật cụ thể (CPU model code, RAM bus MHz, SSD generation, VGA model + dung lượng VRAM). KHÔNG dùng cụm "phổ thông/đời mới/mạnh" — sẽ bị tính lỗi.

DANH SÁCH MODEL HIỆN HÀNH 2026 (chọn từ đây, KHÔNG bịa):
- CPU Intel: i3-12100F, i3-13100F, i5-12400F, i5-13400F, i5-14400F, i7-13700F, i7-14700KF, i9-14900K, Core Ultra 5 245K, 7 265K, 9 285K
- CPU AMD: Ryzen 5 5500/5600/5600X3D (DDR4), Ryzen 5 7500F/7600 (DDR5), Ryzen 7 5800X3D, 7700/7700X/7800X3D, Ryzen 9 7900X/7950X, Ryzen 7 9700X/9800X3D, Ryzen 9 9950X
- RAM: DDR4-3200/3600 (gen cũ), DDR5-5200/5600/6000/6400 (gen mới)
- SSD: NVMe Gen3 (~3500MB/s) cho phổ thông; NVMe Gen4 (~7000MB/s) Samsung 990 Pro, WD SN770, Kingston KC3000, Lexar NM710
- VGA NVIDIA: GT 1030, GTX 1650, RTX 3050 6GB/8GB, RTX 4060 8GB, RTX 4060 Ti 8/16GB, RTX 4070 12GB, RTX 4070 Super, RTX 4070 Ti Super, RTX 4080 Super 16GB, RTX 5070/5080/5090 (Blackwell 2025)
- VGA AMD: RX 6600 8GB, RX 6700 XT 12GB, RX 7600 8GB, RX 7700 XT 12GB, RX 7800 XT 16GB, RX 9070 XT (RDNA4)
- Mainboard chipset: B660/B760/B850 (Intel mid), Z790 (Intel cao cấp); A520/B550/B650/X670 (AMD)
- Nguồn: 450W/550W/650W/750W/850W/1000W — thương hiệu Cooler Master, Corsair, FSP, MSI, Aigo

LUẬT QUAN TRỌNG VỀ GIÁ:
- DÙNG RANGE giá (vd "Tầm 15-25 triệu"), KHÔNG ghi giá đơn lẻ ("12.500.000đ", "Sale còn 9.9tr").
- KHÔNG ghi % giảm giá, khuyến mãi cụ thể, mã coupon.
- Đơn vị: "triệu" hoặc "tr" (vd "15-25 triệu" / "15-25tr"). KHÔNG dùng "10.000.000 VNĐ" rườm rà.
- Phụ kiện dưới 1 triệu: dùng "k" (vd "200k-700k").
- Range nên rộng vừa phải (vd "15-25tr" tốt hơn "15-17tr" quá hẹp dễ lệch khi giá biến động).

CÚ PHÁP HTML BẢNG:
<table><tr><th>Cột 1</th><th>Cột 2</th><th>Cột 3</th></tr>
<tr><td>...</td><td>...</td><td>...</td></tr>
...</table>

KHÔNG style inline cho table (theme sẽ apply). KHÔNG dùng <thead>/<tbody> phức tạp.

═══════════════════════════════════════════════════
CẤU TRÚC BODY — STYLE CHUYÊN GIA PHÂN TÍCH (KHÔNG TEMPLATE SEO 101)
═══════════════════════════════════════════════════
⚠️ TUYỆT ĐỐI KHÔNG dùng H2 generic dài dòng ("Cách chọn X phù hợp", "Các mẫu nổi bật trong X"), VÀ KHÔNG biến mọi H2 thành câu hỏi ghép dài lặp khuôn ("Trước khi chọn X cần nhìn vào tiêu chí nào?", "X nên ưu tiên gì trước?"). Đó là style cứng, lan man, volume search THẤP.

✅ STYLE CHUẨN (học trang TMĐT mạnh như Minh Tuấn Mobile): H2 NGẮN GỌN — là CHỦ ĐỀ/CỤM DANH TỪ hoặc CÂU HỎI NGẮN bám đúng từ khoá người ta search nhiều. Trộn 3 loại H2:
  (a) H2 TAXONOMY — phân rã danh mục thành nhóm THẬT, bẻ xuống H3:
      vd "Các dòng [SP]" → H3 từng dòng/model thật; "Phân loại [SP] theo [tiêu chí]" → H3 từng loại.
  (b) H2 TOPICAL ngắn — "Bảng giá [SP] mới nhất tại Sintech", "Kinh nghiệm chọn [SP] phù hợp", "[SP] nào đáng mua nhất hiện nay?", "Vì sao nên mua [SP] tại Sintech?".
  (c) H2 CÂU HỎI NGẮN volume cao — câu thật khách gõ Google: "[SP] bao nhiêu [đơn vị] là đủ?", "[SP] A khác B thế nào?", "[SP] có [tính năng] không?", "[SP] bảo hành mấy năm?".

VÍ DỤ BLUEPRINT (collection "Màn Hình Asus") — học BỐ CỤC + ĐỘ NGẮN này:
- H2 Các dòng màn hình Asus
    H3 TUF Gaming · H3 ROG Strix · H3 ProArt · H3 Eye Care · H3 ZenScreen di động
- H2 Phân loại theo tấm nền & tần số quét
    H3 IPS / Fast IPS · H3 VA · H3 OLED · H3 dải tần số 75-180Hz vs 240Hz+
- H2 Bảng giá màn hình Asus mới nhất tại Sintech      (BẢNG phân khúc giá — H2#3)
- H2 Kinh nghiệm chọn màn hình Asus phù hợp           (kèm bảng tiêu chí)
- H2 Màn hình Asus nào đáng mua nhất hiện nay?
- H2 Vì sao nên mua màn hình Asus tại Sintech?
- H2 Màn Asus bao nhiêu Hz hợp gaming?
- H2 Câu hỏi thường gặp về màn hình Asus              (H3 FAQ)

CHỌN TRỤC TAXONOMY theo loại collection (CẤM bịa — chỉ dùng dòng/model/loại CÓ THẬT):
- Theo hãng/dòng con: Asus TUF/ROG/ProArt; Acer Nitro/Predator/Aspire; MSI/Dell tương tự.
- Theo linh kiện/chip: VGA theo chip (RTX 4060/4070...), CPU theo đời/socket, RAM theo DDR4/DDR5, SSD theo Gen3/Gen4.
- Theo tấm nền/độ phân giải/tần số (màn hình); theo nhu cầu (gaming/văn phòng/đồ hoạ); theo phân khúc giá.
- Theo tình trạng (mới/cũ/like-new) — CHỈ khi danh mục thật sự có bán dạng đó.
- Collection hẹp (vd "Pin Laptop", "Laptop Dưới 15 Triệu") → trục taxonomy = phân loại theo công năng / nhu cầu / phân khúc giá thay cho dòng con.

THỨ TỰ NỘI DUNG:
1. <p> Intro 3-4 câu: định vị collection + ai dùng + lợi ích chính + chốt bằng "...có thể tham khảo tại <a href='https://sintech.vn'><strong>Sintech</strong></a>."

2. 10-12 <h2> theo STYLE CHUẨN ở trên (taxonomy + topical ngắn + câu hỏi volume cao). H2 NGẮN — tối đa ~8-10 từ; dùng TÊN SP NGẮN ("màn hình Asus", "MacBook Air") chứ KHÔNG nhồi full title collection dài vào mọi H2. THỨ TỰ + RULE BẮT BUỘC:
   ⚠️ 2 H2 ĐẦU TIÊN (ngay sau intro) PHẢI là H2 TAXONOMY (loại a) — bẻ xuống H3, KHÔNG chứa <table>. Vừa định hướng vừa giàu entity/từ khoá:
     • H2 #1 — "Các dòng [SP]" hoặc "Các loại [SP]": 1 đoạn <p> dẫn (2 câu), RỒI 4-6 <h3>, mỗi H3 là 1 dòng/model/loại CÓ THẬT + 1-2 câu <p> mô tả ngắn (hợp ai, khác gì).
     • H2 #2 — "Phân loại [SP] theo [tiêu chí]" (tấm nền/chip/nhu cầu/phân khúc): 1 đoạn <p> dẫn, RỒI 3-5 <h3> + <p> ngắn. Đoạn cuối làm cầu nối sang bảng giá.
   → Bảng <table> ĐẦU TIÊN chỉ xuất hiện TỪ H2 THỨ 3 ("Bảng giá [SP] mới nhất tại Sintech"). 3-4 bảng đặt ở H2 #3 trở đi. Bảng nằm ở H2 #1/#2 = FAIL.
   → Các H2 phân tích còn lại: mỗi H2 có 3-4 đoạn <p> (2-3 câu/đoạn) — phân tích đủ sâu (so sánh, ví dụ thực tế, lưu ý khi chọn), KHÔNG viết hời hợt 1-2 câu rồi nhảy section. H2 dạng câu hỏi ngắn cần 2-3 đoạn. <h3> CHỈ dùng cho 2 H2 taxonomy đầu + FAQ cuối, KHÔNG rải H3 lung tung.

3. <h2>Mua [tên collection] tại Sintech</h2> — section riêng giới thiệu dịch vụ Sintech (tư vấn, bảo hành, giao hàng, hỗ trợ kỹ thuật).

4. <h2>Câu hỏi thường gặp về [tên collection]</h2>
   <p>1 câu dẫn FAQ.</p>
   <h3>[Câu hỏi 1]?</h3><p>2-4 câu trả lời</p>
   <h3>[Câu hỏi 2]?</h3><p>2-4 câu trả lời</p>
   ... (4-6 cặp H3 + P)

5. <p>Tóm lại, [tên collection] tại <a href="https://sintech.vn"><strong>Sintech</strong></a> [chốt 2 câu phân tích lại]. Nếu chưa chắc nên chọn [option A] hay [option B], Sintech có thể tư vấn theo [nhu cầu/ngân sách/use case cụ thể] của bạn.</p>

6. <p><em>Tư vấn cấu hình bởi team kỹ thuật Sintech — Hotline 0911 713 000 · 457 Trần Xuân Soạn, Q7, TP.HCM.</em></p>

═══════════════════════════════════════════════════
⚠️ UNIQUE — MỖI BÀI PHẢI ĐỘC NHẤT
═══════════════════════════════════════════════════
Bài nào cũng giống bài nào = vô dụng cho SEO + người đọc. Quy tắc CỨNG:

1. H2 dùng TÊN SP NGẮN GỌN ("màn hình Asus", "PC RTX 4060", "MacBook Air") — KHÔNG lặp nguyên full title collection dài vào MỌI H2 (gây cứng, lan man). ~4-5 H2 có tên SP ngắn là đủ; H2 taxonomy/câu hỏi ngắn gọn tự nhiên là được.
   ❌ "Phù hợp với ai?" (generic) → ✅ "Màn Asus nào hợp dân thiết kế?"
   ❌ Lặp "Trước khi chọn [full title] cần nhìn tiêu chí nào?" ở mọi bài → ✅ taxonomy "Các dòng [SP]" / "Phân loại [SP] theo..."

2. ĐA DẠNG góc nhìn — bố cục blueprint đã phủ: taxonomy (dòng/loại) + phân khúc giá + so sánh + kinh nghiệm chọn + recommendation + brand + câu hỏi volume cao. KHÔNG cần ép cứng "Lỗi dễ gặp" mỗi bài (đó là filler volume thấp — chỉ thêm khi thật sự có sai lầm phổ biến đáng nói).

3. NGƯỜI ĐỌC dùng input "danh sách H2 đã dùng" để TRÁNH copy y nguyên cụm headings — tự viết phiên bản khác.

4. KHÔNG được dùng nguyên văn các H2 GENERIC sau (cấm tuyệt đối):
   ❌ "Vì sao chọn X tại Sintech?"
   ❌ "Các mẫu nổi bật trong X"
   ❌ "Cách chọn X phù hợp"
   ❌ "X phù hợp với ai?" (quá generic — phải hỏi cụ thể: "X phù hợp với ai hơn laptop?" / "X phù hợp với ngân sách bao nhiêu?")
   ❌ "Tính năng nổi bật của X"
   ❌ "Lợi ích khi mua X"

5. KHÔNG copy y nguyên đoạn intro hoặc câu signature giữa các bài — phải viết lại mỗi bài với context riêng.

═══════════════════════════════════════════════════
LƯU Ý VỀ DANH SÁCH SP TRONG INPUT (sp_names)
═══════════════════════════════════════════════════
- Nếu sp_names CHỨA tên SP thật khớp với collection (vd: collection "PC RTX 4060" có sp_names như "PC Gaming SIN Hyper RTX 4060") → có thể tham chiếu nhẹ trong section "Cấu hình nên ưu tiên" hoặc "Các mẫu phù hợp".
- Nếu sp_names KHÔNG khớp (vd: collection "Máy bộ Rosa" mà sp_names toàn mainboard/VGA do scrape lỗi) → IGNORE sp_names, KHÔNG liệt kê. Viết theo góc phân tích phân khúc thay vào đó.
- KHÔNG bao giờ liệt kê 5 SP với <ul><li>tên SP: lợi ích</li></ul> kiểu generic — đó là style cũ.

═══════════════════════════════════════════════════
LUẬT NỘI DUNG
═══════════════════════════════════════════════════
- Xưng "bạn", KHÔNG dùng "anh/em/quý khách".
- Câu mở ĐA DẠNG: "Hiện nay...", "Đối với...", "Trong khi đó...", "Nhờ đó...", "Bên cạnh đó...", "Một điểm đáng chú ý là...", "Khi [tình huống]...", "Tuy nhiên...". CẤM lặp "Bạn cần... Bạn nên... Bạn có thể..." liên tiếp.
- Mỗi đoạn 2-3 câu, mỗi câu 1 ý — KHÔNG nhồi spec, KHÔNG cộc 1-ý-xuống-dòng.
- Connector tự nhiên giữa các đoạn: "Nhờ đó", "Ngoài ra", "Tuy nhiên", "Một điểm đáng chú ý là".
- KHÔNG bịa thông số (CPU model, RAM GB, giá tiền) nếu không có trong input.

═══════════════════════════════════════════════════
INTERNAL LINK (BẮT BUỘC ≥6 link tổng)
═══════════════════════════════════════════════════
- Intro: 1 link <a href="https://sintech.vn"><strong>Sintech</strong></a>
- Body: ≥4 link tới collection/page con NGANG HÀNG hoặc related trên sintech.vn. Ví dụ phổ biến:
  + /pages/xay-dung-cau-hinh (Build PC custom)
  + /collections/pc-gaming
  + /collections/pc-van-phong
  + /collections/laptop
  + /collections/man-hinh-may-tinh
  + /collections/man-hinh-gaming
  + /collections/ban-phim
  + /collections/chuot
  + /collections/pc-gaming-theo-vga
  + /collections/pc-gaming-theo-gia
  + Collection cùng phân khúc trên/dưới (vd: bài "PC RTX 4060" → link "PC RTX 3050 / 4050" và "PC RTX 4070 / 5070")
- Outro: 1 link <a href="https://sintech.vn"><strong>Sintech</strong></a>
- Format: <a href="URL"><strong>anchor</strong></a> — KHÔNG <strong><a>...</a></strong>
- Anchor text: cụm danh từ ≤30c, mô tả đúng nội dung target. CẤM "tại đây", "xem thêm", "click here", "tham khảo".

═══════════════════════════════════════════════════
CẤM TRONG BODY (forbidden phrases)
═══════════════════════════════════════════════════
"bền bỉ", "đẹp mắt", "tốt nhất 2026", "đáng mua nhất", "khôn nhất", "vượt trội", "đỉnh cao",
"trong bài này", "sản phẩm này mang lại", "người dùng sẽ", "category này", "search intent",
"chia sẻ với bạn", "đem đến", "carte này",
"Free ship" (không sync policy), giá tiền cụ thể (nếu không có trong input).

═══════════════════════════════════════════════════
CHECKLIST TRƯỚC KHI TRẢ
═══════════════════════════════════════════════════
☑ title len 48-58 (đếm bằng len()), KHÔNG có "Sintech", KHÔNG capitalize từng từ kiểu "Máy Bộ Rosa Chính Hãng"
☑ meta len 140-160, có CTA HOA cuối
☑ body_html bắt đầu bằng <p>, KHÔNG <div>/<section> wrapper
☑ body 2000-2500 từ — ĐẾM số từ, TỐI THIỂU 2000 (dưới 2000 = FAIL, viết thêm phân tích cho đủ, KHÔNG thêm heading rỗng)
☑ Có 10-12 H2 (gồm 2 H2 taxonomy đầu + "Bảng giá... tại Sintech" + "Mua [X] tại Sintech" + "Câu hỏi thường gặp")
☑ H2 NGẮN (≤~10 từ): trộn taxonomy + topical ngắn + câu hỏi volume cao. KHÔNG để mọi H2 là câu hỏi ghép dài lặp khuôn ("Trước khi chọn X..."). KHÔNG generic "Vì sao chọn/Các mẫu nổi bật/Cách chọn".
☑ Có 4-6 H3 FAQ (mỗi H3 là câu hỏi, <p> theo sau là trả lời 2-4 câu)
☑ Mọi H2 có ≥2 câu dẫn trước <h3>/<table>
☑ 2 H2 ĐẦU (sau intro) là TAXONOMY có H3: H2#1 "Các dòng/loại [SP]" (4-6 H3 dòng/model THẬT), H2#2 "Phân loại [SP] theo [tiêu chí]" (3-5 H3) — KHÔNG <table>. H3 taxonomy CẤM bịa dòng/model không có thật.
☑ Có 4 BẢNG <table> 3-cột — BẮT BUỘC gồm Pattern 5 (BẢNG PHÂN KHÚC GIÁ) + 3 pattern khác (phân khúc nhu cầu / so sánh SP / chọn theo input / tiêu chí cấu hình)
☑ Có H2 "Bảng giá [SP] mới nhất tại Sintech" ở H2#3 (chứa BẢNG phân khúc giá)
☑ H2 dùng TÊN SP NGẮN (~4-5 H2 là đủ), KHÔNG nhồi full title collection dài vào mọi H2
☑ Đa dạng: taxonomy(H3) + bảng giá + so sánh + kinh nghiệm chọn + "nào đáng mua nhất" + brand + ≥1 câu hỏi volume cao. KHÔNG ép "Lỗi dễ gặp" mỗi bài.
☑ Câu ≤20 từ, đoạn 2-3 câu — readability ≥65
☑ Có ≥6 internal link <a> (1 intro, ≥4 body, 1 outro), link đa dạng collection ngang hàng + /pages/xay-dung-cau-hinh
☑ Có signature italic cuối
☑ Xưng "bạn", không "anh"
☑ Không forbidden phrases
☑ Không tag <section>/<article>/<div>, không data-*, không class Tailwind

═══════════════════════════════════════════════════
""" + "\n\n" + sintech_rules.common_rules_block(include_length=False) + """

═══════════════════════════════════════════════════
OUTPUT BẮT BUỘC: CHỈ JSON THUẦN — KHÔNG markdown code fence, KHÔNG text giải thích trước/sau.
═══════════════════════════════════════════════════
{
  "title": "...",
  "meta": "...",
  "body_html": "..."
}"""


def _get_used_h2_pool(limit: int = 60) -> list:
    """Lấy danh sách H2 đã dùng từ các collection job đã gen/sync, để AI tránh lặp."""
    try:
        import sqlite3
        from pathlib import Path
        db_path = Path(__file__).parent / "data" / "posts.db"
        if not db_path.exists():
            return []
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(
            "SELECT edited_body_html FROM collection_jobs "
            "WHERE edited_body_html IS NOT NULL AND status IN ('draft','synced') "
            "ORDER BY updated_at DESC LIMIT 25"
        )
        h2_set = set()
        for (body,) in cur.fetchall():
            if not body:
                continue
            for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", body, re.I | re.S):
                txt = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                if txt and len(txt) <= 120:
                    h2_set.add(txt)
                if len(h2_set) >= limit:
                    break
            if len(h2_set) >= limit:
                break
        conn.close()
        return sorted(h2_set)
    except Exception:
        return []


# ─────────── AUTO-FIX META LENGTH (đưa meta về 140-160c) ───────────
_META_CTAS = ["XEM NGAY tại Sintech", "THAM KHẢO NGAY tại Sintech",
              "CHỌN NGAY mẫu phù hợp tại Sintech", "KHÁM PHÁ NGAY tại Sintech"]
_META_PADS = [" với mức giá hợp lý", " cùng nhiều mức giá", " phù hợp nhiều ngân sách",
              " kèm tư vấn chọn cấu hình", " cùng đội kỹ thuật Sintech"]


def _meta_ok(m: str) -> bool:
    return 140 <= len(m or "") <= 160


def _quick_extend_meta(meta: str) -> str:
    """Chèn 1 cụm ngữ cảnh TRƯỚC câu CTA cuối để kéo meta tới 140-160c, giữ CTA HOA ở cuối."""
    for cta in _META_CTAS:
        idx = meta.rfind(cta)
        if idx <= 0:
            continue
        head = meta[:idx].rstrip()
        tail = meta[idx:].strip()
        head_core = head[:-1].rstrip() if head.endswith(".") else head
        for pad in _META_PADS:
            cand = f"{head_core}{pad}. {tail}"
            if _meta_ok(cand):
                return cand
    return meta


def _ai_regen_meta(old_meta: str, collection_name: str) -> str:
    """Nhờ Codex viết lại meta đúng 145-158c. Trả '' nếu fail."""
    sysp = ("Bạn viết meta description SEO tiếng Việt cho Sintech (PC/laptop/gaming gear). "
            "Trả về DUY NHẤT 1 dòng meta, CHÍNH XÁC 145-158 ký tự (đếm cả khoảng trắng + dấu câu), "
            "kết bằng CTA HOA 'XEM NGAY tại Sintech'. Văn tự nhiên, có ngữ cảnh dùng. "
            "CẤM bịa số liệu/giá, CẤM 'bền bỉ'/'Free ship'. KHÔNG giải thích, KHÔNG markdown.")
    usr = (f"Collection: {collection_name}\n"
           f"Meta cũ (sai length {len(old_meta)}c): {old_meta}\n"
           "Viết lại đúng 145-158 ký tự, giữ ý chính.")
    try:
        raw = ai_provider.call_ai(sysp, usr, timeout=60, reasoning_effort="low")
    except Exception:
        return ""
    for ln in raw.strip().splitlines():
        ln = ln.strip().strip("`").strip('"').strip()
        if len(ln) >= 80:
            return ln
    return raw.strip().strip("`").strip('"').strip()


def _fix_meta_length(meta: str, collection_name: str, max_ai_retries: int = 2) -> tuple:
    """Đưa meta về 140-160c: quick-suffix → AI regen → giữ nguyên nếu fail.

    Trả (meta_mới, cách_fix). cách_fix ∈ {ok, quick_suffix, ai_regen1/2, still_bad}.
    """
    meta = (meta or "").strip()
    if _meta_ok(meta):
        return meta, "ok"
    if len(meta) < 140:
        q = _quick_extend_meta(meta)
        if _meta_ok(q):
            return q, "quick_suffix"
    for i in range(max_ai_retries):
        new = _ai_regen_meta(meta, collection_name)
        if _meta_ok(new):
            return new, f"ai_regen{i+1}"
    return meta, "still_bad"


# ─────────── GUARD WORD-COUNT (ép body ≥2000 từ — bài chất lượng) ───────────
_WORD_FLOOR = 2000  # vợ yêu cầu: bài collection chất lượng phải ≥2000 từ

_EXPAND_SYSTEM_PROMPT = """Bạn là chuyên gia SEO + copywriter cho Sintech.vn (PC, laptop, gaming gear, 457 Trần Xuân Soạn Q7 TP.HCM, hotline 0911 713 000).
NHIỆM VỤ DUY NHẤT: MỞ RỘNG một body HTML collection đã có cho ĐỦ 2000-2500 TỪ (nhắm ~2200), giữ NGUYÊN cấu trúc + chất lượng. KHÔNG viết lại từ đầu. KHÔNG vượt quá 2500 từ.

CÁCH MỞ RỘNG (chỉ THÊM, không xoá nội dung cũ):
- Mỗi section H2 phân tích (không phải taxonomy/FAQ): thêm 1-2 đoạn <p> phân tích sâu hơn — so sánh thực tế, ví dụ cấu hình/use case cụ thể, lưu ý khi chọn. Mỗi đoạn 2-3 câu, mỗi câu ≤20 từ.
- Có thể thêm 1-2 H2 CÂU HỎI volume cao MỚI (câu thật khách search Google) + 2-3 đoạn trả lời.
- Có thể thêm 1-2 cặp <h3>câu hỏi</h3><p>trả lời</p> vào section FAQ cuối.
- GIỮ NGUYÊN: intro, 2 H2 taxonomy đầu (kèm H3), TOÀN BỘ <table> hiện có, mọi internal link <a>, signature italic cuối, và thứ tự các section.
- KHÔNG đổi/xoá title/meta. KHÔNG thêm H1. KHÔNG nhồi heading rỗng chỉ để tăng số từ.

RULE HTML (CỰC QUAN TRỌNG — sai là Haravan strip mất nội dung trên web):
- CHỈ tag: <p> <h2> <h3> <ul> <ol> <li> <a> <strong> <em> <table> <tr> <td> <th> <br>.
- CẤM <div> <section> <article>, mọi attribute data-*, mọi class Tailwind/markdown/prose. body PHẢI bắt đầu NGAY bằng <p>.
- Internal link format: <a href="URL"><strong>anchor</strong></a>.
- CẤM forbidden phrases: "bền bỉ","đẹp mắt","tốt nhất 2026","đáng mua nhất","vượt trội","đỉnh cao","Free ship", giá tiền cụ thể.
- Xưng "bạn". Readability ≥65 (câu ≤20 từ, đoạn 2-3 câu).

OUTPUT: CHỈ JSON thuần {"body_html": "..."} chứa body ĐẦY ĐỦ (cũ + phần thêm) — KHÔNG markdown fence, KHÔNG giải thích."""


def _count_body_words(html: str) -> int:
    """Đếm số từ trong body HTML (strip tag) — đồng nhất với audit DB."""
    if not html:
        return 0
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text.split()) if text else 0


def _body_html_valid(html: str) -> bool:
    """Body hợp lệ: bắt đầu bằng <p>, không wrapper cấm."""
    if not html:
        return False
    low = html.lstrip().lower()
    if not low.startswith("<p"):
        return False
    if "<div" in low or "<section" in low or "<article" in low:
        return False
    return True


def _expand_body_to_floor(body_html: str, collection_name: str, max_retries: int = 1) -> tuple:
    """Nếu body < _WORD_FLOOR từ → nhờ Codex mở rộng cho đủ ≥2000 từ.

    Trả (body_mới, n_words, đã_expand). Chỉ nhận bản expand nếu DÀI HƠN + hợp lệ HTML.
    """
    best = body_html
    best_w = _count_body_words(body_html)
    if best_w >= _WORD_FLOOR:
        return best, best_w, False

    for _ in range(max_retries):
        usr = (f"COLLECTION: {collection_name}\n"
               f"Body hiện tại MỚI CÓ {best_w} từ — CẦN đạt 2000-2500 từ (nhắm ~2200). Mở rộng theo hướng dẫn, "
               f"trả về body ĐẦY ĐỦ (cũ + phần thêm) dạng JSON {{\"body_html\":\"...\"}}.\n\n"
               f"--- BODY HIỆN TẠI ---\n{best}")
        try:
            raw = ai_provider.call_ai(_EXPAND_SYSTEM_PROMPT, usr, timeout=180)
        except Exception:
            break
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", text)
            if not m:
                break
            try:
                data = json.loads(m.group(0))
            except Exception:
                break
        nb = (data.get("body_html") or "").strip()
        nw = _count_body_words(nb)
        if nb and nw > best_w and _body_html_valid(nb):
            best, best_w = nb, nw
            if best_w >= _WORD_FLOOR:
                break
    return best, best_w, (best_w > _count_body_words(body_html))


def gen_collection_content(collection_url: str, collection_name: str,
                           page_title: str = "", admin_desc: str = "",
                           sp_names: list = None, haravan_id: int = None) -> dict:
    """Gọi Codex CLI sinh title + meta + body HTML cho 1 collection."""
    if not codex_provider.is_codex_available():
        return {"ok": False, "error": "Codex CLI chưa cài."}

    sp_names = sp_names or []

    # Bơm dữ liệu thật từ Haravan — SP thật + giá thật → hết "commodity"
    real_data_block = ""
    if haravan_id:
        hv = fetch_real_products(haravan_id)
        if hv.get("ok") and hv.get("names"):
            sp_names = hv["names"]  # Haravan names > web scrape
            parts = [f"- SP thật ({hv['n']} mẫu, từ Haravan): {', '.join(hv['names'][:10])}"]
            pmin, pmax = hv.get("price_min_tr"), hv.get("price_max_tr")
            if pmin and pmax:
                spread = (pmax - pmin) / pmin if pmin > 0 else 0
                if spread >= 0.3:
                    # Range đủ rộng → chia 4 tầng có ý nghĩa
                    parts.append(
                        f"- Giá thật từ Haravan: {pmin}tr – {pmax}tr\n"
                        f"→ BẢNG PHÂN KHÚC GIÁ (Pattern 5) PHẢI cover từ {pmin}tr đến {pmax}tr, "
                        f"chia 4 tầng đều. KHÔNG dùng range generic."
                    )
                else:
                    # Range quá hẹp (đồng giá / 1 SP) → bảng phân khúc 4 tầng vô nghĩa
                    parts.append(
                        f"- Giá thật từ Haravan: ~{pmin}tr (collection đồng giá hoặc ít mẫu)\n"
                        f"→ KHÔNG làm bảng phân khúc giá 4 tầng (sẽ bịa, vô nghĩa). "
                        f"Thay bằng bảng SO SÁNH TÍNH NĂNG (3 cột: Tiêu chí / Mức cơ bản / Mức nâng cấp) "
                        f"hoặc bảng CHỌn THEO NHU CẦU (nhu cầu / gợi ý chọn / lý do)."
                    )
            real_data_block = "\n\nDỮ LIỆU THẬT TỪ HARAVAN:\n" + "\n".join(parts)

    used_h2 = _get_used_h2_pool()
    used_h2_block = ""
    if used_h2:
        sample = used_h2[:40]
        used_h2_block = (
            "\n\nDANH SÁCH H2 ĐÃ DÙNG TRONG CÁC BÀI TRƯỚC — TRÁNH COPY Y NGUYÊN:\n"
            + "\n".join(f"  - {h}" for h in sample)
            + "\n→ Em phải viết H2 mới khác với danh sách trên (có thể giữ ý tưởng nhưng PHẢI thay từ ngữ + thêm tên collection cụ thể)."
        )

    user_msg = f"""COLLECTION cần viết content (mỗi bài PHẢI UNIQUE — không trùng heading/content với bài khác):
- Tên: {collection_name}
- URL: {collection_url}
- Page title hiện tại (Haravan): {page_title or '(rỗng)'}
- Description admin hiện tại: {admin_desc[:500] if admin_desc else '(rỗng)'}
- Top SP trong collection ({len(sp_names)} mẫu): {', '.join(sp_names[:8])}{used_h2_block}{real_data_block}

YÊU CẦU CỨNG:
1. 2 H2 ĐẦU = TAXONOMY có H3: "Các dòng/loại [SP ngắn]" (4-6 H3 dòng/model CÓ THẬT) + "Phân loại [SP] theo [tiêu chí]" (3-5 H3). CẤM bịa dòng/model không tồn tại.
2. H2#3 = "Bảng giá [SP ngắn] mới nhất tại Sintech" chứa BẢNG PHÂN KHÚC GIÁ (Pattern 5: Tiết kiệm / Tầm trung / Cao cấp / Ngân sách dư).
3. Tổng 4 BẢNG (1 phân khúc giá ở H2#3 + 3 trong: nhu cầu / so sánh dòng / chọn theo input / tiêu chí cấu hình). Bảng CHỈ từ H2#3 trở đi — H2#1/#2 không bảng.
4. 10-12 H2 NGẮN (≤~10 từ), dùng TÊN SP NGẮN (KHÔNG nhồi full title "{collection_name}" vào mọi H2). Trộn taxonomy + topical ngắn + ≥1 câu hỏi volume cao. KHÔNG ép "Lỗi dễ gặp" mỗi bài.
5. Body 2000-2500 từ — TỐI THIỂU 2000 từ (KHÔNG được dưới; mỗi H2 phân tích viết 3-4 đoạn sâu). Readability ≥65 (câu ≤20 từ, đoạn 2-3 câu).
6. META nhắm 148-158 ký tự (KHÔNG dưới 140), kết bằng CTA HOA. Intro mở câu với context riêng của {collection_name}, KHÔNG giống bài cũ.

Trả JSON thuần."""

    try:
        raw = ai_provider.call_ai(_SYSTEM_PROMPT, user_msg, timeout=180)
    except Exception as e:
        return {"ok": False, "error": f"Codex: {e}"}

    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {"ok": False, "error": "Codex không trả JSON.", "raw": text[:500]}
        try:
            data = json.loads(m.group(0))
        except Exception as e:
            return {"ok": False, "error": f"JSON parse: {e}", "raw": text[:500]}

    title = (data.get("title") or "").strip()
    meta = (data.get("meta") or "").strip()
    body_html = (data.get("body_html") or "").strip()

    if not title or not meta or not body_html:
        return {"ok": False, "error": "Codex trả thiếu field.", "raw": text[:500]}

    # Auto-fix meta về 140-160c (quick-suffix → AI regen)
    meta, meta_fix = _fix_meta_length(meta, collection_name)

    # Guard word-count: ép body ≥2000 từ (bài chất lượng) — mở rộng nếu hụt
    body_html, body_words, body_expanded = _expand_body_to_floor(body_html, collection_name)

    return {
        "ok": True,
        "title": title,
        "meta": meta,
        "body_html": body_html,
        "title_len": len(title),
        "meta_len": len(meta),
        "meta_fix": meta_fix,
        "body_words": body_words,
        "body_expanded": body_expanded,
    }


_TITLE_META_SYSTEM_PROMPT = """Bạn là chuyên gia SEO copywriter cho Sintech.vn (PC, laptop, gaming gear, 457 Trần Xuân Soạn Q7 TP.HCM, hotline 0911 713 000).

Nhiệm vụ: Gen LẠI title + meta description CHO 1 collection. KHÔNG cần body.

RULES CỨNG (length riêng cho collection):
- TITLE: 48-58 ký tự (sweet 50-56). KHÔNG capitalize từng từ ("Máy Bộ Rosa Chính Hãng" SAI). Tone phân tích lợi ích, không SEOer. NÊN cài 1-2 tín hiệu tin cậy chữ thường ("chính hãng", "bảo hành chính hãng"); KHÔNG nhồi >2 cụm; CẤM superlative ("rẻ nhất / sốc / đáng mua nhất").
- META: 140-160 ký tự, kết thúc bằng CTA HOA (xem pool ở RULE CHUNG bên dưới).
- Tone tư vấn, KHÔNG SEOer.
- ĐẾM len() trước khi trả — TITLE 48-58, META 140-160 STRICT.

""" + sintech_rules.title_meta_rules_block() + """

NẾU đã có title/meta hiện tại trong input → bản gen lại PHẢI KHÁC GÓC NHÌN với bản cũ
(thay angle: từ SPEC → USE CASE / từ AUDIENCE → SO SÁNH / etc.).

OUTPUT: JSON thuần {"title": "...", "meta": "..."} — KHÔNG markdown fence, không text giải thích."""


def gen_title_meta_only(collection_url: str, collection_name: str,
                        page_title: str = "", admin_desc: str = "",
                        sp_names: list = None,
                        existing_title: str = "", existing_meta: str = "",
                        field: str = "both") -> dict:
    """Gen LẠI title hoặc meta hoặc cả 2 cho collection — lightweight, không gen body.

    field: "title" | "meta" | "both"
    existing_title/meta: nếu có sẽ feed vào prompt để AI tránh lặp + đổi góc nhìn.

    Returns: {ok: bool, title?, meta?, title_len?, meta_len?, error?}
    """
    if field not in ("title", "meta", "both"):
        field = "both"
    # Default: Codex CLI (ưu tiên — dùng quota ChatGPT, không tốn API credit).
    # Fallback Claude CLI chỉ khi Codex chưa cài.
    use_codex = codex_provider.is_codex_available()
    try:
        import claude_provider as cp_claude
        use_claude = cp_claude.is_claude_available()
    except Exception:
        cp_claude = None
        use_claude = False
    if not (use_codex or use_claude):
        return {"ok": False, "error": "Cả Codex CLI và Claude CLI đều chưa cài."}

    sp_names = sp_names or []

    if field == "title":
        focus_line = "CHỈ gen lại TITLE (KHÔNG cần meta). Title 48-58 ký tự, KHÔNG \"Sintech\"."
        schema = '{"title": "..."}'
        old_block_lines = [f"  TITLE cũ: {existing_title or '(rỗng)'}"] if existing_title else []
    elif field == "meta":
        focus_line = "CHỈ gen lại META DESCRIPTION (KHÔNG cần title). Meta 140-160 ký tự, kết bằng CTA HOA."
        schema = '{"meta": "..."}'
        old_block_lines = [f"  META cũ: {existing_meta or '(rỗng)'}"] if existing_meta else []
    else:
        focus_line = "Gen lại CẢ title VÀ meta."
        schema = '{"title": "...", "meta": "..."}'
        old_block_lines = []
        if existing_title: old_block_lines.append(f"  TITLE cũ: {existing_title}")
        if existing_meta:  old_block_lines.append(f"  META cũ:  {existing_meta}")

    existing_block = ""
    if old_block_lines:
        existing_block = (
            "\n\nBẢN HIỆN TẠI (gen lần này PHẢI KHÁC GÓC NHÌN — không lặp):\n"
            + "\n".join(old_block_lines)
            + "\n→ Bản mới phải đổi angle (vd cũ nhấn SPEC thì mới nhấn USE CASE / AUDIENCE / SO SÁNH)."
        )

    user_msg = f"""COLLECTION cần gen lại {field}:
- Tên: {collection_name}
- URL: {collection_url}
- Page title hiện tại (Haravan): {page_title or '(rỗng)'}
- Description admin: {(admin_desc or '')[:400]}
- Top SP trong collection ({len(sp_names)} mẫu): {', '.join(sp_names[:6]) if sp_names else '(chưa có)'}{existing_block}

{focus_line}
Trả JSON {schema} duy nhất."""

    try:
        if use_codex:
            raw = ai_provider.call_ai(_TITLE_META_SYSTEM_PROMPT, user_msg, timeout=90)
        else:
            raw = cp_claude.call_claude(_TITLE_META_SYSTEM_PROMPT, user_msg, timeout=90)
    except Exception as e:
        return {"ok": False, "error": f"AI provider fail: {e}"}

    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return {"ok": False, "error": "Codex không trả JSON.", "raw": text[:500]}
        try:
            data = json.loads(m.group(0))
        except Exception as e:
            return {"ok": False, "error": f"JSON parse: {e}", "raw": text[:500]}

    title = (data.get("title") or "").strip()
    meta = (data.get("meta") or "").strip()

    out = {"ok": True}
    if field in ("title", "both"):
        if not title:
            return {"ok": False, "error": "AI trả thiếu title.", "raw": text[:500]}
        out["title"] = title
        out["title_len"] = len(title)
    if field in ("meta", "both"):
        if not meta:
            return {"ok": False, "error": "AI trả thiếu meta.", "raw": text[:500]}
        out["meta"] = meta
        out["meta_len"] = len(meta)
    return out


def sanitize_pasted_html(html: str) -> str:
    """Strip wrapper junk khi paste từ ChatGPT/AI chat trước khi sync Haravan.

    Bệnh: ChatGPT copy ra HTML có wrapper kiểu:
      <div data-turn-id-container="..." data-is-intersecting="true">
        <section class="text-token-text-primary R6Vx5W_threadScrollVars
                        focus:outline-none has-data-writing-block:pointer-events-none ...">
          <p data-start="..." data-end="..." data-is-last-node="">...</p>
        </section>
      </div>
    Haravan filter strip hết class/attribute lạ → còn vỏ <div></div> rỗng,
    body trên web mất sạch nội dung.

    Fix:
      1. Unwrap mọi <section> (Haravan kén tag này)
      2. Unwrap <div> nếu có attribute/class wrapper ChatGPT
      3. Strip data-* attribute ChatGPT-specific khỏi mọi tag còn lại
    """
    if not html:
        return html

    soup = BeautifulSoup(html, "lxml")

    WRAPPER_ATTRS = {
        "data-turn-id-container", "data-is-intersecting", "data-writing-block",
        "data-message-id", "data-message-author-role", "data-testid",
    }
    WRAPPER_CLASS_PARTS = [
        "R6Vx5W_", "_threadScrollVars", "text-token-", "has-data-", "scroll-mb-",
        "focus:outline", "pointer-events", "relative w-full overflow-visible",
        "thread-",
        "markdown", "prose", "dark:", "empty:", "wrap-break-word",
        "flex w-full", "flex max-w-full", "flex-col", "gap-1", "gap-4",
        "markdown-new-styling",
    ]

    def is_wrapper_div(tag) -> bool:
        for a in tag.attrs:
            if a in WRAPPER_ATTRS:
                return True
        cls = tag.get("class") or []
        if cls:
            cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)
            for p in WRAPPER_CLASS_PARTS:
                if p in cls_str:
                    return True
        return False

    for tag in soup.find_all("section"):
        tag.unwrap()

    for tag in soup.find_all("div"):
        cls = tag.get("class") or []
        cls_str = " ".join(cls) if isinstance(cls, list) else str(cls)
        if cls_str.strip() == "contents" and not tag.get_text(strip=True):
            tag.decompose()

    for _ in range(15):
        changed = False
        for tag in soup.find_all("div"):
            if is_wrapper_div(tag):
                tag.unwrap()
                changed = True
        if not changed:
            break

    STRIP_ATTRS = {
        "data-turn-id-container", "data-is-intersecting", "data-start", "data-end",
        "data-is-last-node", "data-is-only-node", "data-writing-block",
        "data-message-id", "data-message-author-role", "data-testid",
        "data-node-index",
    }
    for tag in soup.find_all(True):
        for a in list(tag.attrs):
            if a in STRIP_ATTRS:
                del tag.attrs[a]

    body = soup.body
    out = "".join(str(c) for c in body.children) if body else str(soup)
    return out.strip()


def compress_html(html: str) -> str:
    """Compress HTML body trước khi sync Haravan để giảm size.

    Aggressive: strip default CSS values từ Google Doc paste (giảm ~50% size):
      - font-variant:normal, vertical-align:baseline, white-space:pre-wrap
      - font-style:normal, text-decoration:none, background-color:transparent
    Plus: empty <span>, comments, whitespace giữa tags.
    """
    if not html:
        return html

    # 1. Strip HTML comments
    html = re.sub(r"<!--[\s\S]*?-->", "", html)

    # 2. Strip CSS properties defaults (Google Doc redundant)
    redundant_props = [
        r"background-color\s*:\s*transparent\s*;?",
        r"font-variant\s*:\s*normal\s*;?",
        r"vertical-align\s*:\s*baseline\s*;?",
        r"white-space\s*:\s*pre-wrap\s*;?",
        r"font-style\s*:\s*normal\s*;?",
        r"text-decoration\s*:\s*none\s*;?",
        r"font-weight\s*:\s*400\s*;?",  # 400 = normal default
        r"line-height\s*:\s*[\d.]+\s*;?",
        r"margin-top\s*:\s*12pt\s*;?",
        r"margin-bottom\s*:\s*12pt\s*;?",
        r"text-decoration-skip-ink\s*:\s*[^;\"]+\s*;?",
        r"letter-spacing\s*:\s*-?0\.\d+px\s*;?",
        # Aggressive level 2 — default font sizes Google Doc
        r"font-family\s*:\s*Arial\s*,\s*sans-serif\s*;?",
        r"font-family\s*:\s*Roboto\s*,\s*[^;\"]*;?",
        r"font-size\s*:\s*11pt\s*;?",  # default paragraph
        r"font-size\s*:\s*10pt\s*;?",
        r"color\s*:\s*rgb\(\s*0\s*,\s*0\s*,\s*0\s*\)\s*;?",  # color black = default
        r"color\s*:\s*#000000\s*;?",
        r"color\s*:\s*#000\s*;?",
        # Padding/margin với 5pt 5pt 5pt 5pt (table cells default)
        r"padding\s*:\s*5pt\s+5pt\s+5pt\s+5pt\s*;?",
        # Border styles in table cells (default 0.5pt solid black)
        r"border-(?:top|bottom|left|right)\s*:\s*solid\s+#000000\s+0\.5pt\s*;?",
        r"overflow-wrap\s*:\s*break-word\s*;?",
        r"overflow\s*:\s*hidden\s*;?",
    ]
    for prop in redundant_props:
        html = re.sub(prop, "", html, flags=re.IGNORECASE)

    # 3. Clean empty/dangling style attrs: style="  ;  ;  " or style="" or style="; ;"
    html = re.sub(r';\s*;', ';', html)  # collapse `;;`
    html = re.sub(r'style\s*=\s*"\s*;*\s*"', '', html)  # empty style=""
    html = re.sub(r'style\s*=\s*"\s*;', 'style="', html)  # leading `;`
    html = re.sub(r';\s*"', '"', html)  # trailing `;`
    html = re.sub(r'style\s*=\s*"\s+', 'style="', html)  # leading whitespace
    html = re.sub(r'\s+"', '"', html)  # trailing whitespace before close quote
    html = re.sub(r'\sstyle\s*=\s*""', '', html)  # cleanup empty styles

    # 4. Unwrap span lồng nhau không có style: <span><span>X</span></span> → X
    # Idempotent — chạy nhiều lần để unwrap dần các tầng
    for _ in range(5):
        html_new = re.sub(r'<span>\s*([^<]*?)\s*</span>', r'\1', html)
        if html_new == html: break
        html = html_new

    # 5. Strip whitespace giữa tags
    html = re.sub(r">\s+<", "><", html)

    # 6. Multiple spaces in text → 1 space
    html = re.sub(r" {2,}", " ", html)
    html = re.sub(r"\n+", " ", html)

    return html.strip()


def sync_collection_to_haravan(haravan_id: int, title: str, meta: str, body_html: str) -> dict:
    """Sync collection lên Haravan trong 1 PUT: body_html + SEO flat field.

    Theme Sintech đọc title/meta từ flat field `metafields_global_title_tag` /
    `metafields_global_description_tag` (verified 15/5 — endpoint /metafields
    cũng nhận data nhưng theme KHÔNG đọc từ đó).
    """
    import job_sync
    body_compressed = compress_html(sanitize_pasted_html(body_html))
    payload = {
        "id": haravan_id,
        "body_html": body_compressed,
        **job_sync.seo_metafields(title, meta),
    }

    try:
        haravan_client._request(
            "PUT", f"/smart_collections/{haravan_id}.json",
            payload={"smart_collection": payload},
        )
        return {"ok": True, "type": "smart_collections"}
    except Exception as e_smart:
        try:
            haravan_client._request(
                "PUT", f"/custom_collections/{haravan_id}.json",
                payload={"custom_collection": payload},
            )
            return {"ok": True, "type": "custom_collections"}
        except Exception as e_custom:
            return {"ok": False, "error": f"smart fail: {e_smart} | custom fail: {e_custom}"}


def sync_page_to_haravan(page_id: int, title: str, meta: str, body_html: str,
                         confirm: str = None) -> dict:
    """Sync 1 Haravan Page tĩnh qua Open API (admin pages bị 502 cứng).

    🔒 GUARD LIVE (2026-06-26): PUT Haravan CHỈ chạy khi `confirm == "LIVE_HARAVAN"`.
    Mặc định (confirm=None) → TỪ CHỐI, KHÔNG gọi Haravan. Caller muốn sync thật
    phải truyền confirm="LIVE_HARAVAN" có chủ đích (tránh sync live ngoài ý muốn).

    LƯU Ý: Open API page object KHÔNG expose field SEO title/meta → chỉ ghi
    được body_html. SEO `<title>`/meta description phải set TAY trong admin
    Haravan. (title/meta vẫn lưu trong tool để tham chiếu/gen.)
    """
    if confirm != "LIVE_HARAVAN":
        return {
            "ok": False, "blocked": True,
            "error": ("Sync Haravan Page bị KHÓA an toàn: cần confirm='LIVE_HARAVAN' "
                      "để PUT live. ĐÃ KHÔNG gọi Haravan."),
        }
    body_compressed = compress_html(sanitize_pasted_html(body_html))
    # Backup body sắp đẩy (audit/rollback) TRƯỚC khi PUT
    try:
        from pathlib import Path as _P
        _bk = _P(__file__).parent.parent / "nox-outputs"
        _bk.mkdir(parents=True, exist_ok=True)
        (_bk / f"_page_sync_{int(page_id)}.html").write_text(body_compressed, encoding="utf-8")
    except Exception:
        pass
    cfg = haravan_client.load_config()
    url = f"https://apis.haravan.com/web/pages/{page_id}.json"
    headers = {
        "Authorization": f"Bearer {cfg['access_token']}",
        "Content-Type": "application/json",
    }
    try:
        r = requests.put(
            url, headers=headers,
            json={"page": {"id": int(page_id), "body_html": body_compressed}},
            timeout=120,
        )
        if r.status_code in (200, 201):
            return {"ok": True, "type": "web_page"}
        return {"ok": False, "error": f"PUT page {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": f"PUT page exc: {e}"}
