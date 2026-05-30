# SEO Crawl Optimization — Backlog & Roadmap

> Vợ giao project: tối ưu chu trình crawl + audit SEO cho Sintech để máy tắt vẫn chạy được, phát hiện regression sớm, lấp lỗ hổng schema. Tạo 30/5/2026. Source: discussion 30/5 9:47–10:12.

---

## ✅ Task 1 — CWV GitHub Actions (Option C) — ĐÃ CODE XONG

**Trạng thái:** code xong 4 file (script + workflow + 2 route + 1 card), **CHƯA commit / CHƯA restart server / CHƯA smoke test**. Detail đầy đủ ở **WORKLOG.md checkpoint 30/5 10:10**.

**Quyết định kiến trúc (vợ chốt 30/5 9:51):**
- URL source: **sitemap fetch** (`https://sintech.vn/sitemap.xml`, realtime, không cần commit snapshot).
- Output: **full lưu trữ** (commit JSON vào repo + marketing_hub local pull về upsert `seo_cwv`).
- **KHÔNG dùng bot Telegram** — thông báo hiện trên web (ops-center card 🐢 "CWV perf kém").

**File đã thêm/sửa:**
- `nox-1/.github/scripts/cwv_scan.py` (mới)
- `nox-1/.github/workflows/cwv-scan.yml` (mới)
- `nox-1/marketing_hub/app.py` (sửa — +`import requests`, +2 route, +block CWV trong `_dashboard_health`)
- `nox-1/marketing_hub/templates/dashboard.html` (sửa — +1 ops-card 🐢)

**Việc tay vợ cần làm trước khi Action chạy được:**
1. Tạo PSI API Key ở Google Cloud Console (project `ggSCS` đã có, enable PageSpeed Insights API).
2. Add GitHub Secret `PSI_API_KEY` ở repo `nghiango4554/nox-1` → Settings → Secrets and variables → Actions.

**Việc tiếp theo của anh (Nox-N kế tiếp):**
1. Smoke test `py -3.12 .github/scripts/cwv_scan.py --strategy mobile --url-type page --limit 2 --output /tmp/cwv_test.json` (encoding đã fix).
2. Restart marketing_hub (kill PID python, watchdog .bat tự relaunch).
3. Commit + push 4 file → Action mới được GitHub nhận diện.
4. Manual trigger 1 lần qua `workflow_dispatch` để test pipeline.

---

## ✅ Task 2 — Cron weekly + diff vs tuần trước → web alert (KHÔNG Telegram) — DONE 30/5/2026

**Là gì:** Mỗi Chủ nhật 02:00 → Task Scheduler kick `/api/seo/cwv/scan/start-all` (local) hoặc dùng kết quả GitHub Actions từ Task 1 → diff vs tuần trước → hiện alert trên web dashboard: "Tuần này avg mobile 71.8→73.5 (+1.7) · 12 URL khá hơn · 5 URL regress: [list URL]".

**Implement plan:**
- Thêm bảng `seo_cwv_history` (week_no, year, url, strategy, score, lcp_ms, cls_score) — snapshot weekly.
- Script `weekly_cwv_diff.py`:
  - So sánh `seo_cwv` (mới nhất) vs `seo_cwv_history` của tuần trước.
  - Output JSON: `{avg_change, improved: [...], regressed: [...]}`.
  - Lưu vào file `marketing_hub/data/cwv_weekly_diff.json`.
- Tích hợp vào dashboard ops-center: card "📊 Tuần này vs tuần trước" hiện trend + top 5 regress URL link tới `/seo/cwv?filter=regressed`.
- Task Scheduler cron Sunday 02:00 (local Windows).

**Effort:** 3–5h
**ROI:** ⭐️ RẤT CAO — phát hiện regression theme/code ngay, không phải manual check.
**Caveat cũ:** "Bot Telegram 401 cần rotate token" → **BỎ QUA** vì vợ đã chốt KHÔNG dùng bot Telegram, alert lên web là đủ.

**Phụ thuộc:** Task 1 chạy thật (có data trong `seo_cwv` để diff).

