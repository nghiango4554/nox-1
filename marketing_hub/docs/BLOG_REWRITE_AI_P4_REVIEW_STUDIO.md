# BLOG REWRITE AI — P4 REVIEW STUDIO (10/6/2026)

> Theo spec `Desktop\Past.txt`. P3.1 editorial validation pilot + P4 Review Studio local. **KHÔNG batch · KHÔNG Haravan PUT · KHÔNG apply · KHÔNG upload/rehost ảnh · KHÔNG commit/push/deploy.**

## 1. P3.1 — Editorial validation pilot (draft v1 → fix → v2)

**Draft v1 (id 9) FAIL:** IMAGES_DROPPED — bài gốc 6 ảnh (hstatic CDN, alt="GEARVN-...") → draft 0 ảnh. (Các tiêu chí khác PASS: brand text sạch, HTML sạch, headings/table giữ, overlap 1.7%.)

**Fix an toàn (prompt + gen, KHÔNG xóa v1):**
- Prompt V1: thêm rule GIỮ ảnh Sintech CDN (dùng đúng src), chèn rải sau H2, viết lại alt tiếng Việt bỏ tên thương hiệu nguồn.
- `extract_images` (chỉ ảnh hstatic) → đưa vào prompt; `_reinsert_images` deterministic nếu AI vẫn rơi ảnh; `_clean_alt` xóa brand trong alt; tách brand-in-visible (fail thật) vs brand-in-src-filename (chỉ flag rehost P4).

**Draft v2 (id 10) PASS:**
| Tiêu chí | Kết quả |
|---|---|
| word count | 1011 → ~1180 (117%) |
| h2/h3/table | 4→9 / 6→6 / 1→1 (giữ) |
| **images** | **6 → 6 IMAGES_PRESERVED** ✓ |
| 5-gram overlap | **2.0%** · originality HIGH |
| brand cleanup (text+alt) | **PASS** (alt = mô tả tiếng Việt) |
| brand in src filename | gearvn (6) → flag REHOST image plan, KHÔNG chặn |
| internal/external link | 0/0 (gốc không có) |
| HTML safety | sạch |
| approval | **draft_ready** |
→ **P3.1 ACCEPTANCE = PASS** → build P4. (v1 giữ nguyên, versions [v1=9, v2=10].)

## 2. P4 Review Studio — `/seo/blog-rewrite-ai` (detail drawer 7 tab)
Tabs: **Tổng quan · Bài gốc · Draft AI · So sánh · Quality · Link & ảnh · Lịch sử**.
- **Bài gốc**: preview HTML live, badge "Chỉ đọc".
- **Draft AI**: editor textarea (title/summary/body) + title/meta options + outline + nút Lưu local / Regenerate single / Tạo version / Approve local / Reject local. Watermark **"DRAFT LOCAL — CHƯA APPLY HARAVAN"**, Apply disabled (P5).
- **So sánh**: side-by-side gốc↔draft + overlap/longest-phrase/heading.
- **Quality**: scorecard (originality/images/brand_cleanup/manual_verify) + metrics.
- **Link & ảnh**: image plan dry-run table (host/loại/brand/action) + refresh.
- **Lịch sử**: versions + events timeline.

## 3. API P4 (local — KHÔNG PUT)
- `PATCH /drafts/{id}` (edit local → re-sanitize + recompute quality + event draft_edited_local)
- `GET /candidates/{id}/drafts` · `POST /drafts/{id}/clone-version` · `POST /candidates/{id}/regenerate-single` (explicit_confirm, 1 bài, provider thật)
- `POST /drafts/{id}/approve-local` (approval_status=approved_local, candidate status, event — KHÔNG Haravan) · `POST /drafts/{id}/reject-local`
- `GET /drafts/{id}/image-plan` · `POST /drafts/{id}/image-plan/refresh` (dry-run: original_src/host/is_haravan/is_external/contains_competitor_brand/recommended_action ∈ KEEP_HARAVAN_CDN|REHOST_EXTERNAL_LATER|REMOVE_COMPETITOR_BRAND_ALT|MANUAL_REVIEW/planned_new_url=null/status=pending_review)

## 4. Apply guard
`POST /drafts/{id}/apply|rollback` + `/bulk-approve` → **501** `{"ok":false,"phase":"P5","error":"Apply Haravan chưa bật. Không có thay đổi nào được gửi lên website."}`.

## 5. Migration
KHÔNG cần migration mới — reuse field hiện có (approval_status cho approved_local/rejected_local, image_mapping_json cho image plan, candidate.status). Additive cũ (audit_*, rewrite_eligible...) giữ nguyên.

## 6. QA
- compileall OK · node --check N/A (JS inline Jinja).
- P3.1: identity/length/image/link/fact/brand/html/editorial audit ✓ · acceptance PASS sau regenerate v2.
- P4 UI: 7 tab render ✓ · editor ✓.
- Local edit (PATCH title): ok + re-sanitize + recompute ✓. Version: list/clone ✓. Regenerate-single: explicit_confirm + 1 bài ✓.
- Approve/reject local: ok, KHÔNG Haravan ✓. Image plan refresh: 6 ảnh, action REMOVE_COMPETITOR_BRAND_ALT, no download/upload ✓.
- Guard: apply/rollback/bulk-approve **501** ✓ · **Haravan PUT KHÔNG gọi** · **image upload KHÔNG gọi** · broken-link config **nguyên (48/8/4/2s)** · secret scan sạch.
- Data test đã revert (draft 10 title + approval về draft_ready).

## 7. Files
- **MOD**: `blog_rewrite_gen.py` (giữ ảnh + clean alt + brand split), `blog_rewrite.py` (edit/clone/approve/reject/image_plan), `routes/blog_rewrite.py` (8 endpoint P4 + message guard), `templates/blog_rewrite_ai.html` (Review Studio 7 tab).
- **NEW**: `docs/BLOG_REWRITE_AI_P4_REVIEW_STUDIO.md`.
- **Backup**: `_backup/blog-rewrite-p4-review-20260610-150640/` (P3 backup chứa bản trước) + sửa trong phiên này.

## 8. Deferred P5
- Apply Haravan: conflict check content_hash + fetch live mới + backup payload + PUT Open API + rollback per-bài.
- Image rehost THẬT: download ảnh external/brand-filename → upload_asset → đổi src draft (hiện chỉ image plan dry-run).
- Batch generate (5/10) sau khi pilot review PASS.

## OUTPUT
**BLOG REWRITE AI P4 REVIEW STUDIO COMPLETED** · P3.1 pilot #64 v2 PASS (images preserved 6/6, overlap 2%, originality high, brand cleanup PASS) · 7-tab review studio + local edit/version/regenerate/approve-reject + image plan dry-run · apply guard 501 · no Haravan PUT / no upload / no batch / broken-link untouched · no commit/stage/push/deploy/browser.
