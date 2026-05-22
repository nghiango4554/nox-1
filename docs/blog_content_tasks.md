# Blog Content — Kế hoạch task chi tiết (T1–T6)

> Chốt 22/5/2026. Mục tiêu: nâng cấp mảng Blog Content `/blog-content` — gen bài → tự gom ảnh ứng viên về local → vợ chọn 2-3 ảnh chèn vào bài → đẩy lên Haravan (ẩn). Kèm đề xuất Pillar + cluster.

## Quyết định nền (áp cho mọi task)
- **Nguồn ảnh ưu tiên:** hãng → Sintech → nước ngoài/free. **Gom tối đa 10 ảnh/bài**, vợ **chọn 2-3**.
- **Bản 1 (làm trước):** nguồn = **Sintech** (ảnh SP Haravan) + **Pexels/Unsplash** (free, cần API key). **Bản 2 (sau):** thêm **hãng + web/nước ngoài** qua Google Custom Search.
- **Lưu ảnh local:** `marketing_hub/data/blog_images/<job_id>/` + file metadata (nguồn, url gốc, alt/credit).
- **Bản quyền:** vợ chịu trách nhiệm nguồn ảnh chọn; ưu tiên stock free + ảnh SP + ảnh hãng.
- **Tạo bài Haravan:** đã có `haravan_blog.py` (Open API `apis.haravan.com/web/blogs`). Field article: `title, author, body_html, tags, handle, image:{src}, page_title (SEO title), meta_description (SEO meta)`. Ẩn = `published_at:null` (module tự xử lý). Blog IDs: 1000960873 Hướng dẫn · 1000906526 Tin tức.

---

## T1 — Module gom ảnh về local (lõi)
**Mục tiêu:** cho 1 bài (keyword + SP liên quan) → gom ≤10 ảnh ứng viên về local.
**Việc cần làm:**
- Tạo `marketing_hub/image_gather.py`, hàm `gather(job_id, query, product_handles=[], max_n=10)`.
- Nguồn theo thứ tự ưu tiên, gom tới khi đủ 10:
  1. **Sintech**: query `haravan_products` theo keyword/handle → ảnh từ cột `images` → dùng `_to_grande` (tái dùng logic `content_writer.py`).
  2. **Pexels API** (search theo keyword) — cần key.
  3. **Unsplash API** (search) — cần key.
- Tải mỗi ảnh về `data/blog_images/<job_id>/` (đặt tên `NN_<source>.jpg`), lưu `meta.json`: {file, source, origin_url, alt/credit, w, h}.
- Dedup theo URL/hash, cap 10, giữ thứ tự ưu tiên.
**File:** `image_gather.py` (mới); config key Pexels/Unsplash vào `state/` hoặc `.secrets/`.
**Phụ thuộc:** key Pexels (vợ đăng ký — anh hướng dẫn).
**Done khi:** gọi `gather()` → folder có ≤10 ảnh + `meta.json`.

## T2 — Tự gom ảnh khi gen bài
**Mục tiêu:** gen 1 bài xong → tự chạy T1 cho job đó.
**Việc cần làm:** trong route `/blog-content/<id>/gen` (app.py) hoặc `blog_content_writer.gen_blog_content`, sau khi gen body → rút keyword + SP liên quan → gọi `image_gather.gather(job_id, ...)`. Set cờ "đã gom ảnh" cho job.
**File:** `app.py` (route gen), `blog_content_writer.py`.
**Phụ thuộc:** T1.
**Done khi:** gen xong là kho ảnh sẵn cho picker.

## T3 — Trang sửa bài: lưới ảnh + chọn chèn
**Mục tiêu:** `/blog-content/<id>` hiện lưới ≤10 ảnh local → vợ tick 2-3 → chèn vào bài.
**Việc cần làm:**
- Route serve ảnh local + metadata (vd `/blog-content/<id>/images`); static serve từ `data/blog_images/<job_id>/`.
- UI lưới ảnh trong `blog_content_detail.html`: thumbnail, tick chọn, xem to, nhãn nguồn.
- Chọn xong → chèn `<img>` vào `edited_body_html` (bản 1: chèn sau intro + rải giữa các H2; sau có thể kéo-thả). Đánh dấu ảnh `selected` trong metadata.
**File:** `blog_content_detail.html`, `app.py` (route serve images + save selection).
**Phụ thuộc:** T1/T2.
**Done khi:** tick ảnh → bài có `<img>`, lưu DB `edited_body_html`.

