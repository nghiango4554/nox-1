# GTM Contact Events Manifest — Sintech

> Đề xuất GTM (manual). GTM container KHÔNG nằm trong repo → **không tự publish**. Đây là spec để vợ/dev tạo tag trong GTM rồi tự preview + publish.
> Param an toàn: KHÔNG gửi PII, KHÔNG gửi số điện thoại đầy đủ, KHÔNG gửi nội dung chat/form.

## Built-in variables cần bật
Click URL, Click Element, Click Text, Page Path, Page Hostname.

## Trigger + Tag (mỗi event = 1 trigger Click + 1 GA4 Event tag)

| Event | Trigger (Click URL / Element) | Ghi chú |
|---|---|---|
| `phone_click` | Click URL **starts with** `tel:` | hotline |
| `email_click` | Click URL **starts with** `mailto:` | |
| `zalo_click` | Click URL **contains** `zalo.me` HOẶC `zaloapp.com` | xác minh pattern thật trên storefront |
| `messenger_click` | Click URL **contains** `m.me` HOẶC `messenger.com` | |
| `map_click` | Click URL **contains** `maps.google` HOẶC `google.com/maps` | |
| `chat_click` | **CHỈ làm khi xác minh selector/widget thật** (TODO) | widget chat live chat |

## GA4 Event tag config
- Tag type: **GA4 Event**, Measurement ID = G-XXXXXXXX (Sintech, lấy từ GA4 Admin — KHÔNG hard-code trong repo).
- Event name = tên cột trên.
- Event params (an toàn):
  - `link_type` = phone | email | zalo | messenger | map
  - `placement` = {{Click Element → closest section}} hoặc page region (nếu xác minh được)
  - `page_path` = {{Page Path}}
  - `page_type` = product | collection | blog | build_pc | homepage | other (Lookup Table theo Page Path)
- **KHÔNG** gửi: `{{Click URL}}` đầy đủ với số điện thoại, email, nội dung.

## Preview + Publish (manual, KHÔNG tự động)
1. GTM **Preview** (Tag Assistant) → click thử từng link → xác nhận tag fire đúng, param đúng.
2. GA4 **DebugView** → thấy event + param.
3. GTM **Submit/Publish** version với ghi chú "contact click events v1".
4. Rollback: GTM Versions → chọn version trước → Publish.

## Mark key event (sau khi có data, manual trong GA4 Admin)
`phone_click`, `zalo_click`, `messenger_click`, `generate_lead` → Admin → Events → toggle **Mark as key event**. KHÔNG mark qua API.
