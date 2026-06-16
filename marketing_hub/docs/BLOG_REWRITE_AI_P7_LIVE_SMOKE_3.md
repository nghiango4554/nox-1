# P7 — LIVE SMOKE 3 BÀI (sau P7.2 reconcile PASS)

> Theo spec `Desktop/Past.txt`. Confirm phrase: `START FULL AUTO BLOG REWRITE SYNC`. Ngày 2026-06-11.
> **CHƯA COMMIT.** Runner nền độc lập (CREATE_NO_WINDOW). Dừng sau smoke 3 — KHÔNG tự chạy tiếp full queue.

## Kết quả tổng
| Field | Giá trị |
|---|---|
| run_id | **41** |
| processed / max | **3 / 3** ✓ |
| generated | 3 (mỗi bài generate/dùng draft sẵn) |
| regenerated | 2 (#77, #11 — regenerate tối đa 1 lần/bài) |
| **applied** | **0** |
| applied_reconciled | 0 |
| not_applied_retryable | 0 |
| HOLD (time-sensitive) | 1 |
| BLOCKED_IMAGE | 0 |
| BLOCKED_FACT | 1 |
| MANUAL_REVIEW | 1 |
| CONFLICT | 0 |
| FAILED | 0 |
| current_stage | completed |

**Cả 3 bài bị gate chặn TRƯỚC bước apply → 0 PUT, 0 apply_armed.** Đúng hành vi an toàn: không để
bài quality thấp / fact rủi ro / time-sensitive lên live.

## Chi tiết từng bài
| Thứ tự | cid | article_id | Bài | Decision | Lý do | PUT count | HTTP PUT | verify source | semantic verify |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 77 | 1002402249 | Cấu hình chơi ZZZ | **MANUAL_REVIEW** | quality score 78 < 80 (regenerate 1 lần vẫn 78) | **0** | — (không PUT) | N/A (chưa tới apply) | N/A |
| 2 | 220 | 1002704151 | PC Hatsune Miku ASUS | **HOLD_TIME_SENSITIVE** | tin "ra mắt" + fact time-sensitive | **0** | — | N/A | N/A |
| 3 | 11 | 1002728313 | PC chơi GTA 5 | **BLOCKED_FACT** | score 60, overlap 15.7%, claim fps/build | **0** | — | N/A | N/A |

> Vì 0 bài tới bước PUT nên **rule 500-but-write không bị kích hoạt lượt này**. Rule + reconcile 3 chiều
> đã được validate đầy đủ ở **P7.2 QA 21/21 PASS** (PUT 500/502/timeout → APPLIED_RECONCILED; original →
> NOT_APPLIED_RETRYABLE; khác → UNCERTAIN+CB; public fallback; crash no-rePUT; double-submit PUT=1).

## Gate đã chạy đúng (serial, 1 article/lần)
- Pipeline mỗi bài: SELECT → GENERATE → SELF_REVIEW P1 → AUTO_FIX → SELF_REVIEW P2 → FULL_RECOMPUTE
  QUALITY → IMAGE GATE → FACT GATE → CONFLICT → (gate fail → KHÔNG apply). Regenerate ≤1/bài.
- #77: regenerate 1 lần, score vẫn 78 → MANUAL_REVIEW (ngưỡng min 80).
- #220: fact gate bắt tin time-sensitive ("ra mắt") → HOLD.
- #11: fact gate (fps/build chưa nguồn) + overlap 15.7% cao + score 60 → BLOCKED_FACT.

## State sau run
| Mục | Giá trị |
|---|---|
| checkpoint | run 41, current_stage=completed, processed=3, saved sau mỗi bài |
| **PUT live (tổng)** | **0** |
| **upload** | **0** |
| rehost | 0 |
| terminal pop count | **0** (claude/codex provider + runner đều CREATE_NO_WINDOW) |
| **stale process count** | **0** (runner exit 0, không claude child sót) |
| flags | **OFF** (all False) |
| CB | **closed** (open=false) |
| scheduler | OFF (0 run) |
| log path | `marketing_hub/state/logs/blog_rewrite_full_auto.log` (chỉ id/stage/event, KHÔNG token/body/prompt) |
| broken-link config | **unchanged** (LINK_CHECK_WORKERS=48, PER_HOST=4, HEAD 2s) |
| Flask | alive PID 11536 (Python312) |

## Acceptance (đạt hết)
| Tiêu chí | Kết quả |
|---|---|
| processed = 3 | ✓ |
| terminal pop = 0 | ✓ |
| stale process = 0 | ✓ |
| PUT tối đa 1/bài | ✓ (0 PUT — đều bị gate chặn) |
| không re-PUT | ✓ |
| flags OFF sau run | ✓ |
| CB closed (không uncertain thật) | ✓ |
| upload = 0 | ✓ |
| scheduler = 0 | ✓ |
| broken-link config unchanged | ✓ |

## Nhận xét + NEXT (chờ vợ)
- Smoke an toàn nhưng **0 bài lên live** do gate chất lượng/fact quá chặt với 3 bài LOW-traffic này
  (2 bài game config + 1 tin sản phẩm). Để có bài thực sự APPLIED, nên chọn batch bài evergreen
  fact-safe (như #110/#112/#163 đã từng pass) thay vì game-config/tin-tức.
- Có thể nới nhẹ: #77 chỉ thiếu 2 điểm quality (78 vs 80) — review tay rồi approve thủ công nếu vợ thấy ổn.
- **Dừng tại đây theo spec.** KHÔNG tự chạy tiếp full queue. Chờ vợ quyết hướng tiếp.

## File đụng (chưa commit)
`blog_rewrite_full_auto.py` (thêm priority_cids) · `_scripts/run_blog_rewrite_full_auto.py` (--priority-cids) ·
`routes/blog_rewrite.py` (priority_cids + fix ALREADY_RUNNING completed_reconciled) · báo cáo này.
