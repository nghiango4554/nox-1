# QUY TẮC ĐẶT TÊN SẢN PHẨM SINTECH (v2026-05-09)

**Nguồn:**
- 13 quy tắc gốc từ PDF `QUY TẮC ĐẶT TÊN.pdf` của vợ Nghĩa
- Quy tắc Laptop bổ sung — Nox-1 đề xuất (analyse 40 SP laptop hiện tại Sintech)

**Mục đích:** Đảm bảo tên SP trên Haravan / FB / web Sintech nhất quán, dễ search, đủ thông tin cho khách + Google.

---

## Quy ước chung (áp dụng MỌI loại)

- **Chữ thường** cho từ thường, **HOA tên riêng** (Asus, Intel, RTX, IPS...)
- **Dấu phân cách**: dùng dấu cách + dấu `,` trong ngoặc `()`. KHÔNG mix `|`, `/`, `\`
- **Tránh viết tắt không chuẩn**: `i5` (chuẩn) thay vì `I5`, `Inch` viết bằng `''` hoặc `inch`
- **Trình tự spec**: từ chính → phụ (CPU → RAM → SSD → GPU → Màn hình → Pin)
- **Hết hàng / Demo / Cũ Đẹp** → ghi cuối tên trong `()` hoặc sau dấu cách
- **Trắng** ghi rõ; **đen** không ghi
- **Kích thước** màn hình: `21.5'' → làm tròn 22''`
- **Spec không chắc** → BỎ, không bịa

---

## 1. MAINBOARD

```
Mainboard + Hãng + Mã + Chuẩn RAM
```

**Ví dụ:** `Mainboard Asus Prime H610M-K DDR4`

Chuẩn RAM bắt buộc: `DDR4` / `DDR5`

---

## 2. CPU

```
CPU + Hãng + Mã (Xung Turbo + Số nhân/luồng) - Tình trạng
```

**Ví dụ:** `CPU Intel Core i5 14400F (4.7 GHz, 10 Nhân 16 Luồng) - Tray New`

Tình trạng phổ biến: `Tray New` / `Box New` / `Tray 2nd` / `Box 2nd`

---

## 3. RAM

```
RAM + Hãng + [Model] + [RGB] + Dung lượng + Chuẩn + Bus + Màu
```

**Ví dụ:** `RAM Centaur Ragnarok Pro RGB 8GB DDR4 3200 Đen`

- Model + RGB → có thì ghi, không thì bỏ
- Trắng ghi rõ; Đen không bắt buộc nhưng nên ghi cho rõ

---

## 4. SSD / HDD

```
Ổ Cứng SSD + Hãng + Mã + Dung lượng + Chuẩn (Sata III / M2 NVMe)
```

**Ví dụ:**
- `Ổ Cứng SSD Netac SA500 512GB 2.5 Sata III`
- `Ổ Cứng SSD Colorful CN600 Pro 1TB M2 NVMe`

Chuẩn HDD: `3.5` / `2.5` + tốc độ vòng quay nếu khác biệt

---

## 5. CARD ĐỒ HỌA (VGA)

```
Card Màn Hình + Hãng + [Model] + Mã + Dung lượng + Version
```

**Ví dụ:** `Card Màn Hình Asus Dual RTX 3060 12GB V1`

- Model + Version → có thì ghi, không thì bỏ
- Version (V1/V2/OC...) ghi nếu hãng phát hành nhiều bản

---

## 6. VỎ CASE

```
Vỏ Case + Hãng + Model + Size + Màu + Kèm fan
```

**Ví dụ:** `Vỏ Case Magic Luxury E-ATX Đen Sẵn 4 Fan`

Size: `M-ATX`, `ATX`, `E-ATX`, `Mini-ITX`

---

## 7. NGUỒN (PSU)

```
Nguồn + Hãng + [Model] + Mã + Công suất + Chuẩn + (Trắng nếu trắng)
```

**Ví dụ:** `Nguồn Gigabyte P650SS ICE 650W 80 Plus Silver`

- Trắng → ghi `Trắng` cuối; Đen → không ghi
- Chuẩn 80 Plus: `Bronze / Silver / Gold / Platinum / Titanium`

---

## 8. TẢN NHIỆT

```
Tản Nhiệt + Khí/Nước + Hãng + [Model] + Mã + (Dual nếu khí 2 tháp) + Trắng
```

**Ví dụ:**
- `Tản Nhiệt Khí Centaur CT-X9000`
- `Tản Nhiệt Khí Centaur CT-AIR03 Dual Trắng`
- `Tản Nhiệt Nước MSI MAG CoreLiquid 240R`

Quy ước:
- Khí 2 tháp → ghi `Dual`
- Khí 1 tháp → để trống
- Nước → để trống (không cần phân loại tháp)

---

## 9. FAN CASE

```
Fan Case + Hãng + Mã + Màu Sắc + SYNC MAIN / SYNC HUB / [Để Trống]
```

**Ví dụ:** `Fan Case Coolmoon K2 Led RGB Đen Sync Main`

---

## 10. MÀN HÌNH

```
Màn Hình + Tính chất + Mã + Kích thước + (Tần số quét, Tấm nền, Độ phân giải, Tốc độ phản hồi)
```

**Tính chất:**
- `Văn Phòng`
- `Gaming`
- `Cong` (đặc biệt cho màn cong, không gộp với Gaming)

**Ví dụ:**
- `Màn Hình Văn Phòng AIVision A243FV 24 Inch (100Hz, VA, FHD, 5ms)`
- `Màn Hình Gaming MSI G275L 27 Inch (FHD, IPS, 144Hz, 1ms)`

**Note:** 21.5 inch → làm tròn 22 inch

---

## 11. BÀN PHÍM

```
Phím + Cơ/Văn phòng + Hãng + Mã + (Loại Switch + Màu) + [Có dây / Không dây]
```

**Ví dụ:** `Phím Cơ Aula S98 Pro (Grey Wood V4 Switch Xanh Lá Trắng) Không Dây`

- Có dây → có thể bỏ qua (default)
- Không dây → BẮT BUỘC ghi

---

## 12. CHUỘT

```
Chuột + Gaming/Văn phòng + Hãng + Mã + (Led RGB) + Màu + [Có dây / Không dây]
```

**Ví dụ:** `Chuột Gaming Aula F813 Led RGB Màu Đen Không Dây`

> 📌 Note: Các thông tin khác phải thể hiện rõ trong THÔNG SỐ SẢN PHẨM (DPI, switch, weight...).

---

## 13. PC BUILD SẴN

```
PC + Gaming/Văn phòng + SIN + Tên Vỏ Case + QUY ƯỚC | + Đời CPU + VGA + VRAM
```

**Quy ước CPU theo dòng PC:**
- i3 → `PLUS`
- i5 → `PRO`
- i7 → `MAX`
- i9 → `PROMAX`

**Ví dụ:**
- `PC Gaming SIN Hyper 12 Pro | i5 12400F, RTX 3060 12GB`
- `PC Văn Phòng SIN Office i5 10400 Pro`

---

## 14. LAPTOP (đề xuất bổ sung — Nox-1, 2026-05-09)

```
Laptop + Hãng + [Tính chất] + Dòng + Mã (CPU, RAM, SSD, [GPU], Màn hình) + [Tình trạng]
```

**Tính chất** (nếu rõ):
- `Gaming`
- `Văn phòng`
- `AI Creator`
- `Đồ họa`

**Spec trong `()` cách bằng `,`:**
- CPU → RAM → SSD → GPU rời → Màn hình → Pin/cổng đặc biệt

**Ví dụ chuẩn:**

```
Laptop Asus Gaming TUF F16 FX607JU-N3139W (i7-13650HX, 16GB, 512GB, RTX 4050, 16'' WUXGA 165Hz)

