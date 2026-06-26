# Collection Content Writer — Live Guard Report (audit-only)

## File này làm gì
`marketing_hub/collection_content_writer.py` gen + sync nội dung **collection** và **Haravan Page tĩnh**:
- `sync_collection_to_haravan(...)` — PUT collection qua Admin API (smart → custom fallback).
- `sync_page_to_haravan(...)` — PUT **Haravan Page** qua **Open API** (`apis.haravan.com/web/pages/<id>.json`)
  vì admin pages bị 502 cứng. Open API page chỉ ghi được `body_html` (SEO title/meta set tay).

## Rủi ro live (trước khi vá)
- `sync_page_to_haravan` **PUT live mặc định** — không guard, không confirm, không backup. Bất kỳ caller nào
  gọi là **ghi thẳng Haravan Page**.
- ⚠️ **Bug tiềm ẩn trên master**: `routes/content_collection.py` (đã merge) GỌI `ccw.sync_page_to_haravan`
  2 lần (`collection_content_sync`, `collection_content_sync_all`, nhánh `/pages/`), nhưng
  `collection_content_writer.py` trên master **CHƯA định nghĩa hàm** → bấm Sync trang `/pages/` ném
  AttributeError → "Lỗi server" (page-sync thực chất đang HỎNG, may là không PUT). PR này **vá** reference đó.
- Token: đọc từ `haravan_client.load_config()` — **KHÔNG hardcode secret** (chỉ dùng trong header Bearer).

## Guard đã thêm
`sync_page_to_haravan(page_id, title, meta, body_html, confirm=None)`:
- **Mặc định (confirm=None) → TỪ CHỐI**, trả `{ok:False, blocked:True, error:...}`, **KHÔNG gọi Haravan**.
- **PUT live CHỈ khi `confirm == "LIVE_HARAVAN"`** (truyền có chủ đích).
- **Backup `body_html` sắp đẩy** ra `nox-outputs/_page_sync_<id>.html` TRƯỚC khi PUT (audit/rollback).
- Không auto-call khi import module / render route.

## Xác nhận task KHÔNG gọi Haravan
- Toàn bộ test chạy offline: compileall + Flask test_client (no port) + gọi `sync_page_to_haravan` **không/sai confirm** → cả 2 **blocked**, không exception, không network.
- **KHÔNG** test `confirm="LIVE_HARAVAN"` (sẽ PUT thật). 0 PUT/POST/DELETE Haravan trong task này.

## Cách dùng an toàn sau này (live page sync)
1. Khi muốn sync Page thật, caller phải truyền `confirm="LIVE_HARAVAN"` có chủ đích.
2. Hiện 2 caller UI (`collection_content_sync*`) **chưa** truyền confirm → page-sync sẽ trả thông báo
   "bị KHÓA an toàn" (an toàn, không PUT). Khi cần bật live page-sync: follow-up wire confirm qua UI
   (kèm nút xác nhận rõ ràng) — **task riêng**, cần người dùng duyệt.
3. Kiểm body đã backup ở `nox-outputs/_page_sync_<id>.html` để đối chiếu/rollback.

## Ngoài scope (flag cho sau)
- `sync_collection_to_haravan` (nhánh collection thường) **chưa có guard** — cân nhắc guard tương tự ở task khác.
