# HARAVAN IMAGE ROUTING BY USAGE CONTEXT

> Sửa spec: KHÔNG phải mọi ảnh đều cần `/file/`. Route theo VỊ TRÍ sử dụng.
> Read-only + routing + gate. **0 upload test, 0 sửa article/product/theme, 0 commit/push.**
> Ngày 2026-06-16. Module: `marketing_hub/haravan_image_store_guard.py`. Tests 16/16 PASS + compile OK.

## Nguyên tắc
Ảnh được phân tuyến theo context dùng, không gộp chung 1 rule:

| Context | Adapter | URL hợp lệ | Files Manager bắt buộc? |
|---|---|---|---|
| `product_main_image` | `haravan_product_image` | `product.hstatic.net/200000860097/product/...` | KHÔNG |
| `product_gallery` | `haravan_product_image` | `product.hstatic.net/200000860097/product/...` | KHÔNG |
| `blog_hero` | `haravan_article_image` | article/hero workflow (Sintech) | KHÔNG |
| `product_description_inline` | `haravan_files_manager_admin_session` | `file.hstatic.net/200000860097/file/...` | **CÓ** |
| `blog_body_inline` | `haravan_files_manager_admin_session` | `file.hstatic.net/200000860097/file/...` | **CÓ** (editor-style) |

## Files requirement (chỉ cho 2 context inline)
`product_description_inline` + `blog_body_inline` **chỉ chấp nhận** `SINTECH_FILES`:
```
file.hstatic.net/200000860097/file/<name>   |   /files/200000860097/file/<name>
```
**KHÔNG chấp nhận / KHÔNG fallback:** `cdn.hstatic.net/themes/...`, `product.hstatic.net/...`,
`file.hstatic.net/<store_khác>/file/...`, URL đối thủ, external hotlink, Theme Asset, Product Image.

## Store id bắt buộc
`EXPECTED_STORE_ID = 200000860097` (Sintech). `file.hstatic.net/200000420363/file/...` → **reject** (sai store).

## Adapter routing (đã implement)
`choose_image_upload_adapter(context)` → product_main/gallery=`haravan_product_image`,
blog_hero=`haravan_article_image`, product_description_inline & blog_body_inline=`haravan_files_manager_admin_session`,
khác=`disabled`. 2 context inline **không fallback** Theme Asset / Product Image.

## Files Manager adapter
`haravan_files_manager_admin_session` — `enabled=OFF`, `session_status=FILES_MANAGER_SESSION_REQUIRED`.
Cần admin browser session đúng store Sintech (user tự đăng nhập). Không log cookie/token,
không lưu password, không upload hàng loạt. Test 1 ảnh nhỏ chỉ khi có phrase `TEST HARAVAN FILES UPLOAD`.
Nếu thiếu session → `status=FILES_MANAGER_SESSION_REQUIRED`, **không fallback** sang theme/product.

## Không phá luồng hiện có
Giữ nguyên: product main image upload, product gallery upload, blog hero workflow,
theme asset fallback cho context KHÔNG yêu cầu `/file/` (collection content, page content).
Chỉ siết rule cho `product_description_inline` + `blog_body_inline`.

---

## Output cuối

```
HARAVAN IMAGE ROUTING BY CONTEXT COMPLETED

Contexts:
- product_main_image: haravan_product_image (product.hstatic.net/200000860097/...)
- product_gallery: haravan_product_image (product.hstatic.net/200000860097/...)
- blog_hero: haravan_article_image (article/hero workflow)
- product_description_inline: haravan_files_manager_admin_session (CHỈ /file/)
- blog_body_inline: haravan_files_manager_admin_session (CHỈ /file/)

Files requirement:
- product_description_inline accepts only: SINTECH_FILES (file.hstatic.net/200000860097/file/...)
- wrong store rejected: file.hstatic.net/200000420363/file/... -> UPLOAD_WRONG_STORE
- theme asset fallback: KHÔNG cho 2 context inline (BLOCKED_INLINE_IMAGE_NOT_FILES)
- product image fallback: KHÔNG cho 2 context inline (BLOCKED_INLINE_IMAGE_NOT_FILES)

Admin session:
- status: FILES_MANAGER_SESSION_REQUIRED
- required for files manager: YES (admin browser session đúng store Sintech)
- test upload ready: chờ confirm phrase TEST HARAVAN FILES UPLOAD (+ user đăng nhập admin)

Safety:
- no cookie log: YES
- no token log: YES
- no bulk upload: YES
- no article/product apply: YES
- no theme edit: YES
- no commit/push/deploy: YES
```

**Dừng sau routing + gate + report. Không test upload khi chưa có confirm phrase.**
