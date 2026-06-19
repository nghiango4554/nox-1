# Title Review Policy (sau audit LibreCrawl) — 19/6/2026

## Nguyên tắc
**KHÔNG rewrite title hàng loạt.** Giữ title hiện tại. LibreCrawl báo "Title Too Long" 4681 lần — phần lớn là tên sản phẩm/blog dài tự nhiên, **không phải lỗi**.

## Tiêu chí ĐƯA VÀO QUEUE REVIEW (chỉ review, không auto sửa)
1. **Rendered title + suffix ` - Sintech` > 70 ký tự** — flag review (KHÔNG rewrite nếu dài do tên SP/spec).
2. **Title trùng nhiều trang** — ưu tiên cao (Shopify/Haravan auto-gen dễ trùng).
3. **Thiếu keyword chính** — cần đối chiếu thủ công.
4. **GSC query CTR thấp cần rescue** — cần data GSC (xử lý ở luồng GSC CTR Rescue riêng).

## Số liệu hiện tại (2615 trang indexable 200)
| Tiêu chí | Số | Ưu tiên |
|---|---|---|
| Title (+ ` - Sintech`) > 70 | **2126** | THẤP — đa số tên SP/blog dài by-design, **review-only, không rewrite** |
| Nhóm title trùng | **4 nhóm** | CAO — nên xử lý trước |
| Thiếu keyword chính | (thủ công) | trung bình |
| GSC CTR thấp | (luồng GSC riêng) | theo chiến dịch |

## Hành động
- File queue: [`title_review_queue.csv`](./title_review_queue.csv) — cột `reasons` phân biệt `over70_with_suffix` vs `duplicate_title`.
- **Ưu tiên:** xử 4 nhóm title trùng trước (lọc `reasons` chứa `duplicate_title`).
- Phần `over70_with_suffix` đơn thuần: **bỏ qua trừ khi** kèm thêm lý do khác (trùng / CTR thấp / thiếu keyword).
- Title dài do tên SP/spec: **chỉ flag, không auto rewrite** (đúng yêu cầu vợ 19/6).

## Đề xuất chỉnh crawler
Đổi rule "Title Too Long" của crawler nhà (`seo.py`) từ ngưỡng cứng 60 → **đánh giá theo `len(title + ' - Sintech') > 70`**, và hạ severity của product-title-dài xuống "review" thay vì "error", để report khỏi nhiễu.
