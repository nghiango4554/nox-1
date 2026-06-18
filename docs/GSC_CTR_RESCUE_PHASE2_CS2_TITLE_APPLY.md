# GSC CTR RESCUE — PHASE 2 (CS2 title apply + tracking)

> Ngày 18/6/2026. Scope: (A) tracking baseline, (B) apply CS2 `article.title`, (C) tạo manual admin task cho Build. Không đụng Build SEO qua API · không Office/crack · không FAQ schema · không theme · không commit.

## B. CS2 — apply `article.title` (article 1002399773)

- **Title CŨ (52):** `Cấu hình chơi CS2 - Counter Strike 2 trên PC, Laptop`
- **Title MỚI (49):** `Cấu hình chơi CS2 mượt: chọn PC & laptop theo FPS`
- PUT 1 lần → **201**. Backup full payload: `data/seo_phase1_backup/cs2_article_1002399773_phase2_pre.json`.
- Chỉ đổi `title`; **không** đụng body_html (57.170 ký tự giữ nguyên), handle, tags, published, author, image — verify API OK.

### ⚠️ Phát hiện quan trọng về `<title>`
Mục tiêu B là đổi **`<title>` thật**. Kết quả kiểm chứng live (cùng 1 response, X-Cache hit):
| Phần tử | Sau apply |
|---|---|
| **H1** | ✅ MỚI: `Cấu hình chơi CS2 mượt: chọn PC & laptop theo FPS` |
| **og:title** | ✅ MỚI (giống H1) |
| **`<title>` tag** | ❌ VẪN CŨ: `Cấu hình chơi CS2 - Counter Strike 2 trên PC, Laptop` |

→ `article.title` điều khiển **H1 + og:title**, KHÔNG điều khiển `<title>`. `<title>` của bài (giống page Build) do **field SEO ẩn ở admin** quyết định — Open API không ghi được (đã thử `meta_title` ở Phase 1: bị bỏ qua).

**Kết luận:** đổi `article.title` cải thiện H1 + og:title (tốt cho người đọc + chia sẻ MXH), nhưng **`<title>` search vẫn chưa đổi** → cần sửa tay ở admin (xem `build_pc_manual_admin_seo_task.md`, có thêm mục CS2). Giữ thay đổi vì khi sửa `<title>` ở admin xong, H1/og/title sẽ khớp nhau hoàn toàn.

**Verify nhanh chóng nếu cần:** dòng `meta_description` (Phase 1) đã đổi đúng; H1/og đổi đúng; `<title>` chờ admin.

## A. Tracking baseline
Bảng DB **`gsc_ctr_tracking`** (migration additive idempotent, schema chuẩn 24 cột: resource_type/resource_id/url/query/landing_group/baseline_clicks/impressions/ctr/position/baseline_title/baseline_meta/applied_fields_json/apply_date/next_check_date/check_14d|28d|60d_date/status/expected_change/notes/report_path/created_at/updated_at) + `gsc_ctr_tracking_baseline.csv`.

**5 record (1 record/query):**
| query | landing_group | clicks | impr | CTR | pos | status |
|---|---|---|---|---|---|---|
| cs2 | cs2 | 28 | 3.936 | 0,7% | 6,3 | waiting_14d |
| build pc | build_pc | 147 | 4.836 | 3% | 11,7 | waiting_14d |
| build pc online | build_pc | 861 | 3.738 | 23% | 2,6 | waiting_14d (giữ top) |
| build | build_pc | 9 | 2.853 | 0,3% | 7,3 | waiting_14d |
| xây dựng cấu hình pc | build_pc | 15 | 890 | 1,7% | 8,9 | waiting_14d |

Lịch check: 14d **2026-07-02** · 28d 2026-07-16 · 60d 2026-08-17. Status enum: waiting_14d→checked_14d→waiting_28d→...→done/paused.

**UI:** thêm section **"CTR Rescue Tracking"** ở `/seo/history` (route `seo_history_page` + helper `db.gsc_ctr_tracking_list()` + template `seo_history.html`) — **chỉ đọc DB, KHÔNG gọi GSC API khi render**, có empty state. Server đã restart, trang HTTP 200, section hiển thị 5 record. (Code chưa commit.)

Cách đo lại sau 14/28/60 ngày: chạy `gsc/gsc_query.py` (OAuth) cho từng query, so baseline → cập nhật record + đổi status.

## C. Build page
SEO title/meta/H1 **không apply qua API** (field thật không expose, admin 502) → đã tạo `build_pc_manual_admin_seo_task.md` (kèm cả CS2 `<title>`).

## Safety
backup trước PUT ✓ · PUT đúng 1 lần (CS2 title) ✓ · không retry ✓ · không đổi body_html/handle/tags/published/author/image ✓ · không sửa Build qua API ✓ · không theme ✓ · không commit/push ✓.
