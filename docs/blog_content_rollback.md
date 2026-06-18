# Blog SEO Command Center — Rollback

Backup: `marketing_hub/_backup/blog-content-command-center-all-in-one-20260616-170521/`

## Khôi phục code (trả về trạng thái trước)
Copy đè lại từ backup:
```
app.py
routes/content_blog.py
templates/base.html
templates/redesign_base.html        (nếu cần — bản gốc có trong git/working tree trước đó)
templates/blog_content.html
```
Rồi xóa 2 file mới (tùy chọn):
```
marketing_hub/blog_content_center.py
marketing_hub/routes/blog_content_center.py
```
→ Khôi phục lại import/register `blog_rewrite` trong `app.py` (bỏ comment) + dòng đăng ký `/blog-content` trong `content_blog.py` (bỏ comment).

## Khôi phục DB (an toàn — chỉ gỡ bảng MỚI)
Bảng mới do feature này tạo, **drop KHÔNG ảnh hưởng data cũ**:
```sql
DROP TABLE IF EXISTS blog_content_items;
DROP TABLE IF EXISTS blog_content_events;
```
> Bảng cũ `blog_rewrite_*` + `blog_jobs` KHÔNG bị đụng trong toàn bộ quá trình — không cần khôi phục.

## Restart
Kill python listen :5055 → watchdog (`_scripts/start_marketing_hub*.bat`) tự relaunch (Python312).

## Lưu ý
- Backup ảnh blog đã tối ưu trước đó: `data/_img_opt_backup/` (không liên quan feature này).
- Backup body sync (nếu đã sync bài): `data/_blog_content_sync_backup/`.
