# Sintech Marketing Hub — Báo cáo cập nhật cuối ngày (2026-06-07)

## 1. Tóm tắt dễ hiểu
Trước đây tool đã theo dõi được GA4 Analytics (traffic, thiết bị, sự kiện) và đọc Search Console qua Google Sheet xuất tay. Hôm nay tool được nâng cấp lớn: kéo dữ liệu **Search Console trực tiếp qua API** (tươi hơn, theo từng ngày), ghép **SEO × GA4 theo ngày** dùng đúng nguồn **Organic Search**, và thêm 3 màn hình mới: **Tracking Audit** (soi sự kiện nào đang đo / thiếu), **Task Center** (gom việc cần làm, phân loại ưu tiên), **Analytics Ops** (chạy cả pipeline 1 nút + cảnh báo Telegram). Hiện tool nội bộ **đã dùng được đầy đủ** để xem sức khỏe dữ liệu và biết cần đo thêm gì. Phần **chưa bật live**: scheduler tự chạy (đang tắt), cảnh báo Telegram live, và việc cài tracking thật trên website (GTM/theme). **Website Haravan KHÔNG bị đụng** — không sửa theme, không publish GTM. **GitHub đã backup sạch** tới `1efba83` qua clean worktree (không push từ bản chính).

## 2. So sánh phiên bản cũ và mới
| Hạng mục | Cũ | Mới | Lợi ích thực tế |
|---|---|---|---|
| GA4 dashboard | Có | Giữ nguyên + dùng cho join | Xem traffic/thiết bị/sự kiện |
| GSC data source | Google Sheet xuất tay | **Search Console API daily** | Dữ liệu tươi (tới 06-03 vs Sheet 05-11), theo ngày |
| Google Sheet fallback | Nguồn chính | Vẫn còn, làm **fallback** | An toàn khi API lỗi |
| SEO × GA4 join | Chỉ period-level (tổng kỳ) | Thêm **daily-aligned theo ngày** | So GSC clicks vs GA4 organic theo từng ngày |
| Organic vs all-channel | Trộn all-channel | **Organic Search là chính**, all-channel chỉ tham khảo | So đúng loại (không lệch) |
| Tracking Audit | Không có | **Mới** `/seo/tracking` | Biết sự kiện nào đang đo / thiếu |
| Event Catalog | Không có | **Mới** 30 expected vs 17 detected | Danh mục sự kiện chuẩn |
| Ecommerce funnel audit | Không | **Mới** (directional) | Thấy rớt ở bước nào |
| Lead/contact audit | Không | **Mới** | Phát hiện thiếu tracking click liên hệ |
| Build PC gap audit | Không | **Mới** | Trang xây cấu hình chưa có funnel |
| Task Center | Không | **Mới** `/tasks` | Gom việc, ưu tiên, dedup |
| Severity vs impl priority | — | **Tách riêng** | Contact gap = ưu tiên cao NHƯNG không báo động khẩn |
| Telegram alert filter | — | Lọc theo **incident severity** (đã sửa) | Không spam cảnh báo sai |
| Analytics Ops | Không | **Mới** `/ops/analytics` | Chạy cả pipeline 1 nút |
| Scheduler | Chỉ SEO weekly | Thêm job analytics (đang **tắt**) | Tự động khi vợ bật |
| Security/token | Token riêng | Giữ + thêm token GSC API riêng | Tách bạch, gitignore |
| Git workflow | — | **Clean worktree** push fast-forward | Lịch sử sạch, an toàn |
| Canonical reconcile | — | Lập **kế hoạch** (chưa làm) | Dọn 73 file WIP sau |

