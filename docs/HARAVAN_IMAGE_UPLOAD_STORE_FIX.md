# HARAVAN IMAGE UPLOAD — STORE FIX

> Điều tra read-only + dựng store guard. **KHÔNG upload test, KHÔNG sửa live/theme/blog, KHÔNG commit.**
> Ngày: 2026-06-16. Repo canonical: `nox-1/marketing_hub`.

## Bối cảnh
Mong muốn: ảnh lên Files Manager đúng store Sintech, URL dạng
`file.hstatic.net/200000860097/file/<filename>` (hoặc `/files/200000860097/file/<filename>`).
Hiện hệ thống upload qua **Theme Asset** → URL `cdn.hstatic.net/themes/200000860097/assets/<filename>`
(đúng store Sintech, nhưng KHÔNG phải Files Manager URL).

---

## 1. Official API capabilities (kiểm tra trong code thật)

| Khả năng | Endpoint | Trả URL | Trạng thái |
|---|---|---|---|
| **Theme Asset API** | `PUT apis.haravan.com/web/themes/{theme}/assets.json` (base64) | `cdn.hstatic.net/themes/200000860097/assets/...` | ✅ CÓ, proven, đúng store |
| **Product Image API** | `POST /products/{id}/images.json` (base64) | `product.hstatic.net/200000860097/product/...` | ✅ CÓ, proven, đúng store |
| **Article image field** | `apis.haravan.com/web/blogs/*` (`haravan_blog.create_article`) | ảnh nhúng URL trong body_html | ⚠️ CÓ API nhưng không có upload ảnh riêng; blog API hay **502** |
| **Files Manager API** | (không có) | `file.hstatic.net/<store>/file/...` | ❌ KHÔNG có resource công khai trong API Haravan |
| **Admin file upload (cũ)** | — | — | ❌ Không có dấu vết code gọi admin file upload |

Tách 3 nhóm:
- **A. API token official upload** → Theme Asset + Product Image (đều đúng store Sintech).
- **B. Admin/browser-session upload** → cần cookie/session admin; **chưa khả dụng trên máy này** (xem mục 6).
- **C. Theme asset fallback** → chính là A, đường an toàn mặc định.

---

## 2. Audit env / token / store

Nguồn cấu hình: `nox-1/state/haravan_token.json` (đọc bằng `haravan_client.load_config()`).
Field có: `access_token`, `blog_access_token`, `blog_ids`, `open_api_base`, `shop_domain`.
**Không in token.**

| Mục | Giá trị |
|---|---|
| shop_domain | `sintech.myharavan.com` |
| base admin | `https://sintech.myharavan.com/admin` |
| Open API | `https://apis.haravan.com` |
| theme id hiện tại | `1001489132` (`sync_collection_images.MAIN_THEME`) |
| **expected Sintech store id** | **`200000860097`** |
| store_id trong token | KHÔNG có field (suy ra từ public_url) |
| current adapter | `haravan_theme_asset` |
| current returned URL pattern | `cdn.hstatic.net/themes/200000860097/assets/<name>` |

**Xác nhận store qua GET read-only:** theme asset `assets/cc-wifi-mesh-01.jpg` →
`public_url` host `cdn.hstatic.net`, **store_id `200000860097`** ⇒ token map ĐÚNG store Sintech.
**Nguy cơ sai store của đường theme asset hiện tại: KHÔNG.**

⚠️ Bằng chứng "sai store" tồn tại thật: trong `workspace/marketing_hub/fetch_gallery_images.py`
có URL `file.hstatic.net/**200000420363**/file/...` — đây là Files Manager URL nhưng thuộc
**store 200000420363 ≠ Sintech**. Đúng loại lỗi cần guard.

---

## 3. Diagnosis — vì sao "Claude khác" upload được `/file/` mà bản này không

Files Manager (`file.hstatic.net/<store>/file/...`) **không có endpoint API công khai**.
Muốn đẩy file vào đó chỉ có 2 khả năng:
1. **Admin browser session** (cookie đăng nhập) điều khiển UI "Tập tin" của admin Haravan.
2. Token/cửa nội bộ khác (không thuộc public API).

Bản Claude này:
- **Không** có playwright/selenium/puppeteer/webdriver trong code (grep = 0).
- **Không** có `HARAVAN_ADMIN_COOKIE` / admin_session / saved cookie.
- **Không** có MCP browser cho Haravan (MCP khả dụng chỉ Canva + DataHub).
- Chỉ giữ **access_token API** (Bearer) → không mở được Files Manager UI.

→ "Claude khác" upload được `/file/` **gần như chắc do có admin browser session** (hoặc URL nó tạo
thực ra thuộc **store khác** như 200000420363 ở trên = sai store). Trên máy này, **adapter Files
Manager chưa khả dụng** vì thiếu auth session — KHÔNG đoán endpoint, KHÔNG mượn credential người dùng.

---

## 4. Store guard (đã dựng)

File mới: `marketing_hub/haravan_image_store_guard.py` (additive, không đụng luồng cũ).
- `EXPECTED_STORE_ID = "200000860097"`.
- `classify_haravan_image_url(url)` → `SINTECH_FILES | SINTECH_THEME_ASSET | SINTECH_PRODUCT_ASSET | HARAVAN_OTHER_STORE | EXTERNAL | INVALID`.
- `guard_uploaded_url(url)` → `{ok, classification, expected/actual store, flag}`; sai store ⇒ `ok=False`, `flag="UPLOAD_WRONG_STORE"`.
- Self-test: **7/7 PASS**.

Quy ước dùng: sau khi adapter upload xong → gọi `guard_uploaded_url(url)`; nếu `ok=False`
thì **không dùng URL trong draft, không apply live**, log expected vs actual.

---

## 5. Adapter registry

| adapter | enabled | proven | URL pattern | priority |
|---|---|---|---|---|
| haravan_files_admin_session | **OFF** | no | `file.hstatic.net/200000860097/file/...` | 1 |
| haravan_theme_asset | **ON** | yes | `cdn.hstatic.net/themes/200000860097/assets/...` | 2 |
| haravan_product_image | **OFF** | yes | `product.hstatic.net/200000860097/product/...` | 3 |

`active_adapter()` hiện trả `haravan_theme_asset`. Files adapter chỉ lên priority 1 SAU khi proven
(có admin session đúng store + test 1 ảnh). **Không tự dùng admin cookie khi flag chưa bật.**

---

## 6. Điều tra admin Files upload (kết quả)

| Dấu vết | Có? |
|---|---|
| browser profile Claude | không tìm thấy liên kết Haravan |
| MCP browser session | không (chỉ Canva/DataHub MCP) |
| Playwright/Selenium/Puppeteer | KHÔNG (grep 0) |
| saved Haravan admin cookies | KHÔNG |
| endpoint Files Manager từng gọi | KHÔNG |
| HARAVAN_ADMIN_COOKIE / session storage | KHÔNG |

⇒ **Adapter Files Manager CHƯA khả dụng trên máy này** (thiếu session/cookie). Không đoán endpoint,
không dùng credential người dùng.

---

## 7. Kết luận chính xác (không nói chung chung "không thể upload ảnh")

```
Files Manager upload bằng official API token : KHÔNG có resource công khai.
Files Manager upload bằng admin browser session: CHƯA khả dụng trên máy này / chưa authenticated.
Fallback an toàn hiện tại                       : Theme Asset API, URL cdn.hstatic.net/themes/200000860097/... (đúng Sintech).
```

### Hai hướng đề xuất

**A. Dùng Theme Asset cho ảnh blog (khuyến nghị)**
- An toàn, chỉ cần access_token (đã có).
- URL không phải `/file/` nhưng vẫn `cdn.hstatic.net/themes/200000860097/...` = SINTECH_OWNED.
- Đã proven, đúng store. Không cần làm gì thêm.

**B. Bật Files Manager adapter**
- Cần admin session đăng nhập **đúng store Sintech** (store id `200000860097`).
- Cần xác nhận store id sau đăng nhập (read-only trước).
- Cần test 1 ảnh nhỏ + guard sai store.
- Chỉ làm khi có confirm phrase `TEST HARAVAN FILES UPLOAD`.

---

## Report (định dạng yêu cầu)

```
HARAVAN IMAGE UPLOAD STORE FIX COMPLETED

Official API:
- files manager API: KHÔNG có resource công khai
- theme asset API: CÓ (apis.haravan.com/web/themes/{theme}/assets.json), proven, đúng store
- product image API: CÓ (/products/{id}/images.json), proven, đúng store

Current config:
- shop: sintech.myharavan.com
- expected store id: 200000860097
- theme id: 1001489132
- current adapter: haravan_theme_asset
- current returned URL pattern: cdn.hstatic.net/themes/200000860097/assets/<name>

Diagnosis:
- why other Claude may upload files: nhiều khả năng có admin browser session (cookie) điều khiển Files Manager UI; hoặc URL nó tạo thuộc store khác (vd 200000420363) = sai store
- why this Claude cannot: chỉ có access_token API, Files Manager không có endpoint API; không có cookie/session/browser MCP
- missing auth/session: admin browser cookie/session đúng store Sintech
- wrong store risk: đường theme asset hiện tại KHÔNG sai store (đã verify 200000860097); rủi ro sai store đến từ URL /file/ ngoài (đã thấy 200000420363)

Fix:
- store guard: marketing_hub/haravan_image_store_guard.py (classify + guard_uploaded_url), self-test 7/7 PASS
- adapter registry: files=OFF, theme_asset=ON, product_image=OFF
- wrong-store rejection: flag UPLOAD_WRONG_STORE khi URL không thuộc 200000860097
- fallback: haravan_theme_asset

Status:
- files adapter: NOT_AVAILABLE (no admin session on this machine), enabled=OFF
- theme asset adapter: ACTIVE, proven, enabled=ON
- product image adapter: AVAILABLE but enabled=OFF (tránh bẩn gallery)

Next:
- need confirm TEST HARAVAN FILES UPLOAD or not
```

**Đã dừng. Không upload test khi chưa có confirm phrase `TEST HARAVAN FILES UPLOAD`.**
