# P10 — Rollback (CSS-only blog image patch)

Patch CHƯA publish (local). Khi/ nếu đã publish, có 2 cách rollback:

## Cách 1 — Tắt flag (nhanh, không revert file)
- Set theme setting `blog_image_perf_patch_enabled = false` (hoặc xoá setting) → khối CSS bị Liquid loại bỏ, blog về hành vi cũ ngay. Không ảnh hưởng gì khác.

## Cách 2 — Revert file backup
- Ghi đè `assets/blog_article_style.scss.liquid` bằng bản gốc ở `theme_patch_p10/backup/blog_article_style.scss.liquid`.

## An toàn
- Patch chỉ thêm CSS dưới `.article-content` (blog body) → KHÔNG đụng product/collection/home.
- Mặc định flag OFF: kể cả khi file đã lên theme, nếu chưa bật setting thì KHÔNG có hiệu lực.
- KHÔNG xoá file, KHÔNG đổi JS/layout.
