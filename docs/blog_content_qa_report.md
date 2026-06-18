# Blog SEO Command Center — QA Report (2026-06-16)

## compileall
`py -3.12 -m py_compile app.py blog_content_center.py routes/blog_content_center.py routes/content_blog.py` → **OK**.
Module import OK (13 statuses, 40 items).

## Smoke test (server live :5055, sau restart)
| Kết quả | Endpoint |
|---|---|
| 200 | `/blog-content` (Command Center) |
| 200 | `/api/blog-content/status` |
| 200 | `/api/blog-content/items` |
| 200 | `/api/blog-content/items/1` |
| 200 | `/api/blog-content/kanban` |
| 200 | `/api/blog-content/calendar` |
| 200 | `/api/blog-content/kpi` |
| 302 → /blog-content | `/seo/blog-rewrite-ai` (archived redirect, không crash) |
| 200 | `/` , `/blog-pillars` , `/collection-content` , `/seo/title-meta` (trang cũ KHÔNG vỡ) |

## Functional
- Import roadmap: lần 1 = **40 imported**; lần 2 = **0 imported / 40 updated / 0 duplicate** → idempotent ✅
- Chỉ source roadmap: `blog_content_items` query `source='roadmap'` = 40 ✅
- set status (writing) → 200 ✅ · set owner → 200 ✅ · set deadline → endpoint OK ✅
- generate-brief → ok=true, 18 keys, **không gọi AI, không PUT Haravan** ✅
- export CSV → header + dữ liệu đúng ✅
- **sync GATED:** confirm sai → HTTP 400 `FILES_GATE`, **0 PUT Haravan** ✅
- drawer load item → full brief ✅

## An toàn (đối chiếu hard rules)
| Mục | Trạng thái |
|---|---|
| DB cũ preserved | ✅ candidates 233 · drafts 476 · events 3537 · blog_jobs 120 |
| no Haravan PUT khi generate/brief | ✅ |
| sync gated confirm | ✅ (sai phrase chặn) |
| no theme edit | ✅ |
| no scheduler bật thêm | ✅ |
| no commit/push/deploy | ✅ |
| no drop/truncate | ✅ |
| migration additive/idempotent | ✅ (CREATE IF NOT EXISTS, import theo roadmap_id) |
| rollback được | ✅ (backup đầy đủ + bảng mới drop được an toàn) |

## Ghi chú
- generate-draft (gọi Codex) + sync thật (PUT Haravan) CHƯA chạy trong QA (tránh tốn quota / đụng live) — code path đã verify đến sát điểm gọi; vợ tự bấm khi cần.
- Data test trên BLG-001 (status/owner/brief) đã reset về gốc sau QA.
