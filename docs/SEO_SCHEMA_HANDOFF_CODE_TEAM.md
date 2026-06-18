# HANDOFF — Tối ưu Schema JSON-LD (sintech.vn) cho bộ phận Code/Theme

**Ngày audit:** 17/6/2026 · **Phương pháp:** đọc HTML live (read-only), bóc `<script type="application/ld+json">`, đối chiếu rule Google Product/Article structured data 2025–2026.
**Kết luận chung:** Theme Haravan **đã tự xuất schema nền tốt** (Product, Offer, Brand, BreadcrumbList, Article, WebPage, Organization, Store). KHÔNG cần dựng lại từ đầu — chỉ **bổ sung/sửa vài field** ở mức theme. Không đụng dữ liệu Haravan; tất cả sửa ở **theme Liquid** (hoặc Google Merchant Center cho 1 mục).

---

## Tóm tắt việc cần làm

| # | Vấn đề | Mức độ | Phạm vi | Sửa ở đâu |
|---|--------|--------|---------|-----------|
| 1 | Product thiếu `hasMerchantReturnPolicy` | 🔴 Critical | Mọi SP live | Theme `product` schema **hoặc** Merchant Center |
| 2 | Product thiếu `shippingDetails` | 🔴 Critical | Mọi SP live | Theme `product` schema **hoặc** Merchant Center |
| 3 | Article `datePublished` + `dateModified` **rỗng** | 🟠 High | Mọi blog (4/4 mẫu) | Theme `article` schema (Liquid) |
| 4 | Product chưa có `aggregateRating` / `review` | 🟢 Nice-to-have | Mọi SP | Cần hệ thống đánh giá → để sau |

**Bằng chứng:**
- SP live `…/products/vo-case-jonsbo-c6-max-micro-atx-black` (HTTP 200): có Product+Offer+Brand+sku nhưng **không có** `hasMerchantReturnPolicy`, `shippingDetails`, `aggregateRating`.
- Blog `build-pc-online-la-gi`, `huong-dan-xay-dung-cau-hinh-pc`, `build-pc-15-trieu`, `build-pc-do-hoa`: cả 4 đều có field `datePublished`/`dateModified` nhưng **giá trị rỗng**.
- (Các URL SP `pc-gaming-sin-*` trả 404 = SP ngừng bán, không tính.)

---

## #1 + #2 — Product: return policy & shipping (Critical cho Google Shopping/merchant listing)

Google yêu cầu `hasMerchantReturnPolicy` + `shippingDetails` để SP đủ điều kiện **merchant listing rich result**. Hiện thiếu cả 2.

**2 cách (chọn 1):**

**Cách A — Khai 1 lần trong Google Merchant Center (nhanh, không sửa theme):**
Settings → Shipping and returns → khai chính sách ship + đổi trả chung cho shop. Google áp cho toàn bộ SP, không cần đụng schema. **Khuyến nghị nếu shop dùng Merchant Center.**

**Cách B — Thêm vào Product JSON-LD ở theme** (nếu muốn schema tự đầy đủ). Thêm vào object `offers` đoạn (điền giá trị chính sách THẬT của Sintech):

```json
"hasMerchantReturnPolicy": {
  "@type": "MerchantReturnPolicy",
  "applicableCountry": "VN",
  "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
  "merchantReturnDays": 7,
  "returnMethod": "https://schema.org/ReturnInStore",
  "returnFees": "https://schema.org/FreeReturn"
},
"shippingDetails": {
  "@type": "OfferShippingDetails",
  "shippingDestination": { "@type": "DefinedRegion", "addressCountry": "VN" },
  "deliveryTime": {
    "@type": "ShippingDeliveryTime",
    "handlingTime": { "@type": "QuantitativeValue", "minValue": 0, "maxValue": 1, "unitCode": "DAY" },
    "transitTime":  { "@type": "QuantitativeValue", "minValue": 1, "maxValue": 3, "unitCode": "DAY" }
  }
}
```
> ⚠️ Số ngày đổi trả / phí ship / thời gian giao ở trên là MẪU — điền theo chính sách thật của Sintech.

---

## #3 — Article: điền `datePublished` & `dateModified` (đang rỗng)

Field có trong schema nhưng không có giá trị → Google coi như thiếu, ảnh hưởng "freshness" (rất quan trọng cho cả SEO lẫn AI search). Trong theme `article` (Liquid) map về ngày thật của bài:

```liquid
"datePublished": "{{ article.published_at | date: '%Y-%m-%dT%H:%M:%S%z' }}",
"dateModified": "{{ article.updated_at | date: '%Y-%m-%dT%H:%M:%S%z' }}"
```
(Tên biến tùy theme — cốt lõi: trỏ `datePublished` → ngày đăng, `dateModified` → ngày sửa gần nhất, định dạng ISO 8601.)

---

## Lưu ý kỹ thuật (để khỏi làm thừa)

- **FAQPage / HowTo**: rich result đã bị Google khai tử (HowTo 2023, FAQPage 5-2026). **KHÔNG cần** thêm FAQPage để lấy rich result; nếu muốn giữ cho AI search thì OK nhưng không ưu tiên.
- **Server-render**: schema hiện đã nằm trong HTML server-render (tốt) — giữ nguyên, đừng chuyển sang inject bằng JS.
- Mỗi trang chỉ nên có **1 Product / 1 Article** node, tránh trùng lặp.

## Cách verify sau khi sửa
1. Google **Rich Results Test** (search.google.com/test/rich-results) trên 1 URL SP + 1 URL blog.
2. Hoặc báo lại, marketing tự chạy lại script audit (read-only) đối chiếu.
3. Theo dõi Merchant Center → tab "Sản phẩm" hết cảnh báo thiếu return/shipping.

---
*File do marketing (Nox) soạn từ audit 17/6/2026. Mọi đề xuất chỉ ở mức theme/Merchant Center, không thay đổi dữ liệu sản phẩm/bài viết trên Haravan.*
