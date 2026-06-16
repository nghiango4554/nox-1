# IMAGE REMEDIATION WORKLOAD — local queue (10/6/2026)

Read-only queue xử lý ảnh trước khi apply. KHÔNG upload/PUT/sửa live. CSV: `blog_rewrite_image_remediation_workload.csv`.

## Tổng quan
- Tổng ảnh **815** trên 145 bài · safe **6** · **blocked 139**
- Ảnh chết 12 · uncertain 28

## Theo nguồn (source_class)
- UNKNOWN_EXTERNAL: 439
- COMPETITOR_SOURCE: 186
- NEWS_MEDIA_SOURCE: 120
- SINTECH_OWNED: 54
- HARAVAN_OTHER_STORE: 13
- OFFICIAL_MANUFACTURER: 2
- INVALID_URL: 1

## Theo availability
- REACHABLE: 774
- UNCERTAIN_TIMEOUT: 26
- DEAD_404: 7
- DEAD_410: 5
- UNCERTAIN_403: 2
- INVALID: 1

## Hành động
- **Gỡ local ngay**: ảnh DEAD_404/410/INVALID (12+) → REMOVE_DEAD_IMAGE (đã default + bulk confirm).
- **Cần review/thay**: COMPETITOR/NEWS/UNKNOWN/OTHER_STORE → MANUAL_REVIEW (KHÔNG auto gỡ — bản quyền). Gỡ hoặc thay ảnh Sintech/chính hãng.
- **Giữ**: SINTECH_OWNED reachable → KEEP.
- Sau khi mọi ảnh blocked được xử lý (gỡ/giữ) → article gate ALLOW → mới apply (P5B).

## Lưu ý
- Gỡ ảnh chết KHÔNG đủ unblock: 139 bài vẫn blocked do còn ảnh đối thủ/news/unknown cần quyết.
- `build_remediated_draft_local` tạo draft sạch (gỡ ảnh REMOVE) version mới, không overwrite, recompute gate.