# UI Refresh — AdminPro palette + Nalika components

> Local-only UI refresh. **KHÔNG commit / stage / push / deploy.** Additive (3 file CSS mới + 1 dòng link trong base.html). Rollback dễ.

## 1. Mục tiêu UI
Làm dashboard sáng – hiện đại bằng **palette warm của AdminPro Gradient Design** (cam/hồng/vàng/trắng + status) và **cách trình bày widget/card/table/badge của Nalika**, KHÔNG đổi layout/route/API/JS/DB.

## 2. Source tham chiếu đã đọc
- AdminPro: `C:\Users\NGHIANGO\Downloads\adminpro-ui-reference\adminpro\gradient-design\style.css` (clone ở **Downloads** theo yêu cầu trước đó, không phải Desktop).
- Nalika: `C:\Users\NGHIANGO\Downloads\nalika-ui-reference\nalika\` (`style.css`, `css/main.css`, `widgets.html`).

## 3. Palette lấy từ AdminPro (màu thật từ CSS nguồn)
- Gradient cam (chữ ký): `#ff9966 → #d75151`; warm `#ff9966 → #ff66cc`.
- Gradient hồng: `#ff6aa9 → #e73c7e`. Gradient vàng: `#ffd23f → #f5971f`.
- Gradient mint (success): `#1ab394 → #2dda7a`. Info: `#03a9f4 → #2a7de1`.
- Accent: cam `#ff7a45`, hồng `#e73c7e`, vàng `#f5971f`.
- Status: success `#16a87e`, warning `#e08a1e`, danger `#e2445c`, info `#1093d4`, neutral `#8a90a0`.
- Neutral nền/border: trắng, `#f4f6fa`, `#ecedf2`, `#e0e2ea`.

## 4. Component học từ Nalika
Tile KPI (icon + label + value), card radius 8–12px + shadow mềm, table wrapper header nền nhạt + hover hàng, badge bo tròn, progress bar, report/chart card nền trắng. Tạo lại bằng namespace `.mh-*` (KHÔNG bê CSS/HTML, KHÔNG lấy tông dark).

## 5. File mới (3)
- `marketing_hub/static/css/marketing-hub-theme.css` — token màu/gradient/shadow/radius/typography (`--mh-*`).
- `marketing_hub/static/css/marketing-hub-components.css` — thư viện `.mh-*` (kpi/report/chart/table/badge/progress/tabs/alert/state/data-health/skeleton/spinner) + **lớp ADOPT** refresh card/KPI/badge/bảng của dashboard hiện có (scoped theo container `#trk-app/#gsc-health/#tc-app/#ops-app/.g4-card`, dùng `!important` để thắng style inline).
- `marketing_hub/static/css/marketing-hub-responsive.css` — grid `.mh-*` + dashboard KPI 2 cột mobile, bảng scroll ngang.

## 6. File đã sửa (1)
- `marketing_hub/templates/base.html` — thêm 3 `<link>` CSS (sau `style.css`). KHÔNG đổi gì khác.

## 7. File backup
- `_backup/ui-refresh-20260607-205321/marketing_hub/templates/base.html` + `CHANGED_FILES.txt`.

## 8. Route đã kiểm tra (smoke test HTTP 200)
`/seo/ga4` · `/seo/gsc` · `/seo/tracking` · `/tasks` · `/ops/analytics` (và `/seo/ga4#seojoin` cùng trang `/seo/ga4`). 3 file CSS serve 200.

## 9. JS đã sửa
KHÔNG. Không đụng file JS nào (rollback an toàn).

## 10. Dependency mới
KHÔNG. Không thêm CDN/plugin/Bootstrap. Chỉ CSS thuần.

## 11–13. QA
- **compileall:** PASS (`python -m compileall marketing_hub`).
- **node --check:** N/A (không sửa JS).
- **secret scan:** PASS — chỉ match chữ "token" trong comment "THEME TOKENS"/"token mới", không có secret thật.

## 14. Screenshot
`C:\Users\NGHIANGO\Desktop\ui_refresh_screens\` — tracking/tasks/ga4/gsc/ops (desktop 1440) + tracking_mobile (390). KPI tile có accent warm xoay màu, badge status AdminPro, card shadow mềm, mobile KPI 2 cột.

## 15. Rủi ro còn lại
- Lớp ADOPT dùng `!important` để thắng style inline trong template → nếu sau này template đổi class container (vd `#trk-app`) thì rule không áp (chỉ mất thẩm mỹ, không lỗi chức năng).
- Nút primary trong dashboard giữ tông tím cũ (không đổi để tránh lệch với sidebar) — màu warm AdminPro dùng cho KPI/badge/accent, chưa áp lên button.

## 16. Việc chưa làm (chủ động skip — an toàn)
- Chưa chuyển các template dashboard sang dùng trực tiếp class `.mh-*` (đang refresh qua lớp ADOPT để khỏi sửa JS). Có thể migrate dần sau.
- Chưa đụng button/tab màu warm toàn cục.
- KHÔNG commit/stage/push/deploy; KHÔNG bật scheduler/Telegram; KHÔNG đổi API/DB/route.

## 17. Cách rollback
Xoá 3 file CSS mới + khôi phục base.html:
```powershell
Remove-Item "$env:USERPROFILE\.openclaw\workspace\nox-1\marketing_hub\static\css\marketing-hub-theme.css","$env:USERPROFILE\.openclaw\workspace\nox-1\marketing_hub\static\css\marketing-hub-components.css","$env:USERPROFILE\.openclaw\workspace\nox-1\marketing_hub\static\css\marketing-hub-responsive.css" -Force
Copy-Item -Recurse -Force "$env:USERPROFILE\.openclaw\workspace\nox-1\_backup\ui-refresh-20260607-205321\marketing_hub\templates\base.html" "$env:USERPROFILE\.openclaw\workspace\nox-1\marketing_hub\templates\base.html"
```
(Restart Flask sau rollback.)

## 18. File dự kiến stage SAU NÀY (nếu vợ yêu cầu commit)
- `marketing_hub/static/css/marketing-hub-theme.css`
- `marketing_hub/static/css/marketing-hub-components.css`
- `marketing_hub/static/css/marketing-hub-responsive.css`
- `marketing_hub/templates/base.html`
KHÔNG stage: `_backup/`, DB, token, config local, WIP cũ.
