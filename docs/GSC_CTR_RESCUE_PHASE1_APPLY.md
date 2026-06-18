# GSC CTR RESCUE — PHASE 1 APPLY (đã thực thi live)

> Ngày 18/6/2026. Apply có giới hạn, backup trước PUT, verify sau PUT, không retry, không đổi handle/published.
> Backup: `marketing_hub/data/seo_phase1_backup/` (cs2_article_1002399773_pre.json · build_page_1003590100_body_pre.html).

## 1) CS2 — article 1002399773 (`/blogs/news/cau-hinh-choi-cs2-...`)

**Áp dụng:** `meta_description` (qua Open API article PUT → 201, verify API).
- **Meta CŨ:** `Muốn chơi Counter-Strike 2 mượt hơn? Tham khảo cấu hình CS2 theo FPS, màn hình và ngân sách để build PC hoặc chọn laptop. KHÁM PHÁ NGAY tại Sintech.` (148)
- **Meta MỚI ✅:** `CS2 cần cấu hình thế nào để chơi mượt? Xem gợi ý PC và laptop theo mức FPS, màn hình và ngân sách, kèm tư vấn nâng cấp máy. KHÁM PHÁ NGAY tại Sintech.` (150)

**SEO title (`<title>`): KHÔNG áp được — DEFER.**
- Định dùng `meta_title` = `Cấu hình chơi CS2 mượt: chọn PC & laptop theo FPS` (49) nhưng **Haravan Open API bỏ qua field `meta_title`** (PUT 201 nhưng giá trị vẫn `None`, `<title>` live không đổi).
- `<title>` hiện = `article.title`. Muốn đổi `<title>` phải sửa `article.title` — mà đó là **tiêu đề/H1 hiển thị của bài (body)** → **ngoài scope "không sửa body bài" phase này.**
- `article.title` (H1) giữ nguyên ✓, body không đụng ✓.

## 2) Build PC — page 1003590100 (`/pages/xay-dung-cau-hinh`)

**Áp dụng:** thêm **1 internal link** trong intro (body_html PUT → 200, verify API).
- Thêm: `Tham khảo nhanh cấu hình mẫu theo nhu cầu: <a href="/collections/pc-gaming-theo-gia">build PC Gaming theo giá</a>.`
- Đặt ngay sau đoạn intro đầu. body 195.869 → 196.198 ký tự. title/handle/published giữ nguyên ✓.

**SEO title/meta: KHÔNG áp được — DEFER.**
- Page object qua Open API **chỉ có 10 field, KHÔNG có field SEO nào** (title="Xây dựng cấu hình", meta_title/meta_description=None) nhưng `<title>` live = "Build PC Online: Chọn linh kiện..." → **SEO title/meta của page lưu ở admin Haravan, Open API không expose**. Admin pages API đang **502**.
- → Không thể backup/đối chiếu/ghi an toàn (ghi mù có thể NULL mất SEO title đang chạy). **Hoãn — cần sửa qua admin khi hết 502, hoặc kênh expose được field này.**

**H1: KHÔNG áp được — DEFER.**
- H1 live "Build PC Online – Xây Dựng Cấu Hình PC Theo Nhu Cầu" là **theme render** (body_html có 0 thẻ `<h1>`) → không sửa qua API.

## Tổng kết
| Mục | Trạng thái |
|---|---|
| CS2 meta description | ✅ ÁP (201) |
| CS2 SEO title | ⏸️ DEFER (Open API bỏ qua meta_title; cần sửa article.title=body) |
| Build internal link (1) | ✅ ÁP (200) |
| Build SEO title/meta | ⏸️ DEFER (Open API không expose field SEO; admin 502) |
| Build H1 | ⏸️ DEFER (theme render) |

**Đề xuất bước sau (chờ vợ duyệt):**
- CS2 title: cho phép sửa `article.title` → `Cấu hình chơi CS2 mượt: chọn PC & laptop theo FPS` (đổi cả H1+title) nếu vợ OK đổi tiêu đề hiển thị.
- Build SEO title/meta + H1: sửa trong **admin Haravan** (Online Store → Pages → SEO) khi hết 502 — dùng option ở `BUILD_PC_GROWTH_PLAN.md`.

**Safety:** backup trước PUT ✓ · verify sau PUT ✓ · không retry ✓ · không đổi handle/published ✓ · không sửa theme ✓ · không commit/push ✓ · không đụng Office/crack/bản quyền/FAQ schema ✓.
