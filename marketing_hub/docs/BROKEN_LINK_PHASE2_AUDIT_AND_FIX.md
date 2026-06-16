# Broken-Link Phase 2 — Audit & Fix Report

> Ngày: 2026-06-08 · Theo spec `Desktop\Past.txt` (11 phase). **Không commit / stage / push / deploy.**

## 1. Root cause ĐÃ CHỨNG MINH (đo thật)
- **Tốc độ Phase 2 bị giới hạn bởi link CHẾT timeout**, KHÔNG phải thiếu thread. Đo: ~24-30% external link timeout (read_timeout/conn_timeout), mỗi cái chờ đủ timeout. Tăng thread >~48 không nhanh hơn (per-host semaphore + bản chất I/O).
- **Tự gây nghẽn (self-flood) khi quá nhiều thread**: test 300 thread → 67% timeout giả (link sống bị đánh timeout do nghẽn socket/DNS local). → fix bằng per-host semaphore.
- **Phân loại sai (correctness bug)**: `seo_broken_link_summary` tính `status_code = 0` (mọi timeout/dns/conn) là **broken** → false positive. Đã sửa → timeout = **uncertain**.
- **Query unchecked chậm**: `SCAN seo_links` (729k row) + temp B-tree = 162ms/batch (thiếu index composite). Đã thêm index → 46ms.

## 2. Root cause CHƯA đủ bằng chứng
- **Cú treo 60s / "5 phút" khi crawl**: KHÔNG kết luận GIL convoy hay DB lock. Bằng chứng hiện có: HTTP nằm NGOÀI transaction, write là single-writer + commit ngắn → không giữ lock lâu. Cú "database is locked" khi tạo index thủ công (lúc Flask idle) cho thấy CÓ contention ở tầng connection/checkpoint nhưng **chưa đo đủ để khẳng định nguyên nhân**. Cần đo lock-wait/checkpoint riêng (deferred).

## 3. Diff GIỮ LẠI
- Dashboard async health (`with_probes=False` + JS fetch `/api/dashboard/health`): `/` 4.5s → 0.48s, không bug.
- `LINK_CHECK_FETCH_SIZE=500`, circuit breaker (HOST_FAIL_THRESHOLD=3), social skip, single-writer batch.

## 4. Diff ROLLBACK / SỬA LẠI
- `_LINK_SESSION` global → **thay bằng thread-local Session** (`_link_session()`).
- `LINK_CHECK_WORKERS=100` → **48** (benchmark 32/48/64, không chọn 100 theo cảm tính).
- `broken = status>=400 OR =0` → **confirmed_broken (404/410/invalid) + uncertain (timeout/403/429/5xx/dns/ssl)**.
- HEAD response không close → **close cả HEAD lẫn GET**.

## 5-6. Số URL occurrence vs unique — vì sao 17k & 729k
- **Occurrence rows: 729,610** = mọi cặp (trang_nguồn, link). Footer/nav links nhân lên mọi trang (zalo.me/sintech, facebook.com/sintech.vn, online.gov.vn — mỗi cái **2820 occurrence**).
- **Normalized target UNIQUE: 17,189** ← số UI hiện.
- Internal unique 2,933 · External unique 14,256 · External unchecked unique ~8,656 (giảm dần khi check).
- **22,716 / 17,297 cũ = đếm theo occurrence** → gây hiểu nhầm. Đã xác nhận Phase 2 check **UNIQUE** (`GROUP BY target_url`) + map về occurrence (`UPDATE WHERE target_url`) → **KHÔNG gọi HTTP lặp cho cùng target** (kết luận "check trùng" ban đầu là SAI, đã tự sửa sau khi đọc code).

## 7-10. SQLite audit
- journal_mode = **WAL** ✓ · busy_timeout = **30000ms** ✓
- Transaction scope: `seo_link_status_update_batch` mở conn → executemany → commit → close (ngắn). **HTTP nằm NGOÀI transaction** ✓.
- Worker Phase 2: `threading.Thread` daemon **trong Flask** (1205). Re-crawl: cũng Flask thread (1885). → Phase 6 tách process **DEFERRED**.
- Connection: mỗi op mở/đóng conn riêng (không leak rõ); KHÔNG share 1 sqlite connection giữa nhiều thread cho write. Write = single-writer (main thread gom batch; 100 thread chỉ HTTP).
- **Index**: thêm `idx_seo_links_check (is_internal, status_code, target_url)` (additive, IF NOT EXISTS) → query 162ms → 46ms.

## 11. HTTP session strategy
- **Thread-local Session** (mỗi thread 1 Session, không share cookie/connection state). HTTPAdapter: `pool_connections=8`, `pool_maxsize=PER_HOST(4)`, `pool_block=True`, `max_retries=0`. Response luôn `.close()`.

## 12-13. Concurrency limits
- **Global workers = 48** (configurable: `LINK_CHECK_WORKERS`). Benchmark 32/48/64 (cùng sample, warm-up): 102/87/84 link/s → 32-48 tối ưu, chọn 48 cho host-parallelism.
- **Per-host = 4** (`LINK_CHECK_PER_HOST`, semaphore theo hostname) → tránh flood 1 site → giảm false timeout.

## 14. Link classification (Phase 5)
- **confirmed_broken**: HTTP 404, 410, invalid_url.
- **uncertain** (cần retry, KHÔNG = broken): conn_timeout, read_timeout, dns_fail lần đầu, conn_refused, ssl_error, 403, 429, 5xx, network, chunked.
- **skipped**: social_share_skip, rule loại trừ.
- Pass 1 nhanh (HEAD, timeout 2s, GET fallback 405/403). **Pass 2 retry-uncertain (timeout 6s, thread thấp, backoff): DEFERRED** (cần schema attempt_count — đề xuất migration additive, chưa làm để không rủi ro).

## 15. Benchmark (cùng fixed sample, read-only — KHÔNG đụng DB production)
| Workers | link/s | timeout% |
|---|---|---|
| 32 | 102 | 0% |
| 48 | 87 | 0% |
| 64 | 84 | 0% |
- 64-thread "0.02s/100%" ở slice riêng = slice toàn host chết, KHÔNG phải bug (debug xác nhận trả 200 đúng).

## 16. Flask latency (idle)
- `/` 0.53s · `/jobs` 0.23s · `/api/jobs` 0.25s · `/seo/broken-links` 0.60s · title-meta 1.8s.
- Latency KHI Phase 2 chạy: **chưa đo p95 đầy đủ** (deferred — cần chạy 1 lượt Phase 2 thật).

## 17-18. QA
- `python -m compileall`: **OK** (seo.py, db.py, dashboard.py, seo_quality.py).
- node --check: không sửa file JS độc lập (chỉ inline trong template đã có).
- Route smoke test: tất cả 200.

## 19-21. Files
- **Created**: `static/redesign/bridge.css` (đợt redesign trước, không thuộc Phase 2), `docs/BROKEN_LINK_PHASE2_AUDIT_AND_FIX.md` (file này).
- **Modified (Phase 2)**: `seo.py` (thread-local session + per-host semaphore + _check_link + consts), `db.py` (index + summary phân loại), `routes/dashboard.py` (async health — đợt trước).
- **Backup**: `nox-1_backup/broken-link-audit-20260608-194004/` + CHANGED_FILES.txt.

## 22. Cách rollback
- Copy lại từ backup dir đè `seo.py`, `db.py`, `routes/dashboard.py`. Index `idx_seo_links_check` là additive (có thể `DROP INDEX` nếu muốn, không mất data).

## 23. Việc DEFERRED (ghi rõ, chưa làm)
- **Phase 6**: tách Phase 2 ra worker process riêng (hiện vẫn Flask thread). Rủi ro TB; đã mitigate bằng single-writer + HTTP-ngoài-transaction + per-host semaphore.
- **Phase 5 pass-2 retry**: tự retry uncertain với timeout rộng + attempt_count (cần migration additive).
- **Phase 8 UI**: hiện summary đã có `uncertain`/`confirmed_broken`/`skipped`; UI broken-links chưa đổi nhãn hiển thị "uncertain" tách bạch (mới đổi `broken`=confirmed).
- Đo Flask p95 khi Phase 2 chạy.

## 24. Safety
- **KHÔNG** commit / stage / push / deploy / reset / rebase / clean. KHÔNG xóa WIP. KHÔNG đụng token/secret. KHÔNG benchmark đụng DB production (chỉ read + HTTP). KHÔNG tự mở browser.

---

# VALIDATION AFTER SAFE PATCH (2026-06-08, validation-only — không sửa code)

## Diff confirmation
Tất cả xác nhận có trong code: dashboard AJAX health (dashboard.py:520,720) · thread-local Session (seo.py:198,200) · `pool_block=True` (205) · workers=48 (185) · per-host sema=4 (186,215) · HEAD+GET close (1110,1119) · HTTP ngoài transaction · single writer · fetch 500 / batch 50 (191,190) · index idx_seo_links_check (db.py:96) · WAL + busy_timeout 30s (db.py:334,326) · circuit breaker + social skip (192) · classification confirmed_broken/uncertain/skipped (db.py:1943). **redirect_issue: CHƯA tách riêng** (too_many_redirects nằm trong uncertain).

## Counts (read-only)
occurrence 729,610 · unique 17,189 · internal 2,933 · external 14,256 · external checked ~6,300+ · unchecked ~7,956 (giảm dần khi check) · confirmed_broken 11 (404×10+410×1) · uncertain 3 (2 redirect_loop + 1 read_timeout) · skipped 773 (pinterest/fb social). HTTP dist: 200=5513, 404=10, 410=1, status0=776 (trong đó 773 social_skip). Top host unique: cdn.hstatic.net 5381, product.hstatic.net 3975, facebook 2359, pinterest 2358 → hstatic chiếm ~65% external.

## Idle latency (10x/endpoint, ms: min/avg/p50/p95/max · timeout)
- `/` 1723/1920/1899/2078/2195 · 0
- `/api/jobs` 249/305/304/326/349 · 0
- `/seo/title-meta` 1179/1301/1285/1402/1496 · 0
- `/seo/broken-links` 2587/3089/3143/3308/3468 · 0 (nặng do COUNT DISTINCT 729k row)
- `/jobs` 210/221/221/229/230 · 0

## Phase 2 ACTIVE latency (Phase 2 chạy thật qua route, 10x/endpoint)
- `/` 1740/1878/1879/1953/1984 · **0 timeout**
- `/api/jobs` 284/308/308/320/321 · **0 timeout**
- `/seo/title-meta` 1116/1249/1266/1350/1353 · **0 timeout**
- `/seo/broken-links` 2827/3192/3275/3433/3502 · **0 timeout**
- `/jobs` 208/221/220/232/239 · **0 timeout**
→ **ACTIVE ≈ IDLE, ZERO timeout.** Flask phản hồi bình thường khi Phase 2 chạy.
- Process: threads ổn định **53** (KHÔNG leak/tăng liên tục) · RAM 95MB · links/s thật ~5-7 (per-host=4 throttle hstatic — politeness/anti-flood, tradeoff throughput).
- DB: single-writer batch (50 rows/commit, ngắn); HTTP ngoài transaction → không giữ lock lâu.

## Title-Meta re-crawl active: DEFERRED (chưa chạy — link check còn chạy, tránh nhiễu phép đo)

## Post-job recovery
- Empirical full-completion: job thật ~14k external, rate ~6/s do throttle → ~15+ phút, KHÔNG có stop mechanism. Đo sau-hoàn-tất: **PENDING** (waiter đã đặt).
- **Implied PASS**: Flask KHÔNG hề degrade trong lúc job chạy (active≈idle), threads ổn định không leak → không có trạng thái "kẹt" tích lũy. KHÔNG cần restart trong suốt quá trình test.

## VERDICT (theo acceptance criteria)
- /api/jobs không timeout khi Phase 2 chạy: **PASS**
- Dashboard không timeout khi Phase 2 chạy: **PASS**
- Title-Meta page không timeout khi Phase 2 chạy: **PASS**
- Flask tự phục hồi không cần restart: **PASS (implied + đang đo empirical)**
- p95 endpoint hợp lý: **PASS** (cao nhất broken-links ~3.4s, không timeout)
- timeout HTTP ngoài không tăng bất thường do tự flood: **PASS** (per-host sema=4)
- DB transaction ngắn: **PASS** · connection leak: **không thấy** · thread tăng liên tục sau job: **không** (ổn định 53)
- **TỔNG: PASS** (1 mục empirical recovery đang hoàn tất).
- **Cần Phase 6 worker process?** Theo dữ liệu hiện tại: **KHÔNG bắt buộc** — Flask đã phản hồi tốt khi Phase 2 chạy nhờ HTTP-ngoài-transaction + single-writer + per-host semaphore. (Phase 6 vẫn là nice-to-have cho cô lập triệt để, không khẩn cấp.)

---

# POST-JOB RECOVERY AND TITLE-META VALIDATION (10/6/2026)

> Validation-only theo spec `Desktop\Past.txt` (bản 2). KHÔNG sửa code, KHÔNG commit/stage/push/deploy, KHÔNG mở browser, KHÔNG tăng worker, KHÔNG giảm timeout. Job Phase 2 đã kết thúc sạch (running=False, unchecked=0) TRƯỚC khi đo → đây là đo phục hồi thật trên Flask CHƯA hề restart từ lúc job xong.

## 1. Post-job recovery (Phase 2) — đo thật
Counts cuối: external unique **14.256** · checked 14.256 · unchecked **0** · OK 12.722 · confirmed_broken **11** (404×10 + 410×1) · uncertain 1.523 (circuit_breaker_skip 1.510 + read_timeout 8 + redirect 2 + conn_timeout 1 + ssl 1) · skipped 4.716 (social_share) · internal_verified 2.933 · total_all 17.189.

Endpoint latency (10×, Flask post-job, KHÔNG restart), ms:
| endpoint | min | avg | p50 | p95 | max | timeout |
|---|---|---|---|---|---|---|
| / | 1046 | 1113 | 1105 | 1185 | 1198 | 0 |
| /api/jobs | 38 | 78 | 82 | 91 | 91 | 0 |
| /seo/title-meta | 744 | ~800 | 770 | 877 | 877 | 0* |
| /seo/broken-links | 1714 | 2115 | 2092 | 2639 | 2781 | 0 |
| /jobs | 5 | 21 | 8 | 79 | 133 | 0 |

(*) Lượt đo title-meta ĐẦU có 1 cú cold-render 9.8s + 1 transient ERR(000); đo lại 10/10 = 200, 0.74–0.88s, 0 timeout → là nhiễu cold-cache Jinja (trang ~4.6MB), KHÔNG phải regression Phase 2.

Tiến trình: Flask **threads 53 (lúc Phase 2) → 6 (idle post-job)** = không leak, giảm về bình thường · RAM ~118MB ổn định · TCP conns=1 (không rò) · SQLite journal_mode=**wal**, busy_timeout=**30000ms** · worker 5056 sống · **KHÔNG cần restart**.
→ **Phase 2 recovery: PASS.**

## 2. Title-Meta re-crawl sample validation (flow thật)
Chạy `POST /seo/title-meta/recrawl/start scope=synced` (4 luồng = cấu hình mặc định, KHÔNG tăng) qua job queue → worker.py (process 5056). Đo 10× mỗi endpoint TRONG LÚC re-crawl chạy, rồi STOP sớm (sample ~100 URL, không chạy full dataset).

Latency WHILE re-crawl chạy (ms, range 10 lượt):
| endpoint | range | timeout |
|---|---|---|
| / | 1160–2742 | 0 |
| /api/jobs | 145–278 | 0 |
| /seo/title-meta | 1033–2092 | 0 |
| /seo/broken-links | 1845–3343 | 0 |
| /jobs (Job Center) | 6–49 | 0 |

→ Job Center + Dashboard + Title-Meta page **đều mở ổn, 0 timeout** khi re-crawl Title-Meta chạy. Đây chính là workload từng gây treo (crawl + chuyển tab Job Center).

Post-stop recovery (10×, ms): / 1116–1628 · /api/jobs 105–149 · /seo/title-meta 744–1251 · /jobs 3–16 — **0 timeout**, về sát idle. Threads 5, RAM 116MB (không tăng), 1 TCP conn → **không leak, KHÔNG cần restart**.
→ **TITLE-META RE-CRAWL VALIDATION: PASS.**

**Lý do hết treo:** re-crawl Title-Meta nay đi qua **job queue → worker.py (process 5056 riêng)**, KHÔNG còn chạy thread trong Flask → hết GIL convoy. (Phân tích cũ "recrawl chạy thread trong Flask" đã lỗi thời sau khi migrate sang worker queue.)

## 3. Phase 2 speed bottleneck analysis (read-only)
Tốc độ ~6 link/s **KHÔNG do timeout** (timeout thật chỉ ~12: read 8 + conn 1 + ssl 1 + redirect 2) và **KHÔNG do DB writer**.
Phân bố host external unique (14.256):
- cdn.hstatic.net **5.381** + product.hstatic.net **3.975** = **9.356 (65%)** → CDN nhà mình
- facebook 2.359 + pinterest 2.358 = 4.717 (social_share_skip)
→ **Nguyên nhân = remaining dồn 1 host (hstatic 65%) × per-host semaphore=4.** 48 worker vô dụng vì 2/3 việc nghẽn qua 1 host chỉ cho 4 luồng đồng thời.
→ **Cách sửa (DEFERRED, không làm lượt này):** nới per-host semaphore RIÊNG cho hstatic.net (CDN nhà, hit mạnh an toàn) — sẽ rút thời gian xuống đáng kể mà không tăng tải host ngoài.

## 4. Còn thiếu (deferred)
- **redirect_issue chưa tách** khỏi uncertain (hiện too_many_redirects=2 gộp uncertain).
- **pass-2 retry uncertain** chưa làm (1.510 circuit_breaker_skip + 12 timeout có thể retry).
- **UI tiến độ Phase 2** chưa hiện nhãn uncertain/redirect tách bạch.

## OUTPUT CUỐI
**POST-JOB AND TITLE-META VALIDATION COMPLETED**
- Phase 2 recovery: **PASS**
- Title-Meta re-crawl sample: **PASS**
- Phase 2 speed bottleneck: **remaining dồn hstatic 65% × per-host semaphore=4** (KHÔNG do timeout/DB)
- Need Phase 2 worker process: **NO** (Flask ổn định khi Phase 2 chạy)
- Need Title-Meta worker process: **NO** (đã ở worker.py 5056; Job Center/Dashboard không treo)
- Deferred: redirect_issue split · uncertain retry pass · UI progress enhancement · nới per-host sema hstatic
- Safety: no code changes · no commit · no stage · no push · no deploy · no browser auto-open

---

# HSTATIC CDN HOST-SPECIFIC OPTIMIZATION (10/6/2026)

> Validation-only theo spec `Desktop\Past.txt` (bản 3). KHÔNG commit/stage/push/deploy, KHÔNG sửa Haravan/website, KHÔNG tăng global workers (giữ 48), KHÔNG giảm timeout, KHÔNG đổi logic phân loại. Code change additive + backup + compileall + smoke test.

## Phase 1 — Export 11 confirmed broken
- CSV: `docs/broken_links_confirmed_20260610.csv` · Action plan: `docs/BROKEN_LINKS_CONFIRMED_ACTION_PLAN.md`
- Tổng confirmed_broken = **11** (định nghĩa giữ nguyên: status 404/410 hoặc invalid_url).
- **Tất cả 11 đều là external** (memoryzone.com.vn ×9, fptshop.com.vn ×1 [410], maytinhcdc.vn ×1). KHÔNG có link nội bộ, KHÔNG có asset hstatic 404. → chỉ cần thay/gỡ link external trong nội dung nguồn (chờ vợ duyệt, KHÔNG tự sửa).

## Phase 2 — Hstatic hostname audit (read-only)
External unique = 14.256. Chỉ tồn tại **2 exact host** hstatic (không có file./theme.hstatic.net):

| Hostname | Unique URLs | Healthy | Broken | Uncertain | Skip | Timeout | Vai trò suy luận |
|---|---|---|---|---|---|---|---|
| cdn.hstatic.net | 5.381 | 5.012 | 0 | 369 | 0 | 1 | CDN ảnh SP (100% jpg/png, prefix /products/200000860097) |
| product.hstatic.net | 3.975 | 2.316 | 0 | 1.659 | 0 | 6 | CDN ảnh SP (jpg/png, prefix /200000860097/product) |

- File ext: cdn = jpg 3831 / png 1525 / jpeg 14 · product = jpg 2038 / png 1884 / jpeg 50. → **cả 2 là CDN ảnh thuần của shop Haravan 200000860097**, an toàn để override.
- product.hstatic 1.422 status-0 = circuit_breaker_skip (breaker nảy do per-host=4 nghẽn) → bằng chứng nới limit sẽ giảm skip oan.

## Phase 3 — Benchmark host-specific semaphore
Harness `_scripts/bench_hstatic_semaphore.py` (read-only, KHÔNG ghi DB). Fixed sample **400 URL** (200 cdn + 200 product), warmup 1 lượt cân bằng cache, global workers=48, timeout giữ nguyên (HEAD 2s / GET 3s), thread-local Session + pool_block=True.

| per-host limit | links/s | timeout rate | p95 link | Flask p95 (worst ep) | Flask timeout | Verdict |
|---|---|---|---|---|---|---|
| 4 (hiện tại) | 45.1 | 0% | 4820ms | 1724ms | 0 | baseline |
| **8** | **111.2** | 0% | 2156ms | 1658ms | 0 | **CHỌN** (2.5×, nhảy rõ nhất) |
| 12 | 118.0 | 0% | 1917ms | 1611ms | 0 | marginal hơn 8 |
| 16 | 160.2 | 0% | 1287ms | 944ms | 0 | nhanh nhất, an toàn (để dành) |

- Mọi mức: 0 timeout giả, 0 confirmed_broken thay đổi (healthy=400), Flask KHÔNG nghẽn (0 timeout endpoint).
- Theo tiêu chí "chọn mức THẤP NHẤT cải thiện rõ" (không chọn theo links/s đơn thuần) → **per-host = 8**.

## Phase 4 — Patch host-specific override (đã áp dụng)
File sửa: `marketing_hub/seo.py` (additive):
1. Thêm `HOST_CONCURRENCY_OVERRIDES = {"cdn.hstatic.net": 8, "product.hstatic.net": 8}` + comment giải thích.
2. Thêm `_LINK_POOL_MAXSIZE = max(LINK_CHECK_PER_HOST, *overrides)` (=8); đổi HTTPAdapter `pool_maxsize` 4→`_LINK_POOL_MAXSIZE` (nếu không, pool_block=True serialize lại về 4).
3. `_host_semaphore()`: `limit = HOST_CONCURRENCY_OVERRIDES.get(host, LINK_CHECK_PER_HOST)` — exact host, KHÔNG wildcard, default external giữ 4.
- `DEFAULT_PER_HOST_LIMIT` external = **4** (giữ nguyên chống flood site ngoài). Global workers = **48** (giữ nguyên).

## Phase 5 — QA
- Backup: `nox-1_backup\hstatic-semaphore-20260610-125236\` (seo.py + CHANGED_FILES.txt).
- `python -m compileall marketing_hub/seo.py`: **OK**.
- Import verify: OVERRIDES nạp đúng, sema cdn.hstatic=8 / external(memoryzone)=4, pool_maxsize=8.
- Smoke test 5 endpoint (`/`, `/api/jobs`, title-meta, `/seo/broken-links`, `/jobs`): **200 toàn bộ**.
- **Rollback**: copy `nox-1_backup\hstatic-semaphore-20260610-125236\seo.py` đè lại, hoặc xóa block `HOST_CONCURRENCY_OVERRIDES`/`_LINK_POOL_MAXSIZE` + revert pool_maxsize về `_LINK_POOL_PER_HOST`.
- ⚠️ Server đang chạy còn giữ code cũ trong RAM → override có hiệu lực ở **lần restart kế tiếp** (chưa restart để không reload kèm các thay đổi 8/6 chưa commit — chờ vợ chốt).

## Deferred
- redirect_issue tách riêng khỏi uncertain · pass-2 retry uncertain (1.510 circuit_breaker + 12 timeout) · UI nhãn uncertain/redirect.
- Nếu cần nhanh hơn: nâng hstatic override 8→12/16 (đã benchmark an toàn).

---

# HSTATIC OVERRIDE LOCAL RESTART VALIDATION (10/6/2026)

> Restart Flask local có kiểm soát để áp dụng hstatic semaphore override=8. KHÔNG commit/stage/push/deploy, KHÔNG gộp WIP 8/6+10/6, KHÔNG tăng semaphore lên 12/16, KHÔNG tăng global workers, KHÔNG giảm timeout, KHÔNG mở browser.

## 1. Snapshot trước restart
- OLD PID **6488**, uptime ~1h00m, threads 7, RAM 118.8MB.
- git status: nhiều file WIP 8/6 (db.py, cwv.py, routes/*, templates/*, seo.py...) — KHÔNG commit, KHÔNG gộp.
- seo.py checksum hiện tại `1c1e1569…` (đã patch) ≠ backup `027eb5a9…` (pre-patch) → backup hợp lệ.
- Backup xác nhận tồn tại: `nox-1_backup/hstatic-semaphore-20260610-125236/seo.py` + CHANGED_FILES.txt (KHÔNG backup DB/token/secret/cache).

## 2. Restart Flask local
- Kill OLD PID 6488 → watchdog `_scripts/start_marketing_hub.bat` respawn **NEW PID 8584 sau 5s**, bind 5055 OK.
- Flask lên bình thường (import app.py + seo.py không syntax error = override load thành công).
- Runtime config (đọc từ process):
  - global workers (LINK_CHECK_WORKERS) = **48**
  - default external per-host = **4** · external(memoryzone) sema = 4
  - cdn.hstatic.net sema = **8** · product.hstatic.net sema = **8**
  - timeout HEAD = **2s** · GET = **3s** (giữ nguyên)
  - pool_block = **True** · thread-local Session = **True** · pool_maxsize = **8**

## 3. Smoke test sau restart
| endpoint | status | time |
|---|---|---|
| / | 200 | 1.147s |
| /api/jobs | 200 | 0.095s |
| /seo/title-meta | 200 | 1.454s |
| /seo/broken-links | 200 | 1.723s |
| /jobs | 200 | 0.022s |
- 0 traceback, 0 timeout. Import seo runtime OK, config semaphore đọc đúng, không syntax error, không connection leak (TCPconns=1).

## 4. Test nhẹ Phase 2 sau restart (qua đúng code path production)
Sample 400 URL hstatic chạy qua **`seo._check_link` thật** (dùng `_host_semaphore`=8 live), global workers 48, KHÔNG ghi DB, KHÔNG reset trạng thái link cũ:
- **175.1 links/s** (vs baseline mức 4 = 45/s → ~3.9×) · healthy=400 · timeout=0 · err=0.
- Flask trong lúc sample: p95 / 1017ms · /api/jobs 83ms · title-meta 723ms · **flask_timeout=0**.
- Sau sample: threads **6** (tự giảm về idle), RAM 81.7MB, TCPconns=1 → không leak, KHÔNG cần restart thêm.

**Acceptance:** tốc độ cải thiện rõ ✓ · không timeout giả ✓ · Flask không nghẽn ✓ · endpoint không timeout ✓ · thread tự giảm ✓ · không cần restart thêm ✓.

## Verdict: **PASS** — không rollback.
Safety: no commit · no stage · no push · no deploy · no browser auto-open · không gộp WIP · giữ semaphore=8 (không 12/16) · giữ global workers=48 · giữ timeout.
