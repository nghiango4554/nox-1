# BLOG REWRITE AI — P5B-1 ARMED APPLY (10/6/2026)

> Theo spec `Desktop\Past.txt`. P5B-1 = engine apply live ĐẦY ĐỦ nhưng **feature flag OFF (locked)** — KHÔNG gọi PUT thật. QA bằng monkeypatch transport. **KHÔNG apply/rollback live · KHÔNG upload/rehost ảnh · KHÔNG đổi src · KHÔNG batch · KHÔNG commit/push/deploy.**

## 1. Feature flags (mặc định OFF)
File `state/blog_rewrite_flags.json` (gitignored): `BLOG_REWRITE_LIVE_APPLY_ENABLED=false` · `LIVE_ROLLBACK_ENABLED=false` · `BULK_APPLY_ENABLED=false`. Thiếu config → mặc định false. UI hiện "LIVE APPLY: LOCKED".

## 2. Article PUT helper (`apply_draft_body_only`)
Engine đầy đủ, body-only. Transport `_put_article` / `_get_live` tách riêng để QA monkeypatch. Flow: GET fresh live → conflict check → save backup → PUT body-only → GET verify → events. **Flag OFF → trả 423 trước mọi PUT.**

## 3. Single-article guard
Reject nếu: chưa `approved_local` · article ≠ candidate · draft cũ hơn latest · confirm_phrase sai (`APPLY PILOT ARTICLE <article_id>`) · thiếu confirm_reviewed_draft/images · fields.body_html≠true · title/summary/tags=true · reverse-copy · rewrite_eligible=0. **Một article/request, không bulk.**

## 4. Body-only payload
PUT chỉ gồm `{"article":{"id":<id>,"body_html":<sanitized draft>}}`. **KHÔNG** handle/published/published_at/author/image/template_suffix/title/summary_html/tags.

## 5. Fresh conflict check NGAY TRƯỚC PUT
GET live mới nhất → hash body → so với original_content_hash. Khác → `CONFLICT_LIVE_CHANGED`, PUT BLOCKED, candidate status=conflict, event conflict_detected. Không dùng SAFE cũ làm bằng chứng.

## 6. Live backup payload (trước PUT)
`backup_preview` lưu full payload (article_id/blog_id/title/body_html/summary_html/tags/handle/published/published_at/image/updated_at/hash) → `live_backup_payload_json` + event live_backup_saved. KHÔNG log full body ra terminal.

## 7. Idempotency guard
`apply_nonce` (=draft_hash[:12]) + `applied_draft_hash`. Cùng draft_hash đã apply thành công → trả `already_applied`, **KHÔNG PUT lần 2** (chống double-click).

## 8. Post-PUT verify
GET lại → hash body live sau PUT == hash draft? → VERIFIED / VERIFY_MISMATCH / READ_AFTER_WRITE_FAILED. Mismatch → alert, KHÔNG tự PUT lại.

## 9. Rollback engine (`rollback_draft_apply`)
Body-only từ live_backup. Flag `LIVE_ROLLBACK_ENABLED` OFF → 423. Confirm `ROLLBACK PILOT ARTICLE <article_id>`. Build + monkeypatch test, KHÔNG rollback live.

## 10. Image policy
Pilot #64: 6 ảnh **giữ nguyên URL**, KHÔNG upload/rehost/đổi src/filename. Image plan vẫn hiện HARAVAN_EXISTING. KHÔNG coi HARAVAN_EXISTING = ownership proven, KHÔNG auto rehost.

## 11. API P5B-1
- `POST /drafts/{id}/apply-live` → flag OFF → **423 Locked** `{phase:P5B-1, locked:true}`.
- `POST /drafts/{id}/rollback-live` → flag OFF → **423**.
- `GET /drafts/{id}/apply-status` → flags + approval + conflict + backup + applied state.
- `POST /bulk-apply` → **501** `{locked:true, "Bulk apply chưa được hỗ trợ."}`.

## 12. UI
Tab Apply Preview thêm panel "🔒 P5B LIVE APPLY — LOCKED": apply-status (article/version/approval/eligible/reverse/backup/applied/**flags**), confirm phrase input (disabled), 2 confirm checkbox (disabled), nút Apply/Rollback/Bulk **disabled** (flag OFF). Badge "LOCKED — CHƯA CẬP NHẬT WEBSITE".

## 13. QA monkeypatch (transport mocked — 0 PUT thật)
| Test | Kết quả |
|---|---|
| flag OFF → apply-live | **423 locked** ✓ |
| guard: chưa approved / sai phrase / thiếu confirm / field title | **reject 400** ✓ |
| apply hợp lệ (mock PUT) | 200 **VERIFIED**, PUT=**1**, payload **chỉ id+body_html** (no handle/title/published/author/tags/summary/image), backup saved trước PUT ✓ |
| idempotency (apply lần 2) | **already_applied**, PUT vẫn **1** ✓ |
| conflict (live đổi) | **409 CONFLICT_LIVE_CHANGED**, PUT=**0** blocked ✓ |
| rollback (mock) + sai phrase | VERIFIED + reject 400 ✓ |
- **mock PUT count**: 1 (apply) + 1 (rollback) · **live PUT/POST/DELETE = 0** · **image upload = 0**.
- Cleanup: flags về FALSE, draft 10 → draft_ready, events test xóa.

## 14. QA tổng
- compileall OK · node --check N/A (JS inline).
- Smoke (flag OFF): apply-status 200 · apply-live **423** · rollback-live **423** · bulk-apply **501** · page 200.
- **live PUT=0 · POST=0 · DELETE=0 · upload=0 · website edits=0** · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 15. Files
- **MOD**: `blog_rewrite_apply.py` (flags + apply_draft_body_only + rollback + apply_status + idempotency cols), `routes/blog_rewrite.py` (apply-live/rollback-live/apply-status/bulk-apply), `templates/blog_rewrite_ai.html` (P5B locked panel).
- **NEW**: `state/blog_rewrite_flags.json` (flags OFF), `docs/BLOG_REWRITE_AI_P5B1_ARMED_APPLY.md`.
- **Backup**: `_backup/blog-rewrite-p5b1-armed-20260610-161920/`.

## 16. Deferred P5B-2
- **Bật flag + apply THẬT 1 pilot** (sau khi vợ duyệt): set `BLOG_REWRITE_LIVE_APPLY_ENABLED=true`, apply body-only #64, verify live, sẵn rollback.
- Image rehost thật (chứng minh workflow inline blog upload).
- Mở rộng field (title/meta) + batch apply sau pilot live PASS.

## OUTPUT
**BLOG REWRITE AI P5B-1 ARMED APPLY COMPLETED** · flags live_apply/rollback/bulk = **LOCKED (false)** · payload body-only (id+body_html, excluded handle/title/published/author/tags/summary/image) · fresh conflict GET-before-PUT blocks overwrite · backup saved before PUT · idempotency (double-submit → PUT=1) · post-PUT verify · rollback body-only · QA monkeypatch mock PUT=1 (apply)+1(rollback), **live PUT=0** · apply-live/rollback 423, bulk 501 · images preserved (no upload/rehost/src change) · broken-link untouched · no commit/stage/push/deploy/browser.
