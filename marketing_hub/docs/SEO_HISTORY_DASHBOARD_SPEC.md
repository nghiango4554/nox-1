# SEO History Dashboard — Rebuild Spec

_Branch `wip-seo-history-dashboard` (worktree `nox-1-seo-history`, base origin/master 64e02ce). Task: nâng cấp `/seo/history` thành dashboard lịch sử SEO hiện đại, dễ quan sát. KHÔNG gọi Haravan live._

## 1. Current state
`/seo/history` (`routes/seo_core.py:seo_history_page`, template `templates/seo_history.html`) hiện là trang chart-heavy:
- Nguồn data: `db.seo_history_list / seo_history_chart_data / seo_history_regression_check / seo_history_get`, `cwv_history_timeline`, `seo_schema_history_timeline`, `gsc_ctr_tracking_list`.
- Bảng DB: `seo_history` (snapshot tổng: total, avg_score, good/ok_count/bad, broken_links, avg_score_product/blog/collection), `seo_cwv_history`, `seo_schema_history`, `gsc_ctr_tracking`. Snapshot dựng từ `seo_pages` + `seo_links` qua `seo_capture_history` → `seo_stats` + `seo_broken_link_summary`.
- Hiển thị: 4 chart (score, bands, by-type, broken) + CWV/schema timeline + bảng 52 snapshot (radio A/B compare) + CTR Rescue table. Chart.js CDN.

## 2. User problems
- Cột "🔗 Gãy" = 0 ở mọi snapshot (snapshot chụp sau Phase 1, trước link-check) → hiểu nhầm site 0 link gãy.
- Không phân loại link: 4xx thật lẫn 403/429/timeout/CDN/circuit-breaker → nếu hiển thị "broken" sẽ ảo (đã thấy "66% broken" ở `/seo`).
- Không nhìn nhanh được: site khỏe hay lỗi? lỗi tăng/giảm? URL nào mới lỗi / đã fix? nhóm lỗi nào nặng?
- Không drilldown tới URL cụ thể; không filter/search/sort; compare chỉ ở mức tổng.
- Thiếu empty/error/loading/stale state.

## 3. Goals
Trong 10 giây Nghĩa trả lời được: site khỏe/lỗi · lỗi tăng/giảm vs lần trước · URL mới lỗi / đã fix · nhóm lỗi nặng nhất · link gãy THẬT vs blocked/timeout · trang thiếu title/meta/H1/schema/canonical · noindex/redirect/404 · CWV gần nhất · SP/collection/blog cần ưu tiên · export report cho dev/content.

## 4. Non-goals
- KHÔNG gọi Haravan API (đọc DB thuần).
- KHÔNG đổi schema lớn / KHÔNG refactor `/seo`, `/seo/cwv` core.
- KHÔNG đổi `seo_stats` (dùng chung bởi `/seo`) — sẽ tính số đúng trong view-model riêng để tránh regression.
- KHÔNG chạy crawl/link-check mới trong task này (chỉ hiển thị data đã có).
- KHÔNG tự động crawl để lấp data thiếu.

## 5. Data sources
- `seo_pages` (latest state mỗi URL): score, status_code, title/meta/h1 counts, has_canonical, has_og, has_schema + schema_has_*, indexable, redirect_chain, url_type, issues (JSON), last_crawled.
- `seo_links`: target_url, status_code, error_kind, is_internal → phân loại link health.
- `seo_history` + `seo_cwv_history` + `seo_schema_history`: timeline.
- Helpers tái dùng: `seo_stats`, `seo_top_issues`, `seo_broken_breakdown`, `seo_broken_links_filtered`, `seo_count_broken_filtered`, `seo_history_list/chart_data/get/regression`.

## 6. Proposed metrics
**Scan summary:** total scanned · OK/warning/error (theo band) · missing title/meta/H1/schema/canonical · noindex · redirect · duplicate title/meta (nếu có) · avg load_ms · scan started/finished (latest run) · broken THẬT.
**Delta vs snapshot trước:** errors mới/đã fix · broken mới/đã fix · missing meta/schema ±· health ±.
**Health score 0-100** (helper mới, Bước 6): start 100, trừ: 4xx internal −4/URL cap −30 · 5xx −6/URL cap −30 · missing title/meta −2/URL cap −20 · missing H1 −1/URL cap −10 · missing schema −1/URL cap −15 · noindex bất thường −4/URL cap −20. **Blocked/timeout/403/429 KHÔNG tính broken thật** (đưa vào warning riêng, có caption giải thích).

