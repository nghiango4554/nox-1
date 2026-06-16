# P7.3 — AUTO_LANE LIVE SMOKE 5 BÀI

> Theo spec `Desktop/Past.txt`. Confirm phrase: `START FULL AUTO BLOG REWRITE SYNC`. Ngày 2026-06-11.
> **CHƯA COMMIT.** Runner nền độc lập (CREATE_NO_WINDOW). Dừng sau smoke 5 — KHÔNG tự chạy tiếp AUTO_LANE.

## Kết quả tổng
| Field | Giá trị |
|---|---|
| run_id | **43** |
| AUTO_LANE total | 50 (smoke lấy top 5) |
| processed / max | **5 / 5** ✓ |
| generated | 4 (#84/#151/#135/#176 gen mới; #21 dùng draft sẵn) |
| regenerated | 1 (#84 self-review pass 2) |
| **applied** | **2** ✅ (#84, #135 — bài AUTO_LANE đầu tiên lên live) |
| applied_reconciled | 0 |
| not_applied_retryable | 0 |
| HOLD_QUALITY | 0 |
| BLOCKED_IMAGE | 2 (#21, #151) |
| BLOCKED_FACT / HOLD_TIME_SENSITIVE | 1 (#176) |
| MANUAL_REVIEW | 0 |
| CONFLICT | 0 |
| FAILED | 0 |
| current_stage | completed |

**Lần đầu AUTO_LANE có bài APPLIED live** — selector evergreen-first hoạt động đúng mục tiêu.

## Chi tiết từng bài (serial, lane=AUTO)
| # | cid | article_id | Bài | Decision | PUT count | HTTP | verify source | semantic verify |
|---|---|---|---|---|---|---|---|---|
| 1 | 84 | 1002404222 | Tổng hợp kiến thức CPU Intel | ✅ **APPLIED** | **1** | **201** | HARAVAN_READ_API | VERIFIED (LIVE_VERIFIED) |
| 2 | 21 | 1002758362 | DLSS 4 là gì? Cách bật DLSS 4 | 🖼️ BLOCKED_IMAGE | 0 | — | — | — (phụ thuộc ảnh) |
| 3 | 151 | 1002420376 | Cách gắn quạt tản nhiệt PC | 🖼️ BLOCKED_IMAGE | 0 | — | — | — (phụ thuộc ảnh) |
| 4 | 135 | 1002414345 | Khắc phục lỗi Command Prompt | ✅ **APPLIED** | **1** | **201** | HARAVAN_READ_API | VERIFIED (LIVE_VERIFIED) |
| 5 | 176 | 1002431245 | Cách tối ưu card Nvidia chơi game | ⏸️ HOLD_TIME_SENSITIVE | 0 | — | — | — (fact gate) |

## Chất lượng 2 bài đã live (sạch)
| Bài | Words | Ảnh | Ảnh external | Brand đối thủ | Overlap |
|---|---|---|---|---|---|
| #84 CPU Intel (draft 111) | 1119 | 0 | 0 | NONE ✓ | 0.8% |
| #135 lỗi CMD (draft 117) | 1285 | 0 | 0 | NONE ✓ | 1.3% |

Cả 2 text-first, auto-fix gỡ sạch ảnh external, 0 brand đối thủ, overlap rất thấp (nguyên bản), >150 từ,
HTML safe. Apply body-only — KHÔNG đổi title/handle/summary/tags/published/author/featured image.

## Apply Haravan (P7.2 engine)
Mỗi bài applied: fresh GET (conflict SAFE_TO_APPLY) → backup payload trước PUT → PUT body_html only **1 lần**
→ HTTP 201 → GET verify → canonical+semantic VERIFIED → reconcile DB (status=applied) → checkpoint.
**Cả 2 PUT đều 201 verify trực tiếp** nên rule 500-but-write KHÔNG bị kích hoạt (đã validate P7.2 QA 21/21).

## State sau run
| Mục | Giá trị |
|---|---|
| **PUT count từng bài** | #84=1, #135=1 (2 bài còn lại 0) — **PUT ≤1/bài** ✓ |
| **HTTP response** | #84=201, #135=201 |
| **verify source** | cả 2 = HARAVAN_READ_API |
| **semantic verify** | cả 2 = VERIFIED (LIVE_VERIFIED) |
| **terminal pop count** | **0** (claude provider + runner CREATE_NO_WINDOW) |
| **stale process count** | **0** (runner exit 0, không claude child sót) |
| flags | **OFF** (all False) |
| CB | **closed** (open=false) |
| scheduler | OFF (0 run) |
| upload / rehost | **0** (apply body-only, không Theme Asset inline blog) |
| checkpoint | run 43 completed, processed 5, applied 2, saved sau mỗi bài |
| log path | `marketing_hub/state/logs/blog_rewrite_full_auto.log` (chỉ id/stage/event, KHÔNG token/body/prompt) |
| broken-link config | **unchanged** (LINK_CHECK_WORKERS=48, PER_HOST=4, HEAD 2s) |

## Acceptance (đạt hết)
| Tiêu chí | Kết quả |
|---|---|
| processed = 5 | ✓ |
| terminal pop = 0 | ✓ |
| stale process = 0 | ✓ |
| PUT tối đa 1/bài | ✓ |
| không re-PUT | ✓ |
| flags OFF sau run | ✓ |
| CB closed (không uncertain thật) | ✓ |
| upload = 0 | ✓ |
| scheduler = 0 | ✓ |
| broken-link config unchanged | ✓ |

## Nhận xét + NEXT (chờ vợ)
- **Selector evergreen-first thành công**: 2/5 applied (so với 0/3 ở smoke run 41 game-config/news).
  3 bài còn lại bị gate chặn đúng: #21/#151 phụ thuộc ảnh (BLOCKED_IMAGE), #176 fact time-sensitive.
- Gate ảnh vẫn chặt với bài có nhiều ảnh minh hoạ (#21 DLSS 8 ảnh, #151 hướng dẫn 5 bước) — đúng spec
  (text-first mới apply). Nếu muốn các bài này lên, cần xử lý ảnh riêng (review tay / chèn ảnh Sintech).
- **Bài live cộng dồn = 7** (#136/#110/#112/#163 + #63 reconciled + #84 + #135).
- **Dừng tại đây theo spec.** KHÔNG tự chạy tiếp toàn bộ AUTO_LANE. Chờ vợ quyết: chạy tiếp AUTO_LANE
  batch lớn hơn, hay xử lý nhóm BLOCKED_IMAGE.

## File đụng (chưa commit)
`blog_rewrite_full_auto.py` (thêm `auto_only` + tiebreak sort 4-5 `_lane_tiebreak`) ·
`_scripts/run_blog_rewrite_full_auto.py` (`--auto-only`) · báo cáo này.
Không đụng `seo.py` (broken-link). Không Full Auto live mới ngoài smoke 5.
