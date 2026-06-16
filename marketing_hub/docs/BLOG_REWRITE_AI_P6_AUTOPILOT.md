# BLOG REWRITE AI — P6 AUTOPILOT (10/6/2026)

> Orchestrate full pipeline reuse engine sẵn có. **Mặc định OFF · scheduler OFF · QA monkeypatch (KHÔNG live PUT).** Tự apply CHỈ bài evergreen đạt chuẩn chặt; tự HOLD bài rủi ro; tự BLOCK ảnh lỗi; circuit breaker tự dừng. KHÔNG bỏ qua gate, KHÔNG apply song song, KHÔNG commit/push.

## 1. Mục tiêu & modes
- **OFF** (mặc định): không chạy.
- **PREP_ONLY**: chạy pipeline tới PREFLIGHT → phân loại, KHÔNG apply, KHÔNG PUT.
- **SAFE_AUTO_APPLY**: thêm BACKUP→APPLY_ONE_SHOT→VERIFY→RECONCILE — chỉ apply bài AUTO_ELIGIBLE, 1 bài/lần, cần enable + confirm phrase.

## 2. Config `state/blog_rewrite_autopilot.json` (mặc định OFF)
enabled=false · mode=PREP_ONLY · schedule.enabled=false (02:00 Asia/Ho_Chi_Minh) · limits (gen 5/run, apply 2/run, 2/ngày, cooldown 15p, regenerate 1) · quality (overlap≤12%, score≥80, gate ALLOW, conflict SAFE, html/brand/fact required) · apply (body_html_only, auto_backup, semantic_verify, reconcile, auto_rollback=false, one_shot_flag) · circuit_breaker (stop on mismatch/uncertain/backup-fail, 2 gen-fail, 2 fact-fail).

## 3. DB additive (idempotent)
`blog_rewrite_autopilot_runs` · `blog_rewrite_autopilot_items` · `blog_rewrite_autopilot_events` + 3 index. CREATE IF NOT EXISTS.

## 4. Pipeline stages
DISCOVER → SELECT → GENERATE → SANITIZE → IMAGE_REMEDIATE → FACT_CHECK → QUALITY_CHECK → PREFLIGHT → [BACKUP → APPLY_ONE_SHOT → VERIFY → RECONCILE] → REPORT. PREP_ONLY dừng sau PREFLIGHT.

## 5. Reuse engine (KHÔNG duplicate)
store-aware image classify (blog_rewrite_images) · image gate (remediate.article_gate) · HTML sanitizer + table border (gen.sanitize_html) · quality metrics (gen.quality_metrics) · canonical/semantic verify (blog_rewrite_verify) · fresh conflict + backup + body-only PUT + one-shot flag + auto-disarm + idempotency + **reconcile_post_put** (blog_rewrite_apply, P5G-5). Generate qua worker (monkeypatch-able `_generate_draft`).

## 6. Selection policy
evergreen how-to · rewrite_eligible=1 · reverse_copy=0 · chưa applied · không HOLD (đọc `_canary_hold.json`). Loại tin/driver/giá/benchmark. Sort theo traffic. Groups: AUTO_ELIGIBLE · PREP_ONLY · HOLD_TIME_SENSITIVE · HOLD_UNSUPPORTED · BLOCKED_IMAGE · MANUAL_REVIEW · CONFLICT · FAILED · APPLIED.

## 7. Image policy
SINTECH_OWNED+reachable → KEEP · DEAD/INVALID → REMOVE local · COMPETITOR/NEWS/UNKNOWN/OTHER_STORE → REMOVE_FROM_DRAFT local (text-first) → re-gate. **Dấu hiệu phụ thuộc ảnh** ("như hình"/"bước 1"/"ảnh bên dưới"...) → MANUAL_REVIEW, KHÔNG auto remove. KHÔNG upload/rehost.

## 8. Fact policy (heuristic taxonomy)
OFFICIAL_VERIFIED / REPUTABLE_REPORT_UNCONFIRMED / TIME_SENSITIVE_REVIEW / UNSUPPORTED_REMOVE / MANUAL_REVIEW. Auto apply chỉ khi time_sensitive=0 + unsupported=0 + manual=0. Phát hiện: FPS gắn card/game + benchmark → unsupported; giá/news keyword/driver/tồn kho → time-sensitive.

## 9. Quality policy
overlap≤12% · score≥80 · brand PASS · HTML PASS · gate ALLOW · conflict SAFE · 0 competitor href · 0 dead/blocked image · 0 unsupported/time-sensitive claim · latest draft · không reverse · chưa applied. Fail → (regenerate tối đa 1) → vẫn fail → HOLD.

