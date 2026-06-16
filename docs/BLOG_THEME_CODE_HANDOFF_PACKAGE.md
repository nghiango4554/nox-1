# BLOG THEME — CODE HANDOFF PACKAGE (giao bộ phận code)

> Tài liệu **tự-chứa** cho bộ phận code. Gộp: (A) phát hiện Haravan strip attr img, (B) việc theme cần làm, (C) bài blog ưu tiên, (D) cách QA + rollback. **Tất cả read-only từ phía audit — bộ phận code là nơi sửa theme.** KHÔNG ai được sửa nội dung từng bài cho mấy việc này (đã chứng minh body PUT bị strip).
>
> Nguồn: P9 (audit) → P9.1 (apply content live 5 bài) → retest. Chi tiết kèm: `blog_performance_haravan_body_strip_findings.md`, `BLOG_TEMPLATE_CODE_HANDOFF.md`, `blog_template_global_issues.md`, `BLOG_PERFORMANCE_P0_RETEST_AFTER_APPLY.md`.

---

## 0. TL;DR (đọc cái này trước)

- Đã làm xong phần **content-level** cho 5 bài P0 (clean HTML legacy + table responsive) và **apply live thành công, verified**.
- **NHƯNG**: đo lại cho thấy **CLS không cải thiện**. Lý do: layout shift đến từ **ảnh thiếu `width/height`** và **theme**, mà khi PUT `body_html` qua API thì **Haravan strip SẠCH mọi attribute của `<img>` (chỉ giữ `src`)** — kể cả `loading`, `width`, `height`, `fetchpriority`, `alt`.
- ⇒ **Mọi tối ưu ảnh + JS/CSS toàn site PHẢI làm ở THEME.** Không thể xử ở article body. Đây là toàn bộ việc giao bộ phận code dưới đây.
- Ưu tiên cao nhất: bài **#CS2 (8 clicks/tuần — traffic blog cao nhất)** đang CLS 0.47 — chỉ theme mới cứu được.

---

## A. Haravan body_html stripping findings (bằng chứng thực nghiệm)

Apply thật `body_html` qua Open API rồi GET lại live, so từng attribute:

| Phần tử | Attribute | Kết quả | Bằng chứng |
|---|---|---|---|
| `<img>` | `src` | ✅ **GIỮ** | live: `<img src="//cdn.hstatic.net/200000860097/file/..._grande.png">` |
| `<img>` | `alt` | ❌ **STRIP** | draft có alt → live 0 alt |
| `<img>` | `loading="lazy"` | ❌ **STRIP** | draft 10 ảnh lazy → live 0 |
| `<img>` | `fetchpriority="high"` | ❌ **STRIP** | draft hero có → live 0 |
| `<img>` | `width` / `height` | ❌ **STRIP** | live 0 → đây là gốc CLS không sửa được ở body |
| `<img>` | `style` / `class` | ❌ **STRIP** | live 0 |
| `<div>` | `style` (overflow-x wrapper) | ✅ **GIỮ** | live giữ `<div style="overflow-x:auto;-webkit-overflow-scrolling:touch">` |
| `<table>/<td>/<th>` | `style` (border, width) | ✅ **GIỮ** | live giữ `border-collapse`, border `td` |
| text, `<h2>/<h3>/<p>/<ul>`, internal link | — | ✅ **GIỮ** | cấu trúc + link nội bộ giữ nguyên |

**Kết luận:** sanitizer body_html của Haravan **giữ `<img src>` DUY NHẤT** (drop mọi attr img khác), nhưng **giữ `style` trên block/table**. Ngoài ra đổi URL ảnh `https://` → protocol-relative `//`.

**Hệ quả:**
- **CLS** ↑: ảnh không `width/height` → reflow khi ảnh load. *(retest: CLS 5 bài đứng yên/nhích, không giảm.)*
- **LCP** chậm: không set được `fetchpriority`/preload hero ở body.
- **Tải thừa**: không `loading=lazy` được ảnh dưới fold.
- **Image SEO/a11y**: `alt` mất khi PUT body.

---

## B. Việc theme cần làm (mỗi việc có evidence · phạm vi · rủi ro · QA · rollback)

### B1. Tự bổ sung attribute cho ảnh khi RENDER (gốc rễ — fix luôn alt/dims/lazy)
- **Vì sao**: body không giữ được attr img → phải để **theme inject lúc render** (Liquid hậu xử lý `article.content`, hoặc JS on-load). Theme render SAU sanitizer nên attr sẽ sống.
- **Làm**: trong template bài viết, parse `article.content`, với mỗi `<img>`:
  - thêm `loading="lazy"` cho ảnh **dưới fold** (KHÔNG cho ảnh đầu/hero = LCP),
  - thêm `width`/`height` (hoặc bọc container `aspect-ratio`) để khử CLS,
  - thêm `fetchpriority="high"` cho ảnh hero.
