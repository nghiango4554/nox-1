# BLOG PERFORMANCE — P0 ACTION PLAN (read-only)

> Tiếp nối `BLOG_PERFORMANCE_DEEP_AUDIT.md`. 10 bài P0 (traffic + nặng). KHÔNG sửa web/theme/Haravan, không upload/commit.

## Hero image target (chuẩn blog Sintech)
Hero blog chuẩn: ảnh ngang 1200×675 (hoặc 1200×628), WebP nếu workflow hỗ trợ, target <=180KB (cảnh báo >300KB, sửa GẤP >700KB), set width/height, KHÔNG lazy-load hero (ảnh LCP), cân nhắc fetchpriority=high. Ngoại lệ: ảnh cần chất lượng cao (sơ đồ/screenshot chi tiết) ghi rõ.

## quickwin_score = (traffic+1) × fix_ease × (1+severity/100)
- fix_ease: S=1.5 · M=1.0 · L=0.6 · traffic = clicks×3 + sessions×2 + impr×0.02
- Xếp lại nội bộ P0 theo: traffic thật → dễ sửa → severity → impact nhanh.

## Bảng P0 (đã re-rank)

| P0# | Title | Traffic | mPerf | LCP | CLS | Hero | Broken | Owner | Effort | QW | Impact |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Cấu hình chơi CS2 - Counter Strike | 8c/9s | 51 | 4.4s | 0.47 | - | 0 | THEME_CODE | S | 170.0 | Giảm CLS (chủ yếu chờ theme  |
| 2 | Cách tải và sử dụng Chat GPT cho m | 0c/16s | 32 | 12.2s | 0.46 | 160KB | 0 | CONTENT | M | 72.4 | Trang nhẹ + sạch HTML, ổn đị |
| 3 | PC Bị Giật Điện Có Sao Không: Nguy | 0c/13s | 34 | 13.1s | 0.26 | 360KB | 0 | MIXED | M | 61.5 | Giảm byte ảnh/LCP rõ rệt |
| 4 | Trung tâm sửa PC uy tín, lấy ngay  | 3c/4s | 52 | 13.5s | 0.13 | - | 0 | CONTENT | S | 57.5 | Giảm CLS (chủ yếu chờ theme  |
| 5 | Top 10 Thương Hiệu Linh Kiện Máy T | 3c/2s | 46 | 14.7s | 0.19 | - | 0 | CONTENT | S | 48.8 | Giảm CLS (chủ yếu chờ theme  |
| 6 | Thu mua máy tính cũ giá cao tận nơ | 0c/9s | 44 | 13.4s | 0.47 | - | 0 | CONTENT | M | 40.4 | Trang nhẹ + sạch HTML, ổn đị |
| 7 | PC nào chơi được GTA 5? Gợi ý buil | 2c/3s | 32 | 15.2s | 0.77 | 55KB | 1 | MIXED | M | 37.7 | Hết ảnh vỡ + giảm LCP — impa |
| 8 | Bật mí cách gắn quạt tản nhiệt cho | 0c/3s | 39 | 12.6s | 0.77 | 72KB | 0 | THEME_CODE | S | 24.5 | Giảm CLS (chủ yếu chờ theme  |
| 9 | Cách khắc phục lỗi Command Prompt  | 0c/3s | 34 | 8.7s | 0.79 | - | 0 | THEME_CODE | S | 23.1 | Giảm CLS (chủ yếu chờ theme  |
| 10 | Top phần mềm test VGA (card màn hì | 0c/3s | 38 | 12.6s | 0.91 | 194KB | 0 | MIXED | L | 11.6 | Giảm byte ảnh/LCP rõ rệt |

## Chi tiết từng bài

### P0#1 — Cấu hình chơi CS2 - Counter Strike 2 trên PC, Laptop
- article_id `1002399773` · https://sintech.vn/blogs/news/cau-hinh-choi-cs2-counter-strike-2-tren-pc-laptop
- rewritten_ai_live: **True** · traffic: 8 clicks / 1095 impr / 9 ses (28d)
- mobile perf **51** · LCP 4.4s · CLS 0.472 · TTFB NA
- ảnh: 0 (broken 0, nặng 0, external 0) · hero 
- root cause: **CLS_LAYOUT_RISK** / - → owner **THEME_CODE**, effort **S**
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Giảm CLS (chủ yếu chờ theme set kích thước ảnh)

### P0#2 — Cách tải và sử dụng Chat GPT cho máy tính Windows & macOS (Cập nhật 2025)
- article_id `1002794878` · https://sintech.vn/blogs/huong-dan/cach-tai-va-su-dung-chat-gpt-cho-may-tinh-windows-macos-cap-nhat-20
- rewritten_ai_live: **False** · traffic: 0 clicks / 18 impr / 16 ses (28d)
- mobile perf **32** · LCP 12.2s · CLS 0.456 · TTFB NA
- ảnh: 5 (broken 0, nặng 0, external 0) · hero https://cdn.hstatic.net/200000860097/file/19_975ae3dd7b8a46f481c5ccbc8
- root cause: **BODY_HTML_LEGACY** / IMAGES_MISSING_DIMENSIONS → owner **CONTENT**, effort **M**
- **CONTENT:**
  - clean HTML legacy: Gỡ inline-style/font/mso, dựng lại block sạch; GIỮ internal link + URL/title/handle
  - table responsive: 1 bảng — wrap overflow-x cho mobile
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Trang nhẹ + sạch HTML, ổn định render

### P0#3 — PC Bị Giật Điện Có Sao Không: Nguyên Nhân & Cách Khắc Phục Tại Nhà
- article_id `1002753568` · https://sintech.vn/blogs/huong-dan/pc-bi-giat-dien-co-sao-khong-nguyen-nhan-cach-khac-phuc-tai-nha
- rewritten_ai_live: **False** · traffic: 0 clicks / 31 impr / 13 ses (28d)
- mobile perf **34** · LCP 13.1s · CLS 0.256 · TTFB NA
- ảnh: 5 (broken 0, nặng 1, external 0) · hero https://file.hstatic.net/200000860097/file/pc_bi_giat_dien_b585afa8742
- root cause: **HERO_IMAGE_TOO_HEAVY** / BODY_HTML_LEGACY → owner **MIXED**, effort **M**
- **CONTENT:**
  - clean HTML legacy: Gỡ inline-style/font/mso, dựng lại block sạch; GIỮ internal link + URL/title/handle
  - table responsive: 1 bảng — wrap overflow-x cho mobile
- **IMAGE:**
  - [hero #0] (heavy) → resize hero → 1200×675 ≤180KB + set width/height + KHÔNG lazy (ảnh LCP) + cân nhắc fetchpriority=high
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Giảm byte ảnh/LCP rõ rệt

### P0#4 — Trung tâm sửa PC uy tín, lấy ngay ở Quận 7
- article_id `1002398567` · https://sintech.vn/blogs/news/trung-tam-sua-pc-uy-tin-lay-ngay-o-quan-7
- rewritten_ai_live: **False** · traffic: 3 clicks / 55 impr / 4 ses (28d)
- mobile perf **52** · LCP 13.5s · CLS 0.126 · TTFB NA
- ảnh: 0 (broken 0, nặng 0, external 0) · hero 
- root cause: **CLS_LAYOUT_RISK** / - → owner **CONTENT**, effort **S**
- **CONTENT:**
  - table responsive: 4 bảng — wrap overflow-x cho mobile
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Giảm CLS (chủ yếu chờ theme set kích thước ảnh)

### P0#5 — Top 10 Thương Hiệu Linh Kiện Máy Tính Được Yêu Thích Nhất Tại Việt Nam: Game thủ, dân văn phòng, ai cũng mê!
- article_id `1002717797` · https://sintech.vn/blogs/news/top-10-thuong-hieu-linh-kien-may-tinh-duoc-yeu-thich-nhat-tai-viet-nam
- rewritten_ai_live: **False** · traffic: 3 clicks / 73 impr / 2 ses (28d)
- mobile perf **46** · LCP 14.7s · CLS 0.189 · TTFB NA
- ảnh: 0 (broken 0, nặng 0, external 0) · hero 
- root cause: **NEED_MANUAL_REVIEW** / CLS_LAYOUT_RISK → owner **CONTENT**, effort **S**
- **CONTENT:**
  - review tay: Không lấy được body từ DB (bài reverse_copy_defense) — kiểm tra trực tiếp editor
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Giảm CLS (chủ yếu chờ theme set kích thước ảnh)

### P0#6 — Thu mua máy tính cũ giá cao tận nơi tại Tphcm
- article_id `1002404456` · https://sintech.vn/blogs/news/thu-mua-may-tinh-cu-gia-cao-tan-noi-tai-tphcm
- rewritten_ai_live: **False** · traffic: 0 clicks / 19 impr / 9 ses (28d)
- mobile perf **44** · LCP 13.4s · CLS 0.468 · TTFB NA
- ảnh: 0 (broken 0, nặng 0, external 0) · hero 
- root cause: **BODY_HTML_LEGACY** / CLS_LAYOUT_RISK → owner **CONTENT**, effort **M**
- **CONTENT:**
  - clean HTML legacy: Gỡ inline-style/font/mso, dựng lại block sạch; GIỮ internal link + URL/title/handle
  - table responsive: 7 bảng — wrap overflow-x cho mobile
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Trang nhẹ + sạch HTML, ổn định render

### P0#7 — PC nào chơi được GTA 5? Gợi ý build PC chơi GTA V mượt mà, giá tốt
- article_id `1002728313` · https://sintech.vn/blogs/huong-dan/pc-nao-choi-duoc-gta-5-goi-y-build-pc-choi-gta-v-muot-ma-gia-tot
- rewritten_ai_live: **False** · traffic: 2 clicks / 149 impr / 3 ses (28d)
- mobile perf **32** · LCP 15.2s · CLS 0.765 · TTFB NA
- ảnh: 5 (broken 1, nặng 0, external 5) · hero https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/324
- root cause: **IMAGES_BROKEN** / BODY_HTML_LEGACY → owner **MIXED**, effort **M**
- **CONTENT:**
  - clean HTML legacy: Gỡ inline-style/font/mso, dựng lại block sạch; GIỮ internal link + URL/title/handle
  - table responsive: 4 bảng — wrap overflow-x cho mobile
- **IMAGE:**
  - [inline #3] (broken) → THAY ảnh chết (re-host/đổi ảnh) + ảnh external → cân nhắc re-host nội bộ
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Hết ảnh vỡ + giảm LCP — impact nhanh, dễ

### P0#8 — Bật mí cách gắn quạt tản nhiệt cho PC trong 5 bước đơn giản, nhanh chóng
- article_id `1002420376` · https://sintech.vn/blogs/news/bat-mi-cach-gan-quat-tan-nhiet-cho-pc-trong-5-buoc-don-gian-nhanh-cho
- rewritten_ai_live: **False** · traffic: 0 clicks / 37 impr / 3 ses (28d)
- mobile perf **39** · LCP 12.6s · CLS 0.767 · TTFB NA
- ảnh: 5 (broken 0, nặng 0, external 5) · hero https://bizweb.dktcdn.net/100/329/122/files/quat-tan-nhiet-giup-giam-n
- root cause: **IMAGES_MISSING_DIMENSIONS** / IMAGES_MISSING_LAZYLOAD → owner **THEME_CODE**, effort **S**
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Giảm CLS (chủ yếu chờ theme set kích thước ảnh)

### P0#9 — Cách khắc phục lỗi Command Prompt tự mở trên Windows
- article_id `1002414345` · https://sintech.vn/blogs/news/cach-khac-phuc-loi-command-prompt-tu-mo-tren-windows
- rewritten_ai_live: **True** · traffic: 0 clicks / 27 impr / 3 ses (28d)
- mobile perf **34** · LCP 8.7s · CLS 0.792 · TTFB NA
- ảnh: 0 (broken 0, nặng 0, external 0) · hero 
- root cause: **CLS_LAYOUT_RISK** / - → owner **THEME_CODE**, effort **S**
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Giảm CLS (chủ yếu chờ theme set kích thước ảnh)

### P0#10 — Top phần mềm test VGA (card màn hình) hiệu quả 2025 Kiểm tra hiệu năng & ổn định GPU
- article_id `1002792621` · https://sintech.vn/blogs/huong-dan/top-phan-mem-test-vga-card-man-hinh-hieu-qua-2025-giup-kiem-tra-hi
- rewritten_ai_live: **False** · traffic: 0 clicks / 85 impr / 3 ses (28d)
- mobile perf **38** · LCP 12.6s · CLS 0.911 · TTFB NA
- ảnh: 11 (broken 0, nặng 2, external 0) · hero https://cdn.hstatic.net/200000860097/file/13_77529618785240b8baf73c169
- root cause: **INLINE_IMAGES_TOO_HEAVY** / BODY_HTML_LEGACY → owner **MIXED**, effort **L**
- **CONTENT:**
  - clean HTML legacy: Gỡ inline-style/font/mso, dựng lại block sạch; GIỮ internal link + URL/title/handle
  - giảm DOM: DOM ~1589 node — cắt markup thừa
  - table responsive: 1 bảng — wrap overflow-x cho mobile
- **IMAGE:**
  - [inline #1] (heavy) → nén/resize ≤150KB + thêm width/height + thêm loading=lazy
  - [inline #3] (heavy) → nén/resize ≤150KB + thêm width/height + thêm loading=lazy
- **THEME_CODE (chỉ tham chiếu, không sửa):** width/height/aspect-ratio mặc định cho ảnh blog (BLOG_TEMPLATE_CODE_HANDOFF #5) · unused JS/CSS + render-block toàn site (BLOG_TEMPLATE_CODE_HANDOFF #1,#2)
- Expected impact: Giảm byte ảnh/LCP rõ rệt

## Top 5 quick wins (dễ + đáng làm trước)

| P0# | Article | Issue | Action | Owner | Effort | Impact |
|---|---|---|---|---|---|---|
| 2 | Cách tải và sử dụng Chat GPT c | BODY_HTML_LEGACY | clean HTML legacy; table responsive | CONTENT | M | Trang nhẹ + sạch HTML, ổ |
| 3 | PC Bị Giật Điện Có Sao Không:  | HERO_IMAGE_TOO_HEAVY | resize 1 ảnh nặng; clean HTML legacy; ta | MIXED | M | Giảm byte ảnh/LCP rõ rệt |
| 4 | Trung tâm sửa PC uy tín, lấy n | CLS_LAYOUT_RISK | table responsive | CONTENT | S | Giảm CLS (chủ yếu chờ th |
| 6 | Thu mua máy tính cũ giá cao tậ | BODY_HTML_LEGACY | clean HTML legacy; table responsive | CONTENT | M | Trang nhẹ + sạch HTML, ổ |
| 7 | PC nào chơi được GTA 5? Gợi ý  | IMAGES_BROKEN | thay 1 ảnh chết; clean HTML legacy; tabl | MIXED | M | Hết ảnh vỡ + giảm LCP —  |

## Exports
- BLOG_PERFORMANCE_P0_ACTION_PLAN.md
- blog_performance_p0_action_plan.csv
- blog_performance_p0_image_tasks.csv
- blog_performance_p0_content_tasks.csv

## Safety
read-only · no website edits · no Haravan write · no upload · no theme edits · no commit · no push · no deploy
