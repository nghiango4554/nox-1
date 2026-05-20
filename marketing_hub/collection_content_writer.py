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
- TITLE: 48-58 ký tự (chặt hơn để chắc ăn). KHÔNG chứa "Sintech" (Haravan auto-suffix " - Sintech"). Format câu phân tích lợi ích, KHÔNG "Chính Hãng" / "Giá Rẻ" / capitalize từng từ.
- META: 140-160 ký tự. BẮT BUỘC kết thúc bằng 1 CTA viết HOA: "XEM NGAY tại Sintech" / "THAM KHẢO NGAY tại Sintech" / "CHỌN NGAY mẫu phù hợp tại Sintech" / "KHÁM PHÁ NGAY tại Sintech".
- BODY HTML: 1700-2200 từ (match chuẩn baseline). Đủ chiều sâu phân tích. KHÔNG H1.

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
- Đặt trong section H2 phù hợp, sau 1-2 câu dẫn

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
⚠️ TUYỆT ĐỐI KHÔNG dùng H2 template generic: "Vì sao chọn X tại Sintech?", "Các mẫu nổi bật trong X", "Cách chọn X phù hợp" — đây là style SEO 101 chán, không phải style Sintech.

THAY VÀO ĐÓ: 7-9 H2 dạng CÂU HỎI TỰ NHIÊN / GÓC NHÌN PHÂN TÍCH cụ thể, mỗi H2 giải quyết 1 vấn đề thật khách hay thắc mắc.

VÍ DỤ H2 PATTERN (bài PC RTX 4060/5060 đã sync) — học theo style này:
- "PC RTX 4060 / 5060 nằm ở phân khúc nào?"           ← định vị phân khúc
- "RTX 4060 và RTX 5060 nên hiểu sao cho đúng?"        ← so sánh ngang
- "Chọn theo màn hình sẽ dễ đúng hơn"                  ← cách chọn theo 1 tiêu chí thực tế
- "Trải nghiệm game thực tế nên kỳ vọng ra sao?"       ← kỳ vọng thực tế
- "Cấu hình nên ưu tiên khi mua PC RTX 4060 / 5060"    ← tiêu chí cấu hình
- "Khi nào nên chọn RTX 4060 / 5060 thay vì RTX 3050?" ← so sánh up/down
- "Lỗi dễ gặp khi mua PC RTX 4060 / 5060"              ← cảnh báo sai lầm
- "Mua PC RTX 4060 / 5060 tại Sintech"                 ← brand + dịch vụ
- "Câu hỏi thường gặp về PC RTX 4060 / 5060"           ← FAQ (BẮT BUỘC, 4-6 H3)

ÁP DỤNG CHO COLLECTION KHÁC: chế biến lại 7-9 H2 theo cùng tinh thần — câu hỏi tự nhiên, phân tích góc nhìn cụ thể, KHÔNG generic.
Ví dụ collection "máy bộ" có thể có H2 như:
- "Máy bộ phù hợp với ai thay vì laptop?"
- "Cấu hình tối thiểu cho công việc văn phòng hằng ngày"
- "Khi nào nên đầu tư cấu hình cao hơn?"
- "Lỗi dễ gặp khi chọn máy bộ giá rẻ"
- "Mua máy bộ tại Sintech"
- "Câu hỏi thường gặp về máy bộ"
(Đây chỉ là gợi ý — tự sáng tạo theo collection cụ thể)

THỨ TỰ NỘI DUNG:
1. <p> Intro 3-4 câu: định vị collection + ai dùng + lợi ích chính + chốt bằng "...có thể tham khảo tại <a href='https://sintech.vn'><strong>Sintech</strong></a>."

2. 6-8 <h2> phân tích (như pattern trên). MỖI H2 phải có ≥2 đoạn <p>, mỗi đoạn 2-4 câu. Có thể có <ul> trong section nếu cần liệt kê.

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

1. ÍT NHẤT 5 H2 phải chứa TÊN COLLECTION CỤ THỂ (vd: "Máy bộ Rosa", "PC RTX 4060", "Laptop Lenovo gaming"):
   ❌ "Phù hợp với ai?" → ✅ "Máy bộ Rosa phù hợp với ai hơn laptop?"
   ❌ "Lỗi dễ gặp" → ✅ "Lỗi dễ gặp khi mua máy bộ Rosa giá thấp"

