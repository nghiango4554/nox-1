# P7.3 — EVERGREEN-FIRST THROUGHPUT SELECTOR (BUILD)

> Theo spec `Desktop/Past.txt`. **BUILD-ONLY: KHÔNG chạy Full Auto live lượt này.** Dừng sau report.
> **CHƯA COMMIT.** live PUT trong QA = 0, upload = 0, scheduler = absent. Ngày 2026-06-11.

## Mục tiêu
Run 41 (smoke 3) PASS safety nhưng selector ưu tiên sai loại bài (game-config/news → 0 applied).
P7.3 chia queue 2 lane để Full Auto chạy **thuần tự động toàn queue, không duyệt tay, không scheduler**:
- **AUTO_LANE** — evergreen / how-to / concept / troubleshooting text-first → xử lý + sync trước.
- **DEFER_LANE** — news / launch / driver / giá / benchmark / FPS / game-config-FPS / visual tutorial →
  HOLD/BLOCKED, ghi status sau, KHÔNG chiếm slot đầu, KHÔNG generate (tiết kiệm cost).

## Phân lane hiện tại (toàn queue 141 bài)
| Lane | Count |
|---|---|
| **AUTO_LANE** | **50** |
| **DEFER_LANE** | **91** |
| → HOLD_TIME_SENSITIVE (news/launch/giá/driver) | 22 |
| → HOLD_UNSUPPORTED (benchmark/FPS/game-config) | 14 |
| → BLOCKED_IMAGE (visual/tutorial/screenshot) | 1 |
| → MANUAL_COMPLEX (không rõ evergreen) | 54 |

Guard: **0 bài news/launch lọt AUTO_LANE**. 3 bài run-41 picks sai giờ route đúng:
#11 GTA5 → HOLD_UNSUPPORTED · #77 ZZZ → HOLD_UNSUPPORTED · #220 Miku → HOLD_TIME_SENSITIVE ·
#149 watermark → BLOCKED_IMAGE.

## Selector rule (`classify_lane` theo title, trước generate)
- **DEFER ưu tiên bắt** (theo thứ tự): visual (`bước 1/2`, `như hình`, `screenshot`, `photoshop`,
  `watermark`...) → BLOCKED_IMAGE · benchmark/FPS/game-config (`fps`, `benchmark`, `cấu hình chơi`,
  `build pc chơi`...) → HOLD_UNSUPPORTED · news/launch/driver/giá (`ra mắt`, `rò rỉ`, `khai tử`,
  `driver`, `giá rẻ`, `khuyến mãi`...) → HOLD_TIME_SENSITIVE.
- **AUTO** nếu có tín hiệu evergreen (`là gì`, `cách`, `phân biệt`, `khắc phục`, `sửa lỗi`, `mẹo`,
  `tổng hợp`, `kiến thức`, `hướng dẫn`...) VÀ không tín hiệu DEFER.
- Ambiguous → **MANUAL_COMPLEX** (DEFER, xử lý sau).
- **Sort AUTO_LANE**: GSC clicks 28d ↓ → GA4 sessions ↓ → priority_score ↓ (traffic tốt ưu tiên).
- `build_lanes()` trả `(auto_lane, defer_lane)`, run xử lý **AUTO trước, DEFER sau**.

## Quality borderline rule (section 4)
- score ≥ 80 → PASS.
- **75–79 → auto-fix + regenerate tối đa 2 lần tổng cộng + full recompute** → vẫn <80 → **HOLD_QUALITY**.
- < 75 → **HOLD_QUALITY** ngay sau max regen.
- **KHÔNG hạ threshold 80, KHÔNG publish bài borderline.** thin-content (<150 từ) → **MANUAL_REVIEW**.

## Pipeline AUTO_LANE (giữ nguyên P7.2 apply, serial 1 PUT)
SELECT → GENERATE → SELF_REVIEW P1 → AUTO_FIX → SELF_REVIEW P2 → FULL_RECOMPUTE QUALITY → IMAGE GATE →
FACT GATE → CONFLICT → BACKUP → PUT body_html only (1 lần) → GET verify → canonical+semantic →
reconcile DB → checkpoint → next. Rule 500-but-write (P7.2) nguyên vẹn: PUT 5xx/timeout/exception →
UNCERTAIN → GET live → live==draft APPLIED_RECONCILED / ==original NOT_APPLIED_RETRYABLE / khác CB OPEN.
KHÔNG đổi title/handle/summary/tags/published/author/featured. KHÔNG retry PUT.