**Done 30/5/2026:** 5/5 phase đầy đủ. File mới: `db.py` (bảng `seo_cwv_history` + 3 helper), `_scripts/weekly_cwv_snapshot.py`, `_scripts/weekly_cwv_diff.py`, `_scripts/run_weekly_cwv.bat`, `_scripts/start_weekly_cwv_hidden.vbs`, `templates/seo_cwv_diff.html`. Sửa: `app.py` (route `/seo/cwv/diff` + block `out["cwv_diff"]`), `templates/dashboard.html` (card 📊), `_scripts/INSTALL.md` (Layer 5). Tuần 22/2026 đã có snapshot thật trong DB (4972 rows). Việc tay vợ: tạo Task Scheduler "Marketing Hub Weekly CWV Diff" Sunday 02:00 theo INSTALL.md.

---

## 🟡 Task 3 — Orphan page detection (thu hẹp — phần lớn ĐÃ CÓ)

**Là gì:** Tìm URL có trong sitemap/DB nhưng KHÔNG có internal link nào trỏ tới → trang "mồ côi", Google ít crawl.

**Hiện trạng 30/5/2026 (audit khi định chia phase):**
- ✅ **ĐÃ CÓ rồi**: route `/seo/inlinks?view=orphans` (`app.py:985`), template `seo_inlinks.html`, helper `db.seo_orphan_pages(url_type, limit)` ở `db.py:739` query đúng kỹ thuật `LEFT JOIN seo_links ON l.target_url=p.url AND l.is_internal=1 WHERE l.id IS NULL`. Filter theo url_type sẵn. Helper ngược `db.seo_inlinks_for_url(target_url)` query ai link tới X — sẵn.
- ❌ **Còn thiếu**: (1) cross-check sitemap.xml (URL trong sitemap nhưng KHÔNG có trong `seo_pages` — "deep orphan", Google biết qua sitemap mà mình chưa crawl), (2) gợi ý nguồn link "nên thêm link từ trang Y" (cùng category/blog gần nhất).

**Đề xuất tích hợp (KHÔNG làm trang riêng — gộp vào pipeline crawl + UI `/seo/inlinks` hiện có):**

### Phase 3A — Function `crawl_sitemap_diff()` trong pipeline `/seo` crawl
- Sau mỗi full crawl `/seo`, post-process: fetch sitemap.xml, diff vs `seo_pages` table.
- INSERT URL sitemap-only với url_type discover được từ pattern URL + flag `discovered_from='sitemap'` (cột mới).
- Ưu điểm: tận dụng pipeline crawl đã có, ko tốn API call thừa, ko phải job riêng.

### Phase 3B — UI mở rộng `/seo/inlinks?view=orphans`
- Thêm filter `?source=sitemap` để xem nhóm orphan-from-sitemap riêng.
- Column "Gợi ý link từ" — auto query: top 3 page cùng url_type + cùng prefix handle/category + có internal_links_total cao nhất.
- Hành động: nút "+ Vào content_jobs" (nếu là product/blog cần content) hoặc "Đánh dấu skip" (URL nội bộ ko cần index).

### Phase 3C — Dashboard ops-card "👻 Orphan pages"
- Card mới ngay cạnh card 📊 CWV diff, link tới `/seo/inlinks?view=orphans`.
- Hiển thị: total orphan + breakdown (crawled-orphan / sitemap-only) + url_type top 3.

**Effort (thu hẹp):** ~3-4h (vs 4-6h backlog cũ vì phần MAIN đã có)
- 3A: 1.5h (function + DB column + integrate)
- 3B: 1.5h (UI extension)
- 3C: 30 phút (dashboard card)

**ROI:** ⭐⭐ TRUNG BÌNH — site nhỏ (~2486 URL), Google ko thiếu crawl budget. Nhưng vì phần lớn đã có → effort thu hẹp → ROI/effort khá hơn.
**Recommendation:** 🟡 **LÀM SAU Task 4** (Task 4 ROI cao hơn rõ rệt).

---

## ✅ Task 4 — Schema validator (JSON-LD audit) — DONE 30/5/2026 5/5 phase

**Là gì:** Fetch HTML từng URL, extract `<script type="application/ld+json">` blocks bằng BeautifulSoup, identify schema @type (Product / Article / FAQPage / ItemList / BreadcrumbList / Organization...) → biết URL nào có / thiếu schema cho rich snippet (sao, giá, FAQ, breadcrumb trong SERP).

**Approach chốt (30/5):** Self-extract bằng BeautifulSoup, KHÔNG gọi external validator (`validator.schema.org/api/v1/check` rate limit 1 req/s, ~40 phút cho 2486 URL; self-extract chạy ~5-7 phút với 5 worker, không quota).

