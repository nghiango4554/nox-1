# BLOG REWRITE AI — P1 AUDIT & IMPORT (10/6/2026)

> Build theo spec `Desktop\Past.txt`. P1 = schema + import scan + priority + read-only API + candidate page. **KHÔNG gọi AI · KHÔNG PUT Haravan · KHÔNG upload ảnh · KHÔNG commit/push/deploy.** Dừng sau P1 để review.

## 1. Audit feasibility

| Hạng mục | PASS | PARTIAL | BLOCKER | Ghi chú |
|---|:--:|:--:|:--:|---|
| scan files | ✓ | | | 4 CSV + MD ở `docs/`; nguồn chân lý import = fetch Open API live (có `article_id`) |
| dedup key | ✓ | | | `article_id` (UNIQUE) → URL → handle |
| GSC join | ✓ | | | `gsc_ga4_join_daily` theo `normalized_path` (data 7 ngày: 28/5–3/6) |
| GA4 organic join | ✓ | | | cùng bảng, cột `ga4_organic_sessions` |
| Haravan article read | ✓ | | | Open API GET `/web/blogs/{id}/articles` 200 (admin API 502 — không dùng) |
| Haravan article PUT design | | ✓ | | Open API PUT verified (lúc gỡ link); P1 KHÔNG PUT — chỉ thiết kế |
| SEO meta support | | ✓ | | article meta endpoint chưa chứng minh → P3 lưu suggestion local, không bịa endpoint |
| image rehost workflow | ✓ | | | reuse `sync_collection_images.upload_asset` (Theme Assets, resize 600px); rehost thật để P3/P4 |
| sanitizer | | ✓ | | bleach/nh3 KHÔNG có; bs4+lxml CÓ → whitelist sanitizer bằng bs4 ở P3 (không thêm dep P1) |
| AI provider adapter | ✓ | | | `ai_provider.call_ai` / `call_ai_single` reuse; chốt provider + model ở P3 |
| worker convention | ✓ | | | `worker.py` + jobs queue + `sys.executable` pattern reuse cho `run_blog_rewrite_worker.py` (P3) |

→ **KHÔNG có blocker nghiêm trọng** (candidate source ✓, dedup key ✓, migration additive an toàn ✓, kiến trúc cho thêm module ✓) → build P1.

## 2. Counts (sau dedup, từ import live)
Raw 233 bài → 233 candidate unique (dedup theo `article_id`).

| Nhóm (source_group_primary) | Unique | Risk |
|---|---:|---|
| competitor_cdn | 29 | high |
| bizweb_sapo (dktcdn 329122) | 56 | high |
| vn_tech_media | 26 | high |
| foreign_tech_media | 28 | high |
| **→ tổng high** | **139** | |
| google_docs_youtube | 9 | medium |
| strange_host | 6 | review |
| text_only | 79 | unknown |

Traffic join: GSC match **131/233**, GA4 organic match **35/233**, no_traffic_data **100** (badge "chưa có traffic data"). Selected mặc định = 139 (high=true, còn lại=false).

## 3. Migration (additive, idempotent)
`db.py` SCHEMA thêm 4 bảng `CREATE TABLE IF NOT EXISTS` + 12 index `CREATE INDEX IF NOT EXISTS`:
`blog_rewrite_candidates` · `blog_rewrite_jobs` · `blog_rewrite_drafts` · `blog_rewrite_events`.
- `init_db()` chạy 2 lần KHÔNG lỗi (idempotent ✓). Không drop/truncate/sửa bảng cũ.

## 4. Import service — `blog_rewrite.py`
- `build_candidates(dry_run)`: fetch Open API → `_classify` (host ảnh ngoài) → content_hash → traffic join → priority → upsert.
- Priority = `risk_weight(high100/med40/rev20/unk10)` + `10·log10(1+clicks)+3·log10(1+impr)+8·log10(1+sessions)` (minh bạch, dễ audit).
- Idempotent: re-import GIỮ status/selected nếu candidate đã tiến triển (status ∈ queued/draft_ready/applied...); chỉ refresh classification + traffic.
- dry_run mặc định True (không ghi DB). Verify: dry-run DB=0 rows → apply 233 → rerun vẫn 233 (không nhân đôi).

## 5. Routes / API (read-only) — `routes/blog_rewrite.py`
- Page: `/seo/blog-rewrite-ai` (endpoint `seo_blog_rewrite_page`).
- `GET /api/blog-rewrite/status` · `GET /api/blog-rewrite/candidates` (filter/sort/paginate) · `GET /api/blog-rewrite/candidates/<id>` · `POST /api/blog-rewrite/import-scan` (dry_run mặc định; ghi DB local khi apply) · `GET /api/blog-rewrite/export` (CSV).
- import-scan KHÔNG ghi Haravan, KHÔNG gọi AI.

## 6. UI — `templates/blog_rewrite_ai.html`
Header + 8 KPI + nút (Dry-run/Import/Export/Refresh) + filter (risk/traffic/sort/search/only-selected) + bảng candidate + detail panel. Nút Generate/Approve/Apply/Rollback **disabled, gắn nhãn P3/P4/P5**. Sidebar SEO thêm "✍️ AI Viết Lại Blog".

## 7. Files
- **NEW**: `blog_rewrite.py`, `routes/blog_rewrite.py`, `templates/blog_rewrite_ai.html`, doc này.
- **MOD**: `db.py` (4 bảng), `app.py` (import+register), `templates/base.html` (sidebar link).
- **Backup**: `_backup/blog-rewrite-p1-20260610-143116/` (db.py, app.py, base.html + CHANGED_FILES.txt).

## 8. QA
- `compileall`: OK. Migration rerun: idempotent OK. Import dry-run/apply/rerun: dedup OK (233 không đổi).
- Smoke (sau restart Flask PID 5452): `/seo/blog-rewrite-ai` 200 · `/api/blog-rewrite/status` 200 · `/candidates` 200 · `/export` 200.
- Broken-link config **KHÔNG đổi**: workers 48 · hstatic 8 · default 4 · HEAD 2s.
- Secret scan: KHÔNG hardcode token (đọc từ `state/haravan_token.json`). node --check: N/A (JS inline trong Jinja template, không file .js riêng).
- KHÔNG gọi AI · KHÔNG PUT Haravan · KHÔNG upload ảnh trong toàn bộ P1.

## 9. Deferred
- **P2**: bulk-select UI + candidate selected toggle persist + jobs list.
- **P3**: worker `run_blog_rewrite_worker.py` (sys.executable, lock/heartbeat/cancel) + prompt `BLOG_REWRITE_PROMPT_V1` + provider AI + parser JSON + sanitize bs4 whitelist + quality metrics (5-gram overlap...) + image rehost (upload_asset).
- **P4**: review UI + diff original↔draft + approve/reject.
- **P5**: apply (conflict check qua content_hash + fetch live + backup payload + PUT Open API) + rollback per-bài + audit events.

## OUTPUT
**BLOG REWRITE AI P1 COMPLETED** · 233 candidate (139 high / 9 medium / 6 review / 79 unknown) · GSC 131 / GA4 35 / no-traffic 100 · 4 bảng + 12 index · 5 API + 1 page · QA PASS · broken-link config untouched · no AI / no PUT / no image upload / no commit / no push / no deploy / no browser.
