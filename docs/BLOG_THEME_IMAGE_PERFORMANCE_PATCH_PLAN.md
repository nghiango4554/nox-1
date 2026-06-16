# BLOG THEME IMAGE PERFORMANCE PATCH — PLAN (CSS-only, local preview)

> P10 phạm vi **CSS-only** (vợ chốt). Sửa CLS/LCP blog ở tầng theme vì Haravan strip attr `<img>` trong body_html. **KHÔNG publish · KHÔNG PUT Haravan · KHÔNG deploy · KHÔNG commit.** Chỉ patch local + preview.

## 1. Gốc vấn đề
- Live `<img>` chỉ còn `src` (Haravan strip loading/fetchpriority/width/height/alt/class/style).
- Body không có width/height → reflow khi ảnh tải → CLS cao (retest: CLS 5 bài không giảm).
- `<div>/<table>` style + content cleanup thì SỐNG.

## 2. File target (đã scan, KHÔNG giả định)
- Wrapper body blog: `<div class="rte article-content">{{ article.content }}</div>` (templates/article.liquid).
- CSS blog: `assets/blog_article_style.scss.liquid` — **chưa có rule img nào cho .article-content** → đúng chỗ thêm.
- Theme đã có lazyload riêng cho ảnh THUMBNAIL list (`class=lazyload data-src`) — KHÔNG đụng.

## 3. Patch strategy (CSS-only)
- `.article-content img`: max-width 100% + height auto + display block (responsive, không méo).
- **Reserved space khử CLS**: `aspect-ratio:16/9` + `object-fit:contain` + nền nhạt. Ảnh blog Sintech chuẩn 16:9 (600×338) nên vừa khít; ảnh lệch tỉ lệ chỉ letterbox, **KHÔNG méo**.
- Ảnh ĐẦU TIÊN (hero/LCP) để `aspect-ratio:auto` — hiện đúng ngay, không letterbox hero.
- Ổn định `.table-responsive`/`div[overflow-x]` + iframe 16:9.
- **KHÔNG** JS, **KHÔNG** lazy-load (cần JS/attr — ngoài phạm vi CSS-only), **KHÔNG** đụng layout/global.

## 4. Feature flag
- Khối CSS bọc trong Liquid `IF settings.blog_image_perf_patch_enabled`. Mặc định OFF (setting chưa có = false → CSS không xuất).
- Bật: thêm setting `blog_image_perf_patch_enabled=true` (settings_schema/config). Tắt/rollback: set false hoặc revert backup.

## 5. Hạn chế trung thực (CSS-only)
- CSS không set được width/height THẬT từng ảnh (Haravan strip) → dùng aspect-ratio 16:9 giả định. Ảnh không-16:9 sẽ có nền letterbox (không méo, nhưng có khoảng trắng).
- Lazy-load + alt + fetchpriority-hero **không làm được bằng CSS** → vẫn cần JS/Liquid (gói riêng, ngoài P10 này).
- **After-metrics đo thật cần publish** (Haravan API ghi thẳng theme live, không staging) → preview này chỉ dự đoán.

## 6. QA (xem urls.csv): 5 bài P0 + 3 blog ảnh nhiều + 2 blog 0 ảnh + product/collection/home.
Mục tiêu: blog CLS↓, ảnh không méo/không mất, product/collection/home KHÔNG đổi, không lỗi console, TBT không tăng.

## 7. Exports
- BLOG_THEME_IMAGE_PERFORMANCE_PATCH_PLAN.md
- BLOG_THEME_IMAGE_PERFORMANCE_PATCH_PREVIEW.md
- blog_theme_image_perf_patch_urls.csv
- blog_theme_image_perf_before_after.csv
- blog_theme_image_perf_changed_files.txt
- blog_theme_image_perf_rollback.md

## Safety
no theme publish · no Haravan PUT · no upload · no commit/push/deploy · product/collection/home unaffected.
