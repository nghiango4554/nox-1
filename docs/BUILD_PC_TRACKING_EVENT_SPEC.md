# Build PC Tracking Event Spec — `/pages/xay-dung-cau-hinh`

> Theme Haravan storefront KHÔNG nằm trong repo → **selector chưa xác minh** (TODO khi có theme export). KHÔNG bịa selector, KHÔNG tự deploy theme live.
> Event phát từ **frontend (theme)** qua `dataLayer.push` → GTM → GA4. Build PC complete/export/add_to_cart nên mark key event sau.

## Event + trigger logic + params

| Event | Trigger logic (TODO xác minh selector) | Params an toàn | Noise control |
|---|---|---|---|
| `build_pc_start` | mở trang configurator / bấm "Bắt đầu" | `page_path` | fire 1 lần/session (guard flag) |
| `build_pc_add_component` | chọn 1 linh kiện vào cấu hình | `component_type` (cpu/main/ram/vga/...), `page_path` | debounce; KHÔNG gửi tên SP dài/PII |
| `build_pc_remove_component` | gỡ linh kiện | `component_type` | low priority (noisy) |
| `build_pc_complete` | cấu hình đủ phần bắt buộc / bấm "Hoàn tất" | `component_count`, `has_cpu`, `has_main` | fire 1 lần khi đạt complete |
| `build_pc_add_to_cart` | bấm "Thêm cấu hình vào giỏ" | `component_count`, `value`?, `currency` | fire trên click thật |
| `build_pc_export_quote` | bấm "Xuất báo giá" | `format`=pdf/excel | |
| `build_pc_export_image` | bấm "Xuất ảnh cấu hình" | `format`=png | |
| `build_pc_print` | bấm "In" | — | low priority |
| `build_pc_reset` | bấm "Làm lại" | — | low priority (noisy) |

## dataLayer helper (template — KHÔNG nhúng selector giả)
```js
// đặt trong theme sau khi xác minh nút/selector thật
function trackBuildPC(event, params){
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push(Object.assign({event: event}, params || {}));
}
// ví dụ (selector TODO): document.querySelector('SELECTOR_ADD_TO_CART')
//   .addEventListener('click', function(){ trackBuildPC('build_pc_add_to_cart', {component_count: N}); });
```
GTM: 1 Custom Event trigger cho mỗi `event` name → GA4 Event tag tương ứng.

## Vị trí hook dự kiến (TODO khi có theme)
Theme asset Build PC (liquid/js của trang `xay-dung-cau-hinh`). Cần audit: ID/class nút Thêm giỏ / Xuất báo giá / Hoàn tất, localStorage key lưu cấu hình.

## Test + rollback
- **Preview:** GTM Tag Assistant + GA4 DebugView, thao tác thật trên trang preview.
- **Rollback:** theme có backup trước khi sửa; revert asset về bản backup. KHÔNG sửa trực tiếp theme live khi chưa backup.

## Selector audit checklist (mở khi có theme export)
- [ ] Nút "Thêm vào giỏ" — selector?
- [ ] Nút "Xuất báo giá" — selector + format?
- [ ] Nút "Hoàn tất / Lưu cấu hình" — selector?
- [ ] localStorage key cấu hình?
- [ ] Có double-fire không (event lặp khi re-render)?
