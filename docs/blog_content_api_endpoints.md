# Blog SEO Command Center — API endpoints

Route module: `routes/blog_content_center.py` · Logic: `blog_content_center.py`

| Method | Endpoint | Tên | Mô tả |
|---|---|---|---|
| GET | `/blog-content` | blog_content_page | Trang Command Center (5 tab) |
| GET | `/api/blog-content/status` | bcc_status | KPI tổng (total/A1/A2/writing/review/ready/published/overdue/no_owner + by_cluster) |
| GET | `/api/blog-content/items` | bcc_items | List bài; query: cluster, priority, status, week, no_owner=1, overdue=1, q |
| GET | `/api/blog-content/items/<id>` | bcc_item | Chi tiết 1 bài (full brief) |
| POST | `/api/blog-content/items/<id>/status` | bcc_set_status | Đổi status (validate trong 13 status) |
| POST | `/api/blog-content/items/<id>/owner` | bcc_set_owner | Gán owner |
| POST | `/api/blog-content/items/<id>/deadline` | bcc_set_deadline | Đổi deadline_draft / deadline_publish |
| POST | `/api/blog-content/import-roadmap` | bcc_import | Import lại Excel (idempotent) |
| GET | `/api/blog-content/export` | bcc_export | Export CSV roadmap |
| GET | `/api/blog-content/kanban` | bcc_kanban | Kanban 9 cột + WIP warnings |
| GET | `/api/blog-content/calendar` | bcc_calendar | Theo tuần (overdue/no-owner/no-brief flags) |
| GET | `/api/blog-content/kpi` | bcc_kpi | KPI monitor 14/28/60d (đọc DB, không gọi API) |
| POST | `/api/blog-content/items/<id>/generate-brief` | bcc_gen_brief | Dựng brief từ roadmap (không AI/PUT) |
| POST | `/api/blog-content/items/<id>/generate-draft` | bcc_gen_draft | Gen nội dung qua blog_content_writer (local, không publish) |
| POST | `/api/blog-content/items/<id>/sync` | bcc_sync | **GATED** — body `{confirm:"PUBLISH BLOG ITEM", publish:false}` |
| GET (302) | `/seo/blog-rewrite-ai` | seo_blog_rewrite_page | Archived → redirect `/blog-content` |

**Sync gate:** confirm phrase `PUBLISH BLOG ITEM`. Sai phrase → HTTP 400, 0 PUT. Mặc định `publish=false` (tạo bản nháp ẩn Haravan). Backup body live trước PUT vào `data/_blog_content_sync_backup/`.
