# BLOG REWRITE AI — P5G-5 APPLY RECOVERY HARDENING + REVIEW #112 (10/6/2026)

> Harden apply state machine (crash sau PUT → reconcile bằng GET, KHÔNG re-PUT) + monkeypatch QA + review local #112. **KHÔNG PUT live · KHÔNG upload/rehost · KHÔNG apply bài mới · KHÔNG approve.** Flags live KHÓA.

## 1. Bug `after_hash` (gặp ở apply #110)
Khi apply #110, biến `after_hash` bị tham chiếu trong câu UPDATE nhưng đã xóa lúc đổi sang semantic verify (P5F) → **NameError SAU khi PUT** (PUT đã thành công, chỉ crash ở bước ghi DB). Đã fix + thêm regression test.

## 2. Apply state machine (harden)
States: `APPLY_REQUESTED` → `BACKUP_SAVED` → `PUT_SENT` → (`LIVE_VERIFIED` → `DB_RECONCILED`) | `UNCERTAIN_POST_PUT`.
- Sau PUT → record event `put_sent` (state PUT_SENT). Từ đây **TUYỆT ĐỐI KHÔNG PUT lại**.
- Verify + ghi DB bọc trong `try/except` → mọi lỗi sau PUT → gọi `reconcile_post_put` (KHÔNG re-PUT).

## 3. Helper `reconcile_post_put(draft_id, ...)`
GET live read-only → `after_hash` tính TRƯỚC khi dùng → semantic verify vs draft:
- live khớp draft → state `LIVE_VERIFIED` → ghi DB (applied_at COALESCE = idempotent) → candidate `applied` → event `post_put_reconciled` (DB_RECONCILED).
- live KHÔNG khớp / GET fail → `UNCERTAIN_POST_PUT` → event `uncertain_post_put`, KHÔNG set applied.
- Dùng được cả trong apply flow lẫn recovery thủ công sau crash. Idempotent (COALESCE applied_at, không ghi đè).

## 4. Monkeypatch QA — 6 nhóm PASS
| Test | Kết quả |
|---|---|
| 1. apply thành công | VERIFIED · state DB_RECONCILED · **PUT=1** · backup ✓ |
| 2. crash giả NGAY SAU PUT (reconcile raise) | `UNCERTAIN_POST_PUT` · **PUT=1 (KHÔNG re-PUT)** ✓ |
| 3. GET live KHỚP draft → reconcile | VERIFIED · candidate=applied · PUT=1 ✓ |
| 4. GET live KHÔNG khớp | `UNCERTAIN_POST_PUT` · PUT=1 ✓ |
| 5. double submit (idempotency) | already_applied · **PUT vẫn 1** ✓ |
| 6. flag OFF | apply 423 · rollback 423 (đều locked) ✓ |
- PUT count LUÔN = 1 · flag auto-disarm (caller finally) · backup luôn trước PUT · rollback vẫn khóa.
- Test target = #112 draft 27, **reset về chưa-apply sau QA** (applied_at=NULL, approval=ready_for_manual_approval, events QA xóa). Mock `_put_article`/`_get_live`, KHÔNG chạm Haravan thật.

## 5. Review local #112 "Cảm biến HERO là gì" (draft 27 v2)
| Mục | Giá trị |
|---|---|
| article_id | **1002411585** |
| URL live | sintech.vn/blogs/news/cam-bien-hero-la-gi-lieu-co-phu-hop... |
| latest draft | 27 v2 · approval `ready_for_manual_approval` |
| gate | **ALLOW** · conflict **SAFE_TO_APPLY** |
| brand cleanup | **PASS** (0 đối thủ; Logitech = hãng, không phải retailer đối thủ) |
| HTML safety | **PASS** · ảnh 0 · external link 0 · bảng 0 |

### Fact-check HERO
| Tiêu chí | Kết quả |
|---|---|
| HERO = cảm biến quang học Logitech, tiết kiệm điện, chính xác | ✅ đúng |
| Cơ chế điều tiết tần suất ghi hình theo chuyển động | ✅ đúng |
| "toàn dải DPI không smoothing/acceleration" | ✅ đúng (đặc tính HERO) |
| Mẫu chuột G502 HERO / G Pro Wireless / G903 Lightspeed | ✅ có thật, dùng HERO |
| Không bịa benchmark | ✅ **0 số DPI/IPS/polling cụ thể** (dùng định tính) |
| Không bịa giá | ✅ chỉ "giá cao hơn" định tính, 0 số |
| KHÔNG khẳng định mọi HERO cùng DPI/IPS/polling | ✅ dùng ngôn ngữ chung, KHÔNG claim universal |
| Ghi rõ thông số phụ thuộc phiên bản/mẫu | ⚠️ **CHƯA nêu rõ** (gap) |
| Phân biệt HERO / HERO 25K / HERO 2 | ⚠️ chỉ nói "HERO" chung, KHÔNG nhắc biến thể |

### Verdict #112: **READY_FOR_MANUAL_APPROVAL** (fact-safe) — kèm 1 khuyến nghị
- KHÔNG có lỗi facts (không bịa số, không claim sai "mọi HERO giống nhau") → đủ điều kiện fact-safe.
- **Khuyến nghị (không bắt buộc):** thêm 1 câu nêu "thông số cụ thể (DPI tối đa, IPS, polling) tùy phiên bản cảm biến HERO/HERO 25K/HERO 2 và mẫu chuột" — để chính xác hơn. Vợ quyết định thêm trước approve hay không.
- Giữ status `ready_for_manual_approval`. **KHÔNG approve, KHÔNG apply.**

## 6. QA tổng
- compileall OK · monkeypatch 6/6 PASS · PUT count=1 mọi kịch bản.
- #110 draft28 applied_at giữ nguyên (đã apply trước) · **#112 draft27 applied_at=NULL** (reset đúng, chưa apply).
- Smoke `/seo/blog-rewrite-ai` `/remediation/canary-prep` `/drafts/27/apply-status` 200.
- **PUT live=0 · upload=0 · rollback=0** · flags `live_apply/rollback/bulk = false` (khóa) · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 7. Files
- **MOD**: `blog_rewrite_apply.py` (state machine + `reconcile_post_put` + fix `after_hash`).
- **NEW**: doc này.
- **Backup**: `_backup/blog-rewrite-p5g5-recovery/blog_rewrite_apply.py`.

## OUTPUT
**BLOG REWRITE AI P5G-5 RECOVERY HARDENING + REVIEW #112 COMPLETED** · fix bug after_hash + state machine (APPLY_REQUESTED→BACKUP_SAVED→PUT_SENT→LIVE_VERIFIED→DB_RECONCILED | UNCERTAIN_POST_PUT) · `reconcile_post_put` GET read-only, KHÔNG re-PUT · monkeypatch 6/6 PASS (crash sau PUT→reconcile, PUT luôn=1, double-submit không re-PUT, flag auto-disarm, backup trước PUT, rollback khóa) · review #112 fact-safe READY_FOR_MANUAL_APPROVAL (khuyến nghị thêm note version-dependence) · PUT live=0 upload=0 flags OFF · broken-link untouched · no commit/push · **KHÔNG approve, chờ vợ duyệt #112.**
