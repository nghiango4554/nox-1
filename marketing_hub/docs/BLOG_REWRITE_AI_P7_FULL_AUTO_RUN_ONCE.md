# BLOG REWRITE AI — P7 FULL AUTO RUN ONCE (10/6/2026)

> 1 nút chạy hết queue: generate → self-review 2-pass → auto-fix → image/fact/quality gate → backup → body-only PUT 1 lần → verify → reconcile → checkpoint → next. **KHÔNG approve tay · KHÔNG scheduler · KHÔNG daily cap.** Build-only: QA monkeypatch, KHÔNG live PUT, KHÔNG bật full-auto thật, KHÔNG commit/push.

## 1. Mục tiêu & mode
Mode mới **FULL_AUTO_RUN_ONCE**: xử lý toàn bộ candidate cho đến hết queue, tự sync bài đạt chuẩn, tự HOLD/BLOCK/MANUAL bài rủi ro, resume từ checkpoint, không xử lý lại applied, không PUT lặp khi crash. Bỏ approve local / confirm từng bài / whitelist / scheduler / daily cap. Chỉ confirm **1 lần** khi bấm Run: `START FULL AUTO BLOG REWRITE SYNC`.

## 2. Không scheduler
`scheduler_enabled=false`, không cron, không background job trong build. Chạy manual qua nút/API.

## 3. Traffic priority
Sort toàn queue: GSC clicks ↓ → GA4 sessions ↓ → priority_score ↓ → evergreen trước → news/benchmark sau. Tier HIGH (≥50 clicks/ss) 2-pass review nghiêm · MEDIUM 2-pass · LOW 1-pass. KHÔNG bỏ bài traffic cao, chỉ xử lý cẩn thận hơn.

## 4. Pipeline
SELECT → GENERATE (concurrency 1) → SELF_REVIEW pass1 → AUTO_FIX → SELF_REVIEW pass2 (FULL_RECOMPUTE) → IMAGE gate → FACT gate → QUALITY gate → PREFLIGHT → BACKUP → APPLY_ONE_SHOT (body-only) → VERIFY → RECONCILE → CHECKPOINT → next.

## 5-6. Self-review + auto-fix (deterministic, không AI riêng)
- **self_review**: phát hiện brand đối thủ / HTML lỗi / competitor href / unsupported claim / time-sensitive claim.
- **auto_fix**: gỡ ảnh ngoài/chết, **bỏ câu chứa benchmark (card+fps)/giá cụ thể**, unwrap competitor href, sanitize HTML + kẻ bảng + responsive wrapper.
- **pass2**: recompute toàn bộ gate. Nếu fail → regenerate tối đa 1 → vẫn fail → HOLD/BLOCKED + next.
- **Thin-content guard**: nếu auto-fix làm bài còn <150 từ (gutted) → MANUAL_REVIEW, KHÔNG đăng bài rỗng.

## 7. Image policy
SINTECH_OWNED reachable→KEEP · DEAD/INVALID→REMOVE · COMPETITOR/NEWS/UNKNOWN/OTHER_STORE→REMOVE_FROM_DRAFT (text-first) → recompute gate. **Phụ thuộc hình** ("như hình"/"bước 1/2"/screenshot/diagram) → **BLOCKED_IMAGE, không sync, giữ queue, next**. KHÔNG upload (Theme Asset adapter chưa proven) → giữ URL Sintech / gỡ ảnh.

## 8. Fact policy
Taxonomy: OFFICIAL_VERIFIED / SAFE_EVERGREEN / REPUTABLE_REPORT_UNCONFIRMED / TIME_SENSITIVE_REMOVE / UNSUPPORTED_REMOVE / BLOCKED_FACT. Auto bỏ: giá / FPS AI / benchmark không nguồn / tồn kho / timeline / driver mới. Bỏ claim mà bài vẫn đủ ý → PASS; claim cốt lõi không sửa an toàn (gutted) → BLOCKED_FACT/MANUAL → next.

## 9. Quality gate — FULL_RECOMPUTE bắt buộc
Auto sync CHỈ khi: **quality_score_verified ≥80** · **score_source ∈ {FULL_RECOMPUTE, SCORECARD}** (KHÔNG dùng inferred mơ hồ) · evidence_complete · overlap≤12% · HTML PASS · brand PASS · image gate ALLOW · fact gate PASS · 0 competitor href · 0 dead/blocked image · conflict SAFE_TO_APPLY · latest draft · reverse_copy=0 · applied=0 · ≥150 từ.

## 10. Apply Haravan (serial)
Từng bài: fresh GET → conflict → backup (BACKUP_SAVED) → one-shot flag → **PUT body_html only 1 lần** (PUT_SENT) → GET verify → canonical+semantic verify → DB_RECONCILED → auto-disarm → next. Payload chỉ `{article:{id, body_html}}`. KHÔNG đổi title/handle/summary/tags/published/published_at/author/featured image. KHÔNG retry PUT. Crash sau PUT → GET read-only → semantic verify → reconcile, KHÔNG PUT lại (reuse `reconcile_post_put` P5G-5).

