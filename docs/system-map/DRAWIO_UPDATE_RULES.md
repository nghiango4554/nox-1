# Draw.io & Map Update Rules

Quy tắc giữ `MARKETING_HUB_MASTER.drawio` + các CSV **không lệch code** khi hệ thống thay đổi.

## Nguyên tắc gốc
- **Code thật thắng docs.** Khi sửa code → cập nhật map trong cùng PR/commit.
- **Sơ đồ = nhìn nhanh · CSV = chi tiết.** Liên kết qua **Node ID** (duy nhất, không đổi).
- **KHÔNG ghi secret/token/giá trị nhạy cảm.** Chỉ ghi *tên nguồn* credential.

## Quy ước Node ID
- Dạng: `AREA-PAGE-ACTION` viết HOA, gạch nối. Ví dụ: `SEO-CWV-SCAN-ALL`, `HV-SYNC-INCREMENTAL`, `CONTENT-PRODUCT-APPROVE`, `FB-SCHEDULE-PUBLISH`, `SYS-BACKUP-SECRETS`.
- Node ID **không tái sử dụng** sau khi xoá (giữ lịch sử). Đổi tên action → giữ Node ID, sửa label.

## Quy ước màu (kind → ý nghĩa)
| Màu | Kind | Ý nghĩa |
|---|---|---|
| Xanh dương | `ui` | Page / UI |
| Xanh lá | `read` | Read-only |
| Cam | `wlocal` | Write local DB |
| Đỏ | `wext` | Write external / publish / destructive |
| Tím | `ai`/`file` | AI provider / prompt / rule file |
| Xám | `script` | Script / worker / Task Scheduler |
| Vàng | `warn` | Warning / gap / NEEDS_REVIEW |
| Viền đen dày | `sot` | Source-of-truth |

Shape: **Cylinder** = DB table · **Cloud** = API ngoài · **Document** = prompt/rule file · **Actor** = Bạn/Claude/Telegram. Nét **liền** = flow chính · nét **đứt** = optional/fallback/recovery.

## Khi THÊM 1 route/button
1. Thêm 1 dòng vào `ROUTE_BUTTON_FORM_CATALOG.csv` (gán Node ID mới, điền đủ chain: endpoint → backend handler → file → DB R/W → API → prompt/rule → side effect → confirm → status → confidence).
2. Thêm node vào **đúng page** draw.io với **đúng màu side-effect** + Node ID y hệt CSV.
3. Nếu là **trang mới**: thêm dòng `PAGE_INVENTORY.csv` + node vào Page 02 (sitemap) + (nếu thuộc mảng) Page 04–14.
4. Nếu thêm **bảng DB**: cập nhật `DATA_TABLE_INDEX.csv` + Page 13 (cylinder).
5. Nếu thêm **API/integration/prompt/script**: cập nhật index CSV tương ứng (+ Page 09–13).

## Khi SỬA/XOÁ
- Sửa hành vi → cập nhật cột Side effect/Status/Confidence trong CSV + màu node.
- Xoá feature → đánh dấu node màu Vàng "DEPRECATED" 1 vòng release rồi mới gỡ (giữ Node ID trong CSV với status=removed).

## Cấu trúc 15 page (không nhét tất cả vào 1 canvas)
`00 Legend · 01 Master · 02 Sitemap · 03 Page→Button→Endpoint · 04 SEO · 05 Content · 06 Title/Meta · 07 Haravan · 08 Facebook · 09 ALT/Image · 10 Background jobs · 11 Claude workflow · 12 Prompts/Rules · 13 Data/API · 14 Git/Recovery`.
- Mỗi page có **DETAIL PANEL** (text box) tóm tắt + trỏ về CSV.
- Page 03 nếu phình to → tách `03A/03B/03C` theo nhóm trang.

## Regenerate (nếu cần dựng lại từ data)
- File draw.io + CSV hiện được sinh bằng script Python (read-only scan). Khi đổi nhiều, có thể chỉnh script generator rồi chạy lại — nhưng **mọi sửa tay trong draw.io desktop được ưu tiên giữ** (đừng overwrite mù).
- Sau khi sửa: mở `.drawio` trong draw.io để verify render + export PNG/SVG nếu cần chia sẻ.

## Checklist trước khi coi map là "đúng"
- [ ] XML mở được trong draw.io (well-formed).
- [ ] Số page = 15 (hoặc nhiều hơn nếu tách 03).
- [ ] Mọi Node ID trên sơ đồ có trong CSV và ngược lại (action chính).
- [ ] Không có secret/token/giá trị DB nhạy cảm.
- [ ] Không có path sai (chỉ `nox-1`, không phải repo cha `workspace\marketing_hub`).
