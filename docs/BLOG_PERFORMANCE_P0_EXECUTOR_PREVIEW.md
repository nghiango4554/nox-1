# BLOG PERFORMANCE — P0 QUICKWIN EXECUTOR (PREVIEW, local-only)

> Nối tiếp `BLOG_PERFORMANCE_P0_ACTION_PLAN.md`. Preview LOCAL — **PUT=0, upload=0, theme edits=0, no commit/push/deploy**. Dừng sau preview để review.

## Coverage

- P0 total: **10** · auto-safe **6** · image-task **4** · theme-only **3** · manual-review **1**
- preview-ready **5** · blocked-image **1**

## Bảng 10 bài P0

| P0# | Title | Group | Local draft | Auto fix | Image task | Status |
|---|---|---|---|---|---|---|
| 1 | Cấu hình chơi CS2 - Counter Strike | THEME_ONLY | — | — | — | theme_only |
| 2 | Cách tải và sử dụng Chat GPT cho m | AUTO_SAFE_CONTENT | 520 | table responsive ×1; clean HTML legacy + sanitize; loading=lazy ×4 (giữ LCP×1) | — | preview_ready |
| 3 | PC Bị Giật Điện Có Sao Không: Nguy | AUTO_SAFE_CONTENT | 521 | table responsive ×1; clean HTML legacy + sanitize; loading=lazy ×4 (giữ LCP×1) | 1 | preview_ready |
| 4 | Trung tâm sửa PC uy tín, lấy ngay  | AUTO_SAFE_CONTENT | 522 | table responsive ×4; clean HTML legacy + sanitize | — | preview_ready |
| 5 | Top 10 Thương Hiệu Linh Kiện Máy T | MANUAL_REVIEW | — | — | — | manual_review |
| 6 | Thu mua máy tính cũ giá cao tận nơ | AUTO_SAFE_CONTENT | 523 | table responsive ×7; clean HTML legacy + sanitize | — | preview_ready |
| 7 | PC nào chơi được GTA 5? Gợi ý buil | AUTO_SAFE_CONTENT | 524 | table responsive ×4; clean HTML legacy + sanitize; gỡ 1 ảnh chết; loading=lazy ×3 (giữ LCP×1) | 5 | blocked_image |
| 8 | Bật mí cách gắn quạt tản nhiệt cho | THEME_ONLY | — | — | 5 | theme_only |
| 9 | Cách khắc phục lỗi Command Prompt  | THEME_ONLY | — | — | — | theme_only |
| 10 | Top phần mềm test VGA (card màn hì | AUTO_SAFE_CONTENT | 525 | table responsive ×1; clean HTML legacy + sanitize; loading=lazy ×10 (giữ LCP×1) | 2 | preview_ready |

## Chi tiết nhóm AUTO_SAFE_CONTENT

### P0#2 — Cách tải và sử dụng Chat GPT cho máy tính Windows & macOS (Cập nhật 2025)
- article `1002794878` · draft local #520 · https://sintech.vn/blogs/huong-dan/cach-tai-va-su-dung-chat-gpt-cho-may-tinh-windows-macos-cap-nhat-20
- auto: table responsive ×1; clean HTML legacy + sanitize; loading=lazy ×4 (giữ LCP×1)
- gate: HTML PASS · giữ text 100.0% (654/654 từ) · broken sau 0 · table responsive 1 · blocked-image 0 → **preview_ready**
- còn lại (tay): set width/height ảnh → image task (cần metadata)

### P0#3 — PC Bị Giật Điện Có Sao Không: Nguyên Nhân & Cách Khắc Phục Tại Nhà
- article `1002753568` · draft local #521 · https://sintech.vn/blogs/huong-dan/pc-bi-giat-dien-co-sao-khong-nguyen-nhan-cach-khac-phuc-tai-nha
- auto: table responsive ×1; clean HTML legacy + sanitize; loading=lazy ×4 (giữ LCP×1)
- gate: HTML PASS · giữ text 100.0% (943/943 từ) · broken sau 0 · table responsive 1 · blocked-image 0 → **preview_ready**
- còn lại (tay): 1 ảnh nặng → resize (image task); set width/height ảnh → image task (cần metadata)

### P0#4 — Trung tâm sửa PC uy tín, lấy ngay ở Quận 7
- article `1002398567` · draft local #522 · https://sintech.vn/blogs/news/trung-tam-sua-pc-uy-tin-lay-ngay-o-quan-7
- auto: table responsive ×4; clean HTML legacy + sanitize
- gate: HTML PASS · giữ text 99.9% (890/891 từ) · broken sau 0 · table responsive 4 · blocked-image 0 → **preview_ready**
- còn lại (tay): set width/height ảnh → image task (cần metadata)

### P0#6 — Thu mua máy tính cũ giá cao tận nơi tại Tphcm
- article `1002404456` · draft local #523 · https://sintech.vn/blogs/news/thu-mua-may-tinh-cu-gia-cao-tan-noi-tai-tphcm
- auto: table responsive ×7; clean HTML legacy + sanitize
- gate: HTML PASS · giữ text 100.0% (990/990 từ) · broken sau 0 · table responsive 7 · blocked-image 0 → **preview_ready**
- còn lại (tay): set width/height ảnh → image task (cần metadata)

### P0#7 — PC nào chơi được GTA 5? Gợi ý build PC chơi GTA V mượt mà, giá tốt
- article `1002728313` · draft local #524 · https://sintech.vn/blogs/huong-dan/pc-nao-choi-duoc-gta-5-goi-y-build-pc-choi-gta-v-muot-ma-gia-tot
- auto: table responsive ×4; clean HTML legacy + sanitize; gỡ 1 ảnh chết; loading=lazy ×3 (giữ LCP×1)
- gate: HTML PASS · giữ text 100.0% (1020/1020 từ) · broken sau 0 · table responsive 4 · blocked-image 4 → **blocked_image**
- còn lại (tay): 4 ảnh external/đối thủ → image task (re-host tay); set width/height ảnh → image task (cần metadata)

### P0#10 — Top phần mềm test VGA (card màn hình) hiệu quả 2025 Kiểm tra hiệu năng & ổn định GPU
- article `1002792621` · draft local #525 · https://sintech.vn/blogs/huong-dan/top-phan-mem-test-vga-card-man-hinh-hieu-qua-2025-giup-kiem-tra-hi
- auto: table responsive ×1; clean HTML legacy + sanitize; loading=lazy ×10 (giữ LCP×1)
- gate: HTML PASS · giữ text 100.0% (1825/1825 từ) · broken sau 0 · table responsive 1 · blocked-image 0 → **preview_ready**
- còn lại (tay): 2 ảnh nặng → resize (image task); set width/height ảnh → image task (cần metadata)

## Image tasks (tóm tắt) — xem `blog_performance_p0_image_execution_tasks.csv`

## Theme handoff — xem `blog_performance_p0_theme_handoff.csv`

## Manual review — xem `blog_performance_p0_manual_review.csv`

## Exports
- BLOG_PERFORMANCE_P0_EXECUTOR_PREVIEW.md
- blog_performance_p0_executor_items.csv
- blog_performance_p0_image_execution_tasks.csv
- blog_performance_p0_theme_handoff.csv
- blog_performance_p0_manual_review.csv

## Safety
preview local only · PUT=0 · upload=0 · rehost=0 · theme edits=0 · no commit · no push · no deploy