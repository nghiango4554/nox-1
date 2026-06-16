# BLOG REWRITE AI — P5D IMAGE REGRESSION GATE (10/6/2026)

> Regression image audit + apply gate store-aware. Read-only. **KHÔNG apply live · KHÔNG upload/rehost · KHÔNG PUT/POST/DELETE · KHÔNG commit/push/deploy.** Live flags giữ KHÓA.

## 1. Root cause
`file.hstatic.net` (và cdn/product.hstatic.net) là **CDN dùng chung MỌI shop Haravan** — KHÔNG thể coi mọi hstatic = ảnh Sintech. Phải phân loại theo **STORE ID trong path**. Bug cũ coi ảnh GEARVN (store 1000026716) là HARAVAN_EXISTING của Sintech → giữ hotlink → bài #64 hiện ảnh 404.
- Sintech store = **200000860097** · GEARVN = 1000026716.

## 2. Centralize helper — `blog_rewrite_images.py` (mới)
`extract_hstatic_store_id` · `is_sintech_image` · `classify_image_source` · `check_image_availability` · `build_image_audit` · `audit_body_images`. Gỡ logic duplicate: `blog_rewrite_gen._img_is_sintech` + `blog_rewrite_apply` nay delegate về module chung.
Source class: SINTECH_OWNED · HARAVAN_OTHER_STORE · OFFICIAL_MANUFACTURER · COMPETITOR_SOURCE · NEWS_MEDIA_SOURCE · UNKNOWN_EXTERNAL · INVALID_URL.

## 3. Config — `state/blog_rewrite_config.json`
`{"sintech_haravan_store_id":"200000860097"}` (no BOM, no token). Thiếu config → KHÔNG auto coi ảnh là Sintech (mark UNKNOWN). Secret scan: sạch.

## 4. Availability checker
HEAD (GET fallback 403/405), follow redirect có kiểm soát, close response, không download full. 200-399→reachable · 404/410→dead · timeout/403/429/5xx→uncertain (KHÔNG gọi timeout=broken) · invalid→invalid.

## 5. Rights + apply gate
rights_status (OWNED_SINTECH/OFFICIAL/COMPETITOR/NEWS/UNKNOWN/MANUAL_REVIEW) + recommended_action (KEEP/REMOVE_DEAD_IMAGE/REPLACE_WITH_OFFICIAL/CREATE_ORIGINAL/REHOST_ALLOWED_LATER/MANUAL_REVIEW) + apply_gate_status (ALLOW/BLOCK_DEAD_IMAGE/BLOCK_COMPETITOR_IMAGE/BLOCK_UNKNOWN_IMAGE/REVIEW_REQUIRED).

## 6. Pre-apply image gate (harden engine)
`apply_draft_body_only` + `apply_preview` chạy `audit_body_images` → **BLOCK apply (409) nếu có ảnh dead/competitor/unknown**. Chỉ ALLOW khi ảnh đã gỡ/thay hợp lệ. P5D chưa cho manual override live.

## 7. Audit read-only toàn 147 candidate
`docs/BLOG_REWRITE_IMAGE_REGRESSION_AUDIT.md` + `blog_rewrite_image_regression_audit.csv`.
- 147 candidate · 145 có ảnh · **815 ảnh**.
- SINTECH_OWNED 54 · COMPETITOR 186 · NEWS 120 · UNKNOWN_EXTERNAL 439 · HARAVAN_OTHER_STORE 13 · OFFICIAL 2 · INVALID 1.
- Ảnh chết 404/410: **12** · uncertain 28.
- Candidate: safe **4** · **BLOCKED 143** · review 0.
→ **143/147 bài còn ảnh đối thủ/external/chết → gate chặn apply đúng.** Quy mô thật của bug: bài copy bê nguyên ảnh hotlink đối thủ, trước bị tưởng "preserved".

## 8. Pilot #64 verify (live read-only)
article 1002416741 · draft 18 (v3 đã apply): **0 ảnh GEARVN · 0 store 1000026716 · bảng có border · HTML sạch · image gate ALLOW** ✓.

## 9. Table style hardening
sanitize_html: table `border-collapse/width:100%/margin` + th `border 1px#ccc/padding/bg#f4f4f4` + td `border/padding` + **wrapper `<div style="overflow-x:auto">`** (responsive mobile). Verify sanitizer không strip style vừa thêm (thêm SAU whitelist loop).

## 10. UI
Apply Preview hiện **image gate store-aware**: tổng ảnh / safe / BLOCK (chết·đối thủ·unknown) / other-store / gate ALLOW|BLOCK. Apply vẫn disabled (flag OFF).

## 11. QA
- compileall OK · node --check N/A (JS inline).
- **Fixtures PASS**: Sintech store→SINTECH_OWNED · GEARVN store→COMPETITOR · hstatic no-store→UNKNOWN_EXTERNAL · sintech.vn→OWNED · intel→OFFICIAL · fptshop→COMPETITOR · genk→NEWS · invalid→INVALID. Gate: dead→BLOCK_DEAD · competitor→BLOCK_COMPETITOR · other-store→BLOCK_UNKNOWN · Sintech→ALLOW.
- Pilot #64 read-only PASS. Smoke `/seo/blog-rewrite-ai` `/status` `/drafts/18` 200.
- **PUT=0 · POST write=0 · DELETE=0 · upload=0** · live flags **OFF (khóa)** · broken-link config **nguyên (48/8/4/2s)** · secret scan sạch.

## 12. Files
- **NEW**: `blog_rewrite_images.py`, `state/blog_rewrite_config.json`, `docs/BLOG_REWRITE_IMAGE_REGRESSION_AUDIT.md` + `.csv`, doc này.
- **MOD**: `blog_rewrite_apply.py` (gate hook + delegate), `blog_rewrite_gen.py` (delegate + table wrapper), `templates/blog_rewrite_ai.html` (gate display).
- **Backup**: `_backup/blog-rewrite-p5d-image-gate-20260610-164902/`.

## 13. Deferred rollout
- Xử lý ảnh 143 bài blocked: gỡ ảnh chết/đối thủ HOẶC thay ảnh Sintech/chính hãng (workflow rehost hợp lệ cho ảnh OWNED/OFFICIAL).
- Sau khi ảnh sạch + gate ALLOW → mới apply (qua P5B-2 one-shot từng bài / batch có kiểm soát).

## OUTPUT
**BLOG REWRITE AI P5D IMAGE REGRESSION GATE COMPLETED** · root cause hstatic shared CDN → store-aware classify (Sintech 200000860097) · helper centralized `blog_rewrite_images.py` · config local no-token · availability checker · rights+gate (BLOCK dead/competitor/unknown) hardened vào apply engine · audit 147: 815 ảnh, **143 BLOCKED** (competitor 186/news 120/unknown 439/dead 12) safe 4 · pilot #64 verify 0 GEARVN + table styled · table border+responsive · fixtures PASS · PUT=0 upload=0 flags OFF · broken-link untouched · no commit/push.
