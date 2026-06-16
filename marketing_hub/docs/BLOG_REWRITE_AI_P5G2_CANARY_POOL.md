# BLOG REWRITE AI — P5G-2 CANARY POOL (10/6/2026)

> Mở canary pool: regenerate #26 + generate 2 SAFE_NOW (≤3 AI draft local). **KHÔNG PUT/apply/upload/rehost/batch · KHÔNG mở flag · KHÔNG commit/push/deploy.** Live flags KHÓA.

## 1. P5G-1 gap → P5G-2
P5G-1: 6 SAFE_NOW không có draft + chỉ #26 ready (overlap 18.9%). P5G-2 mở pool: regenerate #26 (hạ overlap) + generate 2 SAFE_NOW sạch ảnh.

## 2. Prompt hardening (chống overlap)
Thêm vào BLOG_REWRITE_PROMPT_V1: "TUYỆT ĐỐI không lặp chuỗi 5+ từ liên tiếp giống bài cũ; viết câu cấu trúc khác hẳn (5-gram overlap ≤12%); bài so sánh viết lại nội dung từng ô bảng".

## 3. Audit 6 SAFE_NOW (ảnh bài gốc — nguồn generate)
| ID | Title | Ảnh gốc | Generate sạch? |
|---|---|---|---|
| 21 | DLSS 4 là gì | 8 SINTECH | ✅ |
| 50 | Microsoft kết thúc Win 11 21H2 | 1 Sintech + 1 invalid | ✅ (nhưng deadline đã hết hạn) |
| 55 | Nvidia ngừng RTX 3060 | 2 SINTECH | ✅ |
| 72 | Valorant config | 1 COMPETITOR | ⛔ |
| 71 | Elden Ring config | 3 COMPETITOR | ⛔ |
| 64 | Dota 2 config | 3 UNKNOWN | ⛔ |
→ Chỉ #21/#50/#55 (tech) generate ra draft sạch ảnh; gaming còn ảnh đối thủ. Chọn **#21 + #55** (tránh #50 deadline hết hạn).

## 4. Generate (job #8, 3/3 completed 334s)
- **#26 regenerate → v2 (draft 22)** — v1 (draft 12) giữ nguyên không overwrite.
- **#21 → v1 (draft 23)** · **#55 → v1 (draft 24)**. Total AI draft = 3 (≤3). Worker sys.executable, no PUT/upload.

## 5. Validation 3 bài — ĐỀU PASS
| Candidate | Draft | Overlap | Img | Tbl | Gate | Conflict | Brand | HTML | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| #26 So sánh 3 VGA | 22 v2 | **9.2%** (từ 18.9%) | 1→1 | 1→1 | ALLOW | SAFE | sạch | sạch | **PASS** |
| #21 DLSS 4 | 23 v1 | 10.0% | **8→8** | 0 | ALLOW | SAFE | sạch | sạch | **PASS** |
| #55 Nvidia RTX 3060 | 24 v1 | **1.5%** | 2→2 | 0 | ALLOW | SAFE | sạch | sạch | **PASS** |
→ Regenerate #26 hạ overlap 18.9%→9.2% (prompt hardening ăn). Ảnh Sintech giữ đủ 100%, brand/HTML sạch, conflict SAFE.
⚠️ **Facts tech (DLSS driver / Nvidia / spec VGA) cần vợ verify tay** trước approve.

## 6. Canary-ready pool (cập nhật canary_prep)
Tiêu chí canary-ready: draft + chưa apply + gate ALLOW + conflict SAFE_TO_APPLY + overlap ≤12% + brand/HTML sạch. overlap>12% → REVIEW_REQUIRED.
- **canary_ready: 3** (#26 v2, #55, #21) · review_required: 0 · safe_no_draft: 6 (gaming chưa gen) · blocked_images: 3 (#7/#8/#12) · applied: 1 (#64).
- **Selected 2 canary: #26 + #55** (ít ảnh/bảng, overlap thấp, traffic thấp).

## 7. UI
Section "🚀 Canary rollout": canary-ready badge READY + bảng (gate/conflict/approval/overlap/img/tbl) + checklist thủ công + nút Review/Regenerate/Approve local. Apply live disabled.

## 8. Export
`docs/BLOG_REWRITE_CANARY_POOL_READY.md` + `.csv` (3 ready + facts_manual_verify + rollout_status).

## 9. QA
- compileall OK · node --check N/A (JS inline).
- #26 v1 preserved (id 12) + v2 (id 22) — không overwrite ✓. Total AI generate = 3 (≤3) ✓.
- canary_prep classification (overlap≤12% gate) ✓ · reverse-copy/applied excluded ✓.
- Smoke `/seo/blog-rewrite-ai` `/remediation/canary-prep` `/status` 200.
- **PUT=0 · POST write=0 · DELETE=0 · upload=0** · live flags **OFF (khóa)** · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 10. Files
- **NEW**: `docs/BLOG_REWRITE_CANARY_POOL_READY.md` + `.csv`, doc này.
- **MOD**: `blog_rewrite_gen.py` (prompt anti-overlap), `blog_rewrite_remediate.py` (canary_prep overlap gate + review bucket), `templates/blog_rewrite_ai.html` (canary panel — từ P5G-1).
- **Backup**: `_backup/blog-rewrite-p5g2-canary-pool-20260610-173412/`.

## 11. Deferred
- **Vợ verify facts** 3 bài (DLSS/Nvidia/VGA) → approve_local.
- **Canary apply**: 2 bài selected (#26, #55) qua P5B one-shot — cần vợ xác nhận trực tiếp từng bài (như #64).
- Generate draft cho gaming SAFE_NOW (cần xử lý ảnh đối thủ trước).

## OUTPUT
**BLOG REWRITE AI P5G-2 CANARY POOL COMPLETED** · regenerate #26 v2 overlap 18.9%→9.2% · generate #21(10%)+#55(1.5%) · 3 AI draft, all PASS (gate ALLOW/conflict SAFE/brand+HTML sạch/ảnh giữ đủ) · canary_ready 3, selected 2 (#26+#55) · facts cần verify tay · #26 v1 preserved · PUT=0 upload=0 flags OFF · broken-link untouched · no commit/push. **Chờ vợ verify facts + xác nhận canary apply từng bài.**