2. PHẢI có 4 góc nhìn KHÁC NHAU (mỗi góc 1 H2 riêng):
   - Góc PHÂN KHÚC: định vị collection nằm ở phân khúc nào / phù hợp ngân sách bao nhiêu
   - Góc SO SÁNH: so với SP/collection ngang hàng hoặc thay thế (laptop, build PC, dòng khác)
   - Góc TƯ VẤN: cách chọn theo nhu cầu / màn hình / không gian / công việc cụ thể
   - Góc CẢNH BÁO: lỗi/sai lầm dễ gặp khi mua / khi nâng cấp

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
☑ body 1700-2200 từ (match baseline)
☑ Có 7-9 H2 (gồm cả H2 "Mua [X] tại Sintech" và H2 "Câu hỏi thường gặp")
☑ H2 là CÂU HỎI PHÂN TÍCH tự nhiên, KHÔNG generic "Vì sao chọn / Các mẫu nổi bật / Cách chọn"
☑ Có 4-6 H3 FAQ (mỗi H3 là câu hỏi, <p> theo sau là trả lời 2-4 câu)
☑ Mọi H2 có ≥2 câu dẫn trước <h3>/<table>
☑ Có 4 BẢNG <table> 3-cột — BẮT BUỘC gồm Pattern 5 (BẢNG PHÂN KHÚC GIÁ) + 3 pattern khác (phân khúc nhu cầu / so sánh SP / chọn theo input / tiêu chí cấu hình)
☑ Có H2 riêng "Phân khúc giá [tên collection]" hoặc "[Tên collection] có những phân khúc giá nào?"
☑ ≥5 H2 chứa tên collection cụ thể (không generic "Phù hợp với ai?" mà phải "[Tên collection] phù hợp với ai hơn laptop?")
☑ Có 4 góc nhìn riêng: PHÂN KHÚC / SO SÁNH / TƯ VẤN / CẢNH BÁO
☑ Câu ≤20 từ, đoạn 2-3 câu — readability ≥65
☑ Có ≥6 internal link <a> (1 intro, ≥4 body, 1 outro), link đa dạng collection ngang hàng + /pages/xay-dung-cau-hinh
☑ Có signature italic cuối
☑ Xưng "bạn", không "anh"
☑ Không forbidden phrases
☑ Không tag <section>/<article>/<div>, không data-*, không class Tailwind

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


def gen_collection_content(collection_url: str, collection_name: str,
                           page_title: str = "", admin_desc: str = "",
                           sp_names: list = None) -> dict:
    """Gọi Codex CLI sinh title + meta + body HTML cho 1 collection."""
    if not codex_provider.is_codex_available():
        return {"ok": False, "error": "Codex CLI chưa cài."}

    sp_names = sp_names or []
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
- Top SP trong collection ({len(sp_names)} mẫu): {', '.join(sp_names[:8])}{used_h2_block}

YÊU CẦU CỨNG:
1. ≥5/9 H2 phải chứa cụm "{collection_name}" rõ ràng — KHÔNG H2 generic kiểu "Phù hợp với ai?".
2. Bắt buộc 1 H2 + 1 BẢNG PHÂN KHÚC GIÁ (Pattern 5: Tiết kiệm / Tầm trung / Cao cấp / Ngân sách dư).
3. Bắt buộc 4 BẢNG tổng (1 phân khúc giá + 3 trong: nhu cầu / so sánh SP / chọn theo input / tiêu chí cấu hình).
4. Bắt buộc 4 góc nhìn riêng: PHÂN KHÚC GIÁ + SO SÁNH + TƯ VẤN + CẢNH BÁO LỖI.
5. Body 1700-2200 từ, readability ≥65 (câu ≤20 từ, đoạn 2-3 câu).
6. Intro KHÔNG bắt đầu giống bài cũ — mở câu với context thực tế riêng của {collection_name}.

Trả JSON thuần."""

    try:
        raw = codex_provider.call_codex(_SYSTEM_PROMPT, user_msg, timeout=180)
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

    return {
        "ok": True,
        "title": title,
        "meta": meta,
        "body_html": body_html,
        "title_len": len(title),
        "meta_len": len(meta),
    }


_TITLE_META_SYSTEM_PROMPT = """Bạn là chuyên gia SEO copywriter cho Sintech.vn (PC, laptop, gaming gear, 457 Trần Xuân Soạn Q7 TP.HCM, hotline 0911 713 000).

Nhiệm vụ: Gen LẠI title + meta description CHO 1 collection. KHÔNG cần body.

RULES CỨNG:
- TITLE: 48-58 ký tự (sweet 50-56). KHÔNG chứa "Sintech" (Haravan auto-suffix " - Sintech").
  KHÔNG capitalize từng từ ("Máy Bộ Rosa Chính Hãng" SAI). Tone phân tích lợi ích, không SEOer.
- META: 140-160 ký tự. BẮT BUỘC kết thúc bằng CTA HOA:
  "XEM NGAY tại Sintech" / "THAM KHẢO NGAY tại Sintech" / "CHỌN NGAY mẫu phù hợp tại Sintech" / "KHÁM PHÁ NGAY tại Sintech".
- Tone tư vấn, KHÔNG SEOer.
- KHÔNG filler banned: "bền bỉ", "đẹp mắt", "tốt nhất 2026", "đáng mua nhất", "khôn nhất", "vượt trội", "đỉnh cao", "Free ship".
- KHÔNG bịa giá / mã giảm giá / % giảm.
- ĐẾM len() trước khi trả — TITLE 48-58, META 140-160 STRICT.

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
    # Default: Claude CLI (Codex chưa cài trên máy này). Fallback Codex nếu Claude fail.
    try:
        import claude_provider as cp_claude
        use_claude = cp_claude.is_claude_available()
    except Exception:
        use_claude = False
    use_codex = codex_provider.is_codex_available()
    if not (use_claude or use_codex):
        return {"ok": False, "error": "Cả Claude CLI và Codex CLI đều chưa cài."}

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
        if use_claude:
            raw = cp_claude.call_claude(_TITLE_META_SYSTEM_PROMPT, user_msg, timeout=90)
        else:
            raw = codex_provider.call_codex(_TITLE_META_SYSTEM_PROMPT, user_msg, timeout=90)
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
    body_compressed = compress_html(sanitize_pasted_html(body_html))
    payload = {
        "id": haravan_id,
        "body_html": body_compressed,
        "metafields_global_title_tag": (title or "").strip(),
        "metafields_global_description_tag": (meta or "").strip(),
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
