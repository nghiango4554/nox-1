# BLOG REWRITE AI — P7 FULL AUTO · DRY-RUN HẾT QUEUE (10/6/2026)

> Chạy full-auto dry_run=true toàn bộ queue (143 bài). **KHÔNG sync live · PUT=0 · upload=0 · scheduler=0 · flags OFF · checkpoint giữ.** Content fail → HOLD/BLOCKED + next (không dừng run).

## 1. Tổng kết run (run_id 35)
| Chỉ số | Giá trị |
|---|---|
| run_id | **35** |
| queue_total | **143** |
| processed | **143** (hết queue ✓) |
| generated | 0 · regenerated 0 (dry-run KHÔNG gọi AI) |
| **AUTO_ELIGIBLE** | **4** |
| BLOCKED_IMAGE | 2 |
| BLOCKED_FACT | 0 |
| HOLD_TIME_SENSITIVE | 1 |
| HOLD_UNSUPPORTED | 0 |
| MANUAL_REVIEW | 1 |
| CONFLICT | 0 |
| FAILED | 0 |
| PREP_ONLY (chưa draft, cần generate khi live) | **135** |
| PUT count | **0** |
| upload count | **0** |
| scheduler actual run | **0** |
| circuit breaker | closed |
| checkpoint | saved (stage=completed) |
| broken-link config | nguyên (48/8/4/HEAD 2s) |
| live flags | live_apply/rollback/bulk = false |

> ⚠️ **Quan trọng:** dry-run KHÔNG generate (true dry-run, tránh ~5h AI cho 135 bài). 8 bài đã có draft → phân loại đầy đủ; **135 bài chưa draft → PREP_ONLY "cần generate"** (sẽ được gen + phân loại khi chạy LIVE). Con số AUTO_ELIGIBLE=4 là từ 8 draft sẵn có; chạy live sẽ phát sinh thêm nhiều eligible từ 135 bài kia.

## 2. 4 bài AUTO_ELIGIBLE (sẽ tự sync nếu chạy live)
| # | Clicks | Title | Ghi chú auto-fix |
|---|---|---|---|
| #163 | 1 | Visual Studio Code là gì | evergreen sạch, ov 2.3% |
| #52 | 0 | Tại sao máy tính chạy chậm | gỡ 18 ảnh ngoài → text sạch |
| #8 | 0 | Top 10 sai lầm build PC | gỡ ảnh đối thủ → text sạch, fact safe |
| #14 | 0 | Cách Build PC Gaming | auto-fix bỏ câu giá/benchmark → fact safe |

→ Tất cả ≥150 từ (qua thin-content guard), gate ALLOW, overlap≤12%, brand/HTML PASS, conflict SAFE, score_source FULL_RECOMPUTE/SCORECARD.

## 3. 2 bài BLOCKED_IMAGE (giữ queue xử lý ảnh sau)
| # | Title | Lý do |
|---|---|---|
| #149 | Hướng dẫn xóa logo/watermark | **phụ thuộc ảnh** "bước 1/2/3" |
| #21 | DLSS 4 là gì + cách bật | **phụ thuộc ảnh** (tutorial visual) |

## 4. HOLD / MANUAL
- **HOLD_TIME_SENSITIVE 1**: #7 Sửa máy tính Quận 6 (claim time-sensitive).
- **MANUAL_REVIEW 1**: #12 Keo tản nhiệt (overlap 14% > 12% + score 60).

## 5. Top 20 traffic (queue)
| # | Clicks | SS | Tier | Title |
|---|---|---|---|---|
| #63 | 8 | 9 | MEDIUM | Cấu hình chơi CS2 |
| #11 | 2 | 3 | LOW | PC nào chơi được GTA 5 |
| #149 | 2 | 2 | LOW | Hướng dẫn xóa logo/watermark (→BLOCKED_IMAGE) |
| #77 | 2 | 2 | LOW | Cấu hình chơi ZZZ |
| #220 | 2 | 2 | LOW | ASUS PC Hatsune Miku |
| #84 | 2 | 1 | LOW | Kiến thức về CPU |
| #211 | 1 | 1 | LOW | Intel Core Ultra 300 |
| #68 | 1 | 1 | LOW | Cấu hình Naraka |
| #209 | 1 | 1 | LOW | AMD Radeon RX 9070 GRE |
| #163 | 1 | 1 | LOW | Visual Studio Code (→AUTO_ELIGIBLE) |
| #169 | 1 | 0 | LOW | Khôi phục file đã xóa |
| #21 | 1 | 0 | LOW | DLSS 4 (→BLOCKED_IMAGE) |
| #151/#135/#176/#12/#69/#58/#150/#207 | 0 | ≤3 | LOW | ... |

→ Queue traffic THẤP: chỉ **19/143 bài có traffic>0**, cao nhất #63 (8 clicks). 4 bài AUTO_ELIGIBLE đều traffic ≤1.

## 6. Top 20 "sẽ tự sync nếu live"
Chỉ **4 bài** (mục 2) — vì 135 bài chưa generate. Khi chạy live, danh sách này sẽ dài hơn nhiều sau khi generate.

## 7. Top 20 blocked ảnh
2 bài (mục 3): #149, #21 (đều phụ thuộc tutorial visual → không tự gỡ ảnh).

## 8. Ảnh
- Ảnh gỡ local (dry-run, trên 8 draft xử lý): #52 ~18, #149 ~13, #8 ~9, #21 ~8, #14 ~6, #163 ~4, #12 ~2 (ảnh ngoài/đối thủ → text sạch).
- Ảnh còn blocked: 0 (các bài eligible đã text sạch; #149/#21 blocked do **phụ thuộc hình** chứ không phải ảnh chưa gỡ).

## 9. Acceptance — ĐẠT
- ✅ PUT=0 · upload=0 · scheduler=0 · flags OFF · checkpoint saved · xử lý hết queue (143/143)
- ✅ KHÔNG bài benchmark rỗng AUTO_ELIGIBLE (thin-content guard — #14 sau auto-fix vẫn ≥150 từ mới eligible; bài bị gutted → MANUAL_REVIEW)
- ✅ KHÔNG bài tutorial phụ thuộc ảnh AUTO_ELIGIBLE (#149, #21 → BLOCKED_IMAGE)
- ✅ KHÔNG bài ảnh đối thủ CHƯA GỠ AUTO_ELIGIBLE (#8 ảnh đối thủ đã được auto-fix GỠ → text sạch mới eligible)
- ✅ content fail → HOLD/BLOCKED + next, CB không mở

## 10. Files
- **NEW**: doc này. Drafts clean-version phát sinh cho 8 bài đã xử lý (additive, local).
- Run records: `blog_rewrite_autopilot_runs` #35 + items.

## OUTPUT
**P7 FULL AUTO DRY-RUN ALL COMPLETED** · run 35 · queue 143 · processed 143 · AUTO_ELIGIBLE 4 (#163/#52/#8/#14) · BLOCKED_IMAGE 2 (#149/#21 phụ thuộc ảnh) · HOLD_TIME_SENSITIVE 1 (#7) · MANUAL_REVIEW 1 (#12 overlap) · PREP_ONLY 135 (chưa draft, cần generate khi live) · **PUT=0 · upload=0 · scheduler=0 · flags OFF · checkpoint saved · CB closed · broken-link nguyên** · acceptance ĐẠT (không benchmark-rỗng/visual/ảnh-đối-thủ-chưa-gỡ lọt eligible). **Chờ vợ xem tổng số — chạy live sẽ generate 135 bài còn lại.**
