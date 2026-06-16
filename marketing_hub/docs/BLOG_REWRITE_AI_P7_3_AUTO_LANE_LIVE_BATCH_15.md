# P7.3 — AUTO_LANE LIVE BATCH 15

> Theo spec `Desktop/Past.txt`. Confirm phrase: `START FULL AUTO BLOG REWRITE SYNC`. Ngày 2026-06-11.
> **CHƯA COMMIT.** Runner nền độc lập (CREATE_NO_WINDOW). Dừng sau batch 15 — KHÔNG tự chạy tiếp AUTO_LANE.

## Preflight (trước run, đếm thật)
| Trạng thái AUTO_LANE | Số |
|---|---|
| AUTO_LANE tổng (chưa applied) | 48 |
| đã APPLIED (status=applied, cộng dồn mọi lane) | 7 |
| AUTO APPLIED / APPLIED_RECONCILED | 0 / 0 |
| AUTO HOLD_TIME_SENSITIVE | 1 (#176) |
| AUTO BLOCKED_IMAGE | 2 (#21, #151) |
| AUTO MANUAL_REVIEW | 1 |
| AUTO HOLD_QUALITY / BLOCKED_FACT / MANUAL_COMPLEX / CONFLICT | 0 |
| **AUTO_LANE pending (any-terminal)** | **42** |

Loại bài đã có decision cuối (`skip_decided`): cids `[12, 14, 21, 52, 151, 176]`. Batch lấy **15/42 pending**.

## Kết quả tổng (run 44)
| Field | Giá trị |
|---|---|
| run_id | **44** |
| AUTO_LANE pending trước run | 42 |
| processed / max | **15 / 15** ✓ |
| **applied** | **12** ✅ |
| **applied_reconciled** | **1** ✅ (#152 — 500-but-write thực chiến) |
| not_applied_retryable | 0 |
| HOLD_TIME_SENSITIVE | 1 (#150) |
| HOLD_UNSUPPORTED / HOLD_QUALITY | 0 / 0 |
| BLOCKED_IMAGE | 2 (#183, #165) |
| BLOCKED_FACT | 0 |
| MANUAL_REVIEW / CONFLICT / FAILED | 0 / 0 / 0 |
| **Tổng lên live batch này** | **13** |

## Chi tiết từng bài (serial, lane=AUTO, PUT body-only 1 lần)
| # | cid | Decision | PUT | HTTP | verify source | semantic |
|---|---|---|---|---|---|---|
| 1 | 150 | ⏸️ HOLD_TIME_SENSITIVE | 0 | — | — | — |
| 2 | 132 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 3 | 107 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 4 | 172 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 5 | 134 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 6 | 152 | ✅ **APPLIED_RECONCILED** | 1 | **500** | HARAVAN_READ_API | VERIFIED (live==draft) |
| 7 | 170 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 8 | 143 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 9 | 183 | 🖼️ BLOCKED_IMAGE | 0 | — | — | — |
| 10 | 165 | 🖼️ BLOCKED_IMAGE | 0 | — | — | — |
| 11 | 173 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 12 | 140 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 13 | 144 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 14 | 154 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |
| 15 | 175 | ✅ APPLIED | 1 | 201 | HARAVAN_READ_API | VERIFIED |

**Mỗi bài applied PUT đúng 1 lần** (put_sent=1, không re-PUT). generated: 13 bài (gen mới khi chưa draft);
regenerated theo self-review pass 2 / borderline (không vượt 2 lần/bài).

## ⭐ 500-but-write thực chiến (#152)
`run=44 | cid=152 | stage=APPLY | event=APPLIED_RECONCILED | verify=VERIFIED | source=HARAVAN_READ_API`
→ Haravan trả **HTTP 500** sau PUT, engine KHÔNG ghi FAILED, GET live read-only → **live == draft** →
**APPLIED_RECONCILED**, put_sent=1 (KHÔNG re-PUT), CB KHÔNG mở. Đúng rule P7.2 — lần đầu chạy thật.

## Spot-check chất lượng (bài đã live)
| Bài | Words | Ảnh external | Brand đối thủ | Overlap |
|---|---|---|---|---|
| #132 phóng to/thu nhỏ màn hình | 1029 | 0 | NONE ✓ | 1.1% |
| #152 tản nhiệt nước AIO (reconciled) | 1036 | 0 | NONE ✓ | 0.6% |
| #175 Hộp đen AI | 1344 | 0 | NONE ✓ | 2.8% |

Text-first, gỡ sạch ảnh external, 0 brand, overlap thấp, >150 từ, HTML safe. Apply body-only —
KHÔNG đổi title/handle/summary/tags/published/author/featured image.

## State sau run
| Mục | Giá trị |
|---|---|
| **PUT count** | 13 bài × 1 = 13 (PUT ≤1/bài) ✓ |
| **HTTP response** | 12×201 + 1×500(reconciled) |
| **verify source** | 13/13 = HARAVAN_READ_API |
| **semantic verify** | 13/13 = VERIFIED |
| **terminal pop count** | **0** (CREATE_NO_WINDOW) |
| **stale process count** | **0** |
| flags | **OFF** |
| CB | **closed** |
| scheduler | OFF (0 run) |
| upload / rehost | **0** |
| checkpoint | run 44 completed, processed 15, applied 12 + reconciled 1, saved sau mỗi bài |
| log path | `marketing_hub/state/logs/blog_rewrite_full_auto.log` (chỉ id/stage/event) |
| broken-link config | **unchanged** (LINK_CHECK_WORKERS=48, PER_HOST=4, HEAD 2s) |

## Acceptance (đạt hết)
terminal pop 0 ✓ · stale process 0 ✓ · PUT ≤1/bài ✓ · không re-PUT ✓ · flags OFF ✓ ·
CB closed (không uncertain thật) ✓ · upload 0 ✓ · scheduler 0 ✓ · broken-link unchanged ✓.

## Nhận xét + NEXT (chờ vợ)
- **Tỉ lệ apply rất cao: 13/15 = 87%** (so 2/5 smoke run 43). AUTO_LANE evergreen là mỏ vàng throughput.
- 2 BLOCKED_IMAGE (#183 Google Takeout, #165 ép xung) + 1 HOLD (#150 Nvidia Super/Ti — "nên mua") đúng gate.
- **Bài live cộng dồn ≈ 20** (5 trước + 2 run43 + 13 run44).
- AUTO_LANE pending còn lại ≈ **27** (42 − 15). **Dừng theo spec**, không tự chạy tiếp.
- Vợ duyệt → chạy batch tiếp (15-27 bài còn lại) để dọn hết AUTO_LANE.

## File đụng (chưa commit)
`blog_rewrite_full_auto.py` (thêm `skip_decided` + `decided_candidate_ids`) ·
`_scripts/run_blog_rewrite_full_auto.py` (`--skip-decided`) · báo cáo này. Không đụng `seo.py`.
