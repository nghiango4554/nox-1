# BLOG REWRITE AI — P5A APPLY PREVIEW (10/6/2026)

> Theo spec `Desktop\Past.txt`. P5A = lớp PREVIEW cho apply: image rights audit + rehost dry-run + content-hash conflict check + live payload backup design. **KHÔNG upload ảnh · KHÔNG PUT/POST/DELETE Haravan · KHÔNG sửa website · KHÔNG apply/rollback · KHÔNG commit/push/deploy.**

## 1. Haravan Article apply audit
- Read: `GET /web/blogs/{blog_id}/articles/{article_id}.json` (Open API) — OK.
- Update design: `PUT /web/blogs/{blog_id}/articles/{article_id}.json` (Open API) — verified 201 (lúc gỡ link). `/admin` 502 (không dùng). **P5A KHÔNG gọi PUT.**
- Apply field policy: **mặc định CHỈ `body_html`**. title/summary_html/tags = OFF mặc định. **KHÔNG bao giờ** PUT handle/published_at/published/author.

## 2. Upload workflow audit
| Helper | Endpoint | Scope | Loại ảnh | Inline blog phù hợp | Reuse | Rủi ro |
|---|---|---|---|---|---|---|
| `sync_collection_images.upload_asset` | `/web/themes/{theme}/assets.json` | theme | Theme asset → hstatic public_url | **chưa chứng minh** | candidate (cần verify P5B) | dùng bừa cho inline blog = sai workflow |
| `haravan_client.upload_to_asset_storage` | tạo SP-storage | product | featured/product | KHÔNG | **CẤM** (auto-create SP storage) | vi phạm rule |
| `haravan_client.add_product_image` | `/products/{id}/images.json` | product | product image | KHÔNG | KHÔNG | — |
→ **Inline blog image upload = BLOCKED_FOR_UPLOAD trong P5A.** Chỉ build interface adapter + dry-run. Theme Asset reuse cho inline blog phải chứng minh ở P5B trước khi upload thật.

## 3. Image rights policy (bắt buộc)
Phân loại từng ảnh: rights_status ∈ OWNED_SINTECH / HARAVAN_EXISTING / OFFICIAL_MANUFACTURER / LICENSED_OR_APPROVED / COMPETITOR_SOURCE / NEWS_MEDIA_SOURCE / UNKNOWN_SOURCE / MANUAL_REVIEW.
- **eligible_for_upload=True** chỉ khi OWNED/HARAVAN_EXISTING/OFFICIAL/LICENSED.
- **COMPETITOR_SOURCE / NEWS_MEDIA / UNKNOWN → KHÔNG auto rehost** (bản quyền) → action REPLACE_WITH_OFFICIAL_IMAGE / CREATE_ORIGINAL_IMAGE / MANUAL_REVIEW.
- Hotlink ảnh ≠ quyền dùng ảnh. KHÔNG tự tải+rehost ảnh đối thủ.

## 4. Pilot #64 image audit (draft v2 id 10)
6 ảnh — đều trên `file.hstatic.net` (CDN Sintech), filename còn `gearvn`:
| # | host | rights | action | eligible | planned_new_url |
|---|---|---|---|---|---|
| 1-6 | file.hstatic.net | HARAVAN_EXISTING | REHOST_ALLOWED_LATER (đổi tên bỏ gearvn) | ✅ | null (dry-run) |
→ summary: total 6 · eligible_upload 6 · blocked 0 · keep_existing 0 · manual_review 0. (Ảnh là của Sintech, chỉ cần rename filename — chưa upload.)

## 5. Dry-run rehost plan (`build_image_rehost_plan`)
Output per ảnh: original_src/hostname/filename/rights_status/recommended_action/eligible_for_upload/planned_filename (gearvn→sintech)/planned_alt/**planned_new_url=null**/status=dry_run. Lưu `image_mapping_json`. **KHÔNG tải/upload/đổi src.**