## T4 — Đề xuất Pillar + bài cluster
**Mục tiêu:** gợi ý chủ đề trụ (pillar) + bài con → vợ duyệt → tạo `blog_jobs` để gen.
**Việc cần làm:**
- Nguồn gợi ý (CHỜ VỢ CHỐT): (a) category/collection Sintech, (b) keyword Google Search Console (tab GSC sẵn có), (c) AI đề xuất theo ngành PC/gaming — hay kết hợp.
- AI sinh: mỗi pillar + 4-8 bài cluster (title + search intent + keyword chính).
- DB lưu pillar + cluster (bảng mới `pillars`/`pillar_articles`, hoặc cột `pillar` trong `blog_jobs`).
- Trang mới `/blog-pillars`: hiện pillar đề xuất → vợ tick bài → tạo `blog_jobs` (status draft) để gen.
**File:** route + template mới, `blog_content_writer.py` (prompt pillar), migration DB.
**Phụ thuộc:** không (làm ngay) — cần vợ chốt nguồn gợi ý.
**Done khi:** vợ duyệt → có `blog_jobs` chờ gen.

## T5 — Tối ưu UI /blog-content (list)
**Mục tiêu:** danh sách bài gọn/đẹp, thao tác nhanh.
**Việc cần làm:** filter theo status/blog; badge trạng thái (draft/gen/synced), badge "đã có ảnh" + số ảnh chọn, điểm quality/readability; nút gen/sửa/đẩy nhanh; link admin Haravan.
**File:** `blog_content.html` (+ data ở route).
**Phụ thuộc:** không (làm ngay).
**Done khi:** list dễ nhìn, đủ thông tin trạng thái.

## T6 — Đẩy bài + ảnh lên Haravan (ẩn)
**Mục tiêu:** sync bài đã duyệt lên Haravan dạng ẩn. *(Capability `haravan_blog.py` ĐÃ SẴN.)*
**Việc cần làm:**
- Route "Đẩy lên Haravan (ẩn)" trong trang sửa → `haravan_blog.create_article(blog_id, fields, hidden=True)`.
- Map field: `title`=edited_title, `body_html`=edited_body_html (đã chèn ảnh), `author`, `tags`, `handle`, `page_title`=meta title, `meta_description`=meta, `image:{src}`=ảnh đại diện đã chọn.
- Chọn `blog_id` theo loại bài (Hướng dẫn 1000960873 / Tin tức 1000906526).
- Lưu `haravan_article_id` + `haravan_blog_id` vào `blog_jobs`, status=synced.
- **Ảnh inline trong body:** cần URL công khai. Ảnh Sintech-CDN + Pexels đã công khai → nhúng thẳng URL được; ảnh nào chỉ có ở local thì phải upload lên Haravan trước rồi thay URL.
**File:** `app.py` (route sync blog), `haravan_blog.py` (sẵn), `blog_content_detail.html`.
**Phụ thuộc:** T3 (ảnh đã chọn + chèn).
**Done khi:** bấm đẩy → bài ẩn xuất hiện trên Haravan admin.

---

## Bản 2 (sau)
- Thêm nguồn ảnh **hãng + web/nước ngoài** (Google Custom Search API, cần key) vào T1.
- Kéo-thả ảnh vào vị trí trong bài (T3 nâng cao).

## Thứ tự thực hiện gợi ý
**T1 → T3 → T4 → T5 → T2 → T6**

## Việc cần VỢ làm
1. Đăng ký **key Pexels** (free) — cho T1.
2. Chốt **nguồn gợi ý Pillar** (category / GSC keyword / AI / kết hợp) — cho T4.
3. (Bảo mật) **rotate token blog Haravan** đã lộ trong chat 22/5.