## 7. Proposed UI sections
Header (title + latest scan time + Refresh + Export CSV + Compare latest/prev + quick-link `/seo` `/seo/cwv` `/seo/opportunities`) · Health score card (điểm + badge Good/Needs attention/Critical + delta + tooltip cách tính) · KPI grid · Timeline sparkline (click chọn run) · Issue breakdown theo nhóm (Technical/Metadata/Content/Links/Schema/CWV/Indexability/Redirects) · Compare panel (new/fixed/regressed/improved) · Bảng chính top affected URLs (URL, page type, severity, issues, current/previous status, first/last seen, action, open/copy) · Drilldown drawer · Link health panel phân loại 10 nhóm · Empty/error/loading/stale states.

## 8. Proposed filters
Client-side realtime trên bảng URL: search URL · page type (product/collection/blog/page/other) · severity · issue group · trạng thái (chỉ lỗi mới / còn tồn tại / đã fix). Link health: click bucket để lọc. Server-side cho export.

## 9. Proposed logic corrections (in scope)
- **Link health = 10 bucket** (không gom "broken"): `broken_4xx` (400-499 trừ 403/429) · `server_5xx` · `blocked_403` · `rate_limited_429` · `timeout` (status 0 + error_kind timeout/dns/ssl) · `cdn_blocked` (asset_cdn_skip) · `redirect` (3xx nếu lưu) · `external_unknown` (circuit_breaker_skip + other_error) · `unchecked` (status NULL) · `ok`.
- **Health/KPI KHÔNG tính NULL status = broken** (khác `seo_stats` cũ) — tính trong view-model mới.
- **Thêm index** `idx_seo_links_target ON seo_links(target_url)` qua migration guarded idempotent (an toàn, additive).
- (Ghi report, KHÔNG sửa) `seo_stats.broken` đếm NULL — để nguyên vì `/seo` dùng chung; chỉ note.

## 10. Risk list
- Đổi template có thể vỡ layout base → giữ `redesign_base` blocks, dùng class design-system sẵn có.
- Snapshot cũ `broken_links=0` → timeline broken vẫn phẳng; xử bằng caption + tính link health từ `seo_links` live thay vì cột snapshot.
- Per-URL new/fixed cần data lịch sử per-URL (chưa có) → thêm bảng additive `seo_page_issue_snapshot` populate KHI capture; compare per-URL chỉ có nghĩa sau ≥2 capture (empty-state giải thích "đang tích lũy").
- Index migration chạy 1 lần lúc init — guarded bằng `CREATE INDEX IF NOT EXISTS`.
- Restart 5055: phải kill đúng PID app.py, không đụng 5056.

## 11. Phase plan
- **A** Spec + audit (doc này, no behavior change).
- **B** Backend view-model: `seo_history_view.py` (hoặc helper trong db.py) gom scan summary + health score + link health buckets + issue groups + top affected URLs; route data giữ trong `seo_history_page` (thêm context), optional `/seo/history/data.json`. Index migration.
- **C** UI rebuild: header, health card, KPI grid, timeline, issue breakdown, bảng URL + filter client-side, empty/error states.
- **D** Compare latest vs previous: aggregate delta (có sẵn) + bảng additive per-URL new/fixed/regressed (populate going forward).
- **E** Export/report: CSV lỗi + copy summary + action list dev/content.
- **F** Polish: responsive 390, sticky header, 0 console error, perf.

## 12. QA plan
`py -3.12 -m compileall marketing_hub` (EXIT 0). test_client smoke: `/seo/history` `/seo` `/seo/cwv` `/seo/opportunities` `/seo/serp-briefs` `/blog-content` `/collection-content` `/alt-manager` = 200. Restart 5055 (kill đúng app.py PID, watchdog relaunch, verify 5055 up + 5056 vẫn listening). Browser/CDP: `/seo/history` desktop + mobile 390, 0 console error, filter/search/drawer/export hoạt động, layout không vỡ.

## 13. Rollback plan
Mọi thay đổi trong worktree `nox-1-seo-history` / branch `wip-seo-history-dashboard`, commit theo phase. Rollback = `git worktree remove` (hoặc `git reset --hard origin/master` TRONG worktree) — KHÔNG đụng repo chính `nox-1` (branch wip-products-new + WIP giữ nguyên). DB không migrate phá hủy (chỉ thêm index + bảng additive). Không restart 5055 tới khi compile+smoke pass.
