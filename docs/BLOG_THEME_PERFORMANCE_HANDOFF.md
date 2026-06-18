# HANDOFF — Tối ưu tốc độ (Core Web Vitals) cho bộ phận Code/Theme

> Nguồn: phân tích data CWV crawl 13/6/2026 (5.612 URL: 2.816 mobile + 2.796 desktop) + kiểm tra trực tiếp ảnh/theme Sintech.vn. Soạn 16/6/2026.
> Mục tiêu: giảm LCP (đặc biệt trang blog) bằng các thay đổi ở **theme/code** — phần marketing đã xử xong phía nội dung/ảnh.

---

## TL;DR — 3 việc cho code team, xếp theo mức lợi

| # | Việc | Lợi ước tính | Độ khó |
|---|---|---|---|
| **1** | **Render ảnh đại diện (featured) blog bằng biến thể size** `_large` thay vì ảnh gốc | Rất lớn — áp cho **233 bài**, ảnh hero từ ~1MB → ~200KB | Thấp (1 chỗ sửa template) |
| **2** | **Defer / loại JavaScript thừa** (toàn site) | **~1.570ms** (đòn bẩy lớn nhất) | Trung bình |
| **3** | **Purge CSS thừa** | ~193ms | Trung bình |

Phụ: thêm `width/height` + `loading="lazy"` cho ảnh ở theme; cân nhắc WebP. Server-response (~386ms) là hạ tầng Haravan, ưu tiên thấp.

---

## 1. Bối cảnh — cái gì THỰC SỰ chậm

**Người dùng thật (CrUX field, p75) đều ĐẠT chuẩn Google:**
- Mobile LCP **1.678ms** (chuẩn <2.500) ✅ · INP **171ms** (<200) ✅ · CLS **~0** ✅

→ Khách thật không bị chậm 3 chỉ số. **Cái "chậm" là điểm LAB** (Lighthouse mobile throttle) — quan trọng cho điểm PageSpeed/SEO tool.

**Lab mobile (median) theo loại trang:**

| Loại trang | Perf | LCP lab | FCP lab | TBT |
|---|---|---|---|---|
| **Blog** | **45** | **12.532ms** 🔴 | 3.367ms | 257ms |
| Sản phẩm | 73 | 4.462ms | 3.485ms | 134ms |
| Danh mục | 76 | 3.988ms | 3.376ms | 72ms |
| Trang (page) | 74 | 3.910ms | 3.360ms | 119ms |

**Nhận định:** FCP ~3.4s **giống nhau ở MỌI loại trang** → nghẽn ở **theme toàn site** (render-blocking JS/CSS), không phải từng bài. Blog tệ nhất vì cộng thêm **ảnh đại diện nặng**.

---

## 2. Nguyên nhân gốc (từ Lighthouse opportunities, 40 trang deep-scan)

| Cơ hội tối ưu | Số trang dính | Tiết kiệm TB |
|---|---|---|
| **unused-javascript** | 22/40 | **~1.570ms** 🔴 |
| server-response-time | 9/40 | ~386ms |
| unused-css-rules | 9/40 | ~193ms |

---

## VIỆC 1 — Ảnh đại diện blog: render bằng biến thể size (lợi lớn nhất, dễ)

**Vấn đề:** **36/36 bài** kiểm mẫu có ảnh đại diện (`article.image`) là **ảnh GỐC chưa resize**, nặng **900KB – 2MB/ảnh**. Đây là phần tử LCP đầu mỗi bài blog + thumbnail ngoài danh sách → kéo LCP blog lên 12.5s.

**Bằng chứng — Haravan ĐÃ tạo sẵn biến thể nhẹ** (ví dụ 1 ảnh gốc 1.193KB):

| Biến thể | Dung lượng |
|---|---|
| gốc / `_master` | 1.193 – 1.497 KB |
| `_grande` | 289 KB |
| **`_large`** | **207 KB** (1024px — nét, hợp khổ blog) |
| `_medium` | 67 KB |
| `_small` | 12 KB |

**Cách sửa (theme):** trong template render ảnh đại diện bài viết (article hero + thumbnail list — thường ở `article.liquid`, `blog.liquid`, snippet article-card), đổi nguồn ảnh sang biến thể có size:

```liquid
{# Thay vì dùng ảnh gốc: #}
<img src="{{ article.image.src }}">

{# → dùng filter size của Haravan (hoặc chèn suffix _large): #}
<img src="{{ article.image.src | img_url: 'large' }}"
     width="1024" loading="lazy" alt="{{ article.title | escape }}">
```
(Nếu theme không hỗ trợ filter `img_url`, có thể chèn suffix `_large` vào trước phần mở rộng của URL `cdn.hstatic.net/.../article/<tên>.<ext>` → `<tên>_large.<ext>`.)

**Lợi:** ảnh hero mỗi bài từ ~1MB → ~200KB (giảm ~80%), áp **cả 233 bài** chỉ với 1–2 chỗ sửa template. **Đây là đòn bẩy LCP blog lớn nhất.**

> Lưu ý: chỉ sửa biến thể ở chỗ HIỂN THỊ (img src). Giữ `og:image` dùng ảnh gốc cho chia sẻ MXH (không ảnh hưởng tốc độ).

---

## VIỆC 2 — Loại / defer JavaScript thừa (đòn bẩy lớn nhất toàn site)

**Vấn đề:** unused-javascript lãng phí **~1.570ms** trên phần lớn trang (theme nạp JS không cần cho lần render đầu). Đây là nguyên nhân chính FCP ~3.4s đồng đều mọi trang.

**Đề xuất:**
- Thêm `defer` (hoặc `async` khi an toàn) cho script không cần chặn render.
- Tách/loại bỏ thư viện không dùng (slider/lightbox/plugin… nạp toàn site nhưng chỉ vài trang cần).
- Nạp JS theo điều kiện trang (chỉ load script của trang đó).
- Gộp + minify; bỏ JS theme cũ không còn dùng.

---

## VIỆC 3 — Purge CSS thừa

**Vấn đề:** unused-css-rules ~193ms. CSS chứa nhiều rule không dùng + render-blocking.

**Đề xuất:** purge CSS thừa, inline critical CSS cho phần trên màn hình, defer phần còn lại.

---

## Phụ — ảnh & CLS ở theme

- **Thêm `width`/`height` + `loading="lazy"`** cho ảnh render bởi theme (đặc biệt ảnh trong nội dung). Lưu ý: Haravan **gỡ `loading`/`width-height` khi PUT ở mức bài viết** → phải set ở **theme template/CSS** (đã có sẵn 1 bản vá CSS `aspect-ratio` ở `theme_patch_p10/` — tham khảo).
- **Cân nhắc WebP** site-wide qua image filter của theme (giảm ~25–35% dung lượng ảnh).

---

## Phần marketing ĐÃ làm xong (không cần code team)

- ✅ **Ảnh thân bài blog đã tối ưu:** body images đã dùng biến thể `_grande` (kiểm mẫu 85/85 ảnh) — không còn ảnh body gốc nặng.
- ✅ **18 ảnh blog theme nặng** (rh-*) đã resize ≤800px + nén: **2.74MB → 0.98MB (−64%)**.
- ✅ **791 ảnh content collection** chuẩn 600×338, ~28KB/ảnh — đã tối ưu.
- ⛳ Còn lại = **việc theme** (3 việc trên), marketing không sửa được bằng API.

---

## Phụ lục số liệu

- Crawl: 13/6/2026, 2.816 URL mobile + 2.796 desktop (bảng `seo_cwv`, lịch sử `seo_cwv_history` tuần 22 & 24, chẩn đoán LCP `seo_cwv_lcp`).
- Field p75 (mobile): LCP 1.678ms · INP 171ms · CLS ~0 (đều GOOD).
- Lab mobile median: perf 73 · LCP 4.508ms · FCP 3.483ms · TBT 135ms.
- Ảnh đại diện: 36/36 bài mẫu = ảnh gốc chưa resize (900KB–2MB).
- Biến thể Haravan khả dụng: `_large` 207KB / `_medium` 67KB / `_grande` 289KB.

*Cần thêm danh sách URL cụ thể (top blog/sản phẩm tệ nhất) hoặc export CSV chi tiết — báo để bổ sung.*
