# Phân tích pattern SEO đối thủ (minhtuanmobile.com) — học, không copy

> Crawl 21/5/2026 — 99 URL: 7 collection + 40 product + 52 news. Chỉ rút **pattern cấu trúc**, không lưu/copy nội dung. Tên đối thủ KHÔNG được đưa vào bài public của Sintech.

## Số liệu nền (độ dài thực tế)

| Loại | n | Title TB (min–max) | Meta TB (min–max) | Có CTA | Schema |
|---|---|---|---|---|---|
| Collection | 7 | 59.9c (47–70) | 144.4c (119–163) | 3/7 | BreadcrumbList |
| Product | 40 | 53.8c (43–60) | 128.6c (118–139) | 4/40 | Product (30) / Product+FAQPage (10) |
| News | 52 | 58.5c (40–70) | 132.2c (89–160) | 13/52 | BreadcrumbList (KHÔNG có Article) |

## 10 pattern TITLE phổ biến nhất

1. `[Tên]` trơn — chỉ tên SP/bài, 0 USP — **43 lần** (đa số product + news)
2. `[Tên] - [nội dung]` (gạch nối, không USP) — 13
3. `[Tên]: [nội dung]` (hai chấm, news) — 7
4. `[Tên SP] - giá rẻ/tốt` — 6
5. `[Tên SP] giá rẻ/tốt` (không sep) — 4
6. `[Tên] ưu đãi/sốc/sale` — 4
7. `[Tên SP] chính hãng` — 3
8. `[Tên SP] - chính hãng + giá rẻ` — 3
9. `[Tên], [nội dung]` (phẩy, news) — 3
10. `[Tên SP] chính hãng + giá rẻ` — 2

**Riêng collection** (mẫu rõ nhất): `[Loại SP] [Brand] + [3 USP: giá rẻ/tốt · trả góp 0% · chính hãng (· bảo hành 1 đổi 1)]`. USP nhồi vào title: giá rẻ 6/7, trả góp 6/7, chính hãng 6/7.

## 10 pattern META phổ biến nhất

1. `USP=none · CTA=no` — 34 (chủ yếu news + 1 ít product)
2. `chính hãng + bảo hành/1 đổi 1 · CTA=no` — 21 (product chủ đạo)
3. `USP=none · CTA=yes` — 10 (news có nút Xem thêm)
4. `bảo hành + giá rẻ + trả góp 0% · CTA=no` — 5
5. `chính hãng + miễn phí/giao nhanh · CTA=yes` — 4
6. `bảo hành + chính hãng + ưu đãi/sale · CTA=no` — 3
7. `chính hãng · CTA=no` — 2
8. `chính hãng + miễn phí/giao nhanh · CTA=no` — 2
9. `ưu đãi/sale · CTA=yes` — 2
10. `ưu đãi/sale · CTA=no` — 2

Tần suất USP trong meta product: **chính hãng 33/40, bảo hành 30/40**, giá rẻ 7, trả góp 6, miễn phí 6. Collection meta thường mở đầu bằng "Mua [SP]…" và nhồi 4–5 USP.

## Rule riêng — COLLECTION

- Title 47–70c (TB ~60), nhồi **3 USP cố định**: giá rẻ/tốt + trả góp 0% + chính hãng, đôi khi thêm "bảo hành VIP 1 đổi 1".
- Meta mở đầu **"Mua [loại SP] chính hãng…"**, liệt kê USP dồn dập, kết bằng CTA mạnh ("Mua ngay!").
- H2 collection theo blueprint: *Phân loại [SP]* → *Các dòng [SP]* → *Bảng giá [SP] mới nhất* → *Kinh nghiệm chọn mua* → *[SP] nào đáng mua* → *Vì sao mua tại [shop]* → cụm FAQ ("… là gì?", "khác nhau thế nào?"). Heading taxonomy + câu hỏi volume cao.
- Chỉ có BreadcrumbList schema — **không** có ItemList/CollectionPage.

## Rule riêng — PRODUCT

