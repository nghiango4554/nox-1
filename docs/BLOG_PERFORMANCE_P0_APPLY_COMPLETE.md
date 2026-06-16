# BLOG PERFORMANCE — P0 QUICKWIN APPLY COMPLETE

> P9.1 — apply LIVE body_html cho bài P0 AUTO_SAFE preview-ready. Body-only · 1 PUT/bài · backup + verify + reconcile · rollback manual.

## Coverage
- eligible **5** · applied **5** · applied_reconciled **0** · skipped **0** · conflict **0** · failed **0**
- PUT count **5** · verify pass **5** · CB closed

## Bài đã xử lý
| P0# | article | apply_state | verify | http | PUT | backup |
|---|---|---|---|---|---|---|
| 2 | 1002794878 | LIVE_VERIFIED | VERIFIED | 201 | 1 | ✓ |
| 3 | 1002753568 | LIVE_VERIFIED | VERIFIED | 201 | 1 | ✓ |
| 4 | 1002398567 | LIVE_VERIFIED | VERIFIED | 201 | 1 | ✓ |
| 6 | 1002404456 | LIVE_VERIFIED | VERIFIED | 201 | 1 | ✓ |
| 10 | 1002792621 | LIVE_VERIFIED | VERIFIED | 201 | 1 | ✓ |

## Excluded
- blocked image: [7] (vd #7 GTA5 — ảnh đối thủ)
- theme-only: [1, 8, 9]
- manual-review: [5]

## Lưu ý kỹ thuật (verify live)
- ✅ **Sống trên live:** clean HTML legacy + table responsive (`overflow-x` wrapper) — win CLS chính cho bài nhiều bảng.
- ⚠️ **Haravan STRIP** attr `loading="lazy"` + `fetchpriority` của `<img>` khi PUT (whitelist body) → phần lazy-load/LCP-hint KHÔNG sống ở mức bài. Đây đúng là việc của THEME (BLOG_TEMPLATE_CODE_HANDOFF #4 lazy mặc định, #3 fetchpriority hero, #5 width/height). Đã verify draft local có đủ lazy nhưng live bị gỡ.
- verify VERIFIED do canonical signature so text/ảnh/cấu trúc (bỏ qua attr) → apply đúng nội dung.

## Safety
- body_html only · no title/handle/summary/tags/author/featured change
- upload = 0 · rehost = 0 · theme edits = 0 · no commit/push/deploy
- CB: closed

## Backups
- path: `state/backups/p0_quickwin_apply/20260614-130744/`

## Exports
- BLOG_PERFORMANCE_P0_APPLY_COMPLETE.md
- blog_performance_p0_apply_items.csv
- blog_performance_p0_apply_skipped.csv
- blog_performance_p0_apply_backups.csv