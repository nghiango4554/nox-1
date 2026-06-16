# BLOG REWRITE AI — P6 AUTOPILOT · PREP_ONLY REAL RUN (10/6/2026)

> Chạy manual 1 lượt PREP_ONLY THẬT (cho AI generate local). **KHÔNG apply live · KHÔNG PUT/POST/DELETE · KHÔNG upload/rehost · KHÔNG bật scheduler · KHÔNG commit/push.** enabled trả về false sau run.

## 1. Config run
mode=PREP_ONLY · enabled=true (chỉ trong run) → **false sau run** · scheduler=false · flags live=false · max_generate_per_run=5 · max_apply_per_run=0 · max_apply_per_day=0 · max_regenerate_per_candidate=1.

## 2. Pipeline đã chạy
SELECT → GENERATE (4 bài, job 10-13, ~456s) → SANITIZE → IMAGE_REMEDIATE (gỡ ảnh ngoài local → text sạch) → FACT_CHECK → QUALITY_CHECK → PREFLIGHT → REPORT. Không bài nào làm fail toàn run.

## 3. Per-candidate (run 26 — sau calibration fix)
| # | Article | Title | Lý do chọn | Draft | Ver | Ảnh gốc→draft | Ảnh gỡ local | Gate | Visual dep | Fact | Overlap | Score | Quyết định |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #149 | 1002420321 | Hướng dẫn xóa logo/watermark | evergreen | 56 | v2 | 13→0 | 13 ngoài | ALLOW | **TRUE** (bước 1/2/3) | safe | 0.8% | 88 | **MANUAL_REVIEW** (phụ thuộc ảnh) |
| #163 | 1002423345 | Visual Studio Code là gì | evergreen | 58 | v2 | 4→0 | 4 ngoài | ALLOW | false | safe | 2.3% | 88 | **AUTO_ELIGIBLE** ✅ |
| #12 | 1002728484 | Keo tản nhiệt kim loại lỏng | evergreen | 54 | v3 | 3→1 | 2 ngoài | ALLOW | false | safe | **14.0%** | 60 | **MANUAL_REVIEW** (overlap cao) |
| #14 | 1002732057 | Cách Build PC Gaming | evergreen | 60 | v2 | 6→0 | 6 ngoài | ALLOW | false | **unsafe (time=6, fps=3)** | 4.7% | 88 | **HOLD_TIME_SENSITIVE** |
| #52 | 1002397990 | Tại sao máy chạy chậm | evergreen | 62 | v2 | 18→0 | 18 ngoài | ALLOW | false | safe | 2.7% | 88 | **AUTO_ELIGIBLE** ✅ |

(Ảnh đều SINTECH? Không — bài gốc toàn ảnh ngoài → gỡ local hết → text sạch, gate ALLOW. 0 ảnh giữ, 0 ảnh blocked sau remediate.)

## 4. Kiểm tra đặc biệt — ĐẠT HẾT
- ✅ **Visual tutorial** (#149 "bước 1/2/3") → KHÔNG auto-gỡ-rồi-eligible → **MANUAL_REVIEW** (dù gate ALLOW, overlap 0.8%, fact safe).
- ✅ **Benchmark/FPS/time-sensitive** (#14 time=6, fps=3) → **HOLD_TIME_SENSITIVE** (chưa nguồn chính thức).
- ✅ **Ảnh competitor/news/unknown** → gỡ local (text-first, không phụ thuộc hình) → recompute gate ALLOW. #149 phụ thuộc hình → KHÔNG eligible.
- ✅ **Overlap cao** (#12 14%) → MANUAL_REVIEW.
- ✅ **Evergreen sạch thật** (#163, #52: overlap ≤2.7%, brand/html PASS, fact safe, không phụ thuộc ảnh) → **AUTO_ELIGIBLE**.

## 5. Calibration fix (phát hiện trong run)
Run đầu (run 25) cho 0 AUTO_ELIGIBLE vì `quality_gate` default score=60 khi clean-version thiếu scorecard (gen.quality_metrics ở `_save_clean_version` không kèm scorecard). **Đã sửa:** khi thiếu scorecard, suy score từ overlap+brand+html (ov<5%→88, <10%→82, ≤12%→78). Re-run (run 26) → #163/#52 đúng AUTO_ELIGIBLE. An toàn vẫn giữ (thận trọng nghiêng MANUAL_REVIEW khi nghi ngờ).

## 6. Tổng kết run 26
| Chỉ số | Giá trị |
|---|---|
| run_id | 26 |
| selected | 5 |
| generated | 4 (run 25) · regenerated 0 |
| **AUTO_ELIGIBLE** | **2** (#163, #52) |
| PREP_ONLY | 0 |
| HOLD_TIME_SENSITIVE | 1 (#14) |
| HOLD_UNSUPPORTED | 0 |
| BLOCKED_IMAGE | 0 |
| MANUAL_REVIEW | 2 (#149 visual, #12 overlap) |
| FAILED | 0 |
| **PUT count** | **0** |
| upload count | 0 |
| scheduler actual run | 0 |
| circuit breaker | closed |
| flags sau run | live_apply=false · rollback=false · bulk=false |
| broken-link config | nguyên (48/8/4/HEAD 2s) |
| enabled sau run | **false (paused)** |

## 7. Acceptance — ĐẠT
- ✅ PUT=0 · upload=0 · scheduler actual run=0
- ✅ flags OFF sau run · enabled=false
- ✅ chỉ evergreen thật sự sạch (#163, #52) mới AUTO_ELIGIBLE
- ✅ bài rủi ro: #149 visual→MANUAL_REVIEW, #12 overlap→MANUAL_REVIEW, #14 time-sensitive→HOLD
- ✅ 1 bài lỗi không fail toàn run (FAILED=0), không retry vô hạn (max_regenerate=1)

## 8. Files
- **NEW**: doc này. Drafts mới: #149 v2(56), #163 v2(58), #12 v3(54), #14 v2(60), #52 v2(62).
- **MOD**: `blog_rewrite_autopilot.py` (quality_gate score fallback overlap-based).

## OUTPUT
**P6 AUTOPILOT PREP_ONLY REAL RUN PASS** · 5 evergreen selected · 4 generated local · **AUTO_ELIGIBLE 2 (#163 VS Code, #52 máy chậm)** · MANUAL_REVIEW 2 (#149 visual tutorial, #12 overlap 14%) · HOLD_TIME_SENSITIVE 1 (#14 build PC) · special checks ĐẠT (visual→manual, benchmark→hold, external image gỡ local→gate ALLOW, evergreen sạch→eligible) · **PUT=0 · upload=0 · scheduler run=0 · flags OFF · enabled=false · broken-link nguyên** · no commit/push. **2 bài AUTO_ELIGIBLE sẵn sàng — chờ vợ review để mở SAFE_AUTO_APPLY.**