**Khám phá quan trọng 30/5 Phase 4B (đảo ngược backlog cũ):**
- ✅ Sintech ĐÃ CÓ `Product` schema cho SP (Haravan theme inject mặc định).
- ✅ Sintech ĐÃ CÓ `Article` schema cho blog.
- ✅ Mọi page có `Organization` + `Store` + `BreadcrumbList`.
- ❌ **THIẾU `FAQPage`** trên blog → chưa nhả rich snippet câu hỏi.
- ❌ **THIẾU `ItemList`** trên collection → chưa nhả rich snippet danh sách SP.
- ❌ Một số page 404 trong DB cũ → cần cleanup ở bước sau.

→ Scope thực tế NHỎ HƠN backlog ban đầu nhiều. Phase 4C bulk audit sẽ ra con số chính xác.

**Effort thực tế ước tính:** ~5-6h (giảm so 6-8h backlog cũ vì self-extract + scope nhỏ hơn).
**ROI:** ⭐️ vẫn cao — fix FAQPage blog + ItemList collection vẫn nhả rich snippet, nhưng impact nhỏ hơn assumption ban đầu.
**Recommendation:** ✅ **ĐANG LÀM** (khởi động 30/5/2026 sau khi Task 2 commit).

---

### ✅ Phase 4A — DB schema (30/5 11:30, DONE)

Thêm 7 cột vào `seo_pages` qua migration loop `init_db()`:
- `schema_types` TEXT (JSON array)
- `schema_count` INTEGER DEFAULT 0
- `schema_has_product` / `schema_has_faq` / `schema_has_article` INTEGER DEFAULT 0
- `schema_errors` TEXT (JSON parse errors)
- `schema_scanned_at` TEXT

Index `idx_seo_pages_schema_scanned`.

3 helper trong `db.py`:
- `seo_schema_upsert(url, data)` — UPDATE seo_pages với scan result.
- `seo_schema_stats(url_type=None)` — breakdown total_audited, has_product/faq/article, pct_*.
- `seo_schema_missing(missing='product', url_type, limit=500)` — list URL thiếu schema priority.

Smoke test pass. Baseline: 2026 product URL indexable (target audit Phase 4C).

---

### ✅ Phase 4B — Scanner module (30/5 11:32, DONE)

`marketing_hub/schema_scanner.py` ~150 dòng:
- `extract_jsonld_from_html(html)` — BS4 parse `<script type="application/ld+json">`, JSON.loads, return `{blocks, all_types dedup, errors}`.
- `_iter_jsonld_nodes(payload)` — flatten `@graph` nested + array root.
- `_extract_types_from_node(node)` — handle `@type` string / array / vắng.
- `scan_url(url, timeout=12)` — fetch + extract, robust error.
- `update_page_schema(url)` — wrapper gọi scan + `db.seo_schema_upsert()`.
- CLI: `py -3.12 schema_scanner.py <url> [...]`.

Test 5 URL thật cover 4 url_type: SP ✓ Product, collection ✓ thiếu ItemList, blog ✓ Article, homepage ✓ Org+Store, page test ✓ 404 detect. Edge case handled: malformed JSON, `@graph` nested, `@type` array/string, fetch timeout, HTTP non-200.

→ Memory `reference_competitor_seo_mtm.md` đã strikethrough 2 claim sai về schema gap.

---

### ✅ Phase 4C — Bulk audit + Task Scheduler + data thật toàn site (30/5 11:55, DONE)

**Mục tiêu:** quét toàn site 1 phát → ra data thật về schema gap → quyết định fix scope.

**Scope:**
- `marketing_hub/_scripts/audit_schema_all.py`:
  - Loop `seo_pages` WHERE `status_code=200 AND indexable=1` (~2486 URL).
  - Skip URL có `schema_scanned_at < 7 ngày` (re-audit weekly cycle).
  - 5 worker thread × 0.5s delay → ~5-7 phút toàn site (vs 40 phút nếu rate limit validator API).
  - Progress log + ETA + count per url_type.
  - Args `--limit N` để dev test nhanh.
- `marketing_hub/_scripts/run_audit_schema.bat` + `_scripts/start_audit_schema_hidden.vbs`.
- `INSTALL.md` Layer 6 — Task Scheduler weekly Sunday 03:00 (lệch giờ với CWV diff 02:00).

