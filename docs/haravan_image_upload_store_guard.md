# Haravan Image Upload — Store Guard spec

Module: `marketing_hub/haravan_image_store_guard.py` (read-only logic, không upload).

## Hằng số
- `EXPECTED_STORE_ID = "200000860097"` — Sintech (xác nhận qua theme asset `public_url`).
- `SINTECH_THEME_ID = "1001489132"` — theme id hiện tại.
- `SHOP_DOMAIN = "sintech.myharavan.com"`.

## `classify_haravan_image_url(url) -> str`
Trả về một trong:

| Label | Điều kiện |
|---|---|
| `SINTECH_FILES` | `file.hstatic.net/200000860097/file/...` hoặc `/files/200000860097/file/...` |
| `SINTECH_THEME_ASSET` | `cdn.hstatic.net/themes/200000860097/...` |
| `SINTECH_PRODUCT_ASSET` | `product.hstatic.net/200000860097/...` |
| `HARAVAN_OTHER_STORE` | host hstatic nhưng store id ≠ 200000860097 (vd 200000420363) |
| `EXTERNAL` | domain không thuộc hstatic |
| `INVALID` | rỗng / không phải URL |

## `guard_uploaded_url(url) -> dict`
```
{
  ok: bool,                 # True nếu thuộc Sintech (FILES/THEME/PRODUCT)
  classification: str,
  expected_store_id: "200000860097",
  actual_store_id: str|None,
  flag: None | "UPLOAD_WRONG_STORE",
  url: str
}
```

### Hợp đồng dùng (bắt buộc)
Sau khi BẤT KỲ adapter nào upload xong:
1. Gọi `guard_uploaded_url(returned_url)`.
2. Nếu `ok == False`:
   - KHÔNG chèn URL vào draft/body_html.
   - KHÔNG apply live.
   - Ghi log `expected vs actual` + flag `UPLOAD_WRONG_STORE`.
3. Nếu `ok == True`: được phép dùng.

## Self-test
Chạy `py -3.12 marketing_hub/haravan_image_store_guard.py` → **7/7 PASS**, `active_adapter = haravan_theme_asset`.

## Ghi chú store id
- `200000860097` = Sintech (store/account id trong hstatic CDN path; áp cho themes/ + product/ + file/).
- `1001489132` = theme id (tham số endpoint, KHÁC store id).
- `200000420363` = store KHÁC (xuất hiện trong `fetch_gallery_images.py`) → phải reject.
