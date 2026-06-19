# Sintech Hub — Export thuần HTML / CSS / JS (offline, no framework)

Bộ giao diện 4 trang cùng 1 design system, **không React/Tailwind**, dịch thẳng sang Flask + Jinja.

## Cấu trúc
```
export2/
├── index.html              → redirect sang dashboard.html
├── dashboard.html          KHUÔN 0 — Dashboard tổng quan
├── title-meta.html         KHUÔN 1 — Danh sách + bộ lọc (Title & Meta)
├── editor.html             KHUÔN 2 — Editor WYSIWYG (Collection Content)
├── audit.html              KHUÔN 3 — Audit + Job pipeline (SEO)
│
├── sintech-hub.css         ★ 1 FILE: toàn bộ token + component (có MỤC LỤC ở đầu)
├── sintech-app.js          Tương tác (toggle KPI · filter · collapse · chat · nav)
├── fonts.css               @font-face self-host (xem hướng dẫn bên trong)
│
├── lib/
│   ├── sintech-icons.js    Icon Lucide inline (self-host, KHÔNG CDN) — phần 1
│   ├── sintech-icons-2.js  — phần 2
│   └── sintech-icons-3.js  — phần 3
│
├── data/
│   ├── sintech-data.js     Dữ liệu mẫu Dashboard (nav, KPI, chart, bảng…)
│   └── sintech-pages-data.js  Dữ liệu mẫu 3 trang còn lại
│
└── fonts/                  (đặt .woff2 vào đây — xem fonts.css)
```

## Markup TĨNH — port sang Jinja
- Mỗi file `.html` là **markup tĩnh hoàn chỉnh** (không render bằng JS). Mở trực tiếp là thấy đủ.
- Icon dùng placeholder `<i class="ic" data-icon="search"></i>` → `sintech-app.js` tự thay bằng SVG inline lúc load. Trong Jinja cứ giữ nguyên cú pháp này.
- Để chuyển sang template Jinja: cắt phần `<aside class="sidebar">`, `<header class="topbar">`, `<button class="nox-fab">` thành các `{% include %}` dùng chung; phần `.content` là block riêng mỗi trang.
- Dữ liệu hiện hard-code trong HTML (lấy từ `data/`); thay bằng vòng lặp Jinja `{% for ... %}`.

## CSS — map vào marketing-hub-theme.css
`sintech-hub.css` có **MỤC LỤC 14 mục** ở đầu file. Mỗi component có banner riêng:
TOKENS · TONES · LAYOUT · SIDEBAR · TOPBAR+BUTTONS · KPI CARDS · CHART+HEALTH ·
TABLE · QUICK ACTIONS · CHAT · CHROME · LIST+FILTER · EDITOR · AUDIT+PIPELINE.
→ Copy khối `:root` (tokens) sang `marketing-hub-theme.css`; bê từng component theo banner.
Tuỳ biến nhanh: sửa biến `--accent-* / --header-* / --sb-ink` ngay ở thẻ `<html>` của mỗi trang.

## Tương tác (sintech-app.js, vanilla)
Đổi kiểu thẻ KPI (Gradient/Dịu/Đơn sắc) · lọc bảng theo trạng thái · gập nhóm sidebar ·
chọn thẻ tier · đóng alert · mở/đóng chat Nox-1 · điều hướng giữa 4 trang.

## Offline 100%
- **Icon:** đã self-host inline (lib/) — không gọi unpkg.
- **Font:** đặt 6 file `.woff2` vào `fonts/` theo hướng dẫn trong `fonts.css`
  (link google-webfonts-helper có sẵn). Chưa có → tự fallback system-ui, trang vẫn đẹp.

## Mở thử
Mở `index.html` (hoặc `dashboard.html`) bằng trình duyệt — chạy ngay, không cần server.
```
