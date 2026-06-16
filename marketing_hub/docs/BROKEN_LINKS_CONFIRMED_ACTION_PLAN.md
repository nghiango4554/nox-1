# BROKEN LINKS CONFIRMED — ACTION PLAN (10/6/2026)

Tổng confirmed_broken: **11** link (định nghĩa: status 404/410 hoặc invalid_url). CSV: `docs/broken_links_confirmed_20260610.csv`.

**Phân loại:** TẤT CẢ 11 đều là **external link** trong nội dung blog/SP (không có link nội bộ Sintech, không có asset CDN hstatic 404). Hành động = thay link khác hoặc gỡ trong trang nguồn. KHÔNG tự sửa — chờ vợ duyệt.

## Link internal cần sửa
- (không có)

## Asset CDN cần thay
- (không có asset hstatic 404)

## 410 (Gone) — gỡ/thay link

- `https://fptshop.com.vn/tin-tuc/thong-tin-tham-khao/nhung-khai-niem-ve-phan-cung-may-tinh-ma-ban-nen-biet-phan-1-12179`
  - nguồn: https://sintech.vn/blogs/news/so-sanh-tan-nhiet-nuoc-va-tan-nhiet-khi-nen-lua-chon-bo-tan-nhiet-nao

## 404 (Not Found) — external cần thay/gỡ

- `https://maytinhcdc.vn/laptop-dell-latitude-3420-42lt342002.html` (occ 1)
  - nguồn: https://sintech.vn/products/laptop-dell-latitude-3420-core-i5-1135g7-8gb-256gb-intel-iris-xe-graphics-14-inch-fhd-grayish-black
- `https://memoryzone.com.vn/compact-flash-cf` (occ 1)
  - nguồn: https://sintech.vn/blogs/news/toc-do-the-nho-la-gi-cach-kiem-tra-don-gian-va-chinh-xac-nhat
- `https://memoryzone.com.vn/cpu-may-tinh` (occ 1)
  - nguồn: https://sintech.vn/blogs/news/card-do-hoa-laptop-la-gi-cach-chon-card-do-hoa-roi-laptop-phu-hop-nhu
- `https://memoryzone.com.vn/laptop-gaming-lenovo-legion-5-15arh7-82re002wvn` (occ 1)
  - nguồn: https://sintech.vn/products/laptop-gaming-lenovo-legion-5-15arh7-82re002wvn-ryzen-5-6600h-rtx-3050-4gb-ram-16gb-ddr5-ssd-512gb-15-6-inch-ips-fhd-165hz-100-srgb-win-11
- `https://memoryzone.com.vn/macbook` (occ 1)
  - nguồn: https://sintech.vn/blogs/news/dia-chi-ip-la-gi-cach-xem-va-doi-dia-chi-ip-tren-windows-va-macbook-n
- `https://memoryzone.com.vn/mainboard-pc-colorful-cvn-b760m-frozen-wifi-v20` (occ 1)
  - nguồn: https://sintech.vn/products/mainboard-colorful-cvn-b760i-frozen-wifi-ddr5-v20
- `https://memoryzone.com.vn/nang-tam-ai-voi-gpt-4o-mini` (occ 2)
  - nguồn: https://sintech.vn/blogs/news/gemini-live-kham-pha-the-gioi-thong-qua-cuoc-tro-chuyen-thong-minh; https://sintech.vn/blogs/news/openai-o1-dot-pha-trong-xu-ly-ngon-ngu-tu-nhien-vuot-xa-mong-doi
- `https://memoryzone.com.vn/nas` (occ 1)
  - nguồn: https://sintech.vn/blogs/news/o-cung-mang-nas-la-gi-giai-phap-luu-tru-du-lieu-khong-gioi-han-cho-do
- `https://memoryzone.com.vn/pc-may-bo` (occ 1)
  - nguồn: https://sintech.vn/blogs/news/asus-rog-raikiri-pro-but-pha-moi-gioi-han-chinh-phuc-moi-chien-thang
- `https://memoryzone.com.vn/trello-la-gi` (occ 1)
  - nguồn: https://sintech.vn/blogs/news/notion-ai-tro-ly-viet-lach-thong-minh-nang-cao-hieu-suat-lam-viec

## Ghi chú
- 9/11 trỏ về **memoryzone.com.vn** (đối thủ đã đổi cấu trúc URL) — nên thay bằng link nội bộ Sintech tương đương hoặc gỡ hẳn.
- Đây là external outbound, KHÔNG ảnh hưởng index Sintech, ưu tiên thấp nhưng nên dọn để tránh outbound 404.

---

## CẬP NHẬT 10/6/2026 (chiều) — Re-check live + đề xuất thay/gỡ

Re-check live trang nguồn: **em đã gỡ/fix 5/11** (memoryzone: compact-flash-cf, cpu-may-tinh, legion-5, macbook, gpt-4o-mini). **Còn 6 link cần xử lý** — đề xuất (CHỜ DUYỆT, chưa PUT Haravan):