- **Evidence**: mục A (Haravan strip). **Phạm vi**: blog template (≈230 bài). **Rủi ro**: Trung bình (đụng render). **QA**: GET 1 bài → xác nhận img có `width/height/loading`; đo CLS `/seo/cwv`. **Rollback**: revert file template.

### B2. width / height / aspect-ratio cho ảnh blog (khử CLS) — *handoff #5*
- **Evidence**: ảnh thiếu dimension → CLS risk; retest CLS không giảm. **Phạm vi**: blog template. **Rủi ro**: Thấp. **QA**: đo CLS đợt sau. **Rollback**: revert CSS.

### B3. Lazy-load ảnh dưới fold trong template — *handoff #4*
- **Evidence**: nhiều ảnh thiếu `loading=lazy` (body PUT không giữ). **Giữ ảnh LCP KHÔNG lazy.** **Phạm vi**: blog template. **Rủi ro**: Thấp. **QA**: xác nhận ảnh dưới fold lazy, hero không lazy. **Rollback**: bỏ thuộc tính.

### B4. Preload + fetchpriority=high cho ảnh hero blog — *handoff #3*
- **Evidence**: hero là phần tử LCP. **Phạm vi**: blog template (`<head>` lấy ảnh đầu article). **Rủi ro**: Thấp. **QA**: LCP element load sớm hơn. **Rollback**: bỏ thẻ preload.

### B5. Giảm unused JavaScript (defer/async + tách theo trang) — *handoff #1*
- **Evidence**: Lighthouse mobile opp #1 ~**1.57s**/trang. **Phạm vi**: ~230 blog. **Rủi ro**: Trung bình. **QA**: so Perf mobile trước/sau `/seo/cwv` đợt mới. **Rollback**: revert file JS.

### B6. Giảm unused CSS + critical CSS path — *handoff #2*
- **Evidence**: opp ~193ms; FCP ~3.5s hằng số. **Phạm vi**: ~230 blog. **Rủi ro**: Trung bình. **QA**: đo FCP/Perf đợt sau. **Rollback**: revert asset CSS.

### B7. Cache/CDN giảm TTFB — *handoff #6*
- **Evidence**: server-response-time ~386ms ở ~nửa mẫu. **Phạm vi**: nhiều trang. **Rủi ro**: Trung bình. **QA**: đo TTFB. **Rollback**: tắt rule cache.

> Render-blocking / FCP ~3.5s hằng số toàn site = hệ quả của B5+B6 (xử chung).

---

## C. Bài blog ưu tiên (đối chiếu khi sửa theme)

**P0 theme-only (chỉ theme cứu được, KHÔNG sửa content):**
| Bài | article_id | Traffic | CLS | Ghi chú |
|---|---|---|---|---|
| Cấu hình chơi CS2 | 1002399773 | **8 clk/9 ses** | 0.472 | **Traffic blog cao nhất — ưu tiên #1** |
| Gắn quạt tản nhiệt PC | 1002420376 | 0/3 | 0.767 | ảnh thiếu dims + lazy |
| Lỗi Command Prompt | 1002414345 | 0/3 | 0.792 | CLS layout |

**5 bài đã apply content (cần theme cho phần CLS còn lại):**
1002794878 (ChatGPT) · 1002753568 (PC giật điện) · 1002398567 (Sửa PC Q7) · 1002404456 (Thu mua máy cũ) · 1002792621 (Test VGA).
→ Content đã sạch + bảng responsive (live). **Phần CLS/LCP còn lại = B1–B4 (theme).**

> Lưu ý phối hợp: phần **ảnh nặng cần resize** (#3 hero 360KB, #10 2 ảnh ~350KB) và **ảnh đối thủ cần thay** (#7 GTA5) là việc **content/image team**, KHÔNG phải theme — nằm ở `blog_performance_p0_image_execution_tasks.csv`.

---

## D. Acceptance / cách nghiệm thu sau khi code sửa

1. **Verify attr sống**: GET 1 bài bất kỳ → `<img>` phải có `width/height` + `loading` (ảnh dưới fold) + hero `fetchpriority`.
2. **Đo lại CWV**: chạy quét mới ở `/seo/cwv` (mobile→desktop) → so timeline `/seo/history` với mốc hiện tại. Kỳ vọng **CLS giảm rõ** ở nhóm bài nhiều ảnh.
3. **Field CrUX**: số liệu người-dùng-thật trễ ~28 ngày — đừng kỳ vọng đổi ngay, theo dõi sau 2–4 tuần.
4. **Lab nhiễu**: 1 lần đo lab dao động mạnh; nhìn xu hướng nhiều bài + CLS, không bắt 1 con số LCP.
5. **Rollback**: mỗi việc revert file theme/asset tương ứng (đã ghi từng dòng ở mục B).

---

## Safety
read-only (phía audit) · PUT Haravan = 0 · upload = 0 · theme edits = 0 (bộ phận code thực hiện) · no commit/push/deploy.
