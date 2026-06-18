# Product Description — Inline Image Apply Gate

Module: `marketing_hub/haravan_image_store_guard.py` → `scan_inline_images(body_html, context)`.
Áp cho context `product_description_inline` (và `blog_body_inline` nếu muốn editor-style).

## Quy tắc gate
Trước khi apply mô tả sản phẩm, scan toàn bộ `<img src="">` trong `body_html`.
Mọi ảnh inline PHẢI là `SINTECH_FILES` (`file.hstatic.net/200000860097/file/...`).

| Tình huống ảnh inline | Verdict |
|---|---|
| `SINTECH_FILES` đúng store | OK |
| Theme asset (`cdn.hstatic.net/themes/...`) | `BLOCKED_INLINE_IMAGE_NOT_FILES` |
| Product image (`product.hstatic.net/...`) | `BLOCKED_INLINE_IMAGE_NOT_FILES` |
| Store khác (`file.hstatic.net/200000420363/file/...`) | `UPLOAD_WRONG_STORE` |
| External hotlink (domain khác) | `EXTERNAL_IMAGE_BLOCKED` |
| Thiếu ảnh cần upload mà không có session | `FILES_MANAGER_SESSION_REQUIRED` |
| URL rỗng/sai | `INVALID_IMAGE` |

**Không apply mô tả sản phẩm nếu còn bất kỳ ảnh nào không đạt.**

## Hàm
```
scan_inline_images(body_html, context="product_description_inline") -> {
  ok: bool,                       # True nếu mọi ảnh là SINTECH_FILES
  context, total,
  blocking_reasons: {reason: count},
  gate_status: "OK_INLINE_ALL_FILES" | "BLOCKED",
  files_manager_session: "FILES_MANAGER_SESSION_REQUIRED" | "N/A",
  needs_files_manager_session: bool,
  images: [ {ok, classification, reason, actual_store_id, url}, ... ]
}
```

## Hợp đồng dùng
1. Gọi `scan_inline_images(body_html, "product_description_inline")` trước khi apply.
2. `gate_status != "OK_INLINE_ALL_FILES"` ⇒ **KHÔNG apply**, trả lý do từ `blocking_reasons`.
3. Ảnh cần đưa về `/file/` ⇒ dùng adapter `haravan_files_manager_admin_session`
   (chỉ chạy khi có admin session đúng store + confirm `TEST HARAVAN FILES UPLOAD`).
4. **Không fallback** theme asset / product image cho ảnh inline.

## Không phá luồng khác
Gate này CHỈ áp context inline. Product main/gallery (Product Image) + blog hero (Article)
+ theme asset cho collection/page content **không bị siết** bởi gate này.
