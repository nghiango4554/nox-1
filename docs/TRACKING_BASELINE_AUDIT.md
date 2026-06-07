# Tracking Baseline Audit — Sintech GA4

> Read-only audit. KHÔNG sửa theme/GTM, KHÔNG gọi write API, KHÔNG kết luận bug chắc chắn.
> Nguồn: `ga4_events_daily`, `ga4_ecommerce_daily` (SQLite) + endpoint GA4. Cửa sổ: 28 ngày gần nhất.

## 1. Top events (28 ngày)
| Event | Count | Users | Key | Last seen | Nhóm | Trạng thái |
|---|---|---|---|---|---|---|
| page_view | 47.840 | 14.536 | 0 | gần nhất | automatic | OK |
| user_engagement | 33.882 | 7.568 | 0 | gần nhất | enhanced | OK |
| session_start | 16.473 | 14.532 | 0 | gần nhất | automatic | OK |
| first_visit | 13.161 | 12.888 | 0 | gần nhất | automatic | OK |
| **send** | 9.992 | 4.072 | 0 | gần nhất | **custom_unknown** | nguồn chưa xác minh |
| view_item | 9.124 | 4.055 | 0 | gần nhất | ecommerce | OK |
| scroll | 8.375 | 3.517 | 0 | gần nhất | enhanced | OK |
| ads_conversion_Giỏ_hàng | 3.716 | 796 | 3.716 | gần nhất | ecommerce (Ads import) | key thật |
| click | 1.653 | 539 | 0 | gần nhất | enhanced | OK |
| form_start | 1.387 | 606 | 0 | gần nhất | lead | có |
| view_search_results | 1.117 | 442 | 0 | gần nhất | engagement | OK |
| form_submit | 519 | 272 | 0 | gần nhất | lead (generic) | chưa rõ form nào |
| remove_from_cart | 339 | 49 | 0 | gần nhất | ecommerce | ⚠ |
| add_to_cart | 301 | 150 | 0 | gần nhất | ecommerce | OK |
| ads_conversion_Thanh_toán | 218 | 92 | 218 | gần nhất | ecommerce (Ads) | key thật |
| begin_checkout | 76 | 72 | 0 | gần nhất | ecommerce | thấp |
| purchase | 7 | 7 | 7 | ~10 ngày trước | ecommerce | ⚠ stale |

Key event native chỉ `purchase` (7); phần lớn "conversion" đến từ **Google Ads import** (KHÔNG tự rename).

## 2. Ecommerce gaps
Có: view_item, add_to_cart, remove_from_cart, begin_checkout, purchase.
**Thiếu/chưa thấy:** `view_cart`, `add_payment_info`, `add_shipping_info`, `refund`, `view_item_list`, `select_item`.
Items 28d: viewed 9.124 / added 2.286 / checked_out 155 / purchased 9 · ecommerce_purchases 7 · revenue ~489k · `checkouts` chưa populate đầy đủ.

## 3. Lead / contact gaps (LỚN NHẤT)
**Chưa thấy:** generate_lead, phone_click, zalo_click, messenger_click, chat_click, email_click, map_click, contact.
Chỉ có `form_submit` generic. Shop bán qua inbox/điện thoại nhưng 0 tracking click liên hệ.

## 4. Build PC gaps (CAO)
Trang `/pages/xay-dung-cau-hinh` (top organic) chưa thấy: build_pc_start/add_component/remove_component/complete/add_to_cart/export_quote/export_image/print/reset. 0 funnel tracking.

## 5. Data-quality flags (cần kiểm tra — CHƯA kết luận bug)
- `purchase` stale ~10 ngày → needs_review.
- `remove_from_cart` (339) > `add_to_cart` (301) event count → needs_review.
- Funnel rớt mạnh add_to_cart → begin_checkout → purchase; thiếu bước giữa.
- `send` (9.992, cả realtime) → unknown_source_needs_review.
- Key event native quá ít (chỉ purchase) — phụ thuộc Ads import.

## 6. Giới hạn truy cập
- GTM container + theme Haravan storefront **không nằm trong repo** → audit selector Build PC chi tiết chưa thể xác minh.
- KHÔNG tự publish GTM, KHÔNG tự deploy theme live, KHÔNG tự mark key event.

## 7. Severity vs Implementation priority (tách rõ)
- Contact gap: implementation P0/P1, incident severity P2.
- Build PC gap: implementation P1, incident severity P2.
- `send` unknown, ecommerce funnel gap, purchase stale: P2.
- Ads import note, naming, docs: P3.
- P0 incident chỉ dành outage/credential-fail; P1 cho anomaly nghiêm trọng/pipeline fail.