## 3. Chức năng mới đã hoàn tất
- **GA4 Analytics** — `/seo/ga4`. Giữ nguyên, cấp dữ liệu Organic cho join. Done.
- **Search Console API** — `/seo/gsc` (Data Health). Sync daily 5 báo cáo (summary/pages/queries/devices/countries), coverage = API top rows (không full). Done.
- **SEO × GA4** — `/seo/ga4#seojoin`. 2 mode: API daily-aligned ↔ Sheet period fallback. Max confidence = medium. Done.
- **Tracking Audit** — `/seo/tracking`. Event catalog + funnel + findings. Done.
- **Task Center** — `/tasks`. Gom task từ findings + sync-fail, dedup + cooldown. Done.
- **Analytics Ops** — `/ops/analytics`. Orchestration 1 nút, lock 409. Done (scheduler tắt).
- **Telegram alert** — chỉ incident severity P0/P1, im lặng khi OK. Done (chưa bật live).
- **Git safety** — clean worktree, fast-forward, không force. Done.
- **Documentation** — 8 docs deploy pack + báo cáo. Done.

## 4. Flow hệ thống hiện tại
```text
GA4 API        → SQLite → GA4 Dashboard
Search Console API → SQLite → GSC Data Health
GSC page daily + GA4 Organic Search landing daily
   → SEO × GA4 daily-aligned partial coverage (directional)
Tracking Audit → Findings → Task Center
Analytics Ops  → GA4 sync → GSC sync → SEO×GA4 join → Tracking Audit → Task Center
               → Telegram alert CHỈ khi có incident severity P0/P1
```
- Scheduler hiện **enabled=false**. Telegram live alert **chưa bật**. Fallback Sheet **vẫn còn**. Website live **chưa deploy tracking mới**.

## 5. Route/page mới
| Trang | Route | Để làm gì | Trạng thái |
|---|---|---|---|
| GSC Data Health | `/seo/gsc` | Nguồn GSC API + coverage | ✅ |
| SEO × GA4 (daily) | `/seo/ga4#seojoin` | Ghép SEO × GA4 organic | ✅ |
| Tracking Audit | `/seo/tracking` | Soi sự kiện đo/thiếu | ✅ |
| Task Center | `/tasks` | Gom việc + ưu tiên | ✅ |
| Analytics Ops | `/ops/analytics` | Chạy pipeline + cảnh báo | ✅ (scheduler tắt) |

## 6. API chính
| API | Method | Công dụng | Trạng thái |
|---|---|---|---|
| /api/gsc/status, /refresh | GET/POST | Trạng thái + sync GSC API | ✅ 409 lock |
| /api/gsc-ga4-join/status, /refresh, (list) | GET/POST | Join daily SEO×GA4 | ✅ |
| /api/ga4/seo-join/status | GET | Fallback period-level | ✅ |
| /api/tracking/status, /audit, /events, /findings | GET/POST | Tracking audit | ✅ |
| /api/tasks, /generate, /<id>/resolve\|snooze\|reopen | GET/POST | Task Center | ✅ |
| /api/ops/analytics-daily/status, /run, /alert-preview | GET/POST | Orchestration | ✅ |

## 7. Database đã thêm
| Nhóm | Bảng chính | Mục đích |
|---|---|---|
| GSC API | gsc_daily_summary, gsc_pages/queries/devices/countries_daily, gsc_sync_runs, gsc_cache_status | Lưu data Search Console theo ngày |
| Join | gsc_ga4_join_daily, gsc_ga4_join_runs/status, ga4_landing_pages_channel_daily | Ghép SEO×GA4 organic theo ngày |
| Tracking | tracking_event_catalog, tracking_findings, tracking_audit_runs | Danh mục sự kiện + phát hiện gap |
| Task | (reuse) ga4_tasks + cột implementation_priority/source | Gom việc, tách ưu tiên vs severity |
| Ops | analytics_daily_runs | Lịch sử chạy pipeline |
Tất cả migration **additive, idempotent** (CREATE IF NOT EXISTS / ALTER ADD COLUMN), không drop/truncate.

