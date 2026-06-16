# P7.2 — HARAVAN 500-BUT-WRITE RECONCILE + ENGINE HARDENING

> Thực hiện theo spec `Desktop/Past.txt` (phương án 1). **CHƯA COMMIT/STAGE/PUSH** (spec cấm).
> Reconcile lượt này: **PUT live = 0, upload = 0, rollback = 0, rehost = 0**. Không chạy Full Auto live mới.
> Ngày: 2026-06-11.

## Bối cảnh sự cố
Run 40 (FULL_AUTO thử 5 bài, **live=True**) chết kẹt giữa chừng, để lại state `RUNNING` ảo ~1 ngày.
Bài **#63 CS2** ở stage APPLY trả `event=UNKNOWN verify=UNKNOWN`: engine cũ coi PUT HTTP 500 = FAILED
ngay và bỏ qua, **nhưng Haravan đã ghi body thật** (500-but-write). → web #63 đã đổi sang bản AI mà
DB ghi failed. Đây là lỗ hổng engine: sau PUT_SENT, mọi 5xx/timeout/exception phải coi là *uncertain*
và reconcile bằng GET, không được kết luận FAILED.

---

## A. Freeze run 40
| Mục | Giá trị |
|---|---|
| Runner full_auto PID | NONE alive (đã chết sẵn) |
| Claude child PID | NONE |
| Worker/Codex child | NONE |
| **Stale process count** | **0** ✓ |
| CB (autopilot) | closed (open=false) ✓ |
| Flags | OFF ✓ |
| Checkpoint khi vào | stage=REGENERATE, cid=77, index=3 |

Acceptance A đạt: stale=0, flags OFF, không runner cũ, không Claude child cũ.

---

## B. Reconcile #63 CS2 (read-only, ladder)
| Field | Giá trị |
|---|---|
| article_id | 1002399773 |
| URL | https://sintech.vn/blogs/news/cau-hinh-choi-cs2-counter-strike-2-tren-pc-laptop |
| draft_id | 88 (v2) |
| backup | `live_backup_payload_json` đã lưu trước PUT (draft 88) |
| verify source | **HARAVAN_READ_API** (Open API article GET hoạt động) |
| live signature vs draft | **VERIFIED_RAW** (khớp raw chính xác) |
| live signature vs original | VERIFY_MISMATCH_REAL |
| semantic verify status | **VERIFIED** → verdict **DRAFT** |
| DB sau reconcile | candidate 63 = `applied` · draft 88 `applied_at` set · `applied_draft_hash=dcf3026606648704` |
| **PUT count** | **vẫn = 1** (PUT của run 40; reconcile thêm **0**) |
| event | `post_put_reconciled_applied` |

→ **#63 = APPLIED_RECONCILED**. Giữ bản AI live (sạch: 0 brand đối thủ, 0 ảnh chết, 0 bảng FPS bịa,
overlap 3.9%, HTML hợp lệ). Không rollback, không re-PUT.

---

## C. Audit toàn bộ 5 item run 40
| cid | Bài | Stage cuối | Decision | Draft | PUT thật | Backup | Live đổi? | Action |
|---|---|---|---|---|---|---|---|---|
| 63 | CS2 | APPLY | **APPLIED_RECONCILED** | 88 | ✅ (500-but-write) | ✅ | = DRAFT | giữ, status=applied |
| 11 | GTA5 | GATE | BLOCKED_FACT | — | ❌ | — | = ORIGINAL (verify read-only) | none |
| 149 | Photoshop | GATE | BLOCKED_IMAGE | — | ❌ | — | — | none |
| 77 | ZZZ | REGENERATE (kẹt) | — | 93/94 | ❌ | — | — | reset retryable |
| 220 | Miku | waiting | — | — | ❌ | — | — | về lại queue |

**Ghi chú #11:** có lịch sử event `put_sent×3 + uncertain_post_put` nhưng là **QA monkeypatch cũ**
(cùng nonce trong 1 giây, kết thúc `{"error":"crash"}` — không PUT mạng thật). Audit live read-only
xác nhận **#11 live == ORIGINAL (VERIFIED_RAW)** → bài GTA5 trên web nguyên bản, chưa đổi. Không reset
bài đã PUT, không đánh dấu failed mù.

---

## D. Dọn state run 40
- `blog_rewrite_autopilot_runs` id=40 → status **RECONCILED_INCIDENT**.
- checkpoint → `current_stage=completed_reconciled`, `last_event=reconciled_incident`,
  applied=1, applied_reconciled=1, retryable=1, blocked_image=1, blocked_fact=1, failed=0.
- **#77** status `generating`(kẹt) → **`draft_ready`** (reset local retryable, **KHÔNG tự chạy lại**).
- flags OFF · CB closed (không còn uncertain thật) · checkpoint saved.
- Fix badge: thêm `completed_reconciled` vào TERMINAL_STAGES → `status/progress/status_badge` trả
  **RECONCILED** thay vì RUNNING ảo. Verify live: badge=RECONCILED, finished=true, running=false.

---

## E. Vá engine 500-but-write (`blog_rewrite_apply.py`)
Sau `PUT_SENT`, mọi case sau = **UNCERTAIN_POST_PUT**, không ghi FAILED ngay, không re-PUT, không rollback auto:
HTTP 5xx · timeout · connection reset · exception sau PUT · response parse fail.

