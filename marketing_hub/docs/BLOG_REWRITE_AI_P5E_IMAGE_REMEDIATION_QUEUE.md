# BLOG REWRITE AI — P5E IMAGE REMEDIATION QUEUE (10/6/2026)

> Hàng đợi xử lý ảnh LOCAL trước khi apply. **KHÔNG upload/rehost/tải hàng loạt · KHÔNG PUT/POST/DELETE Haravan · KHÔNG apply/rollback live · KHÔNG auto remove competitor/news/unknown · KHÔNG commit/push/deploy.** Live flags giữ KHÓA.

## 1. P5D → P5E
P5D audit 147 bài = 815 ảnh, 143 blocked. P5E biến audit thành **queue xử lý local**: import vào DB, per-image action, tạo draft sạch local.

## 2. Data model (additive, idempotent)
Bảng `blog_rewrite_image_items` (UNIQUE candidate_id+original_src) + 5 index. Fields tách rõ **source_class** vs **availability_status** (không trộn). Migrate idempotent (x2 OK). Import từ audit CSV: 815 inserted, rerun 0 inserted/815 updated (idempotent, giữ selected_action nếu đã reviewed).

## 3. Source vs Availability (tách)
- source_class: SINTECH_OWNED · HARAVAN_OTHER_STORE · OFFICIAL_MANUFACTURER · COMPETITOR_SOURCE · NEWS_MEDIA_SOURCE · UNKNOWN_EXTERNAL · INVALID_URL.
- availability_status: REACHABLE · DEAD_404 · DEAD_410 · UNCERTAIN_TIMEOUT · UNCERTAIN_403 · UNCERTAIN_429 · UNCERTAIN_5XX · INVALID · NOT_CHECKED.

## 4. Action policy (default)
- SINTECH_OWNED+REACHABLE → **KEEP** · DEAD_404/410/INVALID → **REMOVE_DEAD_IMAGE** · OFFICIAL → MANUAL_REVIEW.
- COMPETITOR/NEWS/UNKNOWN/HARAVAN_OTHER_STORE → **MANUAL_REVIEW** (KHÔNG auto remove). Chỉ dead/invalid mới default remove local.

## 5. Counts (sau import + bulk dead)
815 ảnh / 145 bài · **safe 6 · blocked 139** · dead 12 · uncertain 28.
by_source: UNKNOWN_EXTERNAL 439 · COMPETITOR 186 · NEWS 120 · SINTECH 54 · OTHER_STORE 13 · OFFICIAL 2 · INVALID 1.
→ **Gỡ ảnh chết KHÔNG đủ unblock**: 139 bài vẫn blocked do còn ảnh đối thủ/news/unknown cần quyết (gỡ/thay).

## 6. UI Remediation Dashboard
Section "🖼️ Xử lý ảnh bài viết" (`/seo/blog-rewrite-ai`): KPI (tổng/safe/blocked/dead/uncertain + by-source) + filter (source/availability/search) + table per-image với **dropdown selected_action** + nút "🗑️ Gỡ hết ảnh chết (local)" + "📤 Export workload". Badge local-only, không nút upload/apply.

## 7. Local cleanup — `build_remediated_draft_local`
Gỡ ảnh có action REMOVE_DEAD/REMOVE_FROM_DRAFT (+ wrapper rỗng) → sanitize (table border + responsive) → recompute quality + gate → **clone version mới (không overwrite)** → event image_remediation_draft_created. Pending (competitor/news/unknown/manual) → giữ blocked. KHÔNG download/upload/PUT.

## 8. Bulk dead local
Confirm phrase **"REMOVE DEAD IMAGES FROM LOCAL DRAFTS"** → mark all DEAD/INVALID → REMOVE_DEAD_IMAGE (local). KHÔNG bulk cho competitor/news/unknown/other-store (phải review). Test: sai phrase reject, đúng phrase marked 13.

## 9. Article-level gate
`article_gate(candidate_id)` → ALLOW chỉ khi không còn ảnh blocked + không pending manual review. Block codes: BLOCK_DEAD/COMPETITOR/NEWS/UNKNOWN/OTHER_STORE/REVIEW_REQUIRED.

## 10. Export workload
`docs/BLOG_REWRITE_IMAGE_REMEDIATION_WORKLOAD.md` + `.csv` (815 rows: candidate/article/src/source/availability/rights/action/gate).

## 11. Pilot local (3 ca)
- **dead** (#7): remediate → gỡ 1 ảnh chết → draft v3 (id 19, old v2 giữ nguyên), gate vẫn BLOCK_UNKNOWN (còn 6 ảnh pending) ✓ — đúng: gỡ dead chưa đủ.
- **competitor** (#8): gate BLOCK_COMPETITOR_IMAGE (không auto remove) ✓.
- **unknown** (#7): BLOCK_UNKNOWN_IMAGE ✓.

## 12. QA
- compileall OK · node --check N/A (JS inline).
- Migration idempotent · import idempotent · source/availability tách ✓.
- dead default remove · competitor/news/unknown KHÔNG auto remove · Sintech KEEP ✓.
- Local cleanup clone version + old preserved + quality/gate recompute ✓ · bulk dead confirm ✓ · export ✓.
- Smoke `/seo/blog-rewrite-ai` `/image-summary` `/image-items` `/image-gate` 200.
- **upload=0 · PUT=0 · POST write=0 · DELETE=0** · apply/rollback live **khóa** · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 13. Files
- **NEW**: `blog_rewrite_remediate.py`, `docs/BLOG_REWRITE_IMAGE_REMEDIATION_WORKLOAD.md` + `.csv`, doc này.
- **MOD**: `routes/blog_rewrite.py` (7 endpoint remediation), `templates/blog_rewrite_ai.html` (dashboard section).
- **Backup**: `_backup/blog-rewrite-p5e-image-queue-20260610-170605/`.

## 14. Deferred
- **Image replacement thật**: thay ảnh competitor/news/unknown bằng ảnh Sintech/chính hãng (cần workflow upload hợp lệ + nguồn ảnh) — chưa làm.
- **Rollout**: sau khi từng bài xử lý ảnh xong (gate ALLOW) → apply qua P5B one-shot / batch có kiểm soát.

## OUTPUT
**BLOG REWRITE AI P5E IMAGE REMEDIATION QUEUE COMPLETED** · data model blog_rewrite_image_items (additive, idempotent, 815 imported) · source/availability tách · action policy (dead→remove local, competitor/news/unknown→manual review, sintech→keep) · UI dashboard + per-image action + bulk-dead confirm + export · build_remediated_draft_local (clone version, gỡ dead, recompute gate) · pilot local 3 ca PASS · upload=0 PUT=0 apply locked · broken-link untouched · no commit/push.
