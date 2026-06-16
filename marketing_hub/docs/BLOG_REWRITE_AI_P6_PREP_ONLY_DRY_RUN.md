# BLOG REWRITE AI — P6 AUTOPILOT · PREP_ONLY DRY-RUN (10/6/2026)

> Chạy manual 1 lượt PREP_ONLY dry-run. **KHÔNG gọi AI · KHÔNG PUT/POST/DELETE · KHÔNG upload/rehost · KHÔNG apply · KHÔNG bật scheduler · KHÔNG commit/push.** enabled=false giữ nguyên sau run.

## 1. Run PREP_ONLY dry-run (run_id 24)
Dry-run KHÔNG gọi AI generate (đúng nghĩa dry-run, 0 side-effect). Bài chưa có draft → PREP_ONLY "cần generate"; bài có draft → chạy full gate.

| # | Article | Loại | Draft | Generate | Image gate | Fact gate | Quality | Overlap | Conflict | Quyết định |
|---|---|---|---|---|---|---|---|---|---|---|
| #149 Hướng dẫn xóa logo/watermark | 1002420321 | evergreen | chưa | dry-run skip | — | — | — | — | — | **PREP_ONLY** (cần generate) |
| #163 Visual Studio Code là gì | 1002423345 | evergreen | chưa | dry-run skip | — | — | — | — | — | **PREP_ONLY** (cần generate) |
| #12 Keo tản nhiệt kim loại lỏng | 1002728484 | evergreen | có (v2) | không | ALLOW | safe | **FAIL** | **14.0%** | — | **MANUAL_REVIEW** (overlap>12% + score 60) |
| #14 Cách Build PC Gaming | 1002732057 | evergreen | chưa | dry-run skip | — | — | — | — | — | **PREP_ONLY** (cần generate) |
| #52 Tại sao máy chạy chậm | 1002397990 | evergreen | chưa | dry-run skip | — | — | — | — | — | **PREP_ONLY** (cần generate) |

→ **Selection chọn ĐÚNG 5 bài evergreen how-to.** #12 có draft cũ overlap 14% → quality_gate đẩy MANUAL_REVIEW (đúng).

## 2. Demo gate (read-only) — bài tin/benchmark/external KHÔNG lọt AUTO_ELIGIBLE
Selection policy lọc tin/benchmark/HOLD ngay từ đầu nên chúng không vào run. Demo trực tiếp các gate trên bài có draft sẵn để xác nhận autopilot phân loại đúng:

| Candidate | Loại | Image gate | Fact gate | Quyết định autopilot |
|---|---|---|---|---|
| #55 Nvidia RTX 3060 | **news** | ALLOW | fact_safe=**False** (time-sensitive=4) | **HOLD_TIME_SENSITIVE** ✓ |
| #26 So sánh 3 VGA | **benchmark** | ALLOW | fact_safe=**False** (unsupported=19) | **HOLD_UNSUPPORTED** ✓ |
| #8 Top 10 sai lầm build PC | **external image** | **BLOCK_COMPETITOR_IMAGE** | safe | **BLOCKED_IMAGE** ✓ |
| #112 Cảm biến HERO | **evergreen sạch** | ALLOW | fact_safe=True | MANUAL_REVIEW (quality_gate thận trọng) |

→ Tin/benchmark/ảnh-đối-thủ đều KHÔNG lọt AUTO_ELIGIBLE. (#112 đã live thật nhưng quality_gate dùng score mặc định 60 khi scorecard thiếu field originality/brand → thận trọng đẩy MANUAL_REVIEW thay vì auto-apply — an toàn, không sai hướng.)

## 3. Tổng kết run
| Chỉ số | Giá trị |
|---|---|
| selected | 5 |
| generated | 0 (dry-run) |
| AUTO_ELIGIBLE | 0 (4 cần generate + 1 quality-fail) |
| PREP_ONLY (cần generate) | 4 |
| MANUAL_REVIEW | 1 |
| HOLD / BLOCKED_IMAGE / FAILED | 0 / 0 / 0 |
| **PUT count** | **0** |
| **upload count** | **0** |
| **scheduler run count** | **0** |
| circuit breaker | closed |
| flags sau run | live_apply=false · rollback=false · bulk=false |
| broken-link config | nguyên (48 / 8 / 4 / HEAD 2s) |
| enabled / scheduler sau run | **false / false** |

## 4. Acceptance — ĐẠT
- ✅ PREP_ONLY **PUT = 0**
- ✅ upload = 0 · scheduler actual run = 0
- ✅ flags vẫn OFF (live_apply/rollback/bulk = false)
- ✅ bài tin tức (#55) / benchmark (#26) KHÔNG lọt AUTO_ELIGIBLE → HOLD
- ✅ bài ảnh đối thủ (#8) KHÔNG lọt AUTO_ELIGIBLE → BLOCKED_IMAGE
- ✅ bài evergreen được chọn đúng (5/5 evergreen)
- ⚠️ AUTO_ELIGIBLE=0 trong run này vì 4 bài chưa có draft (dry-run không gen) + #12 overlap cao → cần run thật (PREP_ONLY có generate) để thấy AUTO_ELIGIBLE.

## 5. Nhìn 4 thứ vợ cần
| Câu hỏi | Trả lời |
|---|---|
| Chọn đúng bài evergreen? | ✅ 5/5 evergreen how-to |
| HOLD đúng tin/benchmark? | ✅ #55→TIME_SENSITIVE, #26→UNSUPPORTED |
| Block đúng ảnh external? | ✅ #8→BLOCKED_IMAGE |
| Tuyệt đối 0 PUT? | ✅ **PUT=0** |

## 6. Files
- **NEW**: doc này.
- **MOD**: `blog_rewrite_autopilot.py` (dry_run skip AI generate — true dry-run 0 side-effect).

## OUTPUT
**P6 AUTOPILOT PREP_ONLY DRY-RUN PASS** · 5 evergreen selected · 4 PREP_ONLY (cần generate) + 1 MANUAL_REVIEW · gate demo: news→HOLD_TIME_SENSITIVE, benchmark→HOLD_UNSUPPORTED, external-image→BLOCKED_IMAGE · **PUT=0 · upload=0 · scheduler run=0 · flags OFF · enabled/scheduler=false · broken-link nguyên** · no commit/push. **Dry-run PASS — sẵn sàng bước tiếp (#112 đã live, mở SAFE_AUTO_APPLY 1 bài/ngày khi vợ duyệt).**