## 10. Apply policy (SAFE_AUTO_APPLY)
1 bài/lần · không song song · cooldown 15p · max 2/run · max 2/ngày. Flow: fresh GET → conflict → backup → one-shot flag → PUT body_html only ĐÚNG 1 lần → GET verify → semantic compare → DB reconcile → auto-disarm. KHÔNG retry PUT, KHÔNG auto rollback.

## 11. Circuit breaker
Pause ngay nếu: VERIFY_MISMATCH · UNCERTAIN_POST_PUT · backup fail · 2 gen-fail · 2 fact-fail · apply exception. Khi mở: enabled=false, live flags OFF, event circuit_breaker_opened, KHÔNG tự resume.

## 12. API (11 endpoint)
status · config (GET) · config (PATCH, cần confirm phrase nếu enable apply/schedule) · dry-run · run-prep · pause · resume · emergency-stop · runs · runs/{id} · events. Enable SAFE_AUTO_APPLY phrase = `ENABLE SAFE BLOG AUTOPILOT`; scheduler phrase = `ENABLE BLOG AUTOPILOT SCHEDULE`.

## 13. UI
Section "🤖 Autopilot": badge (OFF/PREP ONLY/SAFE AUTO APPLY/CIRCUIT BREAKER OPEN) + KPI (today/caps/overlap/quality) + nút Dry-run/Run PREP/Enable SAFE_AUTO (confirm)/Pause/Resume/Emergency Stop + last run. Apply tự động chỉ qua autopilot khi enabled.

## 14. Scheduler
Integration sẵn (runner `_scripts/run_blog_rewrite_autopilot.py`) nhưng **enabled=false** mặc định, 02:00 GMT+7. KHÔNG tự bật, KHÔNG chạy background trong build.

## 15. QA monkeypatch (KHÔNG live PUT)
Mock `_generate_draft` + `ap._put_article`/`_get_live` + `ap.apply_preview` (conflict đã proven ở live #110/#112). **Kết quả: 19/19 PASS:**
- default OFF · schedule OFF · SAFE_AUTO chặn khi disabled ✓
- evergreen→AUTO_ELIGIBLE · news→HOLD_TIME_SENSITIVE · benchmark→HOLD_UNSUPPORTED · visual→MANUAL_REVIEW ✓
- PREP_ONLY PUT=0 ✓
- SAFE_AUTO: applied=1 · **PUT đúng 1** · body-only (chỉ id+body_html) · verify VERIFIED ✓
- max_apply_per_run=1 → chỉ 1 PUT, bài 2 → AUTO_ELIGIBLE ✓
- max_apply_per_day chặn (live đã 3 bài hôm nay → autopilot từ chối, đúng) ✓
- **crash sau PUT: PUT vẫn 1 (không re-PUT) → CB mở** ✓
- CB open chặn run ✓ · emergency stop flags OFF + enabled OFF ✓ · bulk flag OFF ✓ · flags auto-disarm ✓
- compileall OK · node --check JS OK · smoke 4 endpoint 200 · confirm phrase guard 403 ✓.
- **PUT live=0 · upload=0 · rehost=0 · scheduler actual run=0** · flags OFF · broken-link config nguyên (48/8/4/2s) · secret sạch.

## 16. Files
- **NEW**: `blog_rewrite_autopilot.py`, `_scripts/run_blog_rewrite_autopilot.py`, `state/blog_rewrite_autopilot.json`, `state/blog_rewrite_autopilot_cb.json`, doc này.
- **MOD**: `routes/blog_rewrite.py` (11 endpoint), `templates/blog_rewrite_ai.html` (autopilot section).
- **Backup**: `_backup/blog-rewrite-p6-autopilot-20260610-193357/`.

## 17. Deferred (cần vợ enable thủ công)
- Enable SAFE_AUTO_APPLY (confirm phrase) khi muốn autopilot tự apply bài evergreen.
- Enable scheduler (confirm phrase riêng) + cấu hình cron 02:00.
- Tự apply sẽ bị daily cap chặn hôm nay (đã 3 bài) — chạy được từ ngày mai.

## OUTPUT
**BLOG REWRITE AI P6 AUTOPILOT COMPLETED** · 3 modes (OFF/PREP_ONLY/SAFE_AUTO_APPLY) mặc định OFF + scheduler OFF · full pipeline reuse engine · selection evergreen + image/fact/quality/conflict gates · apply 1 bài/lần body-only one-shot + reconcile + circuit breaker · 11 API + UI section + confirm-phrase guard · **QA monkeypatch 19/19 PASS, PUT live=0, upload=0, scheduler run=0, flags OFF, broken-link nguyên, secret sạch** · no commit/push. **Chờ vợ enable thủ công (confirm phrase) để chạy thật.**