Flow: `BACKUP_SAVED → PUT_SENT →`
- HTTP 2xx → GET verify → live==draft → `LIVE_VERIFIED`
- non-2xx/exception → `put_response_uncertain` → reconcile (GET ladder + semantic verify):
  - live == draft → **APPLIED_RECONCILED** (candidate=applied)
  - live == original → **NOT_APPLIED_RETRYABLE** (chưa lên, để retry thủ công, không auto)
  - khác cả hai / không đọc được → **UNCERTAIN_POST_PUT** → **circuit breaker OPEN**

`reconcile_post_put` đổi từ 2 nhánh → **3 chiều** (so cả draft lẫn original). PUT exception được bắt
trong `apply_draft_body_only` (không còn propagate ra ngoài làm mất dấu PUT đã gửi).

Events mới: `put_response_uncertain` · `post_put_verify_started` · `post_put_reconciled_applied` ·
`post_put_reconciled_not_applied` · `post_put_reconcile_failed` · `circuit_breaker_opened_uncertain`.

`blog_rewrite_full_auto.py`: `_apply_serial` trả thêm `verify_source`; main loop phân nhánh
APPLIED / APPLIED_RECONCILED (đếm applied) · NOT_APPLIED_RETRYABLE (không CB) · UNCERTAIN_POST_PUT (CB+pause).

## F. Public-page fallback read-only
`_get_live_for_verify`: ưu tiên Haravan admin GET; admin 5xx/exception → `_fetch_public_page` (retry 3,
cache-bust, **chỉ đọc, không bao giờ PUT**). `compare_public_page` (verify module): so dấu vân tay nội
dung article (containment các đoạn đặc trưng) thay vì layout toàn trang → verdict DRAFT/ORIGINAL/UNCERTAIN.
Verify source ghi rõ: `HARAVAN_READ_API` / `PUBLIC_PAGE_FALLBACK`.

## H. UI (`templates/blog_rewrite_ai.html`)
Badge mới: ✅ APPLIED · ✅ APPLIED_RECONCILED (tím) · ⏳ NOT_APPLIED_RETRYABLE · ⛔ UNCERTAIN_POST_PUT ·
⛔ PAUSED_ERROR. KPI thêm Reconciled + Retry. Hàng reconcile hiện verify source (qua decision_reason)
+ ghi chú "PUT 5xx nhưng live=draft · không re-PUT". Banner RECONCILED khi run kết thúc bằng reconcile.

---

## G. QA monkeypatch — 21/21 PASS (10 case spec)
`_scripts/qa_p7_2_reconcile.py` (test candidate+draft thật → cleanup; snapshot/restore CB+flags+config; 0 network thật):
1. PUT 201 + live draft → LIVE_VERIFIED, PUT=1
2. PUT 500 + live draft → **APPLIED_RECONCILED**, PUT=1, no retry
3. PUT 502 + live draft → APPLIED_RECONCILED, PUT=1
4. PUT timeout + live draft → APPLIED_RECONCILED, PUT=1
5. PUT 500 + live original → **NOT_APPLIED_RETRYABLE**, PUT=1, no auto retry
6. PUT 500 + live khác cả hai → **UNCERTAIN_POST_PUT** + **CB OPEN**, PUT=1
7. admin GET 502 + public draft → APPLIED_RECONCILED qua **PUBLIC_PAGE_FALLBACK**
8. Crash sau PUT → UNCERTAIN_POST_PUT, **không re-PUT** (PUT=1)
9. Double submit → **PUT vẫn = 1** (idempotency)
10. Resume checkpoint → bài applied bị loại khỏi queue, không chạy lại

---

## I. QA & smoke
- `python -m compileall` apply/verify/full_auto/autopilot/br/routes → **OK**.
- Smoke (server restart PID 13948, Python312): 5 endpoint **200**
  (`/seo/blog-rewrite-ai`, full-auto `/status` `/progress` `/items` `/events`).
- Live badge: **RECONCILED**, CB open=false, stage=completed_reconciled.
- Secret scan file đã sửa: **sạch** (token đọc từ `state/haravan_token.json`, không hardcode).

## Acceptance (đạt hết)
| Tiêu chí | Kết quả |
|---|---|
| reconcile lượt này PUT | **0** ✓ |
| upload | **0** ✓ |
| #63 | **APPLIED_RECONCILED**, không PUT lại ✓ |
| run 40 RUNNING ảo | đã hết (RECONCILED) ✓ |
| #77 | retryable (draft_ready), không tự chạy lại ✓ |
| flags | OFF ✓ |
| CB | closed (không còn uncertain thật) ✓ |
| broken-link config | unchanged (WORKERS 15/48, per-host 4/8, HEAD 2s) ✓ |
| stale process | 0 ✓ |

## File đụng (chưa commit)
`blog_rewrite_apply.py` · `blog_rewrite_verify.py` · `blog_rewrite_full_auto.py` ·
`templates/blog_rewrite_ai.html` · `_scripts/qa_p7_2_reconcile.py` (mới) · báo cáo này.
Không đụng `seo.py` (broken-link) / không Full Auto live mới / không tự mở browser.
