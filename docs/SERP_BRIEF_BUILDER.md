# SERP Brief Builder

Trang: **`/seo/serp-briefs`** · Module: `marketing_hub/seo_opportunity.py` (phần SERP) ·
Route: `marketing_hub/routes/seo_opportunity.py`

Mục tiêu: lấy **khuôn bài "inspired-by"** từ top SERP đối thủ — cấu trúc, độ dài, độ phủ chủ đề —
để dựng content brief cho blog/service page. **KHÔNG copy nội dung đối thủ, KHÔNG publish.**

## 2 mode

- **Mode A — Manual URLs ✅ (đang dùng):** nhập keyword + 1–5 URL top SERP. Hệ thống fetch **đúng các
  URL đó** (timeout 12s, retry 0, user-agent rõ ràng) — **không crawl cả site**, không follow link nội bộ.
- **Mode B — Provider (DataForSEO/SerpAPI) 🔒 (disabled):** tự lấy top SERP qua API. **Chưa có
  credential & chưa được duyệt → tắt.** Endpoint `/api/seo/serp-briefs/provider` luôn trả 400
  "API key required" — **không bao giờ gọi API trả phí**.

## Extractor an toàn (`fetch_serp_page`)

Lấy từ mỗi URL: `title, meta_description, h1, h2[], h3[], word_count, image_count, schema_types[],
canonical_url, fetch_status`. Bỏ `script/style/nav/footer/header/aside/form` trước khi đếm chữ/heading.
URL lỗi/timeout/không hợp lệ → ghi `fetch_status` lỗi, **không crash**, các URL khác vẫn chạy.

## Brief tổng hợp

- `avg_word_count / avg_h2_count / avg_image_count` của các trang fetch OK.
- **common_headings**: chủ đề (uni/bi-gram, bỏ stopword) xuất hiện ở **≥2 trang** — đây là khung topic
  cần phủ. *Chỉ tần suất + 1 ví dụ ngắn, không copy nguyên câu.*
- **recommended_outline**: dựng từ common_headings (heuristic).
- **3 title options** (≤60 ký tự, KHÔNG chứa "Sintech") + **3 meta options** (140–160 ký tự).
- **missing_angles**: góc khác biệt Sintech nên khai thác.
- **internal_link_suggestions**: anchor gợi ý (người viết tự gắn URL nội bộ).
- **risk_notes**: tránh copy, tránh bịa giá/FPS/thông số, tránh nhồi keyword.

## AI enhance (optional)

Nút *✨ AI enhance* → `ai_provider.call_ai` (Codex/Claude/Gemini **CLI**, không phải API trả phí) viết
lại outline + title/meta + unique angle + FAQ dựa trên cấu trúc SERP. Hết quota → giữ bản heuristic
(không vỡ). Kết quả chỉ ghi vào brief, **không publish**.

## Export

*⤓ Export .md* → `content_brief_<id>.md` để dán vào quy trình viết.

## DB (additive, idempotent)

- `seo_serp_briefs` — 1 brief / keyword-lần-phân-tích (outline/title/meta/headings… dạng JSON).
- `seo_serp_pages` — chi tiết từng URL đối thủ đã trích.

## API

| Method | Path | Việc |
|---|---|---|
| POST | `/api/seo/serp-briefs/create` | Mode A: `{keyword, urls, keyword_id?}` |
| POST | `/api/seo/serp-briefs/provider` | Mode B stub — luôn 400 (không gọi API trả phí) |
| GET | `/api/seo/serp-briefs` | list brief |
| GET | `/api/seo/serp-briefs/<id>` | chi tiết brief + pages |
| POST | `/api/seo/serp-briefs/<id>/ai-enhance` | AI viết outline/title/meta (optional) |
| GET | `/api/seo/serp-briefs/<id>/export.md` | export markdown |
