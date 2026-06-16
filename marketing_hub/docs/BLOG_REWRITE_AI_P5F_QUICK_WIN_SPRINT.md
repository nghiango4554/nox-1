# BLOG REWRITE AI — P5F QUICK-WIN SPRINT (10/6/2026)

> Sprint quick-win LOCAL: canonical verify + gỡ ảnh chết + phân nhóm remediation + quick-win score + top20. **KHÔNG apply/upload/rehost/PUT · KHÔNG sửa website · KHÔNG commit/push/deploy.** Live flags KHÓA.

## 1. Canonical HTML verify hardening — `blog_rewrite_verify.py` (mới)
`canonicalize_article_html` · `build_article_verify_signature` (raw/canonical/plain-text hash + structure + image_src/link_href/heading hash + html_safety) · `compare_article_signatures`.
Taxonomy: **VERIFIED_RAW · VERIFIED_CANONICAL · VERIFIED_SEMANTIC_WITH_NORMALIZATION · VERIFY_MISMATCH_REAL · VERIFY_READ_FAILED**.
→ Fix vụ P5B-2 (Haravan normalize whitespace/entity làm raw hash lệch nhưng nội dung giống) — giờ semantic giống → KHÔNG gọi mismatch giả. **Đã hook vào apply engine** (post-PUT verify) + endpoint verify-live.
Fixtures PASS: raw giống→VERIFIED_RAW · normalize→VERIFIED_CANONICAL · đổi thật→VERIFY_MISMATCH_REAL.

## 2-5. Bulk remove dead local + clone + gate recompute
`bulk_remove_dead_and_clone` (chỉ DEAD_404/410/INVALID, KHÔNG đụng uncertain/competitor/news/unknown): dead_marked 13 · candidates_affected 8 · new_draft_versions 2 (đa số đã có remediated draft từ P5E) · newly_safe 0 · still_blocked 2 (bài có ảnh chết cũng có competitor/unknown → gỡ dead chưa đủ). Clone version mới, không overwrite, event dead_image_removed_local.

## 6-7. Remediation groups + quick-win score
Per-candidate summary (counts theo source/availability + gate + group + score + next_action). Groups (145 bài):
| Group | Số bài |
|---|---|
| SAFE_NOW (gate ALLOW) | **6** |
| LOW_COMPLEXITY_REVIEW | 31 |
| REPLACEMENT_NEEDED (competitor/news) | 37 |
| UNKNOWN_HEAVY (unknown ≥3 hoặc >50%) | **69** |
| MANUAL_COMPLEX | 2 |
| DEAD_ONLY_CLEANUP | 0 (đã gỡ) |

Quick-win score (minh bạch): traffic log-scaled + bonus (ALLOW +100, dead-only +70, ≤1 blocked +40, draft sẵn +20) − penalty (unknown −8/ảnh, competitor −6, news −5, other-store −6, uncertain −3, manual_complex −40).

## 8-9. Top 20 export
`docs/BLOG_REWRITE_QUICK_WIN_TOP20.md` + `blog_rewrite_quick_win_top20.csv`. Sort: SAFE_NOW→DEAD_ONLY→LOW_COMPLEXITY→... rồi score. Top = 6 bài SAFE_NOW (DLSS/Microsoft Win/Nvidia RTX3060/Valorant/Elden Ring/Dota2 — gate ALLOW, sẵn sàng review+apply).

## 10. Pilot #64 read-only verify
draft 18 / article 1002416741: **VERIFIED_RAW** (live khớp draft) · live img **0** · table 1 styled · gate **ALLOW** · HTML sạch. KHÔNG PUT.

## 11. Local pilots (3 ca)
- dead-only: bulk remove → clone draft → gate recompute (nếu hết block → ALLOW).
- competitor: KHÔNG auto remove → vẫn BLOCK_COMPETITOR_IMAGE.
- unknown-heavy: KHÔNG auto remove → vẫn BLOCK_UNKNOWN_IMAGE.

## 12. UI
Section "⚡ Bài dễ xử lý trước": KPI 6 group + top20 table (group/gate/score/dead-comp-news-unknown + nút review). Section "🖼️ Xử lý ảnh" (P5E) giữ nguyên. KHÔNG nút apply live.

## 13. API
`GET /remediation/articles` · `/remediation/articles/{cid}` · `/remediation/top20` · `POST /remediation/remove-dead-local` · `POST /remediation/articles/{cid}/recompute-gate` · `POST /drafts/{id}/verify-live` · `GET /drafts/{id}/verify-status`. KHÔNG live write.

## 14. QA
- compileall OK · node --check N/A (JS inline).
- canonical/semantic verify fixtures PASS · remove dead local only (uncertain/competitor/news/unknown KHÔNG auto remove) · draft clone + old preserved · quality/gate recompute · article summary · quick-win score · top20 export ✓.
- Pilot #64 verify-live VERIFIED_RAW read-only.
- Smoke `/seo/blog-rewrite-ai` `/remediation/articles` `/remediation/top20` `/drafts/18/verify-status` 200.
- **PUT=0 · POST write=0 · DELETE=0 · upload=0** · live flags **OFF (khóa)** · broken-link config **nguyên (48/8/4/2s)** · secret sạch.

## 15. Files
- **NEW**: `blog_rewrite_verify.py`, `docs/BLOG_REWRITE_QUICK_WIN_TOP20.md` + `.csv`, doc này.
- **MOD**: `blog_rewrite_apply.py` (semantic verify hook + verify_live/status), `blog_rewrite_remediate.py` (article summary/groups/score/top20/bulk-clone), `routes/blog_rewrite.py` (7 endpoint), `templates/blog_rewrite_ai.html` (quick-win board).
- **Backup**: `_backup/blog-rewrite-p5f-quickwins-20260610-171423/`.

## 16. Deferred
- **Image replacement workflow**: thay ảnh competitor (186)/news (120)/unknown (439) bằng ảnh Sintech/chính hãng — blocker chính (69 bài UNKNOWN_HEAVY + 37 REPLACEMENT_NEEDED).
- **Live rollout**: 6 bài SAFE_NOW có thể review + apply (qua P5B one-shot) sau khi vợ duyệt.

## OUTPUT
**BLOG REWRITE AI P5F QUICK-WIN SPRINT COMPLETED** · canonical/semantic verify (fix mismatch giả, hook vào engine) · bulk dead removed 13/8 bài · groups: SAFE_NOW 6 / LOW_COMPLEXITY 31 / REPLACEMENT 37 / UNKNOWN_HEAVY 69 / MANUAL 2 · quick-win score + top20 export · pilot #64 VERIFIED_RAW gate ALLOW · UI quick-win board · PUT=0 upload=0 flags OFF · broken-link untouched · no commit/push.
