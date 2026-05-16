# WORKLOG — Sintech Marketing Hub

> File anh (Claude) tự update sau mỗi milestone. Sau /clear, anh đọc file này là biết task tuần này tới đâu, file nào đã edit, bug đang debug. Vợ Nghia có thể scan nhanh để xem anh đang làm gì.

## 🚧 Đang dở (active) — snapshot trước /clear (16/5 15:57)

### Cần vợ confirm / paste data
- [ ] **Bot Telegram token revoked (401)** lúc 12/5 14:00 — vợ paste token mới khi cần resume bot @Web_Sintech_bot
- [ ] **3 bài FB pending đăng** (anh viết 16/5 ~13:30, chờ vợ drop ảnh vào `Desktop\Sintech\PIC đăng page\16-5\`):
  1. Thanh lý nguyên bộ PC i5-10400 + RTX 2060 + 16GB + Cooler Master 212
  2. Loa Edifier R1855DB Bluetooth (~2Tr9xx) — handle `loa-edifier-r1855db-bluetooth`
  3. Tai Nghe Gaming Xiberia X20 RGB 7.1 (~5xx.xxx) — handle `tai-nghe-gaming-xiberia-x20-den-rgb-7-1-virtual-overear`
- [ ] **Chia Codex 3 project** — vợ chưa chốt hướng (1 quota chung / 3 account riêng / khác)

### Sau commit baseline `d2a5260` (16/5 15:56)
- [ ] **Re-crawl 1923 URL trên `/seo`** để DB cập nhật score mới (logic A+B+C+D+E) — chạy nền 15-30 phút
- [ ] **Regen 7 jobs failed**: 4 content_jobs + 3 blog_jobs (status=failed) — đợi vợ ưu tiên
- [ ] **Push GitHub** — vợ tạo empty repo trên web (account mới `nghiatrong4554`), paste URL → anh setup remote + push lần đầu (GCM popup login)
- [ ] Test pattern lazy upload thực tế: gen 1 SP mới → verify body có URL `/local-images/`, sync → upload Haravan thật
- [ ] Re-sync 38 jobs đã synced để cập nhật ALT mới + body với CDN URL (khi vợ sẵn sàng)
- [ ] Nâng cấp bot Telegram v2 nếu vợ chốt (operational commands `/regen`, `/sync`, `/caption`...)

### Git state
- Branch: `master`, 1 commit: **`d2a5260`** — "Initial: Sintech marketing_hub baseline + SEO scoring refactor"
- Author: `nghiatrong4554 <nghiatrong4554@gmail.com>` (global git config setup hôm nay)
- Remote: **chưa setup** (chưa push GitHub)
- `.gitignore` đầy đủ: block secrets/tokens/env/DB/logs/cache/scratch files (xem `.gitignore` file)
- ⚠️ Email gmail thật trong commit — nếu push public sẽ lộ, vợ chấp nhận thì OK

## 📅 Tuần này (12/5 - 18/5)

### Thứ 7 (16/5) — TODAY

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

## 📅 Tuần trước (5-11/5)

### CN 10/5 — bão lớn nhất
- ✅ Regen 220 jobs meta sai length (~498 meta) — pattern M1 SPEC / M2 SETUP / M3 GIẢI PHÁP
- ✅ Update rules SEO v2026-05-10 (mục 4: pattern M1/M2/M3 + CTA mapping + filler cấm; mục 10: format SPEC-FIRST cho money product; mục 18: ALT template 6 vị trí)
- ✅ Code `ai_writer.auto_fix_metas()` validator: quick suffix " với giá tốt" + AI regen max 2 lần
- ✅ Money product detection: auto-flag SP có keyword qd-oled/240Hz/RTX 4070+/MacBook/iPhone/ROG/...
- ✅ Logic chèn ảnh động `pick_target_image_count()`: ≤4 ảnh → hết, ≥5 → 4-6 tùy main H2
- ✅ Fix title case 812 titles (rule-based, BRANDS + ACRONYMS whitelist)
- ✅ Multi-storage Haravan asset upload ⚠️ TÁI INCIDENT race condition tạo 8+ SP rác → vợ pause Haravan + xóa sub-bot Nghia_subSEO
- ✅ Combo Layer 1+3+4: Task Scheduler auto-start (At startup), DB backup 3AM daily zip giữ 30 ngày, Telegram bot @Web_Sintech_bot
- ✅ Update ALT 590 ảnh theo template 6 vị trí (rules mục 18)
- ✅ Filter category trong `/content-jobs?cate=...`
- ✅ Dump `Past.txt` full prompt train AI

### T7 9/5
- ✅ Push 12 SP money product vào queue, gen content cho QD-OLED, RTX 5070, Laptop HP G10
- ✅ Audit 295 bài AI gen → phát hiện 184 meta sai length

### T6 8/5
- ✅ Build pipeline content_jobs hoàn chỉnh: text phase + image phase + sync

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