Laptop Asus Văn phòng VivoBook 15 X1504ZA-NJ070W (i5-1335U, 16GB, 512GB, 15.6'' FHD)

Laptop Lenovo Văn phòng ThinkPad E14 Gen 5 (i5-1335U, 16GB, 512GB, 14'' FHD)

Laptop Acer Gaming Nitro 5 AN515-57 (i5-11400H, 16GB, 512GB, GTX 1650 4GB, 15.6'' FHD 144Hz)

Laptop Apple MacBook Air 13 M2 (8GB, 256GB, Silver)

Laptop Apple MacBook Pro 14 M2 Pro (16GB, 512GB, 10 CPU 16 GPU)

Laptop Dell Inspiron 15 5520 (i5-1235U, 16GB, 512GB, 15.6'' FHD) Cũ Đẹp
```

### Quy ước CPU laptop:

| Hãng | Format chuẩn | Ví dụ |
|---|---|---|
| Intel Core | `iX-mã (chữ i thường, dấu -)` | `i7-13650HX`, `i5-1335U` |
| Intel Core Ultra | `UX-mã` | `U5-125H`, `U7-155H` |
| AMD Ryzen | `Ryzen X-mã` | `Ryzen 5-5500U`, `Ryzen 7-5800H` |
| Apple Silicon | `M[1-4] [Pro/Max/Ultra]` | `M2`, `M3 Pro`, `M4 Max` |

### Quy ước Màn hình:
- Format: `15.6'' FHD 144Hz IPS` hoặc `14'' OLED 2.8K`
- Dùng `''` thay vì "inch" trong tên
- 21.5'' → làm tròn 22''

### Quy ước GPU rời:
- CÓ GPU rời → ghi: `RTX 4050`, `RTX 3060 6GB`, `GTX 1650 4GB`
- KHÔNG GPU rời → BỎ qua (iGPU không ghi vào tên)

### Quy ước Tình trạng:
- Cũ Đẹp → ghi `Cũ Đẹp` cuối tên
- Demo / Hết hàng → ghi `(Demo)` / `(Hết hàng)` cuối
- Mới → KHÔNG ghi (default)

### CẤM ❌:
- Mix nhiều dấu phân cách: `i5 12400P/8GB/15.6"` ⚠️ phải dùng `,` trong `()`
- Viết HOA toàn bộ: `LAPTOP ASUS ROG STRIX G512` ⚠️ chỉ HOA tên riêng
- Thiếu mã hậu tố: `Laptop Asus Vivobook X507UF` ⚠️ phải có spec đầy đủ
- Spec dư: `15.6 inch FHD 144Hz IPS Anti-glare 250 nits` ⚠️ giảm còn `15.6'' FHD 144Hz IPS`
- Bịa thông số → KHÔNG đoán

---

## ✅ Checklist trước khi đăng SP mới:

- [ ] Tên có đúng pattern theo loại SP?
- [ ] Hãng + Model + Mã + Spec quan trọng đủ?
- [ ] Dấu phân cách nhất quán (`,` trong `()`, không mix `|/`)?
- [ ] Chữ HOA chỉ ở tên riêng (Asus, RTX, IPS, FHD)?
- [ ] Spec đã verify từ trang hãng (intel.com, amd.com, lenovo PSREF...)?
- [ ] Màu Trắng ghi rõ; Đen có thể bỏ?
- [ ] Tình trạng "Cũ Đẹp / Demo / Hết hàng" ghi cuối nếu áp dụng?
- [ ] Kích thước màn hình làm tròn (21.5 → 22)?

---

**Khi vợ Nghĩa add SP mới hoặc edit tên SP, tham chiếu file này.**
