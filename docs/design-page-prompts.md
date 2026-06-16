# Prompt cho 3 khuôn trang tiếp theo — claude.ai/design

> Dùng SAU khi đã có dashboard + bộ `sintech-hub.css`. Mỗi prompt dán cùng **ảnh trang hiện tại tương ứng** (trong `design-references-shots/oursite-*.png`).
> Câu mở đầu chung cho cả 3: *"Tiếp tục đúng design system bạn vừa tạo cho Dashboard (sintech-hub.css — cùng design tokens, cùng font/màu/spacing/component: KPI card gradient, badge tone, bảng, progress, sidebar, chat Nox-1). KHÔNG đổi hệ màu hay layout khung. Chỉ thiết kế phần nội dung của trang này theo cùng ngôn ngữ đó. Nền sáng, gradient chỉ làm điểm nhấn."*

---

## KHUÔN 1 — Trang DANH SÁCH + BỘ LỌC (đại diện: `/seo/title-meta`)
> Đính kèm ảnh: `oursite-1-list-filter-title-meta.png`

Đây là kiểu màn hình PHỔ BIẾN NHẤT và DÀY NHẤT của web (nhân viên ngồi đây nhiều giờ). Hãy thiết kế lại trang quản lý "Title & Meta" gồm các khối sau, theo đúng design system Dashboard:

1. **Hàng KPI** (như dashboard): các thẻ số liệu — Tổng SP, Đã gen+sync, Chưa gen, Gen lỗi, Đã sync hôm nay... (mỗi loại 1 tone màu: tốt=emerald, chờ=amber, lỗi=rose, tổng=coral/violet).
2. **Bộ chọn phân tầng (tier)**: 1 hàng thẻ "Tầng 1" (nhóm collection lớn) có thanh % tiến độ trên mỗi thẻ → bấm vào lọc xuống Tầng 2. Thiết kế các thẻ tier gọn, có progress bar + số đếm.
3. **Thanh công cụ lọc (filter bar)**: dropdown chọn phạm vi (tất cả / chỉ lỗi / đã sync...), ô search, sort, toggle "chỉ SP lỗi", các nút hành động chính: **⚡ Gen+Sync (đã lọc)**, **Dual-AI**, **Gen tiếp**, **Re-crawl**. Cho phép filter bar gập gọn + hiện "chip" filter đang active.
4. **Bảng dữ liệu DÀY** (quan trọng nhất — phải đẹp & đọc tốt ở vài nghìn dòng): cột STT, Tên SP (kèm dòng phụ handle), Title hiện tại, Meta hiện tại, Title đề xuất, Meta đề xuất, badge **độ dài** (đếm ký tự, màu 🟢🟡🔴 theo ngưỡng), **trạng thái** (pill: đã sync / chưa / lỗi), cột **Ngày sync**, và nút hành động cuối dòng (Gen+Sync). Cần: sticky header, hover dòng rõ, accent border-left theo trạng thái, zebra nhẹ, mật độ "compact" để chứa nhiều dòng mà không rối.
5. **Phân trang**: kiểu "Hiện 50/Tổng N" + nút "Xem thêm 50".

Mục tiêu: bảng dữ liệu lớn nhìn vẫn sang, dễ quét mắt, trạng thái phân biệt bằng màu tone hệ thống. Đề xuất cả layout cho cột Title/Meta dài (truncate + tooltip / 2 dòng).

---

## KHUÔN 2 — Trang CHI TIẾT + EDITOR WYSIWYG (đại diện: `/collection-content/<id>`)
> Đính kèm ảnh: `oursite-2-editor-wysiwyg.png`

Trang soạn & duyệt nội dung 1 mục (sản phẩm/collection/blog đều chung kiểu này). Thiết kế lại theo design system Dashboard, gồm:

1. **Header trang**: breadcrumb + tên mục + **badge trạng thái** (Mới/Đã gen/Đã sync) + bên phải là **thẻ "Chất lượng"** dạng mini-KPI (Title, Meta, Structure, Link, Readability — mỗi cái 1 điểm số + tone màu). Có thể làm thành 1 dải KPI nhỏ ngang.
2. **Khối SEO meta**: ô nhập **Tiêu đề** (kèm đếm ký tự) + ô **Mô tả meta** (đếm ký tự), mỗi ô có nút **Gen tiêu đề / Gen Meta** (AI) bên cạnh.
3. **Thanh công cụ định dạng (WYSIWYG toolbar)**: ~15 nút — H2, H3, đậm, nghiêng, link (màu đỏ thương hiệu), danh sách, **bảng**, **trích dẫn (blockquote)**, ảnh, format full, undo... Bố trí gọn thành 1 thanh, nhóm logic, icon nhất quán.
4. **Vùng soạn thảo** (contenteditable): hiển thị nội dung đã render (H2, đoạn văn, ảnh 600×338, **bảng thông số** có viền). Cần style đẹp cho nội dung bên trong: heading, đoạn, list, link, bảng, blockquote.
5. **Thanh hành động** (sticky dưới hoặc trên): **AI gen lại bài**, **Lưu chỉnh sửa**, **Đồng bộ lên Haravan** (nút nguy hiểm/outward — màu cảnh báo rõ).

Mục tiêu: không gian soạn thảo rộng rãi, dễ tập trung; toolbar gọn không chiếm chỗ; phân biệt rõ nút "lưu nháp" với nút "đẩy lên Haravan thật".

---

## KHUÔN 3 — Trang AUDIT + JOB TIẾN TRÌNH (đại diện: `/seo`)
> Đính kèm ảnh: `oursite-3-job-progress-seo.png`

Trang tổng SEO: vừa là bảng điều khiển audit, vừa chứa **tiến trình chạy nền realtime**. Thiết kế lại theo design system Dashboard, gồm:

1. **Hàng KPI tổng**: Tổng URL, Điểm TB, số Tốt/OK/Tệ, số loại (tone màu hệ thống).
2. **Lưới thẻ "Vấn đề" (issue cards)**: mỗi thẻ 1 loại lỗi SEO (thiếu mô tả, title trùng, link gãy, indexability, schema...), số đếm to, **phân 3 mức ưu tiên bằng màu** (critical=rose / high=amber / medium=sky), kèm 1 dòng gợi ý fix. Bấm thẻ → cuộn xuống lọc bảng URL.
3. **Khối PIPELINE chạy nền (quan trọng — "ngôn ngữ trạng thái")**: 2 làn song song **Phase 1 Crawl** + **Phase 2 Link check**. Mỗi làn có: **progress bar có % + animation shimmer khi đang chạy**, trạng thái màu rõ ràng (đang chạy=emerald+pulse / xong=sky / lỗi=rose / nghỉ=slate), và 4–5 ô chỉ số (Tiến độ, OK, Lỗi, Tốc độ req/s, ETA). Nút **🚀 Quét toàn bộ** + **⏹ Dừng (giữ tiến độ)**.
4. **Bảng URL DÀY**: cột URL, badge **điểm /100** (gradient theo band tốt/ok/tệ), trạng thái (pill), **mini-icon lỗi** (🔴 N / 🟡 N / 🟢 OK), nhóm nút hành động (Chi tiết / Copy URL / Re-crawl). Sticky header, filter bar gập, phân trang kiểu « ‹ 1 2 3 › ».

Mục tiêu: thấy ngay "việc gì đang chạy / xong / lỗi" qua màu + animation; thẻ vấn đề ưu tiên rõ; bảng URL lớn vẫn dễ đọc. Đây là nơi định nghĩa chuẩn **trạng thái running/done/failed/idle** cho mọi trang job khác trong app.

---

## Sau khi có đủ 5 khuôn (Dashboard + 3 cái này + 1 trang list khác nếu cần)
- Xin Design xuất **bộ component đã bổ sung** (table full-page, filter bar, editor toolbar, pipeline progress, issue card) gộp vào cùng `sintech-hub.css`.
- Dặn **self-host font (Plus Jakarta Sans / Space Grotesk) + icon Lucide** để chạy offline.
- Phần còn lại (~35 trang) chỉ là lắp lại 5 khuôn này → làm trong code Jinja, không cần Design nữa.
