# Blog SEO Command Center — ALL IN ONE (Report)

> Ngày 2026-06-16. Đập đi xây lại `/blog-content` thành Blog SEO Command Center quản lý 40 bài roadmap. Trang AI Viết Lại Blog cũ archive. Additive, idempotent, rollback được. KHÔNG drop DB / commit / push / deploy / sửa theme / publish hàng loạt.

## Tổng quan
- Route giữ nguyên: **`/blog-content`** → nay là Command Center, chỉ hiển thị **40 bài roadmap** (`source='roadmap'`).
- Nguồn: `docs/ke_hoach_blog_seo_sintech_gsc_16m_3m.xlsx` (copy từ Downloads).
- Trang/job blog-content cũ (`blog_jobs`, 120 dòng) + Blog Rewrite (`blog_rewrite_*`) **giữ archive, không drop**.

## 1. Archive Blog Rewrite AI
- **Worker:** không có rewrite worker chạy nền (đã kiểm) → không cần kill.
- **Route/nav:** gỡ `routes_blog_rewrite.register` + import khỏi `app.py`; gỡ 3 nav link (base.html + redesign_base.html).
- **Route cũ `/seo/blog-rewrite-ai`:** giữ endpoint `seo_blog_rewrite_page` dạng **redirect 302 → /blog-content** (không crash, không 404 cho link cũ).
- **Module/template:** `blog_rewrite*.py` + `blog_rewrite_ai.html` để nguyên trên đĩa (không import nữa = disabled), KHÔNG hard delete.
- **DB:** `blog_rewrite_candidates` (233) · `blog_rewrite_jobs` (217) · `blog_rewrite_drafts` (476) · `blog_rewrite_events` (3537) — **giữ nguyên 100%**.

## 2. Data model
Bảng MỚI (không đụng bảng cũ):
- **`blog_content_items`** — 1 bài roadmap = 1 dòng. Đủ field: roadmap_id, title, title_seo, meta, slug, cluster, priority, week, phase, intent, funnel, seo_score, impact, conversion, effort, status, owner, deadline_draft/publish, target_url, cta, main_keyword, secondary_keywords_json, outline_json, eeat_assets, schema_type, internal_links_json, image_keywords_json, risk_note, signal_16m/3m, reason, kpi_note, wordcount_target + workflow: brief_json, draft_title/meta/body_html, publish_url, published_at, haravan_article_id, gsc_14d/28d/60d_json, next_action, import_source, imported_at.
- **`blog_content_events`** — audit log thao tác.
- Schema tạo bằng `CREATE TABLE IF NOT EXISTS` (idempotent). Status workflow: backlog → brief_ready → writing → image_needed → seo_review → ready_publish → published → monitor_14d/28d/60d → refresh_needed → paused → archived.

## 3. Import Excel
- `import_roadmap()` đọc sheet **Blog Roadmap** (40 bài) + **Internal Links** (gộp theo source ID) → `blog_content_items`.
- **Idempotent:** key ổn định `roadmap_id`; re-run cập nhật field KẾ HOẠCH, **giữ** field workflow (status/owner/draft/published/gsc). Test: lần 1 = 40 imported; lần 2 = 0 imported / 40 updated / 0 duplicate.
- Keyword Insights / Dashboard / KPI Tracking: KHÔNG bê nguyên lên bảng chính (chỉ dùng cho drawer/tính tổng) — đúng yêu cầu "không clone Excel".

## 4. Backend API (route module `routes/blog_content_center.py`)
`/blog-content` + 15 API (xem `blog_content_api_endpoints.md`). Sync **GATED** confirm phrase `PUBLISH BLOG ITEM`, body_html-only, backup live trước PUT, mặc định tạo bản nháp ẩn (không tự đăng).

## 5. UI — 5 tab
Header KPI (total/A1/A2/writing/review/ready/published/overdue/no-owner) + quick filters (A1/A2/5 cụm/overdue/no-owner). Tabs: **Queue** (bảng hành động) · **Kanban** (9 cột + WIP warning >5) · **Calendar** (theo tuần, badge overdue/chưa owner/chưa brief) · **KPI Monitor** (14/28/60d, "chưa có data" nếu thiếu) · **Import/Settings**. **Drawer** chi tiết: brief đầy đủ (outline/target/anchor/CTA/schema/EEAT/KPI) + nút Generate Brief / Generate Draft / Status / Sync (gated).

## 6. Pipeline
- **Generate Brief:** dựng brief từ roadmap (không gọi AI), rule cấm nội dung crack, có internal link + CTA. Output local.
- **Generate Draft:** gọi `blog_content_writer.gen_blog_content_from_brief` theo outline/keyword/intent → draft local, KHÔNG publish.
- **Image:** theo guard context đã có (`haravan_image_store_guard`); ảnh inline cần `/file/` chưa proven → BLOCKED, không fallback sai context.
- **Sync:** chỉ khi bấm + confirm phrase; backup → PUT 1 lần → cập nhật state.

## 7. GSC/KPI
Đọc cột `gsc_*_json` đã lưu trong DB khi render (KHÔNG gọi API lúc render). Lịch KPI tính từ `published_at` + 14/28/60 ngày. Thiếu data → badge "chưa có data", không crash.

## 8–9. An toàn + QA
DB cũ giữ nguyên (xác nhận 233/476/3537/120). compileall OK. Smoke: `/blog-content` + 6 API + redirect cũ + 4 trang khác đều 200/302. Import idempotent. Sync gated chặn sai phrase (400, 0 PUT). Chi tiết: `blog_content_qa_report.md`.

## Rollback
Xem `blog_content_rollback.md` (backup ở `_backup/blog-content-command-center-all-in-one-20260616-170521/`).
