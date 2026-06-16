# BLOG PERFORMANCE — P0 RETEST AFTER APPLY (read-only)

> Đo lại 5 bài P0 đã LIVE_VERIFIED (P9.1) để xác nhận tác động content quickwin **trước khi sửa theme**. Read-only · PUT=0 · không sửa theme/website · không commit.

## 1. Before / After (mobile lab + CrUX field)

| P0# | Bài | perf B→A | LCP(ms) B→A | **CLS B→A** | TBT B→A | Field(CrUX) | Result |
|---|---|---|---|---|---|---|---|
| #2 | Cách tải & dùng ChatGPT | 32→43 | 12218→11824 | **0.4563→0.4563** | 594→252 | lcp 1678 cls 0.09 (AVERAGE) | NOISY_LAB |
| #3 | PC bị giật điện | 34→45 | 13085→13361 | **0.2559→0.3906** | 709→208 | lcp 1678 cls 0.09 (AVERAGE) | NOISY_LAB |
| #4 | Trung tâm sửa PC Q7 | 52→48 | 13457→9681 | **0.1261→0.348** | 92→192 | lcp 1678 cls 0.09 (AVERAGE) | NOISY_LAB |
| #6 | Thu mua máy tính cũ | 44→42 | 13352→4935 | **0.4675→0.4675** | 209→476 | lcp 1678 cls 0.09 (AVERAGE) | NOISY_LAB |
| #10 | Top phần mềm test VGA | 38→35 | 12599→8952 | **0.9109→0.9109** | 260→367 | lcp 1678 cls 0.09 (AVERAGE) | NOISY_LAB |

> ⚠️ **Lab 1 lần đo rất nhiễu** (throttle) — perf/LCP dao động ±. Field CrUX giống hệt nhau giữa 5 URL = aggregate origin 28 ngày, **chưa phản ánh apply hôm nay** (CrUX trễ ~28d). Theo spec: ưu tiên CLS/table/image/broken hơn LCP 1 lần đo.

## 2. Verify live content wins (đáng tin hơn lab)

| P0# | HTML legacy | Table responsive | Broken img | script/iframe | competitor | img attrs (live) |
|---|---|---|---|---|---|---|
| #2 | ✅ clean | ✅ overflow-x ×1 | ✅ 0 | ✅ 0 | ✅ 0 | chỉ `src` (alt/loading/dims/style/class bị strip) |
| #3 | ✅ clean | ✅ overflow-x ×1 | ✅ 0 | ✅ 0 | ✅ 0 | chỉ `src` (alt/loading/dims/style/class bị strip) |
| #4 | ✅ clean | ✅ overflow-x ×4 | ✅ 0 | ✅ 0 | ✅ 0 | chỉ `src` (alt/loading/dims/style/class bị strip) |
| #6 | ✅ clean | ✅ overflow-x ×7 | ✅ 0 | ✅ 0 | ✅ 0 | chỉ `src` (alt/loading/dims/style/class bị strip) |
| #10 | ✅ clean | ✅ overflow-x ×1 | ✅ 0 | ✅ 0 | ✅ 0 | chỉ `src` (alt/loading/dims/style/class bị strip) |

**Content wins SỐNG trên live (verified GET):** clean HTML legacy (mso/font=0), table responsive wrapper (`overflow-x` 1/1/4/7/1 khớp số bảng), 0 ảnh chết, 0 script/iframe, 0 competitor. Field title/handle/summary/tags/author/featured KHÔNG đổi (PUT body-only, đã chứng minh QA + backup title/handle khớp).

## 3. Kết luận

- **Content cleanup = thành công & verified live** (HTML sạch + bảng responsive). Đây là phần bài-cụ-thể, đã xong.
- **Perf/LCP lab = NOISY_LAB** — không kết luận mạnh từ 1 lần đo.
- **CLS KHÔNG cải thiện** (gần như y nguyên): layout shift đến từ **ảnh thiếu width/height + theme**, mà Haravan **strip mọi attr img** nên không sửa được ở mức bài → **phải làm ở THEME** (xem file strip findings).
- Muốn thấy cải thiện THẬT: chờ CrUX cập nhật (~28d) **sau khi theme set img dimensions + lazy + preload hero**.

## 4. Exports
- BLOG_PERFORMANCE_P0_RETEST_AFTER_APPLY.md
- blog_performance_p0_retest_after_apply.csv
- blog_performance_haravan_body_strip_findings.md

## Safety
read-only · PUT=0 · upload=0 · theme edits=0 · no commit/push/deploy