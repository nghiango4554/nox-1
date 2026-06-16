# BLOG REWRITE AI — P2 MOCK QUEUE (10/6/2026)

> Theo spec `Desktop\Past.txt`. P2 = hàng đợi biên tập với **MOCK provider** (chưa gọi AI thật). **KHÔNG gọi AI · KHÔNG consume quota · KHÔNG Haravan PUT · KHÔNG upload ảnh · KHÔNG commit/push/deploy.** Dừng sau P2 để review.

## 1. P1 preserved
Candidates 233 (high 139 / medium 9 / review 6 / unknown 79) · GSC 131 · GA4 35 · no-traffic 100 · selected mặc định high=139. 4 bảng + API P1 giữ nguyên.

## 2. P1 audit (trước khi sửa)
| Hạng mục | Hiện có | Bổ sung P2 | File |
|---|---|---|---|
| candidate/job/draft/event table | ✓ P1 | dùng job/draft/event | db.py |
| selected field | ✓ | API select + bulk | blog_rewrite.py |
| worker spawn detached | ✓ (worker.py, DETACHED_PROCESS + sys.executable) | reuse cho run_blog_rewrite_worker | app.py pattern |
| jobs queue helper | ✓ generic | dùng bảng blog_rewrite_jobs riêng | — |
| stale recovery | ✓ (jobs_requeue_stale_running) | recover_stale_jobs() heartbeat | blog_rewrite.py |

## 3. Backup
`_backup/blog-rewrite-p2-20260610-144311/` (blog_rewrite.py, routes/blog_rewrite.py, templates/blog_rewrite_ai.html + CHANGED_FILES.txt).

## 4. Selection UI
- Checkbox từng bài → `PATCH /api/blog-rewrite/candidates/{id}/select` ghi SQLite local.
- Nút: Top 5/10/20 (top_priority risk=high), Chọn/Bỏ trang, Bỏ chọn tất cả. **KHÔNG có nút chọn toàn bộ 233.**
- Risk guard: mặc định chỉ high selected; tick medium/review/unknown → cho phép nhưng badge "review tay".

## 5. Bulk select guard + API
- `POST /api/blog-rewrite/candidates/select-bulk` mode: select_page / unselect_page / top_priority / clear_all / explicit_ids.
- Job guard: 0 → reject · 1-5 OK · 6-20 OK + warning · >20 → block trừ `explicit_confirm=true` (UI confirm dialog).

## 6. Job orchestration (mock)
Bảng `blog_rewrite_jobs` + membership qua events `queued`. API:
`POST /jobs` (tạo + spawn worker) · `GET /jobs` · `GET /jobs/{id}` · `POST /jobs/{id}/cancel` · `POST /jobs/{id}/retry-failed`.
Job status: queued · running · cancel_requested · cancelled · completed · completed_with_errors · stale. provider=mock · model=mock-blog-rewriter-v1.

## 7. Worker skeleton — `_scripts/run_blog_rewrite_worker.py`
- Spawn bởi Flask: `subprocess.Popen([sys.executable, worker, --job <id>], DETACHED_PROCESS, DEVNULL)` — KHÔNG block Flask.
- Flow: claim queued→running → heartbeat → từng candidate: generating → mock draft → draft_ready → completed_count++. Cancel check giữa các bài. Lỗi 1 bài KHÔNG fail batch.
- **KHÔNG network · KHÔNG AI · KHÔNG Haravan · KHÔNG upload.**

## 8. Mock provider / draft / versioning
- provider=mock · model=mock-blog-rewriter-v1 · prompt_version=BLOG_REWRITE_MOCK_V1. Deterministic, no network.
- Mock draft đủ field (search_intent, outline, title/meta options, summary, body, editor_notes=["MOCK DRAFT — KHÔNG APPLY LIVE"]). Lưu `blog_rewrite_drafts` approval_status=mock_review.
- Versioning: retry → draft version mới (MAX(version)+1), KHÔNG overwrite. UI watermark "Bản nháp thử nghiệm — chưa gọi AI thật".

## 9. Events timeline
job_created · queued · generate_started · generate_completed · generate_failed · cancel_requested · cancelled · retry_requested · stale_detected · stale_recovered. API `GET /candidates/{id}/events` · `GET /drafts/{id}`. KHÔNG ghi token / body HTML đầy đủ.

## 10. Queue panel + polling + detail tabs
- Queue panel: job id/mode/status/progress%/OK-Fail + nút Cancel/Retry, badge "MOCK MODE — không gọi AI thật". Poll 2.5s, dừng khi không còn job active.
- Detail drawer 6 tab: Tổng quan · Evidence · Traffic · Draft mock · Quality · Lịch sử.

## 11. Apply guard (P5 chưa bật)
`POST /drafts/{id}/approve|reject|apply|rollback` + `/bulk-approve` → **501** `{"ok":false,"phase":"P5","error":"Chức năng chưa bật. Không có thay đổi nào được gửi lên Haravan."}`. Tuyệt đối KHÔNG gọi PUT.

## 12. Stale recovery
`recover_stale_jobs()` (gọi trong GET /jobs): job running/cancel_requested + heartbeat > 3 phút → stale → candidate generating/queued → failed an toàn + event stale_detected/stale_recovered. Không spawn vô hạn.

## 13. QA
- compileall: **OK**. node --check: N/A (JS inline trong Jinja).
- Migration rerun: idempotent (bảng đã có từ P1).
- Selection: select/unselect/page/clear/top5-10-20/explicit ✓. medium/review/unknown → badge review.
- Job: guard 0 reject ✓ · top5 mock queued ✓ · worker spawn `sys.executable` ✓ · running→completed ✓ · progress 100% ✓ · draft + events tạo ✓.
- Guard >20: needs_confirm ✓ · +explicit_confirm OK ✓.
- Worker E2E (spawn thật qua API): job #3 completed 5/5 ✓.
- Cancel/Retry/Stale: helper test OK (retry → draft version mới, không overwrite).
- Apply guard: approve/reject/apply/rollback/bulk-approve **501** ✓.
- Smoke: `/seo/blog-rewrite-ai` · `/api/blog-rewrite/status` · `/jobs` → 200.
- Broken-link config **KHÔNG đổi**: workers 48 · hstatic 8 · default 4 · HEAD 2s.
- Secret scan: KHÔNG hardcode token. Data test đã reset sạch (candidates=imported, jobs/drafts cleared).

## 14. Files
- **NEW**: `_scripts/run_blog_rewrite_worker.py`, doc này.
- **MOD**: `blog_rewrite.py` (selection/jobs/drafts/events/mock/stale), `routes/blog_rewrite.py` (P2 endpoints + P5 guard), `templates/blog_rewrite_ai.html` (selection toolbar + queue panel + detail tabs).

## 15. Deferred
- **P3**: worker AI THẬT (provider/model/prompt BLOG_REWRITE_PROMPT_V1 + parser JSON + sanitize bs4 whitelist + quality 5-gram overlap + image rehost upload_asset).
- **P4**: review UI + diff original↔draft + approve/reject thật.
- **P5**: apply (conflict content_hash + fetch live + backup payload + PUT Open API) + rollback per-bài.

## OUTPUT
**BLOG REWRITE AI P2 MOCK QUEUE COMPLETED** · P1 preserved (233/139high) · selection (checkbox/top5-10-20/page/clear/guard>20) · queue local (worker sys.executable, heartbeat, cancel, retry, stale) · mock (provider=mock, 0 AI/network/Haravan/image) · apply guard 501 · QA PASS · broken-link untouched · no commit/stage/push/deploy/browser.