## UI realtime
- KPI thêm: **AUTO lane · DEFER lane · HOLD chất lượng** (cạnh Reconciled/Retry/HOLD/Blocked/Conflict/Lỗi).
- Dòng "Lane: X · Stage: Y · đang xử lý #N".
- Mỗi dòng bảng có **lane badge** AUTO (xanh) / DEFER (cam) trước tiêu đề.
- Badge decision mới: ⏸️ HOLD_QUALITY, MANUAL_COMPLEX (tím). `progress()` trả `lane` mỗi item +
  checkpoint `auto_lane/defer_lane/hold_quality/current_lane/lane_index`.

## Checkpoint mở rộng
lane (current_lane) · lane_index · current candidate/stage · processed · applied · applied_reconciled ·
retryable · hold · hold_quality · blocked_image · blocked_fact · conflict · failed · auto_lane · defer_lane ·
updated_at. Resume: không PUT lại applied/applied_reconciled; retryable đưa lại AUTO_LANE nếu phù hợp.

## QA result — 35/35 PASS (đủ 19 case spec)
**P7.3 lane/quality/UI/static (`_scripts/qa_p7_3_lane.py`) — 14/14:**
1. Evergreen troubleshooting → AUTO_LANE ✓ (apply→APPLIED ở case 9 dưới) · 2. News → DEFER HOLD_TIME_SENSITIVE ·
3. FPS/benchmark → DEFER HOLD_UNSUPPORTED · 4. Visual tutorial → DEFER BLOCKED_IMAGE ·
5. External image text-first → remove local → đọc hiểu · 6. External image visual-dependent → blocked ·
7. quality 78 → regen đúng 2 → **HOLD_QUALITY** · 8. thin-content → MANUAL_REVIEW ·
16. progress lane + checkpoint lane fields · 17. scheduler tắt · 18. apply body-only (0 upload/Theme Asset) ·
19. broken-link config unchanged.

**Apply 500-but-write (`_scripts/qa_p7_2_reconcile.py`) — 21/21 (regression PASS):**
9. PUT 201 → APPLIED (PUT=1) · 10. PUT 500-but-write → APPLIED_RECONCILED · 11. PUT 500-no-write →
NOT_APPLIED_RETRYABLE · 12. PUT uncertain → CB OPEN · 13. crash after PUT → reconcile no re-PUT ·
14. resume checkpoint · 15. applied không chạy lại.

- `python -m compileall` full_auto/apply/verify/routes/runner → **OK**.
- Smoke (Flask restart PID 4848): 5 endpoint **200** (`/seo/blog-rewrite-ai`, full-auto status/progress/items/events).
- Secret scan: **sạch**.

## State sau build
| Mục | Giá trị |
|---|---|
| live PUT trong QA | **0** (monkeypatch, không network thật) |
| upload | **0** (apply body-only, không Theme Asset inline blog) |
| scheduler | **absent** (config schedule.enabled=false, status.scheduler=false) |
| CB | **closed** |
| flags | **OFF** |
| broken-link config | **unchanged** (LINK_CHECK_WORKERS=48, PER_HOST=4, HEAD 2s) |
| backup path | `nox-1_backup/p7-3-evergreen-selector-20260611-133408/` |

## Files changed (chưa commit)
- `blog_rewrite_full_auto.py` — `classify_lane` + `build_lanes` + lane keyword sets · run_full_auto
  lane-aware (AUTO trước, DEFER ghi status) · borderline quality (HOLD_QUALITY, regen≤2) · checkpoint
  lane fields · progress() trả lane.
- `templates/blog_rewrite_ai.html` — KPI AUTO/DEFER/HOLD_QUALITY · lane badge mỗi dòng · màu decision mới.
- `routes/blog_rewrite.py` — priority_cids + fix ALREADY_RUNNING (đã từ P7.2).
- `_scripts/run_blog_rewrite_full_auto.py` — `--priority-cids`.
- `_scripts/qa_p7_3_lane.py` (mới).
- KHÔNG đụng `seo.py` (broken-link).

## NEXT (chờ vợ)
- Build xong, **chưa chạy live**. Khi vợ duyệt → chạy Full Auto live (hoặc smoke AUTO_LANE top N) sẽ
  ưu tiên 50 bài evergreen — khả năng APPLIED cao hơn hẳn 3 bài game-config/news của run 41.
- Dừng sau report theo spec.
