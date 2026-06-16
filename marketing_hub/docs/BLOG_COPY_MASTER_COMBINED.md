# BÁO CÁO GỘP — RÀ SOÁT COPY BLOG SINTECH (233 bài) — 10/6/2026

> Kết hợp 2 phương pháp bù trừ nhau: **(A) Scan ảnh** (Claude — `BLOG_PLAGIARISM_SCAN.md`) bắt copy qua ảnh hotlink CDN đối thủ · **(B) Audit text** (ChatGPT — `bao-cao-ra-soat-trung-noi-dung-sintech-day-du.xlsx`) soi 94 bài text-only mà ảnh không bắt được. Dữ liệu audit đã ingest vào `blog_rewrite_candidates` (cột `audit_*`, additive).

## 📊 Bức tranh GỘP toàn bộ 233 bài

| Nhóm | Số bài | Phát hiện bởi |
|---|---:|---|
| 🔴 Copy — ảnh hotlink CDN đối thủ | **139** | A. Scan ảnh |
| 🔴 Copy — text (94 bài "còn lại") | **+8** | B. Audit text |
| **→ TỔNG CẦN REWRITE** | **147** | gộp A+B |
| ⚖️ ĐẢO NGƯỢC — đối thủ copy TỪ Sintech | **3** | B (Sintech là nạn nhân → lưu bằng chứng/takedown, KHÔNG rewrite) |
| 🟡 Text-audit mức TB (soi thêm) | ~9 | B (score 3) |
| ⚪ Còn lại (chưa đủ bằng chứng) | ~74 | — |

**Hai phương pháp bù trừ:** scan ảnh mạnh với bài bê nguyên ảnh đối thủ (139), nhưng MÙ với bài copy text rồi tự thay ảnh / dùng ảnh Google Docs → audit text vá đúng lỗ hổng đó (+8 bài, nổi bật **GEARVN**).

## 🔴 8 bài text-copy MỚI (ảnh không bắt được — cần rewrite)
| Tiêu đề | Người viết | Ngày | Nguồn | Bằng chứng |
|---|---|---|---|---|
| DLSS 4 là gì? Cách bật DLSS 4 | Phương Nam | 2025-09-09 | CellphoneS Sforum | cùng mốc driver 572.16 + 75 game |
| Microsoft kết thúc hỗ trợ Win 11 21H2/22H2 | Sín Hỷ Phát | 2024-07-10 | Thanh Niên | title trùng nguyên văn + nhiều đoạn |
| Cách lấy lại file Word gốc chưa lưu (Mac/Win) | Khang | 2024-08-27 | GEARVN | chuỗi Finder→Go→com.microsoft.Word + **alt ảnh tên GEARVN** |
| Phân biệt Clicky/Linear/Tactile switch | Khang | 2024-09-16 | GEARVN | 🚩 **HTML còn cụm "cùng GEARVN tìm hiểu"** + alt ảnh GEARVN |
| Snap Tap là gì? | Khang | 2024-09-23 | GEARVN | trùng đoạn + mốc giải đấu + alt ảnh |
| Unity là gì? Cách cài đặt | Khang | 2024-09-23 | GEARVN | cùng 6 bước + lỗi gõ "p hiên bản" |
| Tản nhiệt AIO hoạt động thế nào? | Khang | 2024-09-23 | GEARVN | title trùng nguồn ngoài |
| Nvidia ngừng sản xuất RTX 3060 | Khang | 2024-08-21 | Thanh Niên | title trùng nguyên văn |

→ **Dấu vết đóng đinh:** bài #64 còn nguyên cụm **"cùng GEARVN tìm hiểu"** + nhiều bài còn **alt ảnh mang tên GEARVN** (quên xóa thương hiệu nguồn khi copy).

## ⚖️ 3 bài ĐẢO NGƯỢC — Sintech là NẠN NHÂN (đối thủ copy lại)
| Tiêu đề Sintech | Đối thủ copy | Hành động |
|---|---|---|
| Top 10 Thương Hiệu Linh Kiện Máy Tính... | Hữu Computer | Chụp màn hình, lưu HTML/cache, gửi yêu cầu gỡ / xử lý bản quyền |
| RTX 5070 gây bão trên Amazon... | Hữu Computer | Lưu bằng chứng, đối chiếu ngày index |
| Trung Quốc ra mắt GPU 6nm Lisuan... | Hữu Computer | Lưu bằng chứng, đối chiếu ngày index |
→ **KHÔNG rewrite** mấy bài này (Sintech viết trước) — cần phòng thủ bản quyền.

## 👤 Người viết (gộp cả 2 báo cáo)
- **Khang** — thủ phạm chính (copy cả ảnh 2024 + text từ GEARVN/Thanh Niên).
- **Phương Nam** — 2025 (CellphoneS + nhiều nguồn).
- **Lân, Sín Hỷ Phát, Trọng Nghĩa** — mới lộ qua audit text (vài bài tin/dịch vụ).

## 🧭 Nguồn bị copy (gộp)
FPT Shop · TGDĐ/ĐMX · Bizweb-shop (dktcdn 329122) · báo nước ngoài (TechRadar/WCCFtech/PCMag...) · **GEARVN** (text, mới) · Thanh Niên · CellphoneS Sforum · HACOM · Hoàng Hà · An Phát...

## 🔗 Tích hợp vào tool "AI Viết Lại Blog"
- Ingest 94 dòng audit → cột `audit_risk/audit_score/audit_source/audit_action/audit_is_reverse/audit_evidence` (additive, idempotent).
- 8 bài text-copy confirmed → `selected=1` (vào hàng đợi rewrite cùng 139 bài ảnh).
- 3 bài reverse → `audit_is_reverse=1` (loại khỏi rewrite, đánh dấu để phòng thủ).
- ⚠️ Caveat: re-import scan ảnh KHÔNG đụng cột `audit_*` (giữ nguyên), nhưng sẽ reset `selected` theo image-risk → cần giữ audit selection khi build P3 (đọc audit_score trong logic chọn).

## ✅ Khuyến nghị
1. **Rewrite 147 bài** (139 ảnh + 8 text) — ưu tiên bài có traffic (GSC) + 8 bài GEARVN/Thanh Niên có dấu vết rõ.
2. **Phòng thủ 3 bài** Hữu Computer copy ngược: lưu bằng chứng + yêu cầu gỡ.
3. Bài #64 (còn cụm "cùng GEARVN") nên xử lý NGAY — bằng chứng lộ liễu nhất.
4. Dùng tab `/seo/blog-rewrite-ai` (P1+P2 đã build) làm hàng đợi rewrite; P3 (AI thật) sẽ gen bài nguyên bản thay thế.
