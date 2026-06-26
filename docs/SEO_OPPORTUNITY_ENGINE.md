# SEO Keyword Opportunity Engine

Trang: **`/seo/opportunities`** · Module: `marketing_hub/seo_opportunity.py` · Route: `marketing_hub/routes/seo_opportunity.py`

Mục tiêu: gom keyword cơ hội từ nhiều nguồn → chấm `opportunity_score` **giải thích được** →
phân loại page_type + status để feed sang content brief / blog. **Không publish, không PUT Haravan,
không gọi API trả phí.**

## Nguồn dữ liệu

1. **GSC (data thật)** — nút *Sync từ GSC*. Aggregate `gsc_queries_daily` (search_type=web) trong N
   ngày: SUM clicks/impressions, position bình quân theo impression, CTR. `source=gsc`. KD/volume để
   NULL (GSC không có).
2. **Import CSV** — từ SEMrush / Ahrefs / Google Keyword Planner / DataForSEO / sheet thủ công.
   Header nhận diện case-insensitive + alias (xem `_CSV_ALIASES`). **Thiếu cột vẫn import được.**
   Cột hỗ trợ: `keyword, volume, keyword_difficulty, cpc, intent, serp_features, source, country,
   language, topic, note`. File mẫu: `docs/seo_keyword_opportunity_sample.csv`.

> Không bịa KD/volume: thiếu dữ liệu → để trống (NULL), component score tương ứng = 0.

## Opportunity score (0–100, transparent)

```
opportunity_score = intent_weight + volume_weight + low_difficulty_weight
                  + position_weight + ctr_gap_weight + priority_weight
                  - cannibalization_risk - too_broad_penalty
```

| Component | Khoảng | Ý nghĩa |
|---|---|---|
| intent_weight | 0–20 | transactional 20 · commercial 16 · informational 10 · navigational 4 |
| volume_weight | 0–25 | log10(max(volume, gsc_impressions)) — nhu cầu |
| low_difficulty_weight | 0–20 | (100−KD)/100 · 20; không có KD → 0 |
| position_weight | 0–20 | striking distance: pos 4–10 = 20, 11–20 = 15, ≤3 = 4 (đã top) |
| ctr_gap_weight | 0–10 | pos tốt nhưng CTR < kỳ vọng → cần sửa title/meta |
| priority_weight | 0–10 | ưu tiên business nhập tay (high/medium/low) |
| cannibalization_risk | −0…10 | nhiều keyword cùng target URL (reserved) |
| too_broad_penalty | −0…8 | keyword 1 từ thường quá rộng/khó |

Bấm vào số score trên UI → popup breakdown từng thành phần. Score tự recompute khi đổi
intent/priority/status.

## Phân loại

- **page_type** (gợi ý tự động, sửa tay được): `blog_info, blog_commercial, service_page,
  collection_page, product_page, faq, ignore`.
- **status**: `new → review → approved → brief_ready → writing → published → monitoring → ignored`.

## Thao tác UI

- Lọc theo source / intent / status / page_type + search + sort theo score/volume/impressions/position.
- Sửa nhanh page_type & status inline (dropdown trong bảng).
- **Create SERP Brief** → nhập 1–5 URL → tạo brief (sang `/seo/serp-briefs`), keyword → `brief_ready`.
- **→ Blog** (send-to-blog): **SAFE** — chỉ set `approved` + ghi note "→ blog queue (draft)".
  **KHÔNG tạo content job live, KHÔNG publish.** Người vận hành tự kéo sang `/blog-content` khi viết thật.
- **Export CSV** toàn bộ keyword.

## DB (additive, idempotent — `ensure_schema()` gọi mỗi request)

- `seo_keyword_opportunities` — unique `(normalized_keyword, source, country, language)`.
- `seo_keyword_import_batches` — log mỗi lần import/sync.

## API

| Method | Path | Việc |
|---|---|---|
| GET | `/api/seo/opportunities` | list (filters: source/intent/status/priority/page_type/q/sort/limit) |
| POST | `/api/seo/opportunities/import-csv` | import file `file` hoặc field `text` |
| POST | `/api/seo/opportunities/sync-gsc` | sync GSC (days, min_impressions) |
| POST | `/api/seo/opportunities/<id>/update` | đổi status/priority/page_type/topic/notes/intent |
| GET | `/api/seo/opportunities/<id>/score` | breakdown score |
| POST | `/api/seo/opportunities/<id>/send-to-blog` | đánh dấu approved (draft, không publish) |
| GET | `/api/seo/opportunities/export.csv` | export |