## 8. Commit đã push hôm nay
| # | Canonical | Replay (clean worktree) | Nội dung | Push? |
|---|---|---|---|---|
| 1 | e8a6103 | bc41510 | GSC direct API daily sync | ✅ |
| 2 | 5cfae64 | 7ab1cb9 | GSC API source health UI | ✅ |
| 3 | 64f409c | 765d639 | Organic daily-aligned join backend | ✅ |
| 4 | d501851 | 2d52e4b | Daily API + Sheet fallback UI modes | ✅ |
| 5 | 00620b7 | fc6275f | Tracking event catalog + deploy pack | ✅ |
| 6 | 115b8e2 | f6654cf | Task Center dedup + cooldown | ✅ |
| 7 | de3e6d7 | 6bd391c | Analytics Ops + Telegram alert | ✅ |
| 8 | 6e180cc | 30be2fc | Docs deploy approval + reconcile plan | ✅ |
| 9 | 1a18246 | 1efba83 | Fix: tách severity khỏi impl priority | ✅ |
- origin/master cuối ngày: **`1efba83`**. Clean worktree: **sạch**, HEAD == origin/master. Canonical HEAD: `1a18246`. Canonical WIP **73 file còn nguyên**.

## 9. Tracking audit hiện tại
17 detected / 30 expected / 23 missing · 6 open findings · Ads import giữ nguyên.
| Gap | Severity | Impl priority | Đã xử lý | Ghi chú |
|---|---|---|---|---|
| Thiếu contact tracking (phone/zalo/messenger/map) | **P2** | **P0** | Chưa (cần GTM) | KHÔNG phải incident P0; Telegram KHÔNG alert |
| Thiếu Build PC funnel | **P2** | **P1** | Chưa (cần theme export) | — |
| Thiếu bước ecommerce (view_cart/add_payment/shipping) | P2 | P2 | Chưa | Funnel rớt mạnh |
| `send` chưa rõ nguồn | P2 | P2 | Chưa | unknown_source_needs_review |
| purchase stale (~10 ngày) | P2 | P2 | Chưa | needs_review, chưa kết luận bug |
| remove_from_cart > add_to_cart | P2 | P2 | Chưa | needs_review |

## 10. Task chủ động skip (DEFERRED / làm sau)
| Task skip | Lý do | Ảnh hưởng | Làm sau khi nào |
|---|---|---|---|
| GTM contact publish | Cần làm thủ công trong GTM | Thiếu insight click liên hệ | Khi vợ rảnh mở GTM |
| Theme Haravan deploy | Theme ngoài repo | Build PC chưa đo | Khi có theme export |
| Build PC tracking | Thiếu selector | Trang xây PC chưa funnel | Sau theme export |
| Ecommerce checkout patch | Chưa xác minh bug | Funnel còn gap | Sau GA4 DebugView |
| Mark GA4 key events | Chỉ làm trong GA4 Admin | — | Sau khi có data |
| Bật APScheduler live | Giữ an toàn | Phải chạy tay | Khi muốn tự động |
| Bật Telegram live | Chưa duyệt cổng | Không có cảnh báo tự động | Khi vợ duyệt |
| Canonical reconcile | 73 file WIP cần review | Không ảnh hưởng tool | Task riêng |

## 11. Bảo mật & Git
- Token local **ignored**: `.secrets/` (gsc_api_token, gsc_oauth, google_token, ga4_token). DB `posts.db` **ignored**. Config local `state/*.json` (trừ `*.example.json`) **ignored**. OAuth JSON **ignored**.
- **Không force-push, không reset/rebase**, push qua **clean worktree** fast-forward. 73 file WIP canonical **giữ nguyên**. Auto Commit task **Disabled**.

## 12. Việc thủ công duy nhất nếu muốn làm tiếp
```text
Mở GTM và triển khai contact click tracking:
phone_click · zalo_click · messenger_click · email_click · map_click
```
- Có thể **skip**. Website vẫn chạy bình thường. Dashboard nội bộ vẫn dùng được. Chỉ mất insight về click liên hệ.

## 13. Kết luận
- Tool nội bộ **đã đủ dùng** để theo dõi sức khỏe dữ liệu + biết cần đo thêm gì.
- Phần **live tracking** (GTM/theme) làm sau, không gấp.
- Scheduler có thể **giữ tắt** — khi cần chỉ chạy thủ công `/ops/analytics`.
- **Canonical reconcile** tách thành task riêng (kế hoạch ở `docs/CANONICAL_RECONCILE_NEXT_PLAN.md`).
