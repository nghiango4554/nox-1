# Alt Manager — Image Issue Import (LibreCrawl) — 19/6/2026

Import data ảnh từ LibreCrawl crawl #4 (+ sẵn sàng cho crawler nhà) thành **queue review** trong `/alt-manager`. **KHÔNG auto apply live, KHÔNG upload, KHÔNG PUT.**

## Thành phần
- **Bảng** `alt_image_issues` (additive, tự tạo qua `ensure_table()`): `page_url, image_src, issue_type, context, alt_text, source, status, priority, first_seen, last_seen`. **UNIQUE(page_url, image_src)** → idempotent.
- **Module** `marketing_hub/alt_issue_import.py`: classify + import + query (list/counts/mark/export).
- **Routes** (routes/alt.py): `GET /api/alt-manager/issues` (filter type/context/status, sort priority) · `POST /api/alt-manager/issues/mark` · `GET /api/alt-manager/issues/export.csv`.
- **UI** `/alt-manager`: section "🖼️ Image Issue Queue" — count chips, filter type/context/status, bảng (preview ảnh + link trang), nút ✔ reviewed / 🚫 ignored, Export CSV.

## Kết quả import (crawl #4)
- **Tổng queue: 4172 issue** (đã dedup theo page_url+image_src).
- Theo type: `missing_alt` 4027 · `external_image` 74 · `broken_image_404` 42 · `cdn_rate_limited_suspected` 22 · `image_no_response` 6 · `wrong_store` 1.
- Theo context: product_gallery 3118 · blog_body_inline 450 · collection_image 422 · product_description_inline 133 · unknown 49.
- **Theme asset bị bỏ qua: 321.005** (noise, không đưa vào queue).
- Idempotent verified: chạy lại total không đổi.
- Report: [`alt_manager_import_report.csv`](./alt_manager_import_report.csv).

## Phân loại
**type:** missing_alt · empty_alt · broken_image_404 · image_no_response · cdn_rate_limited_suspected · external_image · wrong_store · ok_ignore
**context:** product_main_image · product_gallery · collection_image · blog_hero · blog_body_inline · product_description_inline · theme_asset · unknown
(noise rules ở [`librecrawl_noise_filter_rules.md`](./librecrawl_noise_filter_rules.md): CDN no-response/403 → `cdn_rate_limited_suspected`; 404 thật → `broken_image_404`.)

## Guard khi xử lý (CHƯA làm — chỉ ghi rule)
- Ảnh inline mô tả SP/blog nếu cần upload lại: **chỉ chấp nhận `file.hstatic.net/200000860097/file/...`**; nếu chưa có Files Manager session → status `FILES_MANAGER_SESSION_REQUIRED`; KHÔNG fallback theme asset/product image.
- KHÔNG upload hàng loạt, KHÔNG PUT SP/bài, KHÔNG đổi ảnh live.

## Chạy lại import
```
py -3.12 -c "import alt_issue_import as A; print(A.import_from_librecrawl(crawl_id=4))"
```
(source được gắn `librecrawl`; sẵn sàng thêm `internal_crawler` khi cần.)
