# Marketing Hub — System Operations Map

Bản đồ vận hành toàn bộ Marketing Hub: trang, nút, form, endpoint, backend handler, DB, API ngoài, prompt/rule, script nền, Git/recovery. Dùng để một Claude agent mới hoặc người kỹ thuật mới mở lên là hiểu hệ thống.

- **Ngày scan:** 2026-06-06
- **Commit lúc scan:** `1d757e1` — feat(cwv): add reliable LCP history and diagnostics dashboard
- **Canonical repo:** `C:\Users\NGHIANGO\.openclaw\workspace\nox-1` · runtime `nox-1\marketing_hub` · GitHub `nghiango4554/nox-1` (master)
- **Nguồn sự thật:** **code thật thắng docs**. File này là Batch 0–5 của audit read-only (không sửa app).

## Cách mở
- **`MARKETING_HUB_MASTER.drawio`** (15 page): mở bằng **draw.io desktop** (đã cài) — double-click; hoặc web **https://app.diagrams.net/** → *Open Existing Diagram*; hoặc VS Code extension *Draw.io Integration*.
- Chưa có draw.io CLI trên máy → **không có preview SVG** tự sinh (mở app để xem/export).

## Xem trang nào trước
1. **Page 00 — Legend** (đọc trước để hiểu màu/shape/Node ID).
2. **Page 01 — Master overview** (toàn cảnh).
3. **Page 02 — Dashboard sitemap** (mọi trang).
4. **Page 03–14** đi sâu từng mảng (SEO, Content, Title/Meta, Haravan, FB, ALT, Jobs, Claude workflow, Prompts, Data/API, Git).

## Tra Node ID
Mỗi node quan trọng trong draw.io có **Node ID** (vd `SEO-CWV-SCAN-ALL`). ID này khớp cột **Node ID** trong `ROUTE_BUTTON_FORM_CATALOG.csv` → tra dòng đó để biết: endpoint, backend handler, file, service, DB read/write, external API, AI provider, prompt/rule, side effect, confirm, status, risk, confidence.
> Sơ đồ = nhìn nhanh · CSV = chi tiết. Cập nhật cùng Node ID để không lệch.

## Các file index (CSV)
| File | Nội dung | Số dòng |
|---|---|--:|
| `ROUTE_BUTTON_FORM_CATALOG.csv` | mỗi button/form/action → endpoint → backend → DB → API → prompt/rule | 71 |
| `PAGE_INVENTORY.csv` | mỗi page: route, template, #nút, #form, #AJAX, status | 40 |
| `DATA_TABLE_INDEX.csv` | bảng SQLite: purpose, read/write by, columns, risk | 21 |
| `EXTERNAL_INTEGRATION_INDEX.csv` | API ngoài: source file, credential source (tên), read/write, risk | 13 |
| `PROMPT_RULE_FILE_INDEX.csv` | prompt AI + rule file: file, feature, provider, validation | 17 |
| `SCRIPT_TASK_INDEX.csv` | script + Task Scheduler: trigger, side effect, status | 27 |

## Thống kê
- Route/endpoint: **158** (13 module) · Page: **40** · Button/Form action: **71** (raw UI ~155, gộp WYSIWYG)
- Prompt: **11** · Rule file: **6** · Script: **27** · Task Scheduler (Marketing Hub): **6** (Auto Commit DISABLED)
- DB table: **21** · External integration: **13**
- NEEDS_REVIEW (CSV): **14** + ~32 endpoint MEDIUM-confidence

## Cách cập nhật map khi thêm route/button
Xem `DRAWIO_UPDATE_RULES.md`. Tóm tắt: thêm route → thêm 1 dòng `ROUTE_BUTTON_FORM_CATALOG.csv` (gán Node ID mới) → thêm node cùng Node ID vào đúng page draw.io (đúng màu side-effect) → cập nhật `PAGE_INVENTORY.csv` nếu là trang mới.

## ⚠️ An toàn
- **KHÔNG** ghi secret/token/giá trị nhạy cảm vào bất kỳ file nào — chỉ ghi **tên nguồn** credential (vd `state/haravan_token.json`).
- Đây là tài liệu read-only; mọi đề xuất sửa nằm ở `SYSTEM_GAPS_AND_RECOMMENDATIONS.md` (KHÔNG tự refactor).
