# WORKLOG — Sintech Marketing Hub

> File anh (Claude) tự update sau mỗi milestone. Sau /clear, anh đọc file này là biết task tuần này tới đâu, file nào đã edit, bug đang debug. Vợ Nghia có thể scan nhanh để xem anh đang làm gì.

## ✅ 2026-06-07 (tối) — UI POLISH + REFRESH (origin/master `b865838`, kèm UI refresh LOCAL chưa commit)
Next session đọc: `docs/UI_REFRESH_ADMINPRO_NALIKA_REPORT.md` + `docs/DAILY_ANALYTICS_RELEASE_REPORT_20260607.md`.
**Đã PUSH sạch (origin tiến `1efba83`→`b865838`):**
- Việt hóa 5 dashboard (giữ jargon GSC/GA4/CTR/Organic…) → `f2d5892`.
- Sidebar sắp xếp lại thông minh: gom GA4/Search Console/Tracking/Task/Ops vào nhóm **"Phân tích & Đo lường"**; SEO submenu gọn còn audit tools → `3430e22`.
- Sidebar tông **xám-lavender dịu** (bớt trắng) + active pill trắng; **header đổi đen→sáng** → `b865838`.
**UI REFRESH AdminPro+Nalika — LOCAL, CHƯA COMMIT/PUSH (theo task Past.txt):**
- 3 file CSS mới `marketing_hub/static/css/marketing-hub-{theme,components,responsive}.css` (palette warm AdminPro cam/hồng/vàng + KPI tile/card/badge/table kiểu Nalika, namespace `.mh-*` + lớp ADOPT refresh dashboard cũ qua `!important`).
- Sửa 1 dòng: `base.html` thêm 3 `<link>`. KHÔNG đụng JS/API/DB/route.
- Backup: `_backup/ui-refresh-20260607-205321/`. Rollback = xoá 3 CSS + restore base.html (lệnh trong report).
- Ref clone ở **Downloads** (`adminpro-ui-reference`, `nalika-ui-reference`), KHÔNG trong repo.
- QA: compileall PASS · secret scan sạch · 6 route 200 · screenshot `Desktop\ui_refresh_screens\`.
- ⚠️ Nếu vợ muốn giữ UI refresh: cần COMMIT 4 file (3 CSS + base.html) qua clean worktree. Nếu KHÔNG ưng: chạy rollback trong report.

## ✅ 2026-06-07 (ngày) — SINTECH ANALYTICS FULL RELEASE (origin/master `1efba83`)
Next session: đọc `docs/DAILY_ANALYTICS_RELEASE_REPORT_20260607.md`.
- **GSC direct API daily sync** + Data Health UI (`/seo/gsc`), fallback Sheet vẫn còn.
- **SEO × GA4 daily-aligned join** (organic), 2 mode API daily ↔ Sheet period (`/seo/ga4#seojoin`), max confidence medium, clicks≠sessions.
- **Tracking Audit** (`/seo/tracking`): catalog 17/30/23, 6 findings. **Task Center** (`/tasks`): dedup+cooldown. **Analytics Ops** (`/ops/analytics`): orchestration 1 nút.
- **Telegram alert** lọc theo **incident severity** P0/P1 (đã fix tách khỏi implementation_priority); contact gap = impl P0 / sev P2 → KHÔNG alert khẩn.
- **Scheduler enabled=false** (chưa bật live). Telegram live chưa bật. Website Haravan KHÔNG đụng.
- 9 commit push sạch qua clean worktree (e8a6103→bc41510 … 1a18246→1efba83). Canonical HEAD `1a18246`, **73 file WIP cũ giữ nguyên** (chưa reconcile — plan ở `docs/CANONICAL_RECONCILE_NEXT_PLAN.md`).
- DEFERRED (làm sau): GTM contact publish · theme Build PC · ecommerce checkout · mark key event · bật scheduler/Telegram live · canonical reconcile.

## 🚧 Đang dở (active) — snapshot trước /clear LẦN 2 (16/5 21:00)

### 🔴 Active — có thể trigger NGAY (anh hoặc vợ 1-click)
- [ ] **Bấm "✨ Gen vào Sheet" trên `/seo/title-meta`** — stream gen 1679 SP, push F/G/H Sheet `Meta des + Title Errors`. Auto stop khi quota Claude hit.
- [ ] **Re-crawl 1923 URL trên `/seo`** để DB cập nhật score mới (logic A+B+C+D+E) — chạy nền 15-30 phút. Không bắt buộc (DB đã crawl 16/5 15:55 với code MỚI: avg 67.3 / max 85).
- [ ] **Test pattern lazy upload thực tế**: gen 1 SP mới → verify body có URL `/local-images/`, sync → upload Haravan thật. Anh tự test được.

### 🟢 Pending — SEO Crawl Optimization roadmap (sau Task 1+2 done 30/5)
- [ ] **Task 4 — Schema validator JSON-LD (NEXT, ROI cao nhất)** — gọi `validator.schema.org/api/v1/check` audit ~2486 URL, lấp gap rich snippet vs đối thủ MTM. Effort 6-8h, đã chia 5 phase 4A→4E. Chi tiết `nox-1/docs/seo_crawl_optimization_backlog.md` mục Task 4. Khi vợ chốt khởi động → anh chia phase ngay.
- [ ] **Task 3 — Orphan page (thu hẹp, sau Task 4)** — phần MAIN ĐÃ CÓ ở `/seo/inlinks?view=orphans` + helper `db.seo_orphan_pages()`. Còn thiếu: cross-check sitemap.xml (deep orphan) + gợi ý nguồn link. Đề xuất tích hợp vào pipeline crawl `/seo` thay vì làm trang riêng. Effort thu hẹp ~3-4h, chia 3 phase 3A→3C. Chi tiết backlog file mục Task 3.

### 🟡 Blocked — chờ vợ confirm / paste data / chốt hướng
- [ ] **3 bài FB pending đăng** — chờ vợ drop ảnh vào `Desktop\Sintech\PIC đăng page\16-5\`:
  1. Thanh lý nguyên bộ PC i5-10400 + RTX 2060 + 16GB + Cooler Master 212
  2. Loa Edifier R1855DB Bluetooth (~2Tr9xx) — handle `loa-edifier-r1855db-bluetooth`
  3. Tai Nghe Gaming Xiberia X20 RGB 7.1 (~5xx.xxx) — handle `tai-nghe-gaming-xiberia-x20-den-rgb-7-1-virtual-overear`
- [ ] **Bot Telegram token revoked (401)** từ 12/5 14:00 — vợ paste token mới để resume `@Web_Sintech_bot`.
- [ ] **AI provider cho gen 1679 title/meta SP** — đã switch Claude CLI 17/5. Vợ confirm tiếp dùng Claude hay revert Codex sau 22/5.
- [ ] **Chia Codex 3 project** — vợ chưa chốt (1 quota chung / 3 account riêng / khác).
- [ ] **Regen 7 jobs failed** — 4 content_jobs + 3 blog_jobs (status=failed). Chờ vợ ưu tiên.
- [ ] **Push GitHub** — repo `git@github.com:nghiango4554/nox-1.git` đã accessible SSH. Vợ chốt: push full workspace hay split repo.
- [ ] **Re-sync 38 jobs đã synced** — cập nhật ALT mới + body với CDN URL khi vợ sẵn sàng.
- [ ] **Nâng cấp bot Telegram v2** — nếu vợ chốt (commands `/regen`, `/sync`, `/caption`...).

### Git state
- Branch: `master`, 2 commits:
  - `d2a5260` — "Initial: Sintech marketing_hub baseline + SEO scoring refactor" (175 files, 16/5 15:56)
  - `9eee935` — "WORKLOG: snapshot trước /clear — pending tasks + git state" (16/5 16:00)
- Author: `nghiango4554 <nghiatrong4554@gmail.com>` (name = ngo, không phải trong)
- Remote: **chưa setup** (chưa push GitHub)
- Sau /clear lần 1: nhiều file uncommitted (gemini_provider.py, refactor seo.py + seo_title_meta.html, sheet_writer.py). Khi vợ muốn commit lại thì check `git status`.

### Sheet ops đã setup
- Tab `"Meta des + Title Errors"` (sheet 13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU gid 971701509): 1679 product URL có lỗi title/meta đã fill A-K, helper cột L (Len Title) + M (Len Meta) auto-count với conditional format 🟢🟡🔴. Khi gen → push F/G/H.
- Tab `"W2/M5"` (sheet 1Pta9sA9Aq9Pva6uDpmqjn7RA4h07Sn6wDquwC81KWTE gid 103516100): báo cáo tuần đã fill cột K (Thứ 7 16/5) cho row 9, 10, 12, 15.

### Provider/quota state
- **Codex Plus**: hết quota, reset 22/5 (weekly limit)
- **Gemini 2.5-flash free**: hết 20 RPD hôm nay 16/5
- **Gemini 2.0-flash free**: 200 RPD (chưa thử nhưng phỏng đoán cũng share quota với 2.5)
- **Anthropic API**: chưa setup credit, KHÔNG có `ANTHROPIC_API_KEY` trong `.env`

## 📅 Tuần này (26/5 - 1/6)

### Thứ 7 (30/5) — TODAY

- ✅ **Task 2 SEO Crawl Optimization — Phase 2A: DB schema `seo_cwv_history`** (10:20):
  - Thêm bảng `seo_cwv_history` vào `marketing_hub/db.py` SCHEMA: 20 cột (id, week_no, year, url, strategy, scanned_at, performance_score, lcp_ms, cls_score, tbt_ms, fcp_ms, tti_ms, speed_index_ms, field_data_ok, lcp_field_ms, cls_field, inp_field_ms, fcp_field_ms, overall_category, snapshot_at) + UNIQUE(week_no, year, url, strategy) + 2 index (`idx_seo_cwv_history_week`, `idx_seo_cwv_history_url`).
  - Thêm 3 helper:
    - `cwv_history_has_week(week_no, year, strategy=None) -> bool` — check idempotency.
    - `cwv_history_snapshot(week_no, year, snapshot_at=None) -> int` — copy `seo_cwv` (4972 rows hiện tại) → history với tag tuần. Idempotent: nếu tuần đã có data → return 0.
    - `cwv_history_get_week(week_no, year, strategy='mobile') -> list[dict]` — đọc lại snapshot 1 tuần để diff.
  - Verify smoke test tuần 99/2026: insert 4972 rows ✓, lần 2 → 0 (idempotent) ✓, get_week mobile=2486 / desktop=2486 (tổng = 4972) ✓, has_week trả True/False đúng ✓, cleanup sạch ✓.
  - Bug fix nhỏ: SQLite `cur.rowcount` trả 0 với `INSERT...SELECT` → thay bằng `COUNT(*)` before/after.

- ✅ **Phase 2B: Script `_scripts/weekly_cwv_snapshot.py`** (10:23):
  - Tạo CLI standalone wrap `db.cwv_history_snapshot()`. Pattern follow `_scripts/weekly_empty_desc_scan.py` (UTF-8 stdout fix + sys.path inject).
  - Tự tính ISO week + year từ `datetime.now().isocalendar()` (mặc định). Override qua `--week`/`--year` cho dev test.
  - Log 3 trạng thái: SKIP (đã snapshot), WARN (seo_cwv rỗng), OK (insert N rows).
  - Verify: tuần test 88/2026 insert 4972 ✓, lần 2 SKIP ✓, default → tuần thật 22/2026 insert 4972 ✓.
  - Snapshot tuần 22/2026 ĐÃ LƯU thật (4972 rows) → sẵn data cho Phase 2C diff sau khi tuần 23 có snapshot.

- ✅ **Phase 2C: Script `_scripts/weekly_cwv_diff.py`** (10:26):
  - CLI standalone: auto-pick 2 tuần mới nhất từ `seo_cwv_history` (override `--current 22:2026 --prev 21:2026`).
  - Per strategy (mobile + desktop): tính `current_avg_score`, `prev_avg_score`, `avg_change`, `common_count`, `improved_count`, `regressed_count`, top 10 `improved`/`regressed` URL (sort by delta).
  - Output JSON `data/cwv_weekly_diff.json` ~11KB (gọn cho dashboard load).
  - Exit code 1 + WARN khi <2 tuần (Task Scheduler có signal).
  - Verify dev: fake tuần 21/2026 bằng jitter ±15 từ tuần 22 → run diff → mobile avg 69.0→68.9 (Δ-0.1) improved=1186 regressed=1217 (≈50/50 đúng kỳ vọng uniform jitter); top 10 regress/improve sorted đúng. JSON schema match dashboard spec. Override args + custom output path OK. Cleanup tuần 21 fake xong, file JSON fake cũng xóa.
  - **CHƯA commit.** Next: Phase 2D — dashboard ops-card "📊 Tuần này vs tuần trước" đọc JSON này.

- ✅ **Phase 2D: Dashboard card + route `/seo/cwv/diff`** (10:35):
  - `app.py` `_dashboard_health()`: thêm block đọc `data/cwv_weekly_diff.json` → `out["cwv_diff"]` (best-effort, fallback `None`).
  - `app.py` route mới `/seo/cwv/diff` → `seo_cwv_diff_page()` → render template `seo_cwv_diff.html`. Empty state có message hướng dẫn chạy 2 script `_scripts/weekly_cwv_*.py`.
  - `templates/dashboard.html`: thêm ops-card 📊 ngay sau card 🐢 CWV — hiện week_no, avg score, delta, improved/regressed count. Empty state s-gray "chờ data".
  - `templates/seo_cwv_diff.html` (mới, ~120 dòng): summary header + 2 strategy block (mobile + desktop), mỗi block 2 bảng top 10 regressed/improved side-by-side. URL link mở SP thật trong tab mới.
  - Kill PID Flask 13680 → watchdog VBS relaunch PID 21744 (~6s).
  - Verify smoke (server thật port 5055):
    - Empty state: `GET /seo/cwv/diff` HTTP 200, render "Không có data diff" + hướng dẫn ✓
    - Empty state dashboard: `GET /` HTTP 200, card hiện "chờ data" + "cần ≥2 tuần snapshot" ✓
    - Full data (fake tuần 21 jitter ±15): `/seo/cwv/diff` HTTP 200 31KB, render "T21 → T22", "avg 69.0 → 68.9", top 10 regressed/improved sorted đúng ✓
    - Card dashboard: "T21→T22", "↓-0.1", "🟢 1186 khá hơn · 🔴 1217 regress" ✓
    - Cleanup tuần 21 fake + JSON fake xong, empty state restore ✓
  - **CHƯA commit.** Next: Phase 2E — Task Scheduler cron Sunday 02:00 + E2E test.

- ✅ **Phase 2E: Task Scheduler cron + E2E smoke** (10:44):
  - `_scripts/run_weekly_cwv.bat` (mới): chain snapshot → diff, log vào `data/backups/weekly_cwv.log` với timestamp banner.
  - `_scripts/start_weekly_cwv_hidden.vbs` (mới): VBS wrapper hidden cho Task Scheduler (không CMD window).
  - `_scripts/INSTALL.md`: thêm section "Layer 5 — Weekly CWV Snapshot + Diff (Chủ nhật 02:00)" — hướng dẫn Task Scheduler entry "Marketing Hub Weekly CWV Diff" trigger Sunday 02:00, Program `wscript.exe` + Args VBS path, "highest privileges".
  - Verify E2E full pipeline (giả lập Task Scheduler gọi):
    - Fake tuần 21/2026 (jitter ±15 từ tuần 22 thật).
    - `cmd /c _scripts\run_weekly_cwv.bat` → log ghi `=== Sat 05/30/2026 10:44:02 === / [SKIP] Tuan 22/2026 / [mobile] avg 69.0 → 68.9 / [OK] Diff written`.
    - JSON 11.5KB xuất hiện tại `data/cwv_weekly_diff.json`.
    - `GET /` dashboard: card render "T21→T22 · ↓-0.1 · 🟢 1186 khá hơn · 🔴 1217 regress" ✓
    - `GET /seo/cwv/diff` HTTP 200 31KB ✓
    - Cleanup tuần 21 fake + JSON xong, empty state restore ✓
  - **TASK 2 COMPLETE.** 5/5 phase done. CHƯA commit (gộp commit single Task 2 hoặc theo phase). Việc tay vợ: tạo Task Scheduler entry theo INSTALL.md Layer 5.

- ✅ **Task 4 SEO Crawl Optimization — Phase 4A: DB schema cho schema validator** (11:30):
  - `marketing_hub/db.py` `init_db()` thêm 7 cột vào `seo_pages` (qua dict `new_seo_cols` migration loop):
    - `schema_types` TEXT (JSON array, vd `["Product", "BreadcrumbList"]`)
    - `schema_count` INTEGER DEFAULT 0 (số `<script type="application/ld+json">` block)
    - `schema_has_product` / `schema_has_faq` / `schema_has_article` INTEGER DEFAULT 0 (flag query nhanh)
    - `schema_errors` TEXT (JSON array parse errors)
    - `schema_scanned_at` TEXT
  - Index mới `idx_seo_pages_schema_scanned`.
  - 3 helper:
    - `seo_schema_upsert(url, data)` — UPDATE seo_pages với kết quả scan.
    - `seo_schema_stats(url_type=None)` — breakdown total_audited, has_product/faq/article, no_schema, has_errors, audited_pct, pct_has_*.
    - `seo_schema_missing(missing='product', url_type, limit=500)` — list URL thiếu schema priority.
  - Verify smoke: 7 cột + index tạo OK, upsert fake 1 SP → round-trip OK, stats trả đúng số (100% has_product cho 1 URL audited), missing trả 0 đúng, cleanup sạch.
  - **Baseline note:** Sintech hiện có **2026 product URL indexable** (status_code=200, indexable=1) → đây là target audit Phase 4C bulk scan.
  - **CHƯA commit.** Next: Phase 4B — `schema_scanner.py` module (extract JSON-LD bằng BeautifulSoup).

- ✅ **Phase 4B: Schema scanner module `schema_scanner.py`** (11:32):
  - Module mới `marketing_hub/schema_scanner.py` (~150 dòng):
    - `extract_jsonld_from_html(html)` — parse BS4 `<script type="application/ld+json">`, JSON.loads, return `{blocks, all_types (dedup), errors}`.
    - `_iter_jsonld_nodes(payload)` — flatten `@graph` nested + array root.
    - `_extract_types_from_node(node)` — handle `@type` string / array / vắng.
    - `scan_url(url, timeout=12)` — fetch + extract, robust error (RequestException → fetch_error JSON; HTTP non-200 → record).
    - `update_page_schema(url)` — wrapper gọi scan + `db.seo_schema_upsert()`.
    - CLI runnable: `py -3.12 schema_scanner.py <url> [<url> ...]`.
    - USER_AGENT consistent với `seo.py`.
  - **Khám phá lớn (verified 5 URL thật):** Sintech ĐÃ CÓ `Product` schema cho SP + `Article` schema cho blog + `Organization` + `Store` + `BreadcrumbList` mọi trang (chắc Haravan theme inject). Gap thực tế chỉ là **FAQPage** (blog chưa có) + **ItemList** (collection chưa có) + một số page 404 trong DB cũ. **Đảo ngược assumption backlog cũ.** Đã update memory `reference_competitor_seo_mtm.md` strikethrough 2 claim sai + thêm gap thực tế.
  - Test 5 URL pass đẹp:
    - SP: 3 blocks, types `["Organization", "Store", "BreadcrumbList", "Product"]`, has_product=True ✓
    - Collection: 2 blocks, types `["Organization", "Store", "BreadcrumbList"]` (thiếu ItemList) ✓
    - Blog: 3 blocks, types `["Organization", "Store", "BreadcrumbList", "Article"]`, has_article=True ✓
    - Homepage: 1 block, types `["Organization", "Store"]` ✓ (đúng vì root không có Breadcrumb)
    - Page 404: fetch_error "HTTP 404", schema_errors lưu JSON ✓
  - Edge case handled: malformed JSON (try/except), `@graph` flatten, `@type` array/string, empty block, fetch timeout/connection error.
  - **CHƯA commit.** Next: Phase 4C — bulk audit script `audit_schema_all.py` quét 2026 product + 229 blog + 209 collection (~4-7 phút với 5 worker).

- ✅ **Phase 4C: Bulk audit script + Task Scheduler + audit data thật toàn site** (11:55):
  - `_scripts/audit_schema_all.py` (~120 dòng): ThreadPoolExecutor 5 worker × 0.5s delay, skip URL `schema_scanned_at < 7 ngày` (idempotent re-audit), args `--limit N` `--url-type X` `--force` `--workers N`, progress log mỗi 50 URL + ETA + aggregate top 10 @type + flag breakdown cuối log.
  - `_scripts/run_audit_schema.bat` + `_scripts/start_audit_schema_hidden.vbs` — wrapper Task Scheduler hidden.
  - `_scripts/INSTALL.md` Layer 6 — Task Scheduler weekly Sunday 03:00 (lệch giờ với CWV diff 02:00).
  - **Audit FULL toàn site (background, 13.5 phút):** 2436 target → 2428 success, 8 fail (tất cả 404 SP đã xóa, DB cần cleanup), 3.0 req/s.
  - **Kết quả gap thật toàn site (data 30/5/2026):**

| url_type | total | audited | Product | FAQ | Article | no_schema |
|----------|-------|---------|---------|-----|---------|-----------|
| product | 2026 | 2026 | **2018 (99.6%)** ✅ | 0 | 0 | 8 (404) |
| blog | 231 | 231 | 0 | **0 (0%)** ❌ | 231 (100%) ✅ | 0 |
| collection | 210 | 210 | 0 | 0 | 0 | 0 — **0 ItemList** ❌ |
| page | 19 | 19 | 0 | 0 | 0 | 0 |

  - **Insight quan trọng cho Phase 5+:**
    - SP Product schema: 99.6% coverage (chỉ thiếu 8 SP 404) → KHÔNG cần fix Product, chỉ cleanup DB.
    - Blog Article schema: 100% coverage → KHÔNG cần fix Article.
    - **Gap CHÍNH: FAQPage trên 231 blog (100% blog thiếu)** ← inject FAQPage cho top blog traffic = ROI cao nhất.
    - **Gap CHÍNH thứ 2: ItemList trên 210 collection (100% thiếu)** ← inject ItemList cho top collection sales.
    - Page chỉ 19 URL, ít quan trọng.
  - **CHƯA commit.** Next: Phase 4D — UI page `/seo/schema` để vợ filter + xem chi tiết gap, nút Re-scan + Detail popup JSON-LD raw.

- ✅ **Phase 4D: UI page `/seo/schema` + 2 API endpoint** (11:57):
  - `db.py` thêm 2 helper pagination: `seo_schema_list(url_type, missing, limit, offset, only_audited)` + `seo_schema_count()`.
    - Filter `missing` ∈ {product, faq, article, itemlist, any, errors}.
    - Sắp xếp theo url_type + url.
  - `app.py` 3 route mới:
    - `GET /seo/schema` → render `seo_schema.html` với 4 summary card (Product %, Article %, FAQ %, ItemList %) + filter bar (url_type + missing) + bảng paginated 50 rows + pagination.
    - `POST /seo/schema/rescan/<page_id>` → gọi `schema_scanner.update_page_schema()` real-time, trả JSON kết quả.
    - `GET /seo/schema/detail/<page_id>` → re-fetch URL + `extract_jsonld_from_html()`, trả JSON `{blocks, all_types, errors}` cho popup detail.
  - `templates/seo_schema.html` (~230 dòng):
    - 4 summary card với màu sắc (green=ổn, red=gap)
    - Filter form auto-submit on change + chip "X URL match" + nút Reset
    - Bảng với badge có/thiếu schema (Product/Article/FAQPage/ItemList/Breadcrumb/Org)
    - Per row: 🔄 Re-scan (POST + auto reload) + 👁 Detail (modal popup hiện full JSON-LD blocks)
    - Modal detail dark theme pre/json, collapsible per block, hiện parse errors
    - Pagination nút Prev/Next + trang current
  - Kill PID 21744 → watchdog VBS relaunch PID 13784.
  - Verify smoke (server thật):
    - `GET /seo/schema` HTTP 200 73KB, summary đúng (2018/2026 Product, 231/231 Article, 🔴 231 FAQ, 🔴 210 ItemList) ✓
    - `GET /seo/schema?missing=faq` → "2486 URL match" (đúng vì 2486 URL ko có FAQ, ko filter url_type)
    - `GET /seo/schema?url_type=collection&missing=itemlist` → "210 URL match" ✓
    - `POST /seo/schema/rescan/<id>` blog test → JSON `{ok:true, types:[Org,Store,Breadcrumb,Article], has_article:true, schema_count:3}` ✓
    - `GET /seo/schema/detail/<id>` blog test → 3 blocks với types per block + errors=[] ✓
  - **CHƯA commit.** Next: Phase 4E — dashboard ops-card 🔖 + (optional) scoring rule thiếu FAQ/ItemList.

- ✅ **Phase 4E: Dashboard card 🔖 + integrate health endpoint** (11:58):
  - `app.py` `_dashboard_health()` thêm block `out["schema"]`: tổng audited, SP Product %, blog Article %, blog FAQ %, missing_product/faq/itemlist counts (query `seo_schema_stats(url_type=...)` × 3 type + count ItemList raw query).
  - `templates/dashboard.html` ops-card 🔖 "Schema gap (FAQ + ItemList)" ngay sau card 📊 CWV diff:
    - Big num: tổng gap (FAQ + ItemList missing).
    - Sub: "🔴 X blog thiếu FAQ · Y collection thiếu ItemList".
    - Sub 2: "SP Product Z% · blog Article W%".
    - Color: green (gap=0) / yellow (gap≤100) / red (gap>100) / gray (chưa audit).
    - Link → `/seo/schema`.
  - Verify smoke (server thật, kill PID 13784 → relaunch 7084):
    - Dashboard card render: "Schema gap (FAQ + ItemList)", "231 blog thiếu FAQ · 210 collection thiếu ItemList", "SP Product 99.6% · blog Article 100.0%" ✓
  - (Scoring rule integration scope ngoài 4E — backlog Phase 4F nếu vợ muốn ép URL thiếu schema có score thấp hơn.)
  - **TASK 4 COMPLETE.** 5/5 phase done.

### Thứ 6 (29/5)

- ✅ **CWV Scanner — fix real-time progress + pause/resume**:
  - **Fix bug progress bar không hiện**: `showRunning(v)` dùng `display:''` bị CSS `display:none` override → sửa thành `'block'`. Tương tự `setBtnState` (btnStop) → `'inline-block'`, `showAutoBanner` → `'block'`. Giờ progress bar hiện ngay khi scan bắt đầu, không cần F5.
  - **Live stats cập nhật 5s**: thêm `_startLiveStats()` polling `/api/seo/cwv/progress` mỗi 5s trong lúc scan đang chạy → coverage bars (scanned/total per url_type) tự cập nhật.
  - **Tăng workers 5 → 8**: `WORKERS_WITH_KEY = 8` trong `cwv.py` → nhanh hơn ~60% với PSI API key.
  - **Pause/Resume state**: bấm ⏹ Dừng → lưu `{strategy, urlType}` vào `localStorage['cwv_paused_v1']` → đóng web vào lại thấy banner vàng "⏸️ Có lần quét bị dừng" → bấm ▶ Tiếp tục → scan tiếp với `skip_scanned=true` (bỏ qua URL đã có data).
  - Files: `marketing_hub/cwv.py` (workers 5→8), `marketing_hub/templates/seo_cwv.html` (display fix + live stats + resume banner + JS savePauseState/resumeScan/clearPauseState).

## 📅 Tuần trước (12/5 - 18/5)

### Thứ 7 (16/5)

- ✅ **Sheet ops + reports + Haravan ops** (session sau /clear lần 1, 16/5 16:30-21:00):
  - **Chèn 6 ảnh CDN `_grande` 600x388 vào mô tả SP Card Zotac RTX 4070 Super Twin Edge** (haravan_id 1056283679)
    - Pattern feedback_image_pattern.md: URL gốc + suffix `_grande` + inline CSS object-fit:contain bg:#fff
    - Body 38,200 → 40,325 chars (+2,125), 6 `<img>` mới với ALT 6 vị trí
    - Section heading "Hình ảnh thực tế Zotac RTX 4070 Super Twin Edge" (H2 17pt bold)
    - PUT Haravan API thành công, verify admin OK (public chờ CDN purge 1-5 phút)
  - **Push 1679 product URL có lỗi title/meta vào Sheet "Meta des + Title Errors"** (gid 971701509)
    - Schema 11 cột (A loại lỗi/B URL/C tên/D-E title-meta hiện tại/F-G đề xuất/H trạng thái/I-J apply date/K chồng iu)
    - Sort: nhiều issue trước + score asc (worst at top)
    - Cột A đổi từ join "|" → bullet list xuống dòng, wrap text TOP
    - Helper cột L (Len Title) + M (Len Meta) auto-count + conditional format (45-58 🟢/59-61 🟡/>61 🔴; 140-160 🟢/161-180 🟡/>180 🔴)
  - **Refactor `/seo/title-meta` flow** (xem entry chi tiết bên dưới)
  - **Multi-provider switching** Codex ↔ Gemini (xem entry bên dưới)
  - **Fill weekly report W2/M5 cột K (Thứ 7)**: 4 cell K9/K10/K12/K15 (Content sp mới + Audit + Cấu trúc web + AI Training)

- ✅ **Multi-provider switching Codex CLI ↔ Gemini API** (Codex Plus quota hết, vợ thử Gemini → revert vì free tier hẹp):
  - **TẠO MỚI** `marketing_hub/gemini_provider.py` (129 dòng) — mimic pattern codex_provider.py với google-genai SDK v2.3.0:
    - `is_gemini_available()`, `call_gemini(system_prompt, user_prompt, model, timeout, temperature)`
    - `GeminiRateLimitError` exception (catch 429 RESOURCE_EXHAUSTED)
    - Load `GOOGLE_API_KEY` từ env hoặc `.secrets/google.env`
    - DEFAULT_MODEL = "gemini-2.0-flash" (free 200 RPD) hoặc "gemini-2.5-flash" (free 20 RPD)
  - **`seo.py:_gen_title_meta_with_angle`** swap provider:
    - Sáng: Codex → Gemini (test 5/5 SP success với prompt mới + retry 4)
    - Tối: revert về Codex (vì Gemini 2.5-flash chỉ 20 RPD, không đủ 1679 SP)
    - **Hiện tại**: dùng Codex (đợi reset 22/5)
  - **Prompt tighten**: thêm 3 ví dụ Title length + 2 ví dụ Meta length đẹp + quy trình "draft→đếm→cắt→đếm lại" + mẹo căn 145-158c
  - **Retry logic**: 1 → 4 lần với hint feedback cụ thể (lần trước title=Xc fail vì..., meta=Yc fail vì..., viết khác)
  - Template `seo_title_meta.html` 3 chỗ text: hiển thị Codex CLI / "Codex Plus quota hết" trong popup
  - Verify gen 5 SP với Gemini 2.0-flash + retry 4: **5/5 success** (vs 30-50% trước fix), avg 1.8 attempt/SP

- ✅ **Refactor `/seo/title-meta` — bỏ PUT Haravan, gen → push thẳng Sheet F/G/H** (vợ chốt flow an toàn):
  - Approach: streaming push Sheet (gen xong 1 SP push ngay, không đợi batch) + **5 angle rotate deterministic**
    (`SPEC / USE_CASE / AUDIENCE / PAIN_POINT / COMPARISON` pick theo `hash(url) % 5` → cùng URL → cùng angle)
    + **anti-dup** (pass `recent_titles` deque(10) vào prompt + post-validation `SequenceMatcher` ≥80% retry 1 lần)
    + **quota detect** (catch `CodexRateLimitError` → set `quota_hit=True` + auto stop + popup browser alert).
  - **TẠO MỚI** `marketing_hub/sheet_writer.py` (145 dòng) — module tách logic Google Sheets:
    `_build_url_to_row_index()` cache 1680 URL→row (TTL 5 phút), `push_proposal(url, title, meta, status)` update F/G/H,
    `read_proposal(url)` verify. Token reuse từ `.secrets/google_token.json` (đã có sẵn từ GSC + push 269).
  - **SỬA** `marketing_hub/seo.py` (2379→2749, +370 dòng):
    - GIỮ NGUYÊN `fix_title_meta_for_url()` + `_gen_title_meta_via_codex()` (legacy reference / future Apply)
    - THÊM `_pick_angle_for_url(url)` MD5-based deterministic (verified 20-sample: SPEC=3, USE_CASE=5, AUDIENCE=6, PAIN_POINT=4, COMPARISON=2)
    - THÊM `_gen_title_meta_with_angle()` + `_ANGLE_INSTRUCTIONS` dict 5 prompt blocks + `_ANGLE_DEFAULT_CTA` mapping
    - THÊM `_validate_gen_output()` length (45-58 / 145-158) + similarity check
    - THÊM `_fetch_product_desc_snippet()` lấy 200c body_html Haravan (best-effort)
    - REPLACE `_title_meta_fix_state` → `_title_meta_gen_state` thêm fields `quota_hit`, `last_gen_title`, `last_gen_meta`, `last_gen_angle`
    - REPLACE `run_title_meta_fix_all` → `run_title_meta_gen_all` streaming + 1s delay/Sheet write (tránh 429)
    - RENAME `start_title_meta_fix_all_async` → `start_title_meta_gen_all_async`, `stop_title_meta_fix` → `stop_title_meta_gen`, `title_meta_fix_state` → `title_meta_gen_state`
  - **SỬA** `marketing_hub/app.py` (+3 dòng): GIỮ `/seo/title-meta/fix` (legacy fallback), rename
    `/seo/title-meta/fix-all/{start,stop}` → `/seo/title-meta/gen/{start,stop}` +
    `/api/seo/title-meta/fix-all/status` → `/api/seo/title-meta/gen/status`. Page render dùng `gen_state` thay `fix_state`.
  - **REFACTOR** `marketing_hub/templates/seo_title_meta.html` (502→489, -13 dòng):
    - XÓA per-row "🔧 Auto-fix" + bulk "🚀 Auto-fix tất cả" + "⏹️ Dừng job" cũ
    - THÊM "✨ Gen title+meta vào Sheet" + "⏹️ Dừng Gen" + link "📊 Mở Sheet"
    - Status bar realtime hiển thị `last_gen_title` + `last_gen_angle` (badge OK gắn ✨ ANGLE_NAME per row)
    - Popup `alert()` 1 lần khi `quota_hit=true` ("Codex Plus đã hết quota. Đợi reset ~5h...")
    - Polling 3s, rename JS `startFixAllJob`→`startGenJob`, `stopFixAllJob`→`stopGenJob`
  - **VERIFY**:
    - `_pick_angle_for_url`: 20 URL → distribution {AUDIENCE:6, USE_CASE:5, PAIN_POINT:4, SPEC:3, COMPARISON:2} ✓ phân bố cả 5
    - Determinism: cùng URL gọi 2 lần → cùng angle ✓
    - `sheet_writer.get_url_row_index(url_thật)` → row 2 ✓ (1680 URL trong sheet, cache build OK)
    - `sheet_writer.push_proposal` + `read_proposal` round-trip cell F/G/H thật trên Sheet ✓ (cleanup OK)
    - Flask restart qua VBS (PID 17412 port 5055) + 4 route 200:
      - GET `/seo/title-meta` → 200 ✓
      - GET `/api/seo/title-meta/gen/status` → 200 ✓ JSON đủ fields (`running, total, success, failed, current_url, quota_hit, last_gen_title, last_gen_angle, ...`)
      - POST `/seo/title-meta/gen/start` body `{type:product, issue:meta_long}` → `{ok:true, message:"Đã start job gen vào Sheet"}` (queue 1679 SP, skip 422)
      - POST `/seo/title-meta/gen/stop` → `{ok:true}`
    - **Quota detect end-to-end**: Codex thật đã hết quota (reset 22/5) → start job → fail 1/1 SP đầu →
      `quota_hit=true`, `running=false`, `message="⚠️ Codex Plus quota hết — auto stop"`, loop break đúng ✓
  - KHÔNG modify `db.py` (không cần DB column mới). KHÔNG commit. Đợi vợ confirm/test.

- ✅ **Swap provider Codex → Gemini API tạm (Codex quota Plus reset 22/5)**:
  - **TẠO MỚI** `marketing_hub/gemini_provider.py` (122 dòng) — adapter pattern y hệt `codex_provider.py`:
    `is_gemini_available()` check SDK + key, `call_gemini(system, user, timeout, model, temperature)` gọi
    `client.models.generate_content()` qua `google.genai`, `GeminiRateLimitError` cho quota detect
    (patterns: rate limit / quota exceeded / resource_exhausted / 429 / too many requests).
    Default model `gemini-2.5-flash`, load key từ env `GOOGLE_API_KEY` → fallback `.secrets/google.env`.
  - **SỬA** `marketing_hub/seo.py` (+5 dòng net) — chỉ replace provider trong gen flow MỚI, GIỮ NGUYÊN legacy:
    - `_gen_title_meta_with_angle()`: `import codex_provider` → `import gemini_provider`,
      `call_codex(...)` → `call_gemini(...)`, catch `CodexRateLimitError` → `GeminiRateLimitError`.
      Prompt 5 angle + anti-dup logic GIỮ NGUYÊN 100%.
    - `run_title_meta_gen_all()`: catch + message "⚠️ Gemini quota hết — auto stop" (thay "Codex Plus").
    - `_gen_title_meta_via_codex()` legacy (line 1731) GIỮ NGUYÊN — dùng cho `/seo/title-meta/fix` single-URL.
  - **PKG**: `pip install google-genai` (v2.3.0) — `google.generativeai` cũ deprecated.
  - **VERIFY**:
    - Smoke test `python marketing_hub/gemini_provider.py` → `Available: True` + Output JSON ✓
    - Gen 1 SP thật (`vo-case-magic-gm-08l-pro-m-atx-...`) angle COMPARISON → ok=True, title 60c, meta 187c
      (validate fail length, retry pipeline hoạt động đúng).
    - Gen + push Sheet thật cho `ram-may-tinh-kingston-fury-beast-black-16gb-3200mhz-...`:
      angle=USE_CASE, title 58c "Kingston Fury Beast Black 16GB 3200MHz DDR4: Tối ưu Gaming",
      meta 157c "RAM Kingston Fury Beast Black 16GB 3200MHz DDR4 nâng tầm trải nghiệm gaming…
      KHÁM PHÁ NGAY tại Sintech." → validate=True → push_proposal cell F/G/H row 3 → `read_proposal` round-trip OK ✓
    - Flask restart VBS hidden → `GET /seo/title-meta` 200 ✓
  - **Trade-off**: Gemini 2.5-flash có xu hướng viết meta > 160c hoặc < 140c thường xuyên hơn Codex
    (~3-4/5 SP fail validate lần đầu, retry 1 lần thường vẫn fail). Sau 22/5 nên switch lại Codex,
    hoặc nếu muốn dùng Gemini lâu dài thì cần tighten prompt length constraint + nâng số retry attempts.
  - KHÔNG commit. KHÔNG modify file ngoài scope.

- ✅ **Refactor C — unify 2 hệ thống chấm điểm thành `scoring_core.py`** (backward compat verified):
  - Tách `marketing_hub/scoring_core.py` (~600 dòng) — module pure chứa 6 score function dùng chung:
    `score_title` / `score_meta` / `score_structure` / `score_links` / `score_readability` /
    `score_sintech_sections` / `score_technical_seo`. Mỗi function nhận `max_score` weight để caller scale.
  - `seo_quality.py:rate_content()` refactor 100% → delegate sang scoring_core. Output schema GIỮ NGUYÊN
    (`score/max/tier/breakdown.{title,meta,structure,links,readability}/issues_high/med/low/readability`).
    UI templates 3 trang (content-jobs/blog/collection) KHÔNG đổi.
  - `seo.py`: chuyển import `readability_score` từ `seo_quality` → `scoring_core` (loại circular dep tiềm ẩn),
    re-export `readability_score = readability_metrics` để backward compat.
  - Verify content_jobs: chấm 12 sample → avg Δ(new vs old algorithm) = **+0.00**, max |Δ| = **0** (bit-identical).
    Δ vs DB stored = -2.4 trung bình (DB từ revision cũ với 6 category 'content' tách riêng — expected).
  - Verify crawl seo_pages: re-fetch 5 URL → schema check pass (only `desc_h1_scanned_at` extra, intentional),
    avg Δ = +5.2 (real pages updated since DB last crawl — expected).
  - Flask restart qua VBS wrapper: tất cả route 200 (`/`, `/seo`, `/seo/rules`, `/content-jobs`,
    `/blog-content`, `/collection-content`) + detail page (`/content-jobs/315`, `/blog-content/229`,
    `/collection-content/60`) cũng 200. KHÔNG commit.
  - Files: TẠO `scoring_core.py` (779 dòng), SỬA `seo_quality.py` (285→155 dòng, -130), `seo.py` (2372→2379, +7 dòng import).

- ✅ **Refactor scoring engine `seo.py` — 4 fix A/B/D/E nâng max thực tế 85→100đ**:
  - [x] **Fix A — Cộng điểm Sintech-specific (+15đ cho product)**: thêm 5 hidden_pass rule
    `sintech_section_ok` (+4) / `meta_cta_ok` (+3) / `faq_ok` (+3) / `signature_ok` (+3) / `real_experience_ok` (+2).
    Trước đây 5 rule này chỉ flag warn/info → giờ pass thì cộng điểm. Thêm rule `missing_signature` info-only.
  - [x] **Fix B — Tích hợp readability (+10đ)**: import `readability_score()` từ `seo_quality.py`.
    Map: ≥70→+10, ≥55→+7, ≥40→+4, <40→0 + issue warn. Skip nếu word_count <50. Thêm rule `readability_ok` (hidden_pass) + `readability_weak` vào config.
  - [x] **Fix D — Word count threshold theo url_type**: thay logic cứng (low<500 / thin<800) bằng map theo type.
    blog: 700/1500 | product: 500/800 (giữ) | collection: 150/300 | page+other: 500/800.
    Đưa vào config key `word_count_thresholds` qua helper `_word_thresholds(url_type)`.
  - [x] **Fix E — Dup title/meta cross-site post-process**: function mới `recompute_dup_flags()`.
    Group theo normalized title (strip suffix ` - Sintech`) + meta, ≥2 page = dup, trừ -5/-5 (cap -10), thêm issue `dup_title`/`dup_meta` liệt kê tối đa 3 URL trùng. Có logic restore điểm cho page không còn dup nữa khi re-run.
    Expose route mới `POST /seo/recompute-dup` (`app.py`) trả JSON stats.
  - Config `data/seo_rules_config.json` bump `version: "2026-05-16-1"`, thêm 9 rule mới + key `word_count_thresholds`.
  - **Stats sample re-analyze 10 product page**: avg **76.6** (62-82) vs DB cũ max 75đ — confirm cộng điểm mới hoạt động.
  - **recompute_dup run đầu**: dup_title_count=0, dup_meta_count=3 group, affected_pages=7, total_deducted=35.
  - **DB stats 2460 page 2xx**: avg before 62.06 → after recompute 62.04 (chỉ recompute_dup, chưa re-crawl). Distribution 50-65: 1284 | 65-80: 1169. Sau khi re-crawl đại trà sẽ dịch lên ~70-90.
  - Files modified: `seo.py` (+~110 dòng), `app.py` (+10 dòng route), `data/seo_rules_config.json` (+~95 dòng).
  - Verify: Flask restart qua VBS (port 5055 HTTP 200), route `/seo/recompute-dup` trả JSON valid. KHÔNG commit (vợ review trước).

### Thứ 6 (15/5)

- ✅ **Bỏ scoring dựa trên word count + thêm toolbar Căn giữa đồng bộ 3 trang** (theo yêu cầu vợ — bài AI sẽ không bị loãng do ép wordcount):
  - `seo_quality.py`: bỏ category "content" (30 điểm chấm theo target wordcount). Redistribute → title 20, meta 20, structure 25 (+ thin content gate <100 từ), links 15, readability 20 = 100
  - 3 writer (`content_writer`/`collection_content_writer`/`blog_content_writer` + `ai_writer.py`): bỏ ép độ dài cụ thể (cũ "800-2700 từ", "600-1200", "1500-3000") → đổi sang "viết đủ ý theo cấu trúc, hết ý thì dừng, không lặp/filler"
  - Toolbar WYSIWYG: thêm 3 nút **⬅ Trái / ⬌ Giữa / ➡ Phải** cho cả `/collection-content` + `/blog-content` + `/content-jobs` (detail) — helper `alignText(dir)` smart: nếu selection đang trong `<td>/<th>` → set `text-align` trên cell đó (giữ inline style cho Haravan); ngoài table → dùng `execCommand justifyXxx`
  - `/content-jobs` detail trước đây thiếu toolbar format → thêm full toolbar (B/I/U/S, H2/H3, list, align, link, color, undo/redo) + ẩn khi switch sang Edit raw HTML
  - List page bỏ logic màu cột word count (good/warn/bad theo threshold): `content_jobs_list.html` + `blog_content.html` chỉ hiển thị số neutral, không đánh giá
  - Restart Flask (PID 25004) → 5 category total = 100 verified

- ✅ **Trang `/blog-content` quản lý + gen content cho blog/news** (mới, mirror pattern `/collection-content`):
  - DB table `blog_jobs` schema đầy đủ (haravan_article_id/blog_id, edited_*, status, quality_score, click/imp/pos)
  - Routes app.py: `/blog-content` (list), `/blog-content/<id>` (detail WYSIWYG), `/blog-content/<id>/gen|save|sync`, `/blog-content/sync-all`
  - Templates: `blog_content.html` (KPI + cột Title/Meta len + Words + ⭐ Q + 📖 R + 👆 GSC click + 📊 Pos), `blog_content_detail.html` (WYSIWYG editor giống collection)
  - Writer `blog_content_writer.py`: Codex CLI sinh blog 1500-3000 từ (intro + 4-6 H2 + FAQ + outro + signature Sintech), CTA HOA, prohibit filler "bền bỉ"/"tốt nhất 2026", ép ≥3 internal link
  - Sync PUT `/blogs/{blog_id}/articles/{article_id}` với body_html + metafields title/desc, GIỮ slug (không đổi field `title`)
  - **Seeder `_seed_blog_jobs.py` v2**: pull từ `seo_pages` (229 URL crawled) thay vì Haravan API (vì `/blogs.json` 502) — cross-match GSC → 69/229 bài có click data
  - **Top traffic**: PC bị giật điện (85 click pos 4.9), Command Prompt tự mở (61 click), Bảng mã Mainboard Huananzhi x99 (56 click)
  - Restart Flask qua VBS wrapper (PID 17460) sau khi sửa code; routes verify 200

### Thứ 5 (14/5)

- ✅ **Trang `/seo/gsc` Google Search Console hub** (mới):
  - Fetch + cache 2 sheet GSC export (Performance + Coverage) vào `data/gsc_cache.json`
  - 8 task action với count + URL list chi tiết (404=664, crawled-not-indexed=1465, noindex=188, discovered=60, duplicate-canonical=11, CTR thấp, pos 11-20, cash cow)
  - Fetch 1923 URL list từ 5 drilldown sheets vợ export
  - KPI bar, top 10 keyword, top 10 URL preview
  - Routes: `/seo/gsc`, `/seo/gsc/task/<id>`, `/seo/gsc/refresh`
  - Files: `seo_gsc.html`, `seo_gsc_task.html`, `_fetch_gsc_cache.py`, `_fetch_gsc_url_lists.py`

- ✅ **Trang `/collection-content` (tạm) cho gen content collection** (mới):
  - DB table `collection_jobs` — seed 136 URL từ tab Carte chưa có Date up
  - Codex CLI gen title + meta + body_html (rule SEO Sintech adapted cho collection)
  - Detail page với rich-text WYSIWYG editor (contentEditable)
  - **Nút 🎨 Format full**: áp font Arial 12pt weight 500, H2 17pt, H3 13pt, link đỏ #e74c3c bold underline, viền bảng 1px #ccc, list 12pt
  - Compress HTML aggressive (strip Google Doc inline styles defaults) → giảm 30-70% size
  - Haravan body_html limit ~50,000 chars — cảnh báo realtime raw → compressed
  - PUT smart_collection/custom_collection
  - Files: `collection_content.html`, `collection_content_detail.html`, `collection_content_writer.py`, `collection_writing_rules.md`

- ✅ **Port SEO Machine module**: Readability VN + SEO Quality Rater 0-100:
  - `seo_quality.py` — 6 category (content, title, meta, structure, links, readability)
  - VN-specific: passive voice (được/bị), filler list cấm, complex sentence (>25 từ)
  - Auto-compute on save edit → DB column quality_score, readability_score, quality_breakdown
  - Bulk score 314 content_jobs (avg 87.8/100) + 4 collection_jobs (avg 88-96)
  - UI: list page thêm cột ⭐ Quality + 📖 Read, detail page hiện 6 mini cards + issues_high/med

- ✅ **Sync sheet Carte vs Haravan collections** (210 smart collections):
  - Backup tab Carte_bak_20260514_154737 (giữ rich-text hyperlinks F)
  - Fill 95 URL match, xóa 51 row không match, add 58 Haravan mới
  - Resync giữ thứ tự backup → preserve Doc hyperlinks cột F

- ✅ **Excel báo cáo Sintech `BaoCaoTuan_Sintech_v3_DEMO_20260514.xlsx`** (5 sheet với formula + chart + conditional format)

- ✅ **Fix nhiều bug:**
  - `**read` override `score` của breakdown → quality > 100
  - Word count branch sai (2457>1500 báo "hơi ngắn")
  - Sync fail nhưng status giữ 'synced' → reset 'failed'
  - "Mô tả quá dài" Haravan 50k → compress aggressive (Google Doc CSS defaults)
  - `event.target` undefined khi `saveEdit()` chain từ `syncJob()` → pass `this` qua param

- ✅ **Phân tích SEO Machine README** (TheCraigHewitt/seomachine) → đề xuất 5 module port, Phase 1 done

### Thứ 3 (12/5)
- ✅ **Tab `/seo/rules`** UI quản lý SEO rules (option C đầy đủ):
  - Config JSON `data/seo_rules_config.json` 47 rules + thresholds good/ok
  - Mỗi rule: enabled, level, score, threshold, msg template, applies_to
  - UI table edit inline + nút Lưu
  - Atomic write + auto-reload config (cache mtime)
  - Phase 1 wrap: 8 rule chính (title/meta/h1) đã apply config; 39 rule còn lại hardcoded nhưng vẫn disable được qua `enabled` flag
- ✅ **Phase 1 crawl audit + fix** (combo A+B+C):
  - **A (Score):** fix `sintech_in_title` false positive (regex bỏ suffix Haravan " - Sintech"); adjust threshold "good ≥65" cho Sintech-on-Haravan (cũ ≥80, max page chỉ đạt 70)
  - **B (URL miss):** sitemap có 2423 URLs, DB chỉ 1120 (46%) → last run failed midway, miss 847 product + 229 blog + 209 collection
  - **C (Speed):** WORKERS 8→20, DELAY_PER_WORKER 0.25→0.05, TIMEOUT 15→12s, batch DB progress 20→50 → expected ~4-6x nhanh hơn
  - Em re-run crawl ngon nha
- ✅ **Broken link check tăng tốc 5-8x** (combo B): WORKERS 8→30, TIMEOUT 15→8s, HEAD-only (chỉ retry GET cho 405/403), batch DB write 50/transaction, host circuit breaker, dedup targets. File modified: `seo.py` + `db.py:seo_link_status_update_batch`
- ✅ Resume Haravan (xóa pause flag) sau khi vợ confirm
- ✅ Setup permission gate trong `haravan_client._check_permission()`:
  - BLOCK: `POST /products.json`, `DELETE /products/{id}.json`, `POST /blogs/*/articles.json`, `DELETE /articles/{id}.json`
  - ALLOW: GET, PUT/PATCH, POST `/products/{id}/images.json`, DELETE images
- ✅ Lazy upload pattern hoàn chỉnh:
  - `process_and_upload_images()` → save LOCAL `data/images/<handle>/img_N.jpg`
  - Flask route `/local-images/<handle>/<file>` serve trực tiếp
  - `upload_local_images_in_body_to_haravan()` chạy KHI bấm SYNC: scan body → upload Haravan asset_storage (sequential) → replace URL
- ✅ VBS hidden wrapper `_scripts/start_*_hidden.vbs` → Task Scheduler dùng `wscript.exe` thay batch trực tiếp → KHÔNG còn CMD window visible
- ✅ Fill weekly report sheet `W1/M5` (Thứ 7 + CN cho rows 9, 10, 15)
- ✅ Update WORKLOG.md + memory `project_status.md` (để recover context sau /clear)

## 📅 Tuần trước

Đã archive sang `docs/WORKLOG_ARCHIVE/`:
- [`2026-W1-M5.md`](docs/WORKLOG_ARCHIVE/2026-W1-M5.md) — Tuần 5-11/5 (CN bão lớn nhất 10/5, T7 9/5, T6 8/5)

## 📂 File modified gần đây (tuần này)

### `marketing_hub/haravan_client.py`
- Thêm `_check_permission()` block POST/DELETE SP+article
- Sửa `upload_to_asset_storage()` RAISE khi tất cả storage đầy (KHÔNG auto-create — tránh incident 10/5)
- `_create_new_asset_storage()` marked DEPRECATED auto-call

### `marketing_hub/content_writer.py`
- Thêm `IMAGES_LOCAL_DIR`, `_clean_product_name()`, `_gen_alt_for_position()`
- Refactor `process_and_upload_images()` → save LOCAL thay vì upload Haravan
- Thêm `upload_local_images_in_body_to_haravan()` — chạy khi SYNC
- Thêm `pick_target_image_count()`, `count_main_h2()`

### `marketing_hub/app.py`
- Route `/local-images/<handle>/<filename>` — Flask serve local images
- `content_jobs_sync()`: gọi `upload_local_images_in_body_to_haravan()` trước khi PUT
- `/content-jobs/<id>/toggle-money` endpoint
- Category filter trong `/content-jobs`

### `marketing_hub/_scripts/`
- `start_marketing_hub_hidden.vbs` — VBS wrapper hidden cho web
- `start_telegram_bot_hidden.vbs` — VBS wrapper hidden cho bot
- `run_backup.bat`, `backup_db.py` — DB backup daily
- `INSTALL.md` — hướng dẫn setup Task Scheduler

### Memory (`~/.claude/projects/.../memory/`)
- `feedback_haravan_permission.md` — permission gate + lazy upload + incident race condition
- `reference_marketing_hub_ops.md` — Task Scheduler 24/7 + bot self-service
- `project_status.md` (mới) — overview 4 mảng project

## 🏗️ State hệ thống

### Services
- 🟢 Web Flask `port 5055` — auto-start Task Scheduler (PID 14796 từ 12:11 PM 12/5)
- 🔴 Bot Telegram @Web_Sintech_bot — token revoked 401, vợ paste lại nếu cần
- 🟢 DB Backup — schedule 3AM daily, giữ 30 ngày, path `data/backups/posts_YYYY-MM-DD.db.zip`
- 🟢 Haravan API — RESUMED, permission gate active

### Storage Haravan (7 storage SP)
- 1074465986 (cũ, đầy 91/90)
- 1074494220, 1074495782, 1074495817, 1074495857, 1074495866, 1074495883 (sau incident)
- ⚠️ KHÔNG auto-create nữa — đầy = vợ tạo SP manual + paste haravan_id vào `state/asset_storage_product.json`

### Quyền Claude với Haravan
- ❌ Tạo SP / xóa SP / tạo article / xóa article
- ✅ PUT/PATCH SP+article, upload ảnh vào SP existing, GET *

## 📌 Quy ước update file này
1. Anh tự update CUỐI mỗi response khi vừa xong 1 milestone lớn (≥3 actions hoặc 1 commit-worthy change)
2. Move items từ "Đang dở" → "Hôm nay" khi xong
3. Mỗi cuối tuần (CN), move "Tuần này" → "Tuần trước"
4. Vợ có thể edit thẳng tay vào file này nếu thấy thiếu việc của vợ

---

## 📸 Checkpoint snapshot template (copy khi cần)

> Anh dùng template này TRƯỚC mỗi `/clear`, `/compact`, hoặc handoff task dài. Copy block dưới → fill → paste lên đầu section "Đang dở" hoặc commit riêng `git commit -m "checkpoint: <ngắn>"`.

```markdown
## 📸 Checkpoint YYYY-MM-DD HH:MM

### ✅ What completed (since last checkpoint)
- ...

### 🔴 Current blockers
- ...

### 📝 Modified files (uncommitted)
- `path/to/file` — gì đã đổi
- ...

### ⏭ Exact next action
- Bước cụ thể tiếp theo, không vague ("test", "review") mà cụ thể ("chạy `python X.py` rồi verify Y").

### 🔁 Resume prompt (paste vào session mới)
> "Tiếp tục task <tên>. Anh đã làm xong A+B, đang kẹt ở C vì <reason>. File modified: <list>. Next: <bước cụ thể>. Đọc WORKLOG.md checkpoint <timestamp> để full context."
```

**Quy ước:**
- Mỗi checkpoint = 1 commit riêng `git commit -m "checkpoint: <ngắn>"` để git log dễ scan
- KHÔNG tạo file riêng trong `checkpoints/` folder — append vào WORKLOG.md để 1 nguồn truth
- Sau khi session sau resume xong → có thể xóa checkpoint cũ (giữ ≤3 checkpoint gần nhất trong WORKLOG)
