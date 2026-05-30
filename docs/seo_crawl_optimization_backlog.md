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

## 🟡 Task 3 — Orphan page detection (P3, hoãn)

**Là gì:** Tìm URL có trong sitemap/DB nhưng KHÔNG có internal link nào trỏ tới → trang "mồ côi", Google ít crawl.

**Hiện trạng:** Bảng `seo_pages` đã có cột `internal_links`. Query đơn giản: `WHERE internal_links = 0`. Phức tạp hơn: cross-check `sitemap.xml`.

**Implement plan (nếu làm):**
- Page mới `/seo/orphans`: list URL có `internal_links=0` + URL trong sitemap nhưng KHÔNG có trong `seo_pages`.
- Suggest: thêm link từ trang nào (cùng category, blog gần nhất).

**Effort:** 4–6h (parse sitemap + diff + UI)
**ROI:** TRUNG BÌNH — site Sintech chỉ ~2486 URL, Google không thiếu crawl budget. 50–100 orphan vẫn ok nhưng không phải bottleneck.
**Recommendation:** 🟡 **HOÃN** (P3, làm khi rảnh sau Task 2 + Task 4).

---

## ⭐️ Task 4 — Schema validator (JSON-LD audit)

**Là gì:** Gọi `validator.schema.org/api/v1/check` (hoặc Google Rich Results API) check JSON-LD structured data của từng URL → biết URL nào có schema valid (`Product` / `FAQPage` / `Article`) → có cơ hội rich snippet (sao đánh giá, giá, breadcrumb trong SERP).

**Hiện trạng Sintech (per memory `reference_competitor_seo_mtm.md`):** Đối thủ **Minh Tuấn Mobile có đủ schema**, **Sintech THIẾU** JSON-LD `Product` / `FAQPage` / `Article` → mất rich snippet, mất CTR organic. Đây là gap lớn nhất so với đối thủ.

**Implement plan:**
- API call schema.org validator cho từng URL → parse JSON response → DB cột mới:
  - `seo_pages.schema_types` (TEXT, JSON array: `["Product", "BreadcrumbList"]`)
  - `seo_pages.schema_errors` (TEXT, JSON)
  - `seo_pages.schema_scanned_at` (TEXT)
- Page `/seo/schema`: filter URL có/thiếu schema, hiện lỗi gì, recommendation.
- Audit toàn site 1 phát (~2486 URL × ~1s = 40 phút, rate limit 1 req/s).
- Có thể chạy trên GitHub Actions giống Task 1 nếu API key support (tránh đốt máy local).

**Effort:** 6–8h (script + UI + audit run)
**ROI:** ⭐️ RẤT CAO — schema là gap lớn nhất so với MTM, làm xong có thể nhả rich snippet ngay (1–2 tuần Google đọc lại).
**Recommendation:** ✅ **LÀM** (sau Task 2 — Task 2 quick win dễ làm trước, Task 4 nặng hơn nhưng impact lớn nhất).

---

## 🎯 Roadmap đề xuất

| Thứ tự | Task | Effort | ROI | Phụ thuộc |
|--------|------|--------|-----|-----------|
| 1 | ✅ CWV GitHub Actions (đã code) | — | ⭐️⭐️⭐️ | PSI API Key + GitHub Secret (việc tay vợ) |
| 2 | ⭐️ Weekly diff → web alert | 3–5h | ⭐️⭐️⭐️ | Task 1 chạy thật |
| 3 | ⭐️ Schema validator | 6–8h | ⭐️⭐️⭐️ | Độc lập |
| 4 | 🟡 Orphan detection | 4–6h | ⭐️⭐️ | Độc lập, hoãn |

**Total estimate:** ~14–20h dev (chưa kể setup PSI key + Action verify).

---

## 📌 Context đã có sẵn (không cần redo)

- Bảng `seo_cwv` + helpers (`cwv_upsert`, `cwv_stats`, `cwv_top_urls`, `cwv_progress`, `cwv_clear`) — đã có trong `marketing_hub/db.py`.
- Route `/seo/cwv` + scan API (`/api/seo/cwv/scan/start`, `start-all`, `stop`) — đã có trong `app.py`.
- `cwv.py` module — đã có batch scan 8 workers + chain 8 phase mobile/desktop × product/collection/blog/page.
- Repo `nghiango4554/nox-1` public — sẵn sàng cho Actions.
- Memory `reference_competitor_seo_mtm.md`: benchmark đối thủ, đã xác định schema là gap lớn nhất.
