# BLOG REWRITE AI — P5B-2 SINGLE LIVE APPLY (10/6/2026)

> Apply LIVE thật đúng 1 bài pilot #64 (draft id 10), body_html only, theo xác nhận trực tiếp của vợ. One-shot flag tự khóa sau attempt. **KHÔNG batch · KHÔNG upload/rehost ảnh · KHÔNG đổi field khác · KHÔNG commit/push/deploy.**

## 1. Pilot identity
- candidate #64 (id 136) · draft id **10** (v2) · article_id **1002416741** · blog_id 1000906526.
- URL live: `https://sintech.vn/blogs/news/cach-phan-biet-clicky-linear-va-tactile-switch-chinh-xac-nhat`

## 2. Preflight
draft 10 ✓ · approved_local ✓ (khôi phục — QA cleanup P5B-1 đã reset) · rewrite_eligible 1 ✓ · reverse_copy 0 ✓ · latest=10 ✓ · image draft 6 / original 6 ✓ · image src unchanged ✓ · brand text/alt PASS ✓ · competitor href 0 ✓ · apply_preview **SAFE_TO_APPLY** ✓.

## 3. One-shot flag
Arm `live_apply=true` (rollback=false, bulk=false) → event `live_apply_armed_one_shot`. Sau attempt **tự reset `live_apply=false`** (finally, bất kể kết quả) → event `live_apply_auto_disarmed`. Xác nhận flag sau: tất cả **false**.

## 4. Fresh conflict check (ngay trước PUT)
GET live → hash body == original_content_hash (2e980deb…) → **SAFE_TO_APPLY**. (Engine block nếu khác.)

## 5. Backup live payload
Lưu đầy đủ vào `live_backup_payload_json` TRƯỚC PUT (article_id/blog_id/title/body_html/summary_html/tags/handle/published/published_at/image/updated_at/hash). Event `live_backup_saved`. **Backup hash 2e980deb… (bản gốc trước khi ghi đè) — rollback được.**

## 6. PUT (đúng 1 lần)
- Payload: `{"article":{"id":1002416741,"body_html":<draft sanitized>}}` — **CHỈ id + body_html**.
- **PUT count = 1** · `PUT /web/blogs/1000906526/articles/1002416741.json` · **HTTP 201**.
- Không retry tự động, không PUT lần 2.

## 7. Verify GET (sau PUT)
- hash trước `2e980deb…` → sau `9bd60f97…` (body đã đổi = PUT có hiệu lực).
- `verify_status = VERIFY_MISMATCH` (hash draft ≠ hash live). **ĐÃ ĐIỀU TRA = BENIGN (Haravan normalize HTML khi lưu):**
  - body **text thuần live == draft** (4202 == 4202 ký tự, giống hệt).
  - cấu trúc trùng khít: h2=8, h3=4, p=15, **img=6**, không mất đoạn.
  - → mismatch chỉ do Haravan re-encode whitespace/entity khi save, KHÔNG mất nội dung.
- Theo spec mismatch: **KHÔNG tự PUT lại, KHÔNG tự rollback, giữ backup** ✓. Event `apply_verify_failed` (kỹ thuật) — nhưng nội dung thực tế đúng.
- candidate status = `applied` · draft applied_at set.

## 8. Field unchanged audit
| Field | Unchanged |
|---|---|
| title | ✅ |
| handle | ✅ |
| summary_html | ✅ |
| published | ✅ |
| published_at | ✅ |
| author | ✅ |
| featured image | ✅ |
| tags | ✅ (None→'' chỉ khác biểu diễn, không có tag) |
| **6 URL ảnh inline** | ✅ giữ nguyên (file.hstatic.net, alt đã sạch) |

## 9. Post-apply smoke (GET read-only)
- HTML parse OK · đủ **6 ảnh inline** · brand text/alt **SẠCH** · không `<script>`/`javascript:`/event handler/`<iframe>` · URL bài live KHÔNG đổi.

## 10. Final status
- **APPLIED LIVE thành công.** Bài #64 trên sintech.vn nay là bản viết lại nguyên bản (overlap 2%, sạch GEARVN), giữ nguyên 6 ảnh + mọi field khác.
- verify_status kỹ thuật = VERIFY_MISMATCH nhưng **đã xác minh nội dung đúng 100%** (Haravan normalization).

## 11. Flags / Rollback
- `live_apply` **auto-disarmed = false** ✓ · `live_rollback` = **false (vẫn khóa)** · `bulk_apply` = false.
- **Rollback available**: backup payload đã lưu (`live_backup_payload_json`), hash 2e980deb…. Muốn hoàn tác: bật `LIVE_ROLLBACK_ENABLED` + confirm "ROLLBACK PILOT ARTICLE 1002416741" (chưa làm, chờ vợ).

## 12. Safety
one article only · body_html only · PUT count=1 · no second PUT · no auto rollback · no upload/rehost ảnh · no src/filename change · no batch · broken-link config **nguyên (48/8/4/2s)** · no commit/stage/push/deploy/browser.

## OUTPUT
**BLOG REWRITE AI P5B-2 SINGLE LIVE APPLY COMPLETED** · #64 draft 10 → article 1002416741 LIVE · PUT=1 HTTP 201 · hash 2e980deb→9bd60f97 · verify_status MISMATCH nhưng nội dung BENIGN (text + 6 ảnh + cấu trúc giống hệt, Haravan normalize) · fields title/handle/summary/published/published_at/author/image/tags KHÔNG đổi · 6 ảnh inline giữ nguyên · HTML sạch · backup saved (rollback-able) · live_apply auto-disarmed, rollback vẫn khóa · no upload/rehost/batch · no commit/push.
