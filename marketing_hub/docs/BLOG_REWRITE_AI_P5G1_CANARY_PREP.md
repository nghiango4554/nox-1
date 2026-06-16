# BLOG REWRITE AI — P5G-1 CANARY ROLLOUT PREP (10/6/2026)

> Chuẩn bị canary rollout (read-only). **KHÔNG PUT/apply/upload/rehost/batch · KHÔNG mở flag · KHÔNG commit/push/deploy.** Live flags KHÓA.

## 1. ⚠️ Phát hiện quan trọng (khác giả định spec)
Spec giả định 6 SAFE_NOW có draft sẵn để chọn 2 canary. **Thực tế KHÔNG đúng:**
- **6 bài SAFE_NOW (ids 21,50,55,72,71,64) đều CHƯA có draft AI** — chúng "SAFE_NOW" chỉ vì gate ALLOW ở khía cạnh ẢNH (không có ảnh blocked), NHƯNG **nội dung viết lại chưa được generate**. Không có draft → không canary được.
- Bài CÓ draft thật: chỉ 5 (#136=#64 đã apply · #7/#8/#12 BLOCK ảnh đối thủ · #26 ALLOW).
- → **Canary-ready pool = 1 bài (#26)**, KHÔNG đủ 2.

## 2. Audit candidate có draft
| Candidate | Draft | Gate | Img | Approval | Applied | Title |
|---|---|---|---|---|---|---|
| #136 (#64) | v3 | ALLOW | 0 | approved_local | **YES** (pilot live) | Clicky/Linear/Tactile |
| #7 | v4 | BLOCK_UNKNOWN_IMAGE | 7 | draft_ready | no | Sửa máy quận 6 |
| #8 | v3 | BLOCK_COMPETITOR_IMAGE | 9 | draft_ready | no | Top 10 sai lầm build PC |
| #12 | v2 | BLOCK_COMPETITOR_IMAGE | 3 | draft_ready | no | Keo tản nhiệt kim loại lỏng |
| **#26** | **v1** | **ALLOW** | 1 | review_required | no | So sánh 3 VGA |

## 3. Canary-ready (1 bài)
**#26 — So sánh 3 VGA tầm giá 5-7 triệu** (article 1002431xxx, draft 12 v1):
- gate **ALLOW** · conflict **SAFE_TO_APPLY** · 1 ảnh **SINTECH_OWNED** (store 200000860097, reachable) · brand text/alt **SẠCH** · HTML **sạch** · 1 bảng · 0 internal link · traffic 0 clicks / 1 GA4 session.
- ⚠️ **overlap 18.9% (review_required)** — bản viết lại gần paraphrase (bài so sánh spec VGA tự nhiên trùng tên/thông số nhiều). **Cần editor review hoặc regenerate để hạ overlap trước khi approve+apply.**

## 4. Fresh read-only preflight #26
conflict SAFE_TO_APPLY · image_gate apply_allowed=True (0 blocked) · approved_local=False · apply_enabled=False (flag khóa) · body-only eligible (sau khi approved).

## 5. Kết luận / khuyến nghị
- **KHÔNG đủ 2 canary.** Pool thật = #26 (cần hạ overlap trước).
- Để rollout chuẩn 2 canary: **(a)** generate draft AI cho 2-3 bài SAFE_NOW sạch ảnh (DLSS/Microsoft Win/Nvidia/Valorant/Elden Ring/Dota2 — chỉ cần gen nội dung, gate ảnh đã ALLOW) → **(b)** preflight → chọn 2 bài approved_local overlap thấp; **HOẶC** review/regenerate #26.
- #64 vẫn là pilot live PASS (proven). KHÔNG apply gì lượt này.

## 6. UI
Section "🚀 Canary rollout (prep)": badge "PREP ONLY — Apply khóa", hiện safe_now/no-draft/canary-ready + bảng #26 (gate/conflict/approval/overlap) + checklist thủ công 6 mục + nút Review. KHÔNG nút apply/batch.

## 7. Export
`docs/BLOG_REWRITE_CANARY_ROLLOUT_PREP.md` + `.csv` (1 canary-ready + manual notes).

## 8. QA
- compileall OK · node --check N/A (JS inline).
- canary-prep quét đúng (drafted+ALLOW+chưa apply, bắt #26) · 6 SAFE_NOW no-draft báo rõ.
- Smoke `/seo/blog-rewrite-ai` `/remediation/canary-prep` `/remediation/top20` 200.
- **PUT=0 · POST write=0 · DELETE=0 · upload=0** · live flags **OFF (khóa)** · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 9. Files
- **NEW**: `docs/BLOG_REWRITE_CANARY_ROLLOUT_PREP.md` + `.csv`, doc này.
- **MOD**: `blog_rewrite_remediate.py` (canary_prep), `routes/blog_rewrite.py` (canary-prep endpoint), `templates/blog_rewrite_ai.html` (canary panel).
- **Backup**: `_backup/blog-rewrite-p5g1-canary-20260610-172249/`.

## 10. Deferred
- Generate draft AI cho bài SAFE_NOW (mở canary pool thật).
- Review/regenerate #26 (hạ overlap) → approve_local → canary.
- Live apply canary (qua P5B one-shot, cần vợ xác nhận trực tiếp từng bài).

## OUTPUT
**BLOG REWRITE AI P5G-1 CANARY PREP COMPLETED** · safe_now 6 (6 KHÔNG có draft) · canary-ready **1 bài (#26)** không đủ 2 · #26 gate ALLOW + conflict SAFE + image clean nhưng overlap 18.9% review_required → cần review/regenerate · UI canary panel + checklist · export MD/CSV · PUT=0 upload=0 flags OFF · broken-link untouched · no commit/push. **Khuyến nghị: generate draft cho SAFE_NOW hoặc review #26 trước khi canary.**
