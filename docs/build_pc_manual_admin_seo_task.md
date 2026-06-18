# Manual admin SEO task — Build PC page (+ CS2 `<title>`)

> Lý do phải sửa TAY trong admin: **SEO title/meta (và `<title>`) lưu ở field admin Haravan mà Open API KHÔNG expose** (page object chỉ trả 10 field, không có field SEO; bài viết thì Open API bỏ qua `meta_title`). **Admin pages/blogs API đang 502** nên cũng không ghi tự động được. → Bộ phận có quyền vào admin sửa tay khi admin truy cập được.

## 1) Build PC page — `/pages/xay-dung-cau-hinh` (id 1003590100)
Admin: Online Store → Pages → "Xây dựng cấu hình" → phần **Chỉnh sửa SEO**.

**Hiện tại (rendered live):**
- `<title>`: `Build PC Online: Chọn linh kiện giá tốt - trả góp từ 0%`
- meta: `Build PC online theo nhu cầu gaming, đồ họa và văn phòng. Chọn linh kiện chính hãng, tối ưu ngân sách. Bảo hành linh kiện lâu dài, trả góp chỉ từ 0%.`
- H1 (theme render): `Build PC Online – Xây Dựng Cấu Hình PC Theo Nhu Cầu`

**Đề xuất (từ BUILD_PC_GROWTH_PLAN.md — đẩy "build pc" mà giữ "build pc online"):**
- **Title** (khuyến nghị): `Build PC Online – Tự chọn cấu hình PC giá tốt, trả góp 0%`
- **Meta**: `Build PC online theo nhu cầu Gaming, đồ họa, văn phòng: tự chọn linh kiện chính hãng, tối ưu ngân sách, trả góp 0%. Xây dựng cấu hình PC ngay tại Sintech.`
- **H1** (nếu theme cho sửa): `Build PC Online – Tự xây dựng cấu hình PC Gaming, đồ họa, văn phòng`
- Lưu ý: giữ cụm "Build PC Online" để không tụt query đang #2.6.
- ✅ Đã làm tự động được: thêm 1 internal link trong thân bài (`build PC Gaming theo giá` → /collections/pc-gaming-theo-gia).

## 2) CS2 bài viết — `/blogs/news/cau-hinh-choi-cs2-...` (id 1002399773)
Admin: Online Store → Blogs → news → bài CS2 → **Chỉnh sửa SEO** → sửa **Tiêu đề trang (meta title)**.

**Hiện tại:** `<title>` = `Cấu hình chơi CS2 - Counter Strike 2 trên PC, Laptop` (field SEO ẩn — chưa đổi).
**Đề xuất `<title>`:** `Cấu hình chơi CS2 mượt: chọn PC & laptop theo FPS`
- (H1 + og:title + meta description đã tự đổi qua API rồi; chỉ còn `<title>` này cần sửa tay để khớp.)

## Report liên quan
- `GSC_CTR_RESCUE_TITLE_META_PLAN.md`, `BUILD_PC_GROWTH_PLAN.md`, `GSC_CTR_RESCUE_PHASE1_APPLY.md`, `GSC_CTR_RESCUE_PHASE2_CS2_TITLE_APPLY.md`
- Tracking: `gsc_ctr_tracking_baseline.csv` + bảng DB `gsc_ctr_tracking` (check 14d: 2026-07-02).

## ⚠️ Cảnh báo bắt buộc khi sửa trong admin
- **KHÔNG đổi handle / đường dẫn (URL slug)** của page `xay-dung-cau-hinh` và bài CS2 — đổi URL = mất hết ranking/backlink đang có (build pc online #2,6, build pc #11,7...). Chỉ sửa **trường SEO title / meta description / (H1 nếu theme cho)**, giữ nguyên URL.
- Không đổi trạng thái xuất bản (published), không xóa nội dung body.

## Hướng dẫn sửa tay (khi admin hết 502)
1. Build page: Admin → Online Store → Pages → "Xây dựng cấu hình" → mục **Chỉnh sửa SEO website** (cuối trang) → dán Title + Meta đề xuất ở mục 1 → Lưu. (Giữ handle `xay-dung-cau-hinh`.)
2. CS2 bài: Admin → Blogs → news → bài CS2 → **Chỉnh sửa SEO website** → dán `<title>` đề xuất ở mục 2 → Lưu. (Giữ handle bài.)
3. Sau khi lưu: mở lại URL public, kiểm `<title>` đã đổi (xả cache nếu cần) → cập nhật record trong `gsc_ctr_tracking`.

## Rule khi sửa
Title 45–60 ký tự (Haravan tự thêm " – Sintech", KHÔNG tự ghi Sintech), meta 140–160, không nhồi keyword, không bịa số/FPS, không nội dung crack.
