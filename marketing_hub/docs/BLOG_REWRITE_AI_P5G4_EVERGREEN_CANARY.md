# BLOG REWRITE AI — P5G-4 EVERGREEN CANARY POOL (10/6/2026)

> HOLD bài rủi ro facts + tạo pool canary evergreen (how-to, không số liệu time-sensitive). Local. **KHÔNG PUT/apply/upload/rehost/batch · KHÔNG mở flag · KHÔNG commit/push/deploy.** Live flags KHÓA.

## 1. HOLD #55 + #26
- **#55 RTX 3060** → `HOLD_TIME_SENSITIVE_NEWS` · action REWRITE_AS_UNCONFIRMED_REPORT_OR_SKIP (claim ngừng SX lỗi thời; tin Nvidia đưa 3060 lại chỉ là báo cáo/rumor chưa xác nhận chính thức → chỉ được viết dạng "theo báo cáo").
- **#26 So sánh VGA** → `HOLD_UNSUPPORTED_BENCHMARKS` · action REMOVE_UNSUPPORTED_FPS_AND_REVIEW_SPECS.
- Draft cũ giữ nguyên, KHÔNG apply, KHÔNG regenerate.

## 2. Fact taxonomy (harden)
OFFICIAL_VERIFIED (giữ) · REPUTABLE_REPORT_UNCONFIRMED (chỉ "theo báo cáo", không thành fact) · TIME_SENSITIVE_REVIEW (giá/benchmark/driver/release/tồn kho → verify hiện tại) · UNSUPPORTED_REMOVE (FPS/benchmark/giá AI tự tạo → xóa) · MANUAL_REVIEW.

## 3. Audit chọn 2 evergreen
42 bài how-to ứng viên — **TẤT CẢ còn ảnh ngoài** trong bài gốc (đối thủ/news). Chọn 2 bài concept ít ảnh, fact-safe:
| Slot | Candidate | Title | Group | Images gốc | Time-sensitive risk |
|---|---|---|---|---|---|
| A | #112 | Cảm biến Hero là gì | concept how-to | 1 (ngoài) | KHÔNG (khái niệm chuột) |
| B | #110 | Tần số quét màn hình là gì | concept how-to | 3 (ngoài) | KHÔNG (khái niệm Hz) |

## 4. Generate + remove external images (local)
Prompt thêm: cấm tạo benchmark/FPS/giá/timeline/driver claim không nguồn. Job #9 (2/2, 209s). Sau gen → **gỡ ảnh ngoài** (giữ chỉ Sintech; 2 bài này thành text sạch) → sanitize → version v2. image_items ảnh ngoài → REMOVE_FROM_DRAFT → article_gate ALLOW.

## 5. Fact-check local — 2 evergreen PASS
| Candidate | Draft | Overlap | Img | Gate | Conflict | Brand | HTML | FPS/giá bịa | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| #112 Cảm biến Hero | 27 v2 | 2.5% | 0 | ALLOW | SAFE | sạch | sạch | 0 FPS / 0 giá | **READY_EVERGREEN** |
| #110 Tần số quét | 28 v2 | 2.3% | 0 | ALLOW | SAFE | sạch | sạch | FPS = khái niệm (Hz↔FPS), 0 giá | **READY_EVERGREEN** |
→ #110 nhắc FPS nhưng là **khái niệm** ("màn 144Hz cần ~144 FPS"), mốc Hz chuẩn (60/144/165) — KHÔNG phải benchmark bịa. Cả 2 fact-safe.

## 6. Canary-ready pool (canary_prep cập nhật)
Groups: READY_EVERGREEN · HOLD_TIME_SENSITIVE · HOLD_UNSUPPORTED · REVIEW_REQUIRED · NO_DRAFT · APPLIED.
- **canary_ready: 3** (#110, #112 evergreen + #21 DLSS) · **hold: 2** (#55, #26) · review: 0.
- **Selected 2 canary: #110 + #112** (evergreen fact-safe, 0 ảnh, overlap ≤2.5% — ưu tiên hơn #21 DLSS vì #21 có facts driver time-sensitive + 8 ảnh).

## 7. UI
Canary panel: badge READY_EVERGREEN / HOLD_TIME_SENSITIVE / HOLD_UNSUPPORTED + fact-review (từ P5G-3). Apply live disabled.

## 8. Export
`docs/BLOG_REWRITE_EVERGREEN_CANARY_POOL.md` + `.csv`.

## 9. QA
- compileall OK · node --check N/A.
- #55 HOLD_TIME_SENSITIVE_NEWS ✓ · #26 HOLD_UNSUPPORTED_BENCHMARKS ✓ · 2 evergreen selected ✓ · 2 draft generated (≤2) ✓.
- fact taxonomy · unsupported benchmark/news không lọt canary · gate ALLOW · overlap≤12% · HTML/brand sạch ✓.
- Smoke `/seo/blog-rewrite-ai` `/remediation/canary-prep` 200 · canary_ready 3, hold 2, selected [110,112].
- **PUT=0 · POST write=0 · DELETE=0 · upload=0** · live flags **OFF (khóa)** · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 10. Files
- **NEW**: `docs/BLOG_REWRITE_EVERGREEN_CANARY_POOL.md` + `.csv`, `state/_canary_hold.json`, doc này.
- **MOD**: `blog_rewrite_gen.py` (prompt cấm benchmark/giá/tin), `blog_rewrite_remediate.py` (canary_prep HOLD + READY_EVERGREEN).
- **Backup**: `_backup/blog-rewrite-p5g4-evergreen-20260610-175501/`.

## 11. Deferred
- Vợ review nhẹ 2 evergreen (#110, #112) → approve_local → **canary apply** (P5B one-shot, xác nhận từng bài như #64).
- #55 rewrite dạng "theo báo cáo" / #26 bỏ số FPS (gỡ HOLD).

## OUTPUT
**BLOG REWRITE AI P5G-4 EVERGREEN CANARY POOL COMPLETED** · HOLD #55 (time-sensitive news) + #26 (unsupported benchmark) · generate 2 evergreen #112 Cảm biến Hero + #110 Tần số quét (how-to concept, gỡ ảnh ngoài → text sạch) · fact-check PASS (0 FPS/giá bịa, overlap ≤2.5%, gate ALLOW, brand/HTML sạch) · canary_ready 3, selected 2 (#110+#112) · PUT=0 upload=0 flags OFF · broken-link untouched · no commit/push. **2 canary fact-safe sẵn sàng vợ review → approve → apply.**
