# LibreCrawl Noise Filter Rules — 19/6/2026

LibreCrawl rất nhạy, sinh nhiều warning **không phù hợp bối cảnh Sintech (Haravan e-commerce VN)**. Quy tắc dưới đây dùng để lọc khi đọc/import data LibreCrawl — **dọn tín hiệu thật, không sửa mù**.

| LibreCrawl issue | Xử lý mặc định | Lý do |
|---|---|---|
| **Missing Twitter Card Tags** | `IGNORE` | Shop VN gần như không có traffic Twitter/X; không ảnh hưởng SEO Google. |
| **Canonical URL Different** | `REVIEW_ONLY` (không coi là lỗi) | Phần lớn hợp lệ (canonical trỏ URL sạch/biến thể/paginate). Chỉ soi tay khi nghi ngờ. |
| **Slow / Moderate Response Time** | `IGNORE cho CWV` | Bị thổi phồng do crawl dồn 10 luồng + CDN Haravan; KHÔNG dùng làm Core Web Vitals (CWV thật lấy qua PSI). |
| **Title Too Long** (product) | `REVIEW_ONLY`, không auto rewrite | Tên SP/spec dài tự nhiên. Chỉ queue nếu +suffix>70 KÈM lý do khác (trùng/CTR). Xem `title_review_policy_after_librecrawl.md`. |
| **Broken Image — No Response / 403** trên `cdn.hstatic.net` | `cdn_rate_limited_suspected` | CDN Haravan rate-limit khi check dồn → false positive (ảnh vẫn load thật). |
| **Broken Image — 404** (không phải CDN rate-limit) | `broken_image_404` (tín hiệu thật) | Ảnh thật thiếu — cần verify. |
| **Images Without Alt Text** | đưa vào Alt Manager (`missing_alt`) | Tín hiệu thật nhưng số lượng lớn → xử qua queue Alt Manager, không gấp. |
| **Missing Meta Description** | tín hiệu thật | Số nhỏ (~17) → fix nhanh. |
| **404 Client Error (page/collection)** | tín hiệu thật, ưu tiên | Vd 7 collection chết. |

## Áp dụng
- Image classification trong import Alt Manager dùng đúng nhãn ở cột "Xử lý" (CDN → `cdn_rate_limited_suspected`, ảnh 404 thật → `broken_image_404`).
- Report SEO nội bộ KHÔNG kéo Twitter-card / canonical-different / response-time của LibreCrawl thành "lỗi".
- CWV chỉ tin số từ PSI (module `cwv.py`), không tin response-time của LibreCrawl.
