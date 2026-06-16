# Brief sơ bộ cho Claude Design — Sintech Marketing Hub

> Paste phần dưới (từ "=== PROMPT ===" trở xuống) vào claude.ai/design để nó hiểu nền tảng web trước khi đi vào từng màn hình.

---

=== PROMPT ===

# Sintech Marketing Hub — Design Context Brief

## 1. Sản phẩm là gì
Đây là một **web app nội bộ (internal tool / dashboard)** giúp 1 nhân viên marketing vận hành toàn bộ SEO + nội dung + đăng bài cho một shop bán linh kiện máy tính & gear gaming (Sintech PC Gaming & Gear, thị trường Việt Nam).

Nó KHÔNG phải landing page hay web bán hàng cho khách. Nó là **bảng điều khiển vận hành (operations console)** — dày dữ liệu, nhiều bảng, nhiều nút hành động, nhiều tiến trình chạy nền realtime. Hãy thiết kế theo tinh thần "admin/ops dashboard chuyên nghiệp" (giống Linear, Vercel dashboard, Stripe dashboard) — KHÔNG phải marketing site nhiều hero ảnh.

## 2. Người dùng
- **Đúng 1 người dùng**: nhân viên marketing (nữ), không phải dân kỹ thuật sâu nhưng dùng tool này hàng ngày, nhiều giờ.
- Ngôn ngữ UI: **tiếng Việt 100%**.
- Dùng chủ yếu trên **desktop màn lớn**, thỉnh thoảng mở mobile để xem nhanh trạng thái → cần responsive nhưng desktop-first.
- Ưu tiên: nhìn 1 cái biết ngay "việc gì đang chạy, việc gì lỗi, việc gì cần bấm", thao tác lặp lại nhanh, không bị mỏi mắt khi làm lâu.

## 3. Bố cục tổng (giữ nguyên kiến trúc này)
- **Sidebar trái cố định** (navigation chính, có search box trên cùng, user profile dưới cùng), gom theo nhóm công việc.
- **Vùng nội dung phải**: header trên (tên trang + nút hành động chính) + body cuộn.
- **Widget chat nổi góc phải dưới** (trợ lý AI "Nox-1") — bong bóng tròn, mở ra panel chat.

### Sidebar — các nhóm điều hướng hiện tại
1. **Tổng quan**: Dashboard, Job Center
2. **Phân tích & Đo lường**: GA4 Analytics, Search Console, Tracking Audit, Task Center, Analytics Ops
3. **Facebook**: Bài mới, Bài đã đăng, Lịch đăng
4. **Nội dung**: Content Jobs, Collection Content, Blog Content, SP mới, ALT ảnh
5. **Tối ưu & Kho** (nhóm gập được): **SEO** (9 mục con: Coverage, Title & Meta, H1 trong mô tả, SP thiếu mô tả, Trùng lặp, Link gãy, Indexability, Internal links, Lịch sử) · **Haravan** (3 mục con: Sản phẩm, Blog & News, Audit log)
6. **Khác**: Thư viện ảnh, Đối thủ

## 4. Các KIỂU màn hình (design system cần phục vụ tất cả)
1. **Dashboard tổng quan** — lưới các "thẻ sức khỏe" (KPI cards), số to, trend, trạng thái màu. Có cả lịch kéo-thả (drag-drop reschedule).
2. **Trang danh sách + bộ lọc** — bảng dữ liệu nhiều dòng (vài trăm → vài nghìn dòng), có filter bar, search, sort, phân trang, badge trạng thái, nút hành động theo dòng (Sửa / Copy / Re-crawl / Sync...). Đây là kiểu màn hình PHỔ BIẾN NHẤT — cần làm thật tốt: bảng dày nhưng dễ đọc, sticky header, hàng zebra/hover rõ.
3. **Trang chi tiết + editor** — sửa 1 bài viết, có **editor WYSIWYG** với thanh công cụ định dạng (~15 nút: H2/H3/đậm/link/bảng/trích dẫn...), khung preview, các nút Gen AI / Duyệt / Đồng bộ.
4. **Trang tiến trình nền (job/pipeline)** — thanh progress realtime (%, tốc độ req/s, ETA), nút Bắt đầu / Dừng, log cuộn. Nhiều việc chạy nền và poll cập nhật liên tục → cần trạng thái running/done/failed/idle rõ ràng bằng màu + animation nhẹ (shimmer/pulse).
5. **Trang audit / checklist** — danh sách hạng mục đạt/chưa đạt, gợi ý fix.