| # | Link chết | Nằm trong | Đề xuất |
|---|---|---|---|
| 1 | fptshop tin-tuc/...khai-niem-phan-cung | blog so-sanh-tan-nhiet-nuoc-va-khi | THAY → /blogs/huong-dan/keo-tan-nhiet-kim-loai-long-la-gi-co-nen-dung-khong |
| 2 | maytinhcdc laptop-dell-latitude-3420 | SP laptop-dell-latitude-3420 | GỠ (đối thủ bán cùng máy) — hoặc thay /collections/laptop-dell |
| 3 | memoryzone mainboard-colorful-cvn-b760m | SP mainboard-colorful-cvn-b760i-frozen | GỠ (đối thủ bán cùng main) |
| 4 | memoryzone /nas | blog o-cung-mang-nas-la-gi | GỠ (không có collection NAS nội bộ) |
| 5 | memoryzone /pc-may-bo | blog asus-rog-raikiri-pro | THAY → /collections/may-bo-dell (hoặc gỡ) |
| 6 | memoryzone /trello-la-gi | blog notion-ai-tro-ly-viet-lach | GỠ (không có nội bộ về Trello) |

**Nguyên tắc:** link trong trang SP trỏ thẳng đối thủ bán cùng món → gỡ; link blog tham khảo → thay nội bộ hợp ngữ cảnh nếu có, không thì gỡ. Sửa = PUT body_html Haravan (cần vợ duyệt từng dòng).

---

## KẾT QUẢ XỬ LÝ 10/6/2026 (chiều) — vợ chốt "gỡ hết 6, giữ anchor text"

**✅ 2 SP đã sửa qua API** (gỡ thẻ `<a>`, giữ nguyên anchor text; backup `nox-1_backup/broken-link-content-20260610/`):
- SP Laptop Dell Latitude 3420 (id 1074894195) — gỡ link maytinhcdc, verify link chết KHÔNG còn, anchor giữ. ✓
- SP Mainboard Colorful B760I (id 1071368808) — gỡ link memoryzone, verify sạch, anchor "Mainboard PC Colorful CVN B760I FROZEN WIFI V20" giữ nguyên. ✓

**⛔ 4 blog KHÔNG sửa được qua API** — Haravan blog/article API trả **502 Bad Gateway cứng** (đã biết, memory `reference_haravan_content_api`). Client chỉ có admin API, không wire Open API cho article. → **cần vợ sửa tay trong trình soạn blog Haravan** (bôi đen đoạn chữ có link → bỏ hyperlink, giữ chữ):
| Bài blog (sintech.vn) | Gỡ link trỏ tới |
|---|---|
| /blogs/news/so-sanh-tan-nhiet-nuoc-va-khi-nen-lua-chon-bo-tan-nhiet-nao | fptshop.com.vn/tin-tuc/...khai-niem-phan-cung |
| /blogs/news/o-cung-mang-nas-la-gi-giai-phap-luu-tru-du-lieu-khong-gioi-han-cho-do | memoryzone.com.vn/nas |
| /blogs/news/asus-rog-raikiri-pro-but-pha-moi-gioi-han-chinh-phuc-moi-chien-thang | memoryzone.com.vn/pc-may-bo |
| /blogs/news/notion-ai-tro-ly-viet-lach-thong-minh-nang-cao-hieu-suat-lam-viec | memoryzone.com.vn/trello-la-gi |

---

## ✅ HOÀN TẤT 10/6/2026 — gỡ đủ 6/6 qua API (giữ anchor text)

Blog sửa qua **Open API** `apis.haravan.com/web/blogs/...` (token blog scope web/blogs trong `state/haravan_token.json` — KHÔNG còn dùng /admin bị 502). Backup ORIG+NEW: `nox-1_backup/broken-link-content-20260610/`.

| # | Loại | ID | Link gỡ | Anchor giữ | Verify |
|---|---|---|---|---|---|
| 2 | SP | 1074894195 | maytinhcdc laptop-dell-3420 | (.) | sạch ✓ |
| 3 | SP | 1071368808 | memoryzone mainboard-b760m | Mainboard...B760I | sạch ✓ |
| 4 | Blog | art 1002431111 | memoryzone /nas | "ổ cứng NAS" | sạch ✓ |
| 5 | Blog | art 1002434630 | memoryzone /pc-may-bo | "PC" | sạch ✓ |
| 6 | Blog | art 1002411393 | memoryzone /trello-la-gi | "Trello" | sạch ✓ |
| 1 | Blog | art 1002414328 | fptshop /tin-tuc/khai-niem-phan-cung | (1 space) | sạch ✓ |

**Ghi chú:** bài #1 còn 1 link fptshop khác `/linh-kien/cpu` (đối thủ nhưng KHÔNG nằm trong list chết → giữ nguyên, không đụng). Nếu vợ muốn gỡ luôn thì báo.