- Title ngắn gọn 43–60c (TB ~54), **ưu tiên TÊN SP + cấu hình/dung lượng**; USP rất tiết chế (≈40% thêm "giá rẻ", ít thêm "chính hãng"). Không nhồi USP như collection.
- Meta ngắn 118–139c (TB ~129), gần như luôn có **"chính hãng" + "bảo hành/1 đổi 1"**; phần lớn **KHÔNG có CTA** (chỉ 4/40).
- Có **Product schema** (30/40), 1/4 thêm **FAQPage** → ăn rich snippet.

## Rule riêng — NEWS/BLOG

- Title dạng **topical thuần**, 40–70c, không USP bán hàng — viết theo nhu cầu đọc: tin (23), khuyến mãi (8), hướng dẫn (8), so sánh (7), review (6).
- Meta 89–160c, đa số không CTA; bài khuyến mãi thì chèn CTA + ưu đãi.
- Title dùng số/ngoặc kép gây tò mò ("…iOS 26.5 Beta 1 'bản mới'", "6 smartphone…").
- **KHÔNG có Article/NewsArticle schema** — điểm yếu của họ.

## Điều Sintech NÊN học

1. **Collection nhồi USP có chủ đích vào title** (giá tốt · trả góp · chính hãng/bảo hành) — Sintech hiện title collection còn trơn.
2. **Blueprint H2 taxonomy + FAQ "… là gì / khác nhau thế nào"** cho collection → đúng hướng Sintech đã làm (note 20/5), nên chuẩn hoá thành khung cố định.
3. **Product gắn Product + FAQPage schema** để ăn rich snippet (giá, sao, FAQ) — đòn bẩy CTR lớn.
4. **Meta product luôn có "chính hãng + bảo hành"** như tín hiệu tin cậy — Sintech áp dạng "chính hãng + BH + hỗ trợ kỹ thuật".
5. **News title topical theo intent** (hướng dẫn/so sánh/review), không nhồi bán hàng.

## Điều Sintech KHÔNG nên học

1. **Title/meta trơn không USP & không CTA** ở phần lớn product (CTA chỉ 4/40) — bỏ phí CTR. Sintech giữ CTA HOA cuối meta là đúng.
2. **Nhồi quá nhiều USP** kiểu "giá rẻ + sốc + 0% + 1 đổi 1 + miễn phí" trong 1 meta → loãng, spammy.
3. **Lạm dụng "giá rẻ/giá tốt/sốc"** — đụng filler Sintech đã cấm ("rẻ nhất", "sốc"…). Giữ nguyên cấm filler.
4. **News thiếu Article schema** — Sintech nên thêm để hơn họ.
5. Tiêu đề kiểu "đáng mua nhất" — trùng filler Sintech cấm.

## Prompt rule đề xuất thêm vào SEO writer (generic, KHÔNG nêu tên đối thủ)

**Collection — title:**
> Title collection nên có cấu trúc `[Loại SP] [Thương hiệu] + 2 tín hiệu tin cậy` (vd: chính hãng · bảo hành), 48–60 ký tự. KHÔNG nhồi quá 2 cụm lợi ích; CẤM "giá rẻ nhất/sốc/đáng mua nhất".

**Collection — H2 blueprint cố định:**
> Bắt buộc khung H2: Phân loại [SP] → Các dòng [SP] → Bảng giá [SP] mới nhất → Kinh nghiệm chọn mua → [SP] nào phù hợp → 2–3 câu hỏi FAQ ("[khái niệm] là gì?", "A và B khác nhau thế nào?").

**Product — meta:**
> Meta product 140–160c (Sintech dài hơn đối thủ để đủ ý), BẮT BUỘC nêu "chính hãng" + 1 cam kết (bảo hành/hỗ trợ kỹ thuật), kết bằng đúng 1 CTA HOA. KHÔNG dồn >2 cụm lợi ích.

**Product — schema:**
> Khi gen/sync product, chèn JSON-LD `Product` + (nếu có FAQ) `FAQPage` để ăn rich snippet — lợi thế đối thủ đang có.

**News/blog:**
> Title bài viết theo intent (hướng dẫn / so sánh / đánh giá / tin), 50–65c, được dùng số + ngoặc kép gây tò mò; KHÔNG chèn USP bán hàng. Thêm JSON-LD `Article` (đối thủ đang thiếu).
