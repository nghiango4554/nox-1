# GSC CTR RESCUE — Title/Meta đề xuất (CHỜ DUYỆT, chưa apply)

> Nguồn: GSC API sc-domain:sintech.vn (90 ngày) + sheet GSC. **Không apply live** — chỉ đề xuất để duyệt.
> Rule: title input 45–60 ký tự (Haravan tự thêm " – Sintech", KHÔNG tự ghi Sintech vào title), meta 140–160, không nhồi keyword, không bịa giá/sale/FPS, không nội dung crack.

## Tổng quan query ưu tiên → landing page

| Query | Landing page | Pos | Impr | Clicks | CTR | Ghi chú |
|---|---|---|---|---|---|---|
| cs2 | `/blogs/news/cau-hinh-choi-cs2-counter-strike-2-tren-pc-laptop` | 6.3 | 3.936 | 28 | **0,7%** | CTR rescue chính |
| office 2021 | `/blogs/huong-dan/...office-2021-full-100-thanh-cong` | 6.5 | 3.076 | 111 | 3,6% | ⚠️ bài "full/crack" — **KHÔNG rewrite kiểu crack** (xem file license) |
| build | `/pages/xay-dung-cau-hinh` | 7.3 | 2.853 | 9 | ~0% | xử ở BUILD_PC_GROWTH_PLAN |
| build pc | `/pages/xay-dung-cau-hinh` | 11.7 | 4.836 | 147 | 3% | xử ở BUILD_PC_GROWTH_PLAN |
| xây dựng cấu hình pc | `/pages/xay-dung-cau-hinh` | 8.9 | 890 | 15 | ~2% | xử ở BUILD_PC_GROWTH_PLAN |
| build pc online | `/pages/xay-dung-cau-hinh` | 2.6 | 3.738 | 861 | 23% | ĐANG TOP — chỉ bảo vệ, không phá |

→ 4/6 query "build*" trỏ về **cùng 1 trang** `/pages/xay-dung-cau-hinh` → gộp xử ở `BUILD_PC_GROWTH_PLAN.md`. File này tập trung **CS2** (cơ hội CTR lớn nhất, 3.936 hiển thị mà chỉ 0,7%).

---

## 1) CS2 — `/blogs/news/cau-hinh-choi-cs2-counter-strike-2-tren-pc-laptop`

**Hiện tại:**
- Title (52): `Cấu hình chơi CS2 - Counter Strike 2 trên PC, Laptop`
- Meta (148): `Muốn chơi Counter-Strike 2 mượt hơn? Tham khảo cấu hình CS2 theo FPS, màn hình và ngân sách để build PC hoặc chọn laptop. KHÁM PHÁ NGAY tại Sintech.`
- Bài tốt: 5.930 từ, 11 H2 (cấu hình theo FPS/ngân sách, laptop, màn hình 144–360Hz, FAQ). **Chưa có schema** (FAQ/Article = 0).

**Vì sao CTR thấp (0,7%):**
1. Query "cs2" **intent rộng/điều hướng** — phần lớn người tìm muốn *game* (tải, chơi, tin tức), không phải "cấu hình PC". Trang config chỉ trúng một lát intent → CTR thấp là tự nhiên, title khó kéo 100%.
2. Title hiện **mô tả chủ đề** chứ chưa có **hook lợi ích** ("mượt", "FPS cao", "theo ngân sách") để hút đúng nhóm người tìm cấu hình.
3. Title dài 52 + đuôi " – Sintech" = 62 → đủ nhưng phần giá trị nằm cuối.

**→ 3 TITLE đề xuất** (đưa hook value lên đầu, vẫn giữ "CS2" + "cấu hình"):
1. `Cấu hình chơi CS2 mượt: chọn PC & laptop theo FPS` (49)
2. `CS2 cần cấu hình gì? Gợi ý PC chơi mượt mọi mức FPS` (51)
3. `Build PC chơi CS2: cấu hình tối ưu FPS theo ngân sách` (53)

**→ 3 META đề xuất** (140–160, bám nội dung thật, không bịa số):
1. `CS2 cần cấu hình thế nào để chơi mượt? Xem gợi ý PC và laptop theo mức FPS, màn hình và ngân sách, kèm tư vấn nâng cấp máy. KHÁM PHÁ NGAY tại Sintech.` (153)
2. `Chọn cấu hình chơi CS2 chuẩn nhu cầu: từ máy phổ thông đến PC FPS cao, so sánh CPU, VGA và màn hình theo từng tầm tiền. XEM NGAY tại Sintech.` (146)
3. `Muốn CS2 ổn định FPS, vào trận mượt? Tham khảo cấu hình PC và laptop theo từng ngân sách, kèm gợi ý linh kiện và nâng cấp. TÌM HIỂU NGAY tại Sintech.` (152)

**Đòn bẩy thêm (ngoài title/meta):** thêm **FAQPage schema** (bài đã có sẵn mục "Câu hỏi thường gặp") → cơ hội rich result + tăng CTR; gắn internal link từ bài CS2 → collection PC Gaming / page build.

---

## 2) office 2021 — ⚠️ KHÔNG rewrite ở đây
Landing page đang rank là bài hướng dẫn cài "full 100%" (intent crack). Theo rule, **không tối ưu title/meta cổ vũ crack**. Hướng xử lý chuyển sang **nội dung bản quyền** — xem `software_license_safe_content_opportunities.md` (Sintech đã có sẵn bài `Office 2021 bản quyền khác gì Office crack`, id 1002989389).

---

## Lưu ý chung
- Tất cả mới là **đề xuất**. Chưa PUT, chưa sửa live.
- CS2 là điểm CTR rescue rõ nhất; các query build* đã gộp ở plan riêng.
- Sau khi vợ chốt title/meta, mới apply qua tool /seo (blog) — và đo lại CTR sau 2–4 tuần ở `/seo/history`.
