# Tracking GTM Deployment Checklist — Sintech (manual)

> Tổng hợp các bước deploy thủ công cho tracking. GTM + theme Haravan ngoài repo → **KHÔNG tự publish/deploy**. Marketing Hub chỉ audit + dashboard.

## Thứ tự triển khai (theo priority)
1. **P0 — Contact clicks (GTM):** xem `TRACKING_GTM_CONTACT_EVENTS_MANIFEST.md`. phone/zalo/messenger/map click. Dễ, giá trị cao.
2. **P1 — Build PC funnel (theme):** xem `BUILD_PC_TRACKING_EVENT_SPEC.md`. Cần theme export để xác minh selector.
3. **P2 — Ecommerce verify (GTM Preview):** xem `ECOMMERCE_TRACKING_VERIFICATION.md`. Chỉ sửa khi xác minh bug.
4. **P3 — Housekeeping:** rà nguồn `send`, note Ads import.

## Pre-deploy
- [ ] Có quyền GTM container Sintech (Edit + Publish).
- [ ] Có Measurement ID GA4 (G-XXXX) từ GA4 Admin.
- [ ] (Build PC) có theme export / quyền sửa theme + backup.

## Per-event deploy
- [ ] Tạo trigger + tag theo manifest.
- [ ] GTM **Preview** → thao tác thật → tag fire đúng, param đúng, không PII.
- [ ] GA4 **DebugView** → event + param xuất hiện.
- [ ] Publish version (ghi chú rõ).
- [ ] Theo dõi 1-3 ngày: event vào `ga4_events_daily` → chạy lại **Tracking Audit** (`/seo/tracking`) → finding tự resolve khi detected.

## Post-deploy
- [ ] Mark key event (manual GA4 Admin): purchase, phone_click, zalo_click, generate_lead, build_pc_complete, build_pc_export_quote, build_pc_add_to_cart.
- [ ] Cập nhật `docs/TRACKING_LIVE_DEPLOY_APPROVAL.md` (cổng duyệt).

## Rollback chung
GTM Versions → publish version trước. Theme → revert asset từ backup. KHÔNG force deploy production khi preview chưa pass.