## 11-12. Checkpoint + resume
`state/blog_rewrite_full_auto_checkpoint.json` lưu sau mỗi article (run_id/processed/applied/hold/blocked/current_stage/article_id/draft_id...). Restart → đọc checkpoint, resume bài chưa xong, không xử lý lại applied, không PUT lại PUT_SENT.

## 13. Circuit breaker (chỉ hard errors)
Content fail thường → HOLD → next (KHÔNG dừng run). Dừng toàn run CHỈ khi: backup fail · VERIFY_MISMATCH_REAL · UNCERTAIN_POST_PUT không reconcile · Haravan write lỗi liên tiếp (≥2) · DB/token/checkpoint lỗi. Khi stop: live flag OFF · checkpoint saved · status PAUSED_ERROR · resume bằng nút.

## 14. UI
Section "🚀 Full Auto Rewrite & Sync": badge (OFF/RUNNING/PAUSED_ERROR) + KPI (queue/processed/applied/hold/blocked image/blocked fact/conflict/failed/stage/article/checkpoint) + nút Run Full Auto (confirm phrase)/Dry-run/Pause/Resume/Emergency Stop/Export Report. KHÔNG scheduler.

## 15. API (8)
POST start (confirm phrase) · pause · resume · emergency-stop · GET status · items · events · report.

## 16. QA monkeypatch (mock apply engine + generate — KHÔNG live PUT)
**Toàn bộ PASS:**
- queue 143 candidate · traffic sort · tier HIGH/MEDIUM/LOW.
- C1 evergreen sạch (≥150 từ) → **APPLIED** · C2 visual tutorial ("bước 1/2") → **BLOCKED_IMAGE** · C3 benchmark → auto-fix gỡ claim → gutted → **thin_content → MANUAL_REVIEW** (KHÔNG đăng bài rỗng).
- **apply gọi đúng 1** (chỉ C1) · processed hết queue · content fail KHÔNG dừng run (CB không mở).
- **re-run: applied KHÔNG lặp** (skip applied).
- **crash sau PUT (UNCERTAIN) → CB mở + PAUSED_ERROR + flags OFF** (dừng run, KHÔNG PUT lại).
- live cần confirm phrase `START FULL AUTO BLOG REWRITE SYNC` (thiếu → CONFIRM_PHRASE_REQUIRED).
- dry-run → apply=0.
- score_source FULL_RECOMPUTE/SCORECARD (không inferred apply).
- compileall OK · node --check JS OK · smoke 4 endpoint 200.
- **live PUT=0 · upload=0 · scheduler actual run=0 · flags OFF · broken-link config nguyên (48/8/4/2s) · secret sạch.**

## 17. Files
- **NEW**: `blog_rewrite_full_auto.py`, doc này. (checkpoint/state tạo runtime)
- **MOD**: `routes/blog_rewrite.py` (8 endpoint), `templates/blog_rewrite_ai.html` (full-auto section).
- **Backup**: `_backup/blog-rewrite-p7-fullauto-20260610-202149/`.

## 18. Cách bật run thật (deferred — vợ tự quyết)
1. Mở UI section "🚀 Full Auto Rewrite & Sync" → **Dry-run hết queue** trước (xem phân loại 143 bài, KHÔNG apply).
2. **Run Full Auto** → gõ confirm phrase `START FULL AUTO BLOG REWRITE SYNC` → hệ thống tự generate + sync bài đạt chuẩn, HOLD/BLOCK phần còn lại.
3. Theo dõi KPI + checkpoint; Pause/Emergency Stop bất cứ lúc nào. Crash → tự dừng + reconcile.

⚠️ **Lưu ý quan trọng:** Full-auto sẽ TỰ ĐĂNG LIVE nhiều bài không qua duyệt tay. Đề xuất chạy Dry-run + apply thử số nhỏ (max_articles) trước khi chạy toàn bộ 143 bài.

## OUTPUT
**BLOG REWRITE AI P7 FULL AUTO RUN ONCE COMPLETED** · mode FULL_AUTO_RUN_ONCE (no scheduler, no human approval, no daily cap) · pipeline generate→self-review 2-pass→auto-fix→FULL_RECOMPUTE gate→backup→body-only PUT 1 lần→verify→reconcile→checkpoint · traffic priority + tier · thin-content guard · circuit breaker chỉ hard-errors · checkpoint+resume · 8 API + UI section + confirm-phrase guard · **QA monkeypatch ALL PASS (evergreen→applied, visual→blocked, benchmark→gutted→manual, apply=1, content-fail không dừng, crash→CB+reconcile, applied không lặp, live PUT=0, scheduler=0, flags OFF, broken-link nguyên)** · no commit/push. **Build xong, chưa bật thật — chờ vợ Dry-run + Run Full Auto thủ công.**
