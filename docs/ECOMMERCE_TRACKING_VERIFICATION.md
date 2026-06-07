# Ecommerce Tracking Verification Checklist — Sintech

> KHÔNG tự sửa checkout live khi chưa xác minh bug. Đây là checklist verify thủ công (GTM Preview + GA4 DebugView). Mọi "nghi ngờ" giữ trạng thái **cần kiểm tra**, KHÔNG kết luận bug.

## Trạng thái hiện tại (baseline 28 ngày)
| Event | Có data | Count 28d | Ghi chú |
|---|---|---|---|
| view_item | ✓ | 9.124 | OK |
| add_to_cart | ✓ | 301 | OK (item-level added 2.286) |
| remove_from_cart | ✓ | 339 | ⚠ > add_to_cart (event count) — cần kiểm tra |
| view_cart | ✗ | — | thiếu |
| begin_checkout | ✓ | 76 | thấp |
| add_payment_info | ✗ | — | thiếu |
| add_shipping_info | ✗ | — | thiếu |
| purchase | ✓ | 7 | ⚠ last seen ~10 ngày — cần rà |
| refund | ✗ | — | thiếu (ít ưu tiên) |

## Verify từng event (GTM Preview + GA4 DebugView)
Cho mỗi event kiểm:
- [ ] **Event source** — Haravan native dataLayer hay GTM tag? (xác định nguồn phát thật)
- [ ] **dataLayer payload** — có `ecommerce` object đúng chuẩn GA4?
- [ ] **items array** — item_id, item_name, price, quantity?
- [ ] **value** + **currency** = VND?
- [ ] **transaction_id** (purchase) — có và unique?
- [ ] **double-fire** — event có lặp khi reload/back không?
- [ ] **last seen** khớp thực tế đặt hàng?

## Các điểm cần rà (CHƯA kết luận bug)
1. **purchase stale ~10 ngày:** kiểm có đơn thật trong 10 ngày? Nếu có đơn mà không có event → nghi tracking gap ở trang thank-you. Verify GA4 DebugView khi đặt 1 đơn test.
2. **remove_from_cart > add_to_cart (event count):** kiểm có double-fire remove, hay add_to_cart bị thiếu fire ở 1 số layout.
3. **Funnel thiếu view_cart/add_payment_info/add_shipping_info:** Haravan checkout có thể không phát các bước này → cân nhắc bổ sung qua GTM hoặc theme checkout (nếu Haravan cho phép).

## Nếu xác minh có bug
- Tạo finding/task P1 (nếu purchase/revenue mất) hoặc P2 (funnel gap).
- Sửa nguồn phát (theme/GTM), KHÔNG sửa checkout live khi chưa preview + backup.
- Tránh double-fire: dùng trigger 1-lần hoặc transaction_id dedup.

## Rollback
GTM revert version / theme revert asset từ backup. KHÔNG đụng checkout production khi chưa có bản backup + preview pass.
