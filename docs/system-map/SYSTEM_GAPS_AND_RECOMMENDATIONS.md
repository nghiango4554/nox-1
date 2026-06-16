# System Gaps & Recommendations

Phân tích từ audit Batch 0–5 (2026-06-06, commit `1d757e1`). **KHÔNG refactor trong task này** — chỉ liệt kê + đề xuất ưu tiên.

## 1. Quan sát (analysis)
- **Page nhiều nút nhất:** `content_jobs_detail.html` (~35, gồm 15 nút WYSIWYG) · `post_form.html` (~22).
- **Page khó hiểu nhất:** `seo_title_meta.html` (8 nút batch/dual/recrawl + tier + per-row, nhiều flow nền).
- **Route không có UI rõ:** nhiều API status/poll (`/api/.../status`, `/gen-status`, SSE stream) — đúng bản chất (polling), không phải gap.
- **Button chưa map được endpoint:** một số nút client-side (WYSIWYG `cjCmd`, filter) — không gọi endpoint (đúng).
- **Form thiếu confirm (rủi ro):** vài action ghi-ngoài/destructive cần soi lại confirm — `/seo/clear`, `/seo/crawl-fresh` (PURGE DB), một số sync Haravan.
- **Dangerous action chưa cảnh báo đủ:** `cleanup_asset_storage.py` (DELETE ảnh Haravan), `/api/haravan/prune-stale` (DELETE rows).
- **Script có thể không còn dùng / NEEDS_REVIEW trigger:** `stop_title_meta_gen.ps1`, `start_marketing_hub*.bat/vbs`, `start_telegram_bot*` — không thấy trong Task Scheduler list hiện tại (chạy qua Startup/manual?).
- **Task dễ chạy trùng:** weekly CWV/schema chain qua vbs — cần đảm bảo idempotent (snapshot đã idempotent/week).
- **Source-of-truth trùng:** rules ở `sintech_rules.py` (chuẩn) NHƯNG cũng có `seo_writing_rules.md` + `seo_rules_config.json` — cần giữ 1 nguồn, tránh drift.
- **Docs lệch code:** `blog_jobs` table dùng nhiều nhưng **không có CREATE TABLE trong db.py** (chỉ ALTER) → schema không tự dựng được trên máy mới.
- **Prompt rải rác:** 11 prompt nằm ở 6 file khác nhau (product/collection/blog/seo/alt) — khó bảo trì tập trung.
- **Flow dễ mất state khi Flask restart:** title-meta gen, crawl, CWV pass — có auto-resume (tốt) nhưng phụ thuộc marker file.
- **Hard-code path:** `env.bat`, `auto_commit.bat` chứa path tuyệt đối + username máy.
- **Secret risk:** `backup_secrets.py` zip **KHÔNG mã hoá** toàn bộ token → tuyệt đối không sync cloud công khai.
- **SSL verify=False:** `haravan_client.py` bỏ verify SSL (VPN) — chấp nhận local, rủi ro nếu lên production.
- **Auth/CSRF:** app local-only (127.0.0.1) không có auth/CSRF — ok cho 1 máy, rủi ro nếu expose.
- **Rate limit:** AI providers + PSI có guard riêng nhưng **không có quota tracking thống nhất**.
- **Recovery/checkpoint:** có bundle + DB/secrets zip + git, nhưng restore flow chưa có script 1-lệnh.

## 2. Đề xuất — HIGH ROI (tối đa 10)
1. Thêm `CREATE TABLE IF NOT EXISTS blog_jobs` vào `db.py` (fix schema gap nghiêm trọng nhất).
2. **Mã hoá** secrets backup zip (password/age) — bịt rủi ro lộ toàn bộ token.
3. Confirm bắt buộc + double-confirm cho `/seo/clear`, `/seo/crawl-fresh` (PURGE) và mọi DELETE Haravan.
4. Bỏ `verify=False`, dùng CA bundle nội bộ hoặc bật verify khi không VPN.
5. Gom prompt về 1 thư mục `prompts/` (hoặc 1 module) để bảo trì tập trung.
6. Dọn script chết / xác nhận trigger thật (`stop_title_meta_gen.ps1`, `start_*`); ghi rõ Startup vs Task Scheduler.
7. Thống nhất source-of-truth rules: `sintech_rules.py` là chuẩn, `*.md/json` chỉ tham chiếu (ghi rõ trong file).
8. Thêm health-check + alert khi worker/watchdog chết (Telegram đã có kênh).
9. Viết 1 script `restore.ps1` (bundle→clone + zip→unzip) cho disaster recovery 1-lệnh.
10. Reconcile canonical `master` (1d757e1) với `origin/master` sạch (việc Git còn dang dở).

## 3. Đề xuất — MEDIUM ROI
1. Tách config path ra `.env`/env var, bỏ hard-code username trong `env.bat`/`auto_commit.bat`.
2. Quota tracking thống nhất cho 3 AI provider (1 module đếm chung).
3. Gắn `status`/`confidence` cứng vào mỗi route (decorator) để map tự cập nhật.
4. CSRF token cho POST forms (phòng khi expose ngoài 127.0.0.1).
5. Index thêm cho `seo_cwv_lcp` (url,strategy) + `seo_cwv_lcp_runs(scanned_at)` cho query nhanh.
6. Idempotency guard rõ ràng cho mọi weekly task (đánh dấu đã chạy theo ngày).
7. Trang `/seo/cwv/diff` đang NEEDS_REVIEW — hoàn thiện hoặc gỡ.
8. Gộp 60 file data local (`cc_img_backup`, coverage) ra khỏi tracking (đã có .gitignore mới trên origin).
9. Log có cấu trúc (JSON) cho worker để dễ trace job.
10. Trang Job Center hiển thị cả Task Scheduler state (không chỉ in-app jobs).

## 4. Đề xuất — LOW ROI
1. Tooltip Node ID trên UI để map ↔ code dễ tra.
2. Dark/light theme nhất quán (CWV page override riêng).
3. Gộp các nút WYSIWYG thành 1 component dùng chung (content/collection/blog detail).
4. Đặt tên endpoint nhất quán (`/api/...` cho mọi JSON action).
5. Trang settings UI cho PSI key / provider thay vì sửa file.
6. Export CSV cho mọi bảng audit (đã có vài chỗ).
7. Pagination chuẩn hoá (75 vs 50 vs 2000 khác nhau giữa trang).
8. Breadcrumb nhất quán toàn site.
9. Unit test cho `scoring_core` + validation functions.
10. Thêm `LICENSE`/ownership note (private repo).

> Tất cả chỉ là đề xuất. Ưu tiên thực thi theo thứ tự HIGH → MEDIUM khi vợ duyệt từng cái.