## 6. Content-hash conflict check (`apply_preview`)
Fetch live GET read-only → hash body_html live → so với original_content_hash (snapshot lúc gen). Status: SAFE_TO_APPLY / CONFLICT_LIVE_CHANGED / MISSING_LIVE_ARTICLE / READ_FAILED.
- **Pilot #64: SAFE_TO_APPLY** (hash gốc 2e980deb… == live 2e980deb…, bài chưa đổi). `apply_enabled=False` (P5A luôn OFF).

## 7. Live payload backup design (`backup_preview`)
Fetch live GET → build payload (article_id/blog_id/title/body_html/summary_html/tags/handle/published/published_at/image/updated_at/hash) → lưu `live_backup_payload_json`. **GET read-only OK, PUT KHÔNG.** Pilot: saved_local_preview, body 7189 ký tự.

## 8. UI Apply Preview (tab 8)
Tab "Apply Preview" trong Review Studio: badge **"⛔ P5A PREVIEW ONLY — CHƯA CẬP NHẬT HARAVAN"**. Nút: Kiểm tra conflict · Image dry-run plan · Backup preview local. Nút disabled: Apply Haravan / Upload ảnh / Rollback live (P5B). Checkbox field (body_html ON mặc định, còn lại disabled) — preview only. Image plan hiện rights + eligible + ⛔ ảnh đối thủ.

## 9. API P5A
- `POST /drafts/{id}/apply-preview` (conflict + image summary, apply_enabled=false)
- `POST /drafts/{id}/backup-preview` (GET live + save local)
- `GET/POST /drafts/{id}/image-plan[/refresh]` (rights + dry-run)
- Guard: `POST /drafts/{id}/apply|rollback` + `/bulk-approve` → **501** `{"phase":"P5B","error":"Live apply chưa bật..."}`.

## 10. QA
- compileall OK · node --check N/A (JS inline).
- Upload audit: featured/inline/theme/product phân biệt rõ; inline blog = BLOCKED_FOR_UPLOAD ✓.
- Image rights classification ✓ · pilot 6 ảnh HARAVAN_EXISTING · dry-run planned_url=null · **no upload** ✓.
- apply-preview live GET read-only + hash conflict (SAFE_TO_APPLY) ✓ · backup-preview local ✓.
- Guards apply/rollback/bulk **501 P5B** ✓ · **Haravan PUT=0 · POST=0 · DELETE=0 · image upload=0 · website edits=0** · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 11. Files
- **NEW**: `blog_rewrite_apply.py`, `docs/BLOG_REWRITE_AI_P5A_APPLY_PREVIEW.md`.
- **MOD**: `routes/blog_rewrite.py` (apply-preview/backup-preview + image-plan dùng rights + guard P5B), `templates/blog_rewrite_ai.html` (tab Apply Preview + image rights).
- **Backup**: `_backup/blog-rewrite-p5a-preview-20260610-160949/`.

## 12. Deferred P5B
- **Apply thật**: PUT Open API body_html (sau khi conflict SAFE + user xác nhận đủ checkbox) + ghi audit + áp dụng live_backup để rollback.
- **Image rehost THẬT**: download ảnh eligible → upload (chứng minh đúng workflow inline blog) → đổi src draft + planned_new_url. Ảnh COMPETITOR/NEWS vẫn KHÔNG rehost (cần ảnh chính hãng/tự tạo).
- Rollback live (PUT lại live_backup_payload).

## OUTPUT
**BLOG REWRITE AI P5A APPLY PREVIEW COMPLETED** · Haravan article GET ok / PUT design (Open API) / inline image upload = BLOCKED_FOR_UPLOAD / theme Asset = collection-proven chưa verify inline · pilot #64 draft 10: conflict SAFE_TO_APPLY, 6 ảnh HARAVAN_EXISTING eligible (dry-run planned_url=null), backup preview saved local · apply/rollback/bulk 501 P5B · no Haravan write / no upload / no website edit / broken-link untouched · no commit/stage/push/deploy/browser.
