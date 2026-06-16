# Blog — Global Template Issues (toàn site, KHÔNG quy lỗi từng bài)

Các vấn đề dưới đây xuất hiện đồng đều ở MỌI blog → nguyên nhân là **theme/template chung**, không phải nội dung từng bài. Sửa 1 chỗ ăn toàn bộ blog.

| Vấn đề | Bằng chứng | Phạm vi | Đề xuất |
|---|---|---|---|
| TEMPLATE_GLOBAL_JS (unused JavaScript) | Lighthouse mobile opp #1, ~1.57s tiết kiệm/trang | ~toàn bộ 230 blog | defer/async JS theme, tách JS theo trang |
| TEMPLATE_GLOBAL_CSS (unused CSS) | Lighthouse opp, ~193ms | ~toàn bộ 230 blog | tách critical CSS, bỏ CSS thừa |
| Render-blocking (FCP đều ~3.5s) | FCP mobile-lab gần như hằng số mọi trang | ~toàn bộ 230 blog | critical CSS path, preconnect |
| HIGH_TTFB | server-response-time opp ~386ms ở ~nửa mẫu | nhiều trang | cache/CDN |

> Lab Lighthouse khắc nghiệt (bóp CPU 4x). Field CrUX (người dùng thật) mobile LCP ~1.68s = TỐT. Các fix global cải thiện điểm lab + biên an toàn field.