**Test:** chạy `--limit 50` ra log đẹp → verify 50 row DB updated → chạy full ra số gap thật.

---

### ✅ Phase 4D — UI page `/seo/schema` + 2 API (30/5 11:57, DONE)

**Scope:**
- Route `/seo/schema` trong `app.py`.
- Template `seo_schema.html`:
  - Summary cards: total audited, %has_product, %has_faq, %has_article, %no_schema.
  - Filter UI: url_type + `missing=product/faq/article/any` + last_scanned recency.
  - Bảng list: URL | url_type | schema types có (badge) | thiếu gì (red badge) | last_scanned | action.
  - Per row: nút **"🔄 Re-scan"** (POST scan ngay) + **"👁 Detail"** (popup hiện full JSON-LD blocks raw).
- Default filter `?missing=faq` priority cho blog (gap đã xác định Phase 4B).

**Test:** render với 50 URL audited từ 4C, filter "missing=faq" thấy đúng list blog thiếu schema.

---

### ✅ Phase 4E — Dashboard card 🔖 + integrate health (30/5 11:58, DONE — scoring rule skip)

**Scope:**
- `_dashboard_health()` thêm block `out["schema"]`: total_audited, pct_has_product, pct_has_faq, pct_has_article, missing_faq_count, missing_itemlist_count.
- Dashboard ops-card 🔖 "Schema gap" ngay sau card 📊 CWV diff:
  - Big num: `X% blog có FAQPage` (hoặc metric quan trọng nhất).
  - Sub: `🔴 Y blog thiếu · Z collection thiếu ItemList`.
  - Link → `/seo/schema?missing=faq`.
- (Optional) `data/seo_rules_config.json` thêm rule `missing_faq_blog` (level=warn, score=-3 cho URL type=blog). Tích hợp scoring engine cũ → URL thiếu schema có SEO score thấp hơn.

**Test:** dashboard render đẹp + click card → page filter đúng + rule trừ điểm vào DB sau re-crawl.

---

### 🚫 Phase 5+ — Inject schema (NGOÀI scope Task 4)

Sau khi Phase 4D ra data thật → vợ quyết định có làm Phase 5 không (sửa theme Haravan hoặc dùng metafields để inject FAQPage/ItemList vào head/body của blog/collection). Phase 5 không thuộc Task 4 — sẽ là task riêng khi vợ chốt.

---

## 🎯 Roadmap đề xuất (cập nhật 30/5/2026)

| Thứ tự | Task | Status | Effort | ROI | Phụ thuộc |
|--------|------|--------|--------|-----|-----------|
| 1 | CWV GitHub Actions | ✅ DONE 30/5 | — | ⭐⭐⭐ | PSI key đã setup web |
| 2 | Weekly CWV diff → dashboard | ✅ DONE 30/5 | — | ⭐⭐⭐ | Task 1 chạy thật |
| 3 | Orphan detection (thu hẹp) | 🟡 NEXT (nếu vợ chốt) | 3–4h | ⭐⭐ | Phần lớn đã có |
| 4 | Schema validator (JSON-LD) | ✅ DONE 30/5 | — | ⭐⭐⭐ | Insight: scope nhỏ hơn dự kiến |

**Total còn lại:** ~3-4h dev (Task 3 nếu vợ muốn).

**Có thể tiếp Phase 5+:** Inject FAQPage cho top blog (231 URL) + ItemList cho collection (210 URL) — scope ngoài Task 4, gắn vào Haravan theme hoặc metafields.

---

## 📌 Context đã có sẵn (không cần redo)

- Bảng `seo_cwv` + helpers (`cwv_upsert`, `cwv_stats`, `cwv_top_urls`, `cwv_progress`, `cwv_clear`) — đã có trong `marketing_hub/db.py`.
- Route `/seo/cwv` + scan API (`/api/seo/cwv/scan/start`, `start-all`, `stop`) — đã có trong `app.py`.
- `cwv.py` module — đã có batch scan 8 workers + chain 8 phase mobile/desktop × product/collection/blog/page.
- Repo `nghiango4554/nox-1` public — sẵn sàng cho Actions.
- Memory `reference_competitor_seo_mtm.md`: benchmark đối thủ, đã xác định schema là gap lớn nhất.