## 5. Thành phần UI lặp lại (component cần có trong design system)
- KPI card (số lớn + nhãn + trend + accent màu theo loại).
- Badge/pill trạng thái: tốt (xanh lá) / cảnh báo (vàng) / lỗi (đỏ) / đang chạy (xanh dương + pulse) / nghỉ (xám).
- Progress bar có % overlay + animation khi đang chạy.
- Bảng dữ liệu: sticky thead, accent border-left theo trạng thái dòng, nhóm nút hành động cuối dòng.
- Filter bar gập được + "chip" filter đang active + nút bỏ lọc.
- Toast notification (không chặn thao tác).
- Modal (chọn ảnh từ thư viện, xác nhận hành động nguy hiểm).
- Nút phân cấp rõ: primary (hành động chính) / secondary / nút nguy hiểm (xóa/đồng bộ lên Haravan — màu cảnh báo).
- Tab gập (collapsible group) trong sidebar.

## 6. Thương hiệu & cảm giác mong muốn
- **Màu nhấn chính hiện tại: tím (#7c3aed)**. Có thể giữ tím làm chủ đạo hoặc đề xuất bảng màu mới hài hòa, miễn là chuyên nghiệp + dễ chịu khi nhìn lâu.
- Cảm giác mong muốn: **hiện đại, gọn gàng, "mượt", đáng tin cậy** — như công cụ SaaS xịn. Không màu mè/trẻ con, nhưng cũng không khô khan như tool kế toán.
- Có chút ấm áp/thân thiện (tool này có "nhân cách" trợ lý AI tên Nox-1, icon trái tim 💕) — cho phép 1-2 điểm nhấn dễ thương nhỏ, nhưng không lấn át tính chuyên nghiệp.
- Dùng nhiều **emoji làm icon** trong điều hướng (📊 ⚙️ 🔍 🛒 ...) — có thể giữ hoặc thay bằng bộ icon line nhất quán (đề xuất giúp).
- Cần **chế độ sáng** rõ ràng (dark mode để sau, không bắt buộc).
- Mật độ thông tin cao nhưng phải có nhịp thở (spacing tốt), typography dễ đọc cho tiếng Việt có dấu.

## 7. Ràng buộc kỹ thuật (để design khả thi khi code lại)
- Stack: Flask + Jinja templates + CSS thường + vanilla JS (KHÔNG React/Tailwind framework). Thiết kế nên dịch được sang CSS components thuần.
- Đã có sẵn cấu trúc CSS: `style.css` + `marketing-hub-theme.css` (design tokens) + `marketing-hub-components.css` + `marketing-hub-responsive.css` → ưu tiên thiết kế theo hướng **design tokens** (biến màu/spacing/radius/shadow) để map vào được.
- Giữ cấu trúc layout sidebar + main + chat widget như trên.

## 8. Hiện trạng & việc muốn Design hỗ trợ (đợt này)
**Web ĐÃ có sẵn một bộ giao diện đang chạy** (theme nội bộ kiểu "admin pro": sidebar tím, KPI card, bảng dữ liệu, badge trạng thái — đã hoạt động ổn). Mình KHÔNG nhất thiết đập đi làm lại từ đầu.

Mong muốn đợt này: **Design đề xuất một ngôn ngữ thiết kế mới/cải tiến** (bảng màu, typography, spacing scale, bộ component cốt lõi: card, table, badge, button, progress, filter bar, form) — để mình **đặt cạnh giao diện hiện tại và so sánh, giữ phần nào hay, thay phần nào yếu**. Hãy nêu rõ điểm khác biệt và lý do so với một admin dashboard tím tiêu chuẩn, để dễ quyết định giữ/bỏ.

Sau khi chốt style nền, sẽ đi vào từng màn hình cụ thể (Dashboard → trang danh sách → trang editor → trang job). Ưu tiên đề xuất theo hướng **design tokens** để map vào CSS hiện có, đổi từng phần được mà không phá toàn bộ.

## 9. Hướng thị giác đã chốt (rất quan trọng — bám theo đây)
Mình đã tham khảo 2 admin template và chốt rõ lấy gì từ mỗi bên:

### 9a. MÀU SẮC — lấy theo "AdminPro – Gradient Design"
Thích phong cách **card gradient rực rỡ, hiện đại**. Bảng màu tham chiếu (gradient 2 điểm dừng):
- Cam–coral (chủ đạo): `#ff9966 → #d75151`
- Tím–hồng sen: `#ad6c7c → #d800ff` (và biến thể `#b52ea4 → #f13800`)
- Xanh ngọc (success): `#1ab394 → #2dda7a`
- Đỏ (cảnh báo/lỗi): `#b96f77 → #ca0e0e`
- Vàng–cam (warning): `#fff933 → #ef8f00`
- Xanh dương nhấn nền: `#03a9f4`

Cách dùng mong muốn: các **KPI card / widget số liệu** dùng nền gradient này (mỗi loại 1 màu), badge & trạng thái map theo hệ màu trên (xanh ngọc = tốt, vàng-cam = cảnh báo, đỏ = lỗi, xanh dương = đang chạy). Nền trang sáng, sạch; gradient chỉ dùng cho điểm nhấn (card/nút/header) để không bị chói khi nhìn lâu. Có thể tinh chỉnh độ bão hòa cho dịu mắt hơn bản gốc, nhưng giữ "chất" gradient nhiều màu.

### 9b. BỐ CỤC, BẢNG BIỂU, CHART, CĂN CHỈNH — lấy theo "Nalika" (trang index/dashboard)
Thích cách Nalika **sắp xếp và căn chỉnh element**:
- Lưới card/widget cân đối, khoảng cách (gutter) đều, nhịp thở tốt.
- **Bảng dữ liệu (data-table)** sạch, dễ đọc: header rõ, dòng thoáng, trạng thái bằng badge, gọn gàng.
- **Biểu đồ (chart)** đặt trong card có tiêu đề + chú thích, bố trí hài hòa với phần số liệu xung quanh.
- Cách dóng hàng (alignment) các thành phần trong card, padding nhất quán, phân cấp tiêu đề rõ ràng.

→ Tóm gọn công thức mong muốn: **"Màu & gradient card kiểu AdminPro gradient-design" + "cách bố trí lưới/bảng/chart/căn chỉnh kiểu Nalika"**, áp lên đúng cấu trúc layout (sidebar + main + chat widget) và các kiểu màn hình ở mục 4. (Ảnh chụp 2 giao diện này được đính kèm riêng để tham chiếu trực quan.)

⚠️ **Lưu ý tránh hiểu lầm:** template Nalika trong ảnh là **giao diện NỀN TỐI (dark)**, nhưng mình CHỈ mượn *bố cục / cách dóng hàng / cấu trúc bảng & chart* của nó — **KHÔNG lấy nền tối**. Thành phẩm phải là **nền SÁNG** với điểm nhấn gradient kiểu AdminPro. Nói cách khác: khung & cách sắp xếp của Nalika + bảng màu sáng-gradient của AdminPro.

=== HẾT PROMPT ===
