# BLOG REWRITE AI — P4.1 BATCH 5 VALIDATION (10/6/2026)

> Theo spec `Desktop\Past.txt`. Batch 5 local validation: baseline #64 + generate 4 bài mới (AI thật), validate đa dạng. **KHÔNG batch>5 · KHÔNG Haravan PUT · KHÔNG apply · KHÔNG upload/rehost ảnh · KHÔNG commit/push/deploy.**

## 1. 5 bài đại diện
| Slot | cid | article_id | Source group | Clicks | Ảnh | Bảng | Lý do chọn |
|---|---|---|---|---|---|---|---|
| A baseline | 136 | 1002416741 | text_only (#64 GEARVN) | 0 | 6 | 1 | baseline (draft v2 id 10) |
| B many-img | 8 | — | competitor_cdn | 0 | 10 | 0 | nhiều ảnh + external CDN |
| C VN news | 26 | — | (so sánh VGA, facts) | 0 | 1 | 1 | giữ facts kỹ thuật |
| D foreign | 7 | — | foreign_tech_media | 0 | 8 | 1 | viết nguyên bản, không dịch sát |
| E complex | 12 | — | competitor_cdn (keo tản nhiệt) | 0 | 3 | 1 | bảng + nhiều heading |
Đa dạng nguồn (text/competitor/foreign), traffic 0 (an toàn, không đụng bài traffic cao).

## 2. Job + worker
- Job #6 mode=batch_validation_5 provider=claude, generate **4 bài mới** (8,26,7,12) — baseline 136 dùng draft sẵn. Worker spawn `sys.executable`, completed 4/4 trong 437s, 1 bài không fail cả batch.
- Real-generate limit nới 1→**5** (batch validation; chưa mở full 147).

## 3. Validation lần 1 → 3 FAIL (systemic)
| Slot | v1 verdict | overlap | ảnh | lỗi |
|---|---|---|---|---|
| A #64 | PARTIAL | 2.0% | 6→6 | (baseline ok) |
| B #8 | **FAIL** | 14.2% | **10→3** | rơi ảnh |
| C #26 | PARTIAL | 18.9% | 1→1 | overlap cao |
| D #7 | **FAIL** | 6.0% | **8→1** | rơi ảnh + mất bảng |
| E #12 | **FAIL** | 10.9% | **3→1** | rơi ảnh |

**Nguyên nhân hệ thống:** `extract_images` chỉ giữ ảnh Sintech CDN (hstatic), BỎ ảnh hotlink từ CDN đối thủ → bài copy (ảnh external) bị rơi sạch.

## 4. Systemic prompt/gen fix
- `extract_images` → giữ **TẤT CẢ ảnh** (Sintech + external), trả `is_external`.
- `build_user_prompt` → liệt kê cả ảnh external, đánh dấu "[external — sẽ rehost sau]", yêu cầu giữ đủ.
- `_reinsert_images` → re-insert mọi ảnh thiếu (gồm external) nếu AI rơi.
- image_audit thêm `external_images` (đếm). External giữ URL tạm + flag rehost (KHÔNG drop, KHÔNG upload — P5).

## 5. Re-generate 3 FAIL → re-validation: 0 FAIL
Job #7 regenerate (8,7,12) provider=claude, completed 3/3 (425s). Kết quả cuối **5/5 PARTIAL, 0 FAIL**:
| Slot | cid | v | Verdict | overlap | ảnh | bảng | wc | PARTIAL vì |
|---|---|---|---|---|---|---|---|---|
| A #64 | 136 | v2 | PARTIAL | 2.0% | 6→6 | 1→1 | 893 | src-filename gearvn → rehost P5 |
| B many-img | 8 | v2 | PARTIAL | 9.6% | **10→10** | 0 | 1405 | 5 ảnh external CDN đối thủ → rehost P5 |
| C VN news | 26 | v1 | PARTIAL | 18.9% | 1→1 | 1→1 | 1389 | overlap cao → editor review |
| D foreign | 7 | v2 | PARTIAL | 8.3% | **8→8** | 1→0 | 1533 | mất 1 bảng → editor |
| E complex | 12 | v2 | PARTIAL | 14.0% | **3→3** | 1→1 | 1086 | src-filename hoangha → rehost P5 |

**Brand cleanup (text/alt/href): SẠCH toàn bộ 5 bài · 0 competitor link · HTML sạch · ảnh giữ đủ 100%.**

## 6. PASS/PARTIAL/FAIL
- 0 FAIL, 5 PARTIAL, 0 PASS-tuyệt-đối. PARTIAL = đúng kỳ vọng cho bài copy ảnh đối thủ: **cần rehost filename/ảnh external (P5)** + vài bài editor chỉnh nhẹ (C overlap, D bảng). Không bài nào rơi ảnh / còn brand text / HTML lỗi sau fix.

## 7. UI batch panel
Panel "🧪 Batch validation" (`/seo/blog-rewrite-ai`): bảng candidate · nguồn · version · **verdict PASS/PARTIAL/FAIL** · overlap · ảnh · brand(text/file) · nút Review (mở detail 7 tab). Badge "LOCAL VALIDATION ONLY — CHƯA CẬP NHẬT HARAVAN". API `GET /api/blog-rewrite/batch-results`. KHÔNG có Apply.

## 8. QA
- compileall OK · node --check N/A (JS inline Jinja).
- batch đúng 5 bài đại diện · generate 4 mới (≤5) · baseline draft 10 giữ nguyên · worker `sys.executable` · 1 bài lỗi không fail batch ✓.
- Image preserve sau fix (10→10, 8→8, 3→3, 6→6) · clean alt · filename brand flag · link audit (0 competitor) · HTML safety sạch · quality score ✓.
- Versioning: regenerate tạo v2, v1 giữ nguyên ✓.
- Guard: apply/rollback/bulk-approve **501** ✓ · **Haravan PUT=0 · image upload=0** · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 9. Files
- **MOD**: `blog_rewrite_gen.py` (giữ ảnh external + re-insert), `blog_rewrite.py` (real limit 1→5, batch_results/_verdict), `routes/blog_rewrite.py` (batch-results), `templates/blog_rewrite_ai.html` (batch panel).
- **NEW**: `docs/BLOG_REWRITE_AI_P4_1_BATCH5_VALIDATION.md`.
- **Backup**: `_backup/blog-rewrite-p4-1-batch5-20260610-153913/`.

## 10. Deferred P5
- Apply Haravan (conflict content_hash + fetch live + backup payload + PUT Open API) + rollback.
- **Image rehost THẬT** (download external/branded-filename → upload_asset → đổi src) — hiện image plan dry-run flag REHOST_EXTERNAL_LATER. Đây là blocker chính trước khi PASS sạch.
- Mở batch full 147 sau khi rehost + review PASS.

## OUTPUT
**BLOG REWRITE AI P4.1 BATCH 5 VALIDATION COMPLETED** · baseline 1 + generated 4 · 5 reviewed · 3 nguồn (text/competitor/foreign) · lần 1: 3 FAIL (rơi ảnh external) → systemic fix giữ ảnh external → re-gen → **0 FAIL, 5 PARTIAL** (ảnh giữ đủ 100%, brand text sạch, PARTIAL do rehost filename P5) · apply 501 · no Haravan PUT / no upload / broken-link untouched · no commit/stage/push/deploy/browser.
