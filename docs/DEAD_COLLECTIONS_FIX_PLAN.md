# Dead Collections Fix Plan — 19/6/2026

Nguồn: LibreCrawl crawl #4 (sintech.vn). 7 collection URL trả **404** nhưng bị internal link tới (**35 link nguồn, tất cả ở `body` — KHÔNG phải menu/theme** → sửa được không cần đụng theme).

## Bảng xử lý (đề xuất — CHƯA áp live, chờ duyệt)

| Dead URL (404) | Link nguồn | Anchor | Target đề xuất | Action | Tin cậy |
|---|---|---|---|---|---|
| `/collections/man-hinh` | **30** | Màn hình | `/collections/man-hinh-may-tinh-pc` ✅200 | 301 redirect | cao |
| `/collections/vga-asus` | 1 | VGA ASUS | `/collections/vga` ✅200 | 301 redirect | cao |
| `/collections/mainboard-asus` | 1 | mainboard ASUS | `/collections/mainboard` ✅200 | 301 redirect | cao |
| `/collections/case-may-tinh` | 1 | case máy tính | `/collections/vo-case` ✅200 | 301 redirect | cao |
| `/collections/ban-phim-co-aula` | 0* | (none) | `/collections/ban-phim-co` ✅200 | 301 hoặc bỏ link | TB |
| `/collections/o-cung-hdd` | 1 | ổ cứng HDD | ⚠️ VERIFY (`o-cung-hdd-1` 404) | tìm target → 301 | thấp |
| `/collections/ban-chu-z` | 1 | Bàn chữ Z | ⚠️ VERIFY (collection bàn gaming) | tìm target → 301 | thấp |

(*ban-phim-co-aula: 404 nhưng crawl_links không bắt được nguồn — có thể link qua JS/redirect; ưu tiên thấp.)

## Phân loại nguồn link
- Tất cả **placement = `body`** (nội dung trang), KHÔNG có menu/navigation/theme.
- Phân bố: 30 từ trang `/collections/` (chủ yếu link `man-hinh` lặp trong mô tả collection), 4 từ `/blogs/`, 1 từ `/products/`.
- Chi tiết từng link: [`dead_collections_sources.csv`](./dead_collections_sources.csv).

## Cách xử lý đề xuất (ưu tiên redirect — gọn nhất)
**Khuyến nghị: tạo 301 redirect trong Haravan** (mỗi dead URL 1 redirect → fix toàn bộ link nguồn 1 lần, KHÔNG cần sửa 30 body, KHÔNG đụng theme). 5/7 đã có target chắc.
- Phương án thay thế (nếu không muốn redirect): find-replace URL trong body_html các collection/blog/product nguồn (xem sources.csv).
- 2 URL tin cậy thấp (`o-cung-hdd`, `ban-chu-z`): xác minh target đúng trước khi redirect.

## Ràng buộc
- ⚠️ **CHƯA áp live** — báo cáo để duyệt. Tạo redirect / sửa body = thao tác Haravan → cần bước duyệt riêng.
- KHÔNG sửa theme.
- File action: [`dead_collections_actions.csv`](./dead_collections_actions.csv).
