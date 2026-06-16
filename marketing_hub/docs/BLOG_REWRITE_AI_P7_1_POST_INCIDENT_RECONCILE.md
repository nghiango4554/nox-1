# BLOG REWRITE AI — P7.1 POST-INCIDENT RECONCILE + BACKGROUND HARDENING (10/6/2026)

> Reconcile run LIVE 38 bị dừng giữa chừng + hardening nền. **KHÔNG full-auto live · KHÔNG PUT/upload/rehost · KHÔNG commit/push.** Read-only verify + local cleanup.

## A. Audit process cũ
- runner full-auto cũ: **không còn** (PID 15948 đã kill). claude child: **không còn** (PID 10912 đã kill).
- Flask PID hiện tại: 2096 (sống).
- checkpoint run 38: stage=completed (đã dừng), không running.
- **CB closed · flags live_apply/rollback/bulk = false.** ✅ Acceptance đạt.

## B. Reconcile run 38
| # | Decision | draft | PUT_SENT | verify | Action |
|---|---|---|---|---|---|
| #163 VS Code | APPLIED | 58 | **True** | **VERIFIED** | giữ applied — skip lần sau |
| #149 xóa logo | BLOCKED_IMAGE | None | False | — | giữ blocked (phụ thuộc ảnh) |
| #63/#11/#77/#220/#84/#211/#68/#209 | FAILED | None | False | — | **reset retryable** |

**#163 verify (read-only):** semantic **VERIFIED_RAW** · candidate=applied · applied_at 13:50 · title KHÔNG đổi · 0 ảnh · backup tồn tại · apply http 201. → PUT count=1, đã sync đúng, lần chạy sau **skip**.

**8 FAILED:** đều **draft=None + PUT_SENT=false + 0 backup live** → xác nhận lỗi do **Claude CLI console/generate fail** (chạy trong DETACHED_PROCESS không console), KHÔNG đụng body live. → reset status `imported` (retryable) + event `incident_retry_reset`. KHÔNG reset #163 (applied giữ nguyên).

## C. Audit UI realtime (grep count)
- faStart / faDry / faAct / renderFullAuto / loadFullAuto / pollFullAuto: **mỗi cái đúng 1** (không duplicate).
- Buttons thật (onclick): Run Full Auto ×1 · Chạy thử 30 ×1 · Dry-run ×1 · Pause ×1 · Emergency Stop ×1 (Run Full Auto xuất hiện 4 lần CHỈ trong text title/summary/warning, không phải button dup).
- renderFullAuto nhận `p` (dùng p.badge/p.checkpoint/p.items) — KHÔNG còn s.badge/s.scheduler lẫn.
- poll timer `faPollTimer` đơn (setInterval(pollFullAuto) 1 chỗ, clear khi xong) — không nhân đôi.
- → Đã thêm nút "🚀 Chạy thử 5 bài" (F). Không có dup cần xóa.

## D. Rotating log nền
`state/logs/blog_rewrite_full_auto.log` (RotatingFileHandler, maxBytes 1MB, backup 3). Log: timestamp · run_id · cid · article_id · stage · event · error_type · exit · checkpoint path. **KHÔNG log token/secret/body_html/prompt/response.** Verify: log có run_started + item_decided (cid/stage/event); grep secret → **sạch**.

## E. CREATE_NO_WINDOW regression
Audit + sửa các spawn:
- `claude_provider.py` subprocess.run → **CREATE_NO_WINDOW** (console ẩn).
- `codex_provider.py` subprocess.run → CREATE_NO_WINDOW.
- `routes/_spawn_full_auto` → CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP (giữ group để pause/kill).
- `routes/_spawn_worker` → CREATE_NO_WINDOW (đồng bộ).
- Full-auto generate gọi worker IN-PROCESS (importlib) → claude_provider fix cover.
**Test:** (1) claude CLI health trong CREATE_NO_WINDOW subprocess → OK exit 0, KHÔNG pop window. (2) hidden runner dry-run → realtime progress cập nhật (DONE 142), checkpoint cập nhật, log có stage, PUT=0, upload=0.

## F. Nút live smoke 5 bài
UI thêm "🚀 Chạy thử 5 bài" (max_articles=5, nền dcfce7). Giữ "Chạy thử 30 bài" + "Run Full Auto". Khuyến nghị dùng 5 trước.

## G. QA
- compileall OK · node --check JS OK · grep count UI (không dup).
- Smoke 5 endpoint (page/status/progress/items/events) 200.
- Reconcile: #163 verify VERIFIED · 8 FAILED reset retryable · stale process=0.
- Rotating log hoạt động + sạch secret · hidden runner dry-run no-window · realtime OK.
- **PUT=0 · upload=0 · flags OFF · CB closed · broken-link config nguyên (48/8/4/2s).**

## Files
- **MOD**: `blog_rewrite_full_auto.py` (rotating log + _log calls), `claude_provider.py` + `codex_provider.py` (CREATE_NO_WINDOW), `routes/blog_rewrite.py` (_spawn_full_auto/_spawn_worker CREATE_NO_WINDOW), `templates/blog_rewrite_ai.html` (nút 5 bài).
- **NEW**: `state/logs/blog_rewrite_full_auto.log`, doc này.

## OUTPUT
**P7.1 POST-INCIDENT RECONCILE + HARDENING COMPLETED** · run 38 reconciled (#163 VERIFIED applied giữ, 8 FAILED draft=None/PUT_SENT=false → reset retryable + incident_retry_reset) · stale process=0 · UI không dup (đã thêm nút 5 bài) · rotating log sạch secret · CREATE_NO_WINDOW ở claude/codex/spawn (test: claude OK hidden, no pop) · **PUT=0 · upload=0 · flags OFF · CB closed · broken-link nguyên** · no commit/push. **Reconcile PASS — sẵn sàng chạy thử LIVE 5 bài.**
