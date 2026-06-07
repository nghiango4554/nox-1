# Tracking Live Deploy — Approval Gate

> **CỔNG DUYỆT.** Marketing Hub đã hoàn tất phần an toàn (audit + dashboard + task + ops). Các bước dưới **phải vợ/dev làm thủ công** trong GTM / Haravan / GA4 Admin. Claude **KHÔNG** tự publish GTM, **KHÔNG** tự deploy theme, **KHÔNG** tự mark key event.

## A. GTM manual deploy (contact clicks)
Tham chiếu: `TRACKING_GTM_CONTACT_EVENTS_MANIFEST.md`.
- [ ] Tạo trigger Click + GA4 Event tag: `phone_click`, `email_click`, `zalo_click`, `messenger_click`, `map_click`.
- [ ] Params: `link_type`, `placement`, `page_path`, `page_type` — KHÔNG PII.
- [ ] **GTM Preview** → click thử → tag fire đúng.
- [ ] **GA4 DebugView** → event + param xuất hiện.
- [ ] **Publish** version ("contact click events v1").
- [ ] Rollback: GTM Versions → publish bản trước.

## B. Haravan theme manual deploy (Build PC)
Tham chiếu: `BUILD_PC_TRACKING_EVENT_SPEC.md`.
- [ ] **Selector chưa audit** (theme không có trong repo) → export theme hoặc cấp quyền sửa theme.
- [ ] Backup asset Build PC trước khi sửa.
- [ ] Thêm `dataLayer.push` cho: build_pc_start/add_component/complete/add_to_cart/export_quote/export_image.
- [ ] GTM Custom Event trigger + GA4 Event tag tương ứng.
- [ ] Preview + DebugView trên trang `/pages/xay-dung-cau-hinh`.
- [ ] Rollback: revert asset từ backup.

## C. Ecommerce manual verify
Tham chiếu: `ECOMMERCE_TRACKING_VERIFICATION.md`.
- [ ] Verify nguồn phát + dataLayer payload + items + value + currency + transaction_id.
- [ ] Đặt 1 đơn test → GA4 DebugView xác nhận `purchase` + revenue.
- [ ] Rà `purchase` stale, `remove_from_cart > add_to_cart`, funnel gaps. KHÔNG sửa checkout live khi chưa xác minh + backup.
- [ ] Tránh double-fire (transaction_id dedup / trigger 1-lần).

## D. GA4 key event manual config (Admin → Events → Mark as key event)
Đề xuất mark **sau khi có data**:
- [ ] `purchase` (đã có data)
- [ ] `phone_click`, `zalo_click`, `generate_lead` (sau khi deploy GTM)
- [ ] `build_pc_complete`, `build_pc_export_quote`, `build_pc_add_to_cart` (sau khi deploy theme)
- [ ] Ads conversion import: giữ nguyên, KHÔNG rename.

## E. Sau deploy
- [ ] Theo dõi 1-3 ngày → event vào `ga4_events_daily`.
- [ ] Chạy lại **Tracking Audit** (`/seo/tracking`) → finding tự resolve khi detected.
- [ ] Bật scheduler Analytics Ops (`state/analytics_daily_config.json` → `enabled: true`) nếu muốn tự động hoá.

## 🚦 Trạng thái: CHỜ VỢ DUYỆT
Claude DỪNG ở đây. Không tự thực hiện A/B/C/D.
