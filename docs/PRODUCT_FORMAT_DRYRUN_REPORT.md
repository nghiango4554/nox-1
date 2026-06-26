# Product Format Dry-Run Report (chuẩn ThinkBook 23/6)

Reformat `body_html` SP về chuẩn nhẹ (h2 18px / h3 16px / link #dc2626 / ảnh max 500px /
bảng viền nhẹ; p/ul/li để theme lo). Áp dụng cho `product_writer.inject_sintech_styles`
(pipeline gen) + script `reformat_product_desc.py` (reformat SP cũ).

## An toàn (đã verify)
- **Dry-run là MẶC ĐỊNH**, đọc body từ **DB local `haravan_products`** — KHÔNG gọi Haravan.
- **LIVE PUT chỉ khi đủ 2 điều kiện**: `--apply`/`--sync` **VÀ** `--confirm LIVE_HARAVAN`.
  Test guard: `--apply` thiếu confirm → **TỪ CHỐI, exit 2, KHÔNG PUT** ✅; `--sync --confirm yes` → **TỪ CHỐI** ✅.
- **Text content byte-identical** old↔new (reformat chỉ đổi thuộc tính `style`, KHÔNG động text/giá/spec).

## Sản phẩm test (DRY, offline)

| ID | SP | old_len | new_len | Δ | h2/h3 | table | img | style_attrs old→new | TEXT_IDENTICAL |
|----|----|--------:|--------:|---|------|------:|----:|--------------------|:---:|
| 1074894135 | Laptop Dell Inspiron 5577 (legacy nặng) | 98,373 | 49,857 | −49% | 14/6 | 12→12 | 1→1 | 548→265 | ✅ |
| 1068941745 | Dây Audio 2 đầu 3.5mm V-A615 | 1,469 | 1,784 | +21% | 1/3 | 0 | 0 | 0→4 | ✅ |
| 1068006340 | Mainboard Asus H81M DDR3 | 515 | 678 | +32% | 1/0 | 0 | 1→1 | 2→3 | ✅ |

## Thay đổi chính
- SP legacy nặng (Dell): **giảm ~49%** do gỡ inline Arial 12pt/17pt + viền bảng xám đậm → thay style nhẹ px-based. Bảng (12) + ảnh giữ nguyên.
- SP ngắn (audio/mainboard): tăng nhẹ vì **thêm** h2/h3/img style chuẩn vào tag vốn chưa có style — đúng mục tiêu (đồng bộ format).

## Rủi ro / đánh giá
- ✅ Không mất nội dung chính (text identical 3/3).
- ✅ Không phá bảng thông số (table count giữ nguyên).
- ✅ Không nhồi CSS nặng (style_attrs giảm với SP nặng; SP nhẹ chỉ thêm tối thiểu).
- ✅ Không đổi giá/thông số, không claim bịa (chỉ thao tác thuộc tính style).
- ⚠️ Khi áp LIVE hàng loạt: nên chạy theo lô nhỏ + kiểm CDN render (Haravan strip `<style>` block, chỉ giữ inline — đã đúng hướng). LIVE phải dùng `--apply --confirm LIVE_HARAVAN` (chưa làm trong PR này).

## Lệnh dry-run đã chạy
```
py -3.12 reformat_product_desc.py 1074894135 1068941745 1068006340 --out ../docs/product_format_dryrun_samples
py -3.12 reformat_product_desc.py 1068006340 --apply               # → TỪ CHỐI (exit 2)
py -3.12 reformat_product_desc.py 1068006340 --sync --confirm yes   # → TỪ CHỐI (exit 2)
```
Preview HTML xuất tại `docs/product_format_dryrun_samples/<id>.html` (local, không commit do dung lượng).

## Xác nhận
- **NO Haravan PUT** trong toàn bộ dry-run (offline DB; guard chặn LIVE).
- **NO DB mutation** (chỉ SELECT).
- **NO AI call**, **NO publish**.
