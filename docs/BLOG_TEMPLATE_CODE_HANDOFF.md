# BLOG TEMPLATE — CODE HANDOFF (chỉ đề xuất, CHƯA sửa)

Phạm vi: 230 blog đã crawl. Read-only audit. KHÔNG sửa theme/Haravan/deploy.

| # | Đề xuất | Evidence | URL mẫu | Số trang ảnh hưởng | Rủi ro | QA | Rollback |
|---|---|---|---|---|---|---|---|
| 1 | Giảm unused JavaScript (defer/async + tách theo trang) | Lighthouse mobile opp #1 ~1.57s/trang | https://sintech.vn/blogs/news/intel-gaudi-3-chinh-thuc-co-mat-tren-ibm-cloud-hieu-suat-vuot-nvidia | ~230 blog | Trung bình | So Perf mobile trước/sau ở /seo/cwv (đợt quét mới) | Giữ bản theme cũ, revert file JS |
| 2 | Giảm unused CSS + critical CSS path | opp ~193ms; FCP ~3.5s hằng số | (mọi blog) | ~230 blog | Trung bình | Đo FCP/Perf đợt sau | Revert asset CSS |
| 3 | Preload + fetchpriority=high cho ảnh hero blog | Hero là phần tử LCP của bài | top30 traffic | blog template | Thấp | Kiểm tra LCP element giảm | Bỏ thẻ preload |
| 4 | Lazy-load mặc định ảnh dưới fold trong template | Nhiều bài ảnh thiếu loading=lazy | content quickwins list | blog template | Thấp | Xác nhận ảnh dưới fold lazy | Bỏ thuộc tính |
| 5 | Auto width/height/aspect-ratio cho ảnh blog | Ảnh thiếu dimension → CLS risk | CLS_LAYOUT_RISK list | blog template | Thấp | Đo CLS đợt sau | Revert CSS |
| 6 | Cache/CDN giảm TTFB | server-response-time ~386ms | HIGH_TTFB list | 0 trang TTFB>600ms | Trung bình | Đo TTFB | Tắt rule cache |
