# SEO Dashboard `/seo` — UI/UX Redesign Backlog

> Vợ giao 30/5/2026 14:10 sau khi xem Job Center mới (color-coded 5 section framing). Muốn áp pattern đó cho trang `/seo` (SEO dashboard chính). Vợ chốt 5 phase, KHỞI ĐỘNG SAU.

---

## 📌 Context

- Trang `/seo` hiện 754 dòng template (`marketing_hub/templates/seo.html`).
- Route `app.py:901 seo_dashboard()` — pass stats/state/pages/top_issues/snapshots/filters.
- Trang phức tạp: 5-6 section (KPI / Pipeline progress / Top issues / Filter bar / URL list / Snapshots history).
- Hiện tại: tất cả dùng `.card` base + style inline → giao diện đều màu trắng, **khó phân biệt section** (giống feedback vợ về Job Center cũ).

## 🎨 Approach — Apply pattern Job Center

Áp dụng đúng pattern đã làm cho `/jobs` ngày 30/5 13:55-14:08:
- Mỗi section `<section class="seo-section">` với CSS variable `--frame-bg` / `--frame-border` / `--frame-accent`.
- Title section có accent bar 4px left (color theo section).
- Color palette pastel light-mode: green/blue/red/amber/violet/slate/indigo với cặp `--xxx-bg` + `--xxx-border`.
- Common base: padding 18px 20px, border-radius 16px, border 1px, soft shadow.

Tham khảo code mẫu: `marketing_hub/templates/jobs_center.html` CSS từ `:root` tới `.jc-section`.

---

## 🗂️ Phase chia

### ⏸ Phase S1 — Section framing toàn page (~30', CHƯA LÀM)

**Scope:** Bọc mỗi section trong `<section class="seo-section">` với background pastel distinct.

5 section frames:
1. **KPI compact** (line 49-79): gradient indigo-50→violet-50, border indigo-200, accent indigo.
2. **Pipeline progress** (line 86-139): gradient emerald-50→slate-50, border emerald-300 — đẹp khi đang chạy, idle vẫn ok.
3. **Top issues** (line 142+): gradient amber-50→slate-50, border amber-300 (cảnh báo theme).
4. **Filter + URL list** (sau top issues): white container neutral, border slate-200.
5. **Snapshots history** (gần cuối): gradient violet-50→slate-50, border violet-200.

Mỗi section thêm `.seo-section-title` với accent bar 4px left color theo section.

**Test:** page render đẹp, không còn "1 màu trắng từ đầu tới cuối". Mỗi vùng có khung rõ.

### ⏸ Phase S2 — KPI cards modern (~30', CHƯA LÀM)

**Scope:**
- Animated count-up cho 4 number (Total/Avg/Good/OK/Bad).
- Hover lift + shadow tăng theo accent color.
- Big number 32px font-weight 800 + accent color theo band (good=green, ok=amber, bad=red).
- Distribution mini bar chart inline (good/ok/bad %).
- By_type pill modern hơn (icon trong colored circle 24px).

### ⏸ Phase S3 — Pipeline progress redesign (~30', CHƯA LÀM)

**Scope:**
- Dual phase visual: 2 lane card song song (Phase 1 Crawl + Phase 2 Link check).
- Mỗi phase card có border color theo state (running=emerald, done=blue, idle=slate).
- Progress bar gradient + shimmer animation khi running (clone pattern Job Center `.jc-bar`).
- ETA tính từ tốc độ thực tế (req/s × URL còn lại).
- Realtime stats: rate, ETA, success/fail counter.

### ⏸ Phase S4 — Top issues redesign (~45', CHƯA LÀM)

**Scope:**
- Priority badge per issue: Critical (≥500 URL ảnh hưởng), High (≥100), Medium (<100).
- Color-coded background: critical=red-50, high=amber-50, medium=blue-50.
- Số URL bị ảnh hưởng prominent (big number).
- Click chip → filter URL list mượt (no page reload nếu khả thi qua JS).
- Fix suggestion inline (đọc từ `ISSUE_LABELS` đã có).

### ⏸ Phase S5 — URL list table modern (~1h, CHƯA LÀM)

**Scope:**
- Sticky header khi scroll.
- Score badge color-coded theo band (≥80 green chip, 60-79 amber, <60 red).
- Issue mini-icons inline (vd: 🔴×3 cho 3 critical issue).
- Hover row highlight + shadow.
- Action quick button: 👁 View detail, ✏ Edit, 🔄 Re-crawl, 📋 Copy URL.
- Filter bar collapsible (current đang luôn hiện).
- Pagination bottom redesign (button modern).

---

## 🎯 Roadmap

| Phase | Output | Effort |
|-------|--------|--------|
| S1 | 5 section framing color-coded | ~30' |
| S2 | KPI modern + animation | ~30' |
| S3 | Pipeline progress visual đẹp | ~30' |
| S4 | Top issues badge priority | ~45' |
| S5 | URL list table modern | ~1h |

**Total:** ~3h dev. Đề xuất đi tuần tự S1→S5, mỗi phase test riêng.

**Phụ thuộc:** Không có. Trang `/seo` independent, chỉ là UI/UX không đổi data/logic crawl backend.

---

## 📚 Reference

- Pattern code mẫu: `marketing_hub/templates/jobs_center.html` (CSS sau line 38 + 5 section `<section class="jc-section">`).
- Color palette pastel: `:root { --jc-green/blue/red/amber/violet/slate/indigo }` với cặp `bg` + `border`.
- WORKLOG entries 13:55-14:08: chi tiết approach + verify smoke.
