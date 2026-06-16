# BLOG PERFORMANCE DEEP AUDIT (read-only)

> Spec: `Desktop/Past.txt`. Không sửa website/theme/Haravan, không upload/commit/push. Lab Lighthouse vs Field CrUX tách rõ.

## Coverage
- Blogs audited: **230**
- Có traffic (clicks/sessions>0): **37**
- Đã rewrite AI live: **50**
- Có hero image: **171**
- Có ảnh inline: **171**

## Performance (mobile-lab, trừ khi ghi field)
- Mobile perf median: **45** | Desktop perf median: **78**
- Worst LCP: **43.7s** (Intel Gaudi 3 Chính Thức Có Mặt Trên IBM Cloud – H)
- Worst CLS: **1.111** (Trung tâm sửa laptop - máy tính uy tín, lấy ngay ở)
- High TTFB(>600ms): **0** | Ảnh-nặng (>1 ảnh >300KB): **68** | Broken images: **37**
- ⚠️ Field CrUX (người dùng thật) mobile LCP median ~1.68s = TỐT → lab thấp chủ yếu do throttle + theme global.

## Root causes
**A. Global template** (mọi blog, → THEME_CODE): unused JS (~1.57s), unused CSS, render-blocking FCP ~3.5s. Xem `blog_template_global_issues.md`.

**B. Article-specific** (tần suất issue):

| Issue | Số blog |
|---|---|
| CLS_LAYOUT_RISK | 229 |
| IMAGES_MISSING_LAZYLOAD | 94 |
| IMAGES_MISSING_DIMENSIONS | 89 |
| BODY_HTML_LEGACY | 86 |
| HERO_IMAGE_TOO_HEAVY | 43 |
| INLINE_IMAGES_TOO_HEAVY | 34 |
| IMAGES_BROKEN | 16 |
| HERO_IMAGE_WRONG_DIMENSION | 4 |
| NEED_MANUAL_REVIEW | 3 |
| DOM_TOO_LARGE | 3 |
| EMBED_HEAVY | 2 |

## Owner phân bổ

| Owner | Số blog |
|---|---|
| THEME_CODE | 109 |
| IMAGE | 69 |
| CONTENT | 49 |
| MANUAL_REVIEW | 3 |

## Priority tier

| Tier | Số blog | Nghĩa |
|---|---|---|
| P0 | 10 | traffic + nặng + sửa được → ưu tiên cao nhất |
| P1 | 27 | có traffic / lỗi nặng |
| P2 | 96 | lỗi vừa, traffic thấp |
| P3 | 97 | sạch / điểm ổn |

## Top 10 ưu tiên

| # | Title | Traffic(clk/ses) | mPerf | LCP | Issue | Tier | Owner |
|---|---|---|---|---|---|---|---|
| 1 | Cách tải và sử dụng Chat GPT cho máy tính  | 0/16 | 32 | 12.2s | BODY_HTML_LEGACY | P0 | CONTENT |
| 2 | Cấu hình chơi CS2 - Counter Strike 2 trên  | 8/9 | 51 | 4.4s | CLS_LAYOUT_RISK | P0 | THEME_CODE |
| 3 | PC Bị Giật Điện Có Sao Không: Nguyên Nhân  | 0/13 | 34 | 13.1s | HERO_IMAGE_TOO_HEAVY | P0 | IMAGE |
| 4 | PC nào chơi được GTA 5? Gợi ý build PC chơ | 2/3 | 32 | 15.2s | IMAGES_BROKEN | P0 | IMAGE |
| 5 | Thu mua máy tính cũ giá cao tận nơi tại Tp | 0/9 | 44 | 13.4s | BODY_HTML_LEGACY | P0 | CONTENT |
| 6 | Hướng dẫn 2 cách xóa chữ, logo, watermark  | 2/2 | 46 | 14.6s | INLINE_IMAGES_TOO_HEAVY | P1 | IMAGE |
| 7 | Cấu hình chơi ZZZ - Zenless Zone Zero Trên | 2/2 | 50 | 12.8s | IMAGES_BROKEN | P1 | IMAGE |
| 8 | Trung tâm sửa PC uy tín, lấy ngay ở Quận 7 | 3/4 | 52 | 13.5s | CLS_LAYOUT_RISK | P0 | THEME_CODE |
| 9 | Sửa Chữa Máy Tính Quận 7 - Dịch Vụ Uy Tín  | 2/2 | 51 | 14.5s | HERO_IMAGE_TOO_HEAVY | P1 | IMAGE |
| 10 | ASUS ra mắt bộ PC Hatsune Miku "full gear" | 2/2 | 41 | 10.8s | INLINE_IMAGES_TOO_HEAVY | P1 | IMAGE |

## Exports
- `blog_performance_deep_audit_all.csv` (toàn bộ)
- `blog_performance_priority_top30.csv`
- `blog_template_global_issues.md`
- `blog_content_image_quickwins.csv`
- `blog_content_team_fixlist.csv`
- `BLOG_TEMPLATE_CODE_HANDOFF.md`

## Safety
read-only · no website edits · no Haravan write · no upload · no commit · no push · no deploy
