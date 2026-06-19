# Crawler Blind Spots Fix — 19/6/2026

Vá 2 điểm mù của crawler nhà (`marketing_hub/seo.py` + `db.py`) phát hiện khi đối chiếu LibreCrawl.

## 4.1 Schema detection (false negative → FIXED)
**Bug:** `analyze_html` decompose toàn bộ `<script>` (để lấy text/word_count) **TRƯỚC** khi đếm schema → `soup.find_all("script", ld+json)` luôn rỗng → `has_schema=0` cho cả 2615 trang, dù raw HTML có 3-4 block JSON-LD.

**Fix:**
- Bắt `<script type="application/ld+json">` **TRƯỚC** decompose.
- Helper `_extract_schema_types()`: parse JSON-LD dạng **object / list / lồng `@graph`**, gom `@type` unique, **không fail** nếu 1 block lỗi (lưu `schema_errors`).
- Nhận diện Product / Organization / BreadcrumbList / Article (NewsArticle/BlogPosting) / FAQPage.
- Lưu thêm cột: `schema_types`, `schema_count`, `schema_has_product/article/faq`, `schema_errors`, `schema_scanned_at` (thêm vào cả `seo_upsert_page` + `seo_upsert_pages_batch`).

**Regression:** [`crawler_schema_detection_regression.csv`](./crawler_schema_detection_regression.csv) — **12/12 trang mẫu: trước `has_schema=0` → sau `=1`**. (product: Product/Organization/BreadcrumbList/Store; blog tương tự).

> ❗ KHÔNG tạo task "thêm schema" — Sintech ĐÃ có JSON-LD đầy đủ (LibreCrawl + crawler đã xác nhận). Đây chỉ là sửa lỗi phát hiện.

## 4.2 Internal link check (blind spot → FIXED)
**Bug:** `seo_links_to_check` chỉ check `is_internal = 0` (external). Internal link mặc định coi là OK vì "crawler chính đã verify" — NHƯNG crawler chính chỉ quét theo **sitemap**, nên internal link trỏ tới URL ngoài-sitemap (vd 7 collection chết) **không bao giờ được kiểm** → bỏ sót 404 nội bộ.

**Fix:** `seo_links_to_check` giờ check thêm **internal link mà target KHÔNG nằm trong tập trang status 200 đã crawl** (`target_url NOT IN (SELECT url FROM seo_pages WHERE status_code=200)`). Internal link đã là trang 200 vẫn bỏ qua (khỏi check thừa). CDN/social vẫn preskip.

**Regression:** [`internal_link_check_regression.csv`](./internal_link_check_regression.csv) — **7/7 collection chết (LibreCrawl 404) giờ `WILL_CHECK`** thay vì `SKIPPED`.

> ⚠️ Cần **re-crawl + link check** một lần để áp dụng (dữ liệu seo_links internal hiện chưa có status).

## 4.3 Noise filter
Bộ quy tắc lọc nhiễu khi đọc data LibreCrawl: xem [`librecrawl_noise_filter_rules.md`](./librecrawl_noise_filter_rules.md).

## File đụng
- `marketing_hub/seo.py`: `_extract_schema_types()` + bắt schema trước decompose + field schema vào result.
- `marketing_hub/db.py`: thêm cột schema vào 2 upsert + mở `seo_links_to_check` cho internal ngoài-sitemap.
- KHÔNG đụng Haravan live / theme.
