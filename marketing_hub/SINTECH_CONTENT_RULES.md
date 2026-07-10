# 📕 BỘ RULES CONTENT SINTECH — FILE DUY NHẤT

> **Cập nhật 9/7/2026.** Gom từ `seo_research_rules.md` (research, vợ training 9/7) +
> `seo_writing_rules.md` v2026-05-08 (khuôn viết) + các luật vợ chốt trong phiên gen lại 9 SP.
>
> ⚠️ **Đọc file này TRƯỚC khi viết bất kỳ bài nào.** Hai file cũ giữ lại làm phụ lục tra cứu
> (template xoay vòng, văn phong mẫu, ALT ảnh), nhưng khi mâu thuẫn thì **file này thắng**.

---

# PHẦN 0 — WORKFLOW (làm theo đúng thứ tự)

```
1. Research keyword   → kw_suggest.py (Google Autocomplete)
2. Research nội dung  → SP: 3 hướng | Collection: 4 hướng
3. Trả 2 phần         → "Research + angle"  rồi mới  "Bài viết"
4. Viết               → theo PHẦN 2 (SP) / PHẦN 3 (collection) / PHẦN 4 (blog)
5. QC                 → checklist PHẦN 6
6. Backup body cũ     → PUT → verify trên trang LIVE (không tin response API)
```

**Ba mấu chốt, nhớ nằm lòng:**
- **Gap của đối thủ = các H2 giữa bài.**
- **Điểm dữ liệu mâu thuẫn = H3 giải nghĩa** (vd "1ms MPRT nên hiểu thế nào?").
- **Heading lấy nguyên văn cách người ta gõ trên Google**, không phải cách mình muốn diễn đạt.

---

# PHẦN 1 — RESEARCH TRƯỚC KHI VIẾT

## 1.1 Research keyword (BẮT BUỘC, chạy đầu tiên)

```python
from kw_suggest import harvest, questions_only     # nox-1/marketing_hub/kw_suggest.py
res = harvest(["loa vi tính", "loa 2.0"])          # seed = CỤM NHU CẦU, không phải tên model
qs  = questions_only(res)                          # → mỗi câu hỏi = 1 H2/H3/FAQ
```
- Google Autocomplete = truy vấn người thật gõ, xếp theo độ phổ biến. Free, không cần key.
- Hậu tố quét: `có · cách · bao nhiêu · là gì · loại nào tốt · khác nhau · nên mua`.
- **Tên model gần như KHÔNG có volume** (`usb lexar m400` → Google trả 0 gợi ý). Volume nằm ở cụm rộng: `usb 64gb lưu được bao nhiêu ảnh`, `ổ cứng camera 2t lưu được bao nhiêu ngày`.
- Đối chiếu GSC (`gsc/gsc_query.py`) để biết cụm nào site đã có hiển thị và đang hạng mấy.
- ⚠️ Autocomplete **KHÔNG cho volume tuyệt đối**. Muốn số thật → Keyword Planner / DataForSEO.
- ⚠️ Lọc GSC cẩn thận regex: `loa` khớp cả "down**loa**d". Dùng `\bloa\b`.

## 1.2 Thứ tự ưu tiên nguồn

1. Datasheet / trang hãng / manual chính thức
2. Ảnh hoặc file thông số **do vợ gửi** ← nguồn chốt chính
3. Trang sản phẩm Sintech hiện tại
4. Nhiều nguồn bán lẻ trùng nhau
5. Nguồn lẻ, không chắc → chỉ tham khảo

Mâu thuẫn → theo hãng. Chưa chắc → **viết an toàn**, ghi caveat ở phần Research (NGOÀI bài).

## 1.3 Bài SẢN PHẨM — research tối thiểu 3 hướng

| Hướng | Lấy gì |
|---|---|
| Nguồn hãng | model, series, spec, chuẩn kết nối, kích thước, tương thích, phụ kiện, bảo hành, **giới hạn dễ gây mua sai** |
| Trang Sintech | tên hiển thị, spec đang ghi, mâu thuẫn với hãng, collection, internal link |
| SERP / đối thủ | họ viết angle gì, đặt H2 gì, **THIẾU phần nào**, claim quá đà ở đâu, khách hay hỏi gì |

**CẤM tự thêm tính năng nếu nguồn không xác nhận:** HDMI/VGA/DP/USB-C · WiFi/Bluetooth · HDR/FreeSync/G-Sync · loa · VESA · ARGB · UASP/TRIM · TDP · FPS · bảo hành · giá.

## 1.4 Bài COLLECTION — research tối thiểu 4 hướng

Thêm vào 3 hướng trên:
- **Các collection cùng cụm** → chống cannibalization. Xác định trang nào là hub, trang nào chuyên sâu, trang nào theo ngân sách, trang nào theo phần mềm/tác vụ.
- **Bước 0** — chốt góc riêng (tác vụ / phần mềm / ngân sách / loại người dùng / lỗi mua sai).
- **Bước 0B** — nêu rõ trang này khác gì trang gần nhất, và internal link sang nó với anchor mô tả khác biệt.

Cụm "PC theo nhu cầu" phải phân hóa rõ giữa: `pc-do-hoa-ai-build-san` · `pc-streaming-livestream` · `pc-autocad` · `pc-3d-rendering` · `pc-video-editing` · `pc-photoshop` · `pc-esport` · `pc-ai-workstation` · `pc-do-hoa` · `pc-ke-toan`.

## 1.5 Output BẮT BUỘC — 2 phần trong 1 lượt trả lời

**Phần 1 — Research + angle** (ngoài writing block, ĐƯỢC có citation):
đã research nguồn nào · điểm khai thác chắc · **điểm cần viết an toàn** · đối thủ viết kiểu gì · **khoảng trống nội dung** · unique angle · heading intent · dàn H2/H3 · chốt angle.

**Phần 2 — Bài viết** (trong writing block):
Content · **đúng 3 Title** · **đúng 3 Meta** · bài hoàn chỉnh.

## 1.6 Ca CLONE theo link vợ đưa

Link vợ đưa có **spec chính xác tuyệt đối** → **bê nguyên bảng thông số** làm spec table, KHÔNG research lại spec. Chỉ research thêm **chức năng + lợi ích** để chèn vào bài.

---

# PHẦN 2 — VIẾT BÀI SẢN PHẨM

## 2.1 Heading

- **Không H1.** Chỉ H2/H3.
- **H2 đầu tiên = tên SP + model + biến thể. KHÔNG dấu `:`**
  ✅ `Fan case VSP SF-1225M12S Đen` · `Loa 2.0 SoundMax A140 Xám bạc`
  ❌ `Fan case VSP SF-1225M12S: 120mm, 1200rpm, 38 CFM`
- Ngay dưới H2 đầu: **1 câu dẫn + 5-6 bullet tóm spec**.
- **Mỗi heading MỘT mệnh đề, ≤55 ký tự.** Đừng nối 2 vế bằng `:` hay `,` — vế sau vốn là câu giải thích, đẩy xuống đoạn văn.
- Heading thân bài = **nguyên văn cách người ta gõ Google**.
  ✅ `LED Rainbow và LED RGB khác nhau như thế nào?`
  ❌ `Phân biệt ba loại đèn quạt để không mua nhầm`
- Heading phải unique trong bài (dễ đẻ heading trùng khi chèn H2 mới mà quên xoá cũ).
- Có cụm cố định: **"[Tên SP] phù hợp với ai?"** và FAQ chốt **"Có nên mua [tên SP]?"**

## 2.2 Cấu trúc bài

```
intro (ngắn, KHÔNG nhồi spec, có CTA anchor "Sintech")
H2  tên SP + bullet spec
H2  … các gap từ research, mỗi gap 1 H2 …
H3  … giải nghĩa điểm dễ hiểu sai …
H2  bảng so sánh SP cùng phân khúc (2-3 SP Sintech đang bán, data thật)
H2  [Tên SP] phù hợp với ai?
H2  Những điểm cần kiểm tra trước khi mua   ← checklist H3 nhãn NGẮN (6-21 ký tự)
H2  Vì sao nên mua tại Sintech
H2  Câu hỏi thường gặp   ← FAQ, H3 là câu hỏi dài đúng giọng người gõ, có tên SP
outro (KHÔNG heading, mở "Tóm lại," / "Nói ngắn gọn," / "Kết lại,", có link Sintech)
signature
<blockquote> spec   ← BLOCK CUỐI CÙNG TUYỆT ĐỐI
```

## 2.3 Văn phong

- Xưng **"bạn"**, không dùng "anh". Đoạn 2-3 câu, ngắn (trung vị ~170 ký tự).
- **Nhiều bullet, ít chữ.** Đối thủ mạnh dùng ~1 bullet mỗi 16 từ.
- **KHÔNG bôi đậm trong thân bài.** `<strong>` chỉ dùng cho nhãn trong khối spec.
  (⚠️ Khi đếm `<strong>` để so sánh, phải LOẠI blockquote ra.)
- Trung thực: nói thẳng SP không hợp với ai, hãng không công bố gì.
- CẤM dấu `;` trong body. CẤM `---` separator.
- CẤM lộ nội bộ: không "theo research", "theo SERP", "SEO", "inventory", không nhắc đối thủ, không citation trong bài public.

## 2.4 Giá — luật cứng (vợ chốt 9/7)

- **KHÔNG nhắc giá trong body.** Không số tiền (`45.000 đồng`, `tầm 149k`), không `giá rẻ`, `giá sốc`, `rẻ nhất`.
- Thay bằng: "phổ thông", "đời cũ", "cùng tầm".
- Nếu bắt buộc phải nêu (vợ yêu cầu): **không số thập phân** → `650k` · `1tr100k` · `3tr390k` · range `500k–700k`.

## 2.5 Thông số

- Chỉ dùng spec có trong nguồn. **Không chắc → ghi "chưa xác minh", đừng đoán.**
- Specs dễ nhầm, ghi đúng: `1ms MPRT` ≠ `1ms GtG` · `Full HD 100Hz` không nâng thành gaming cao Hz · `VESA 75x75` ≠ `100x100` · main AM5/LGA1851/LGA1700 không lẫn nền tảng · WiFi 6E/7 cần router+OS · HDD SMR không claim như ổ NAS · cáp >60W cần e-marker (không verify được thì đừng khẳng định) · MFi không tự gán.
- Tên linh kiện viết chuẩn: CPU/RAM/VGA/SSD/NVMe/PCIe in hoa đúng quy ước.

## 2.6 Internal link

- **3-6 link** trong body, URL thật (verify 200 trước khi đẩy).
- Anchor là cụm danh từ mô tả, ≤30 ký tự.
- **CẤM** "tại đây", "xem thêm", "click here".
- Vị trí tự nhiên: 1 ở cuối intro (anchor "Sintech" hoặc collection), 1-2 giữa bài (SP/collection liên quan), 1 ở outro (anchor "Sintech").
- ⚠️ Slug collection phải verify tồn tại — AI hay bịa. `usb`, `cap-sac`, `hub-argb` là 404; đúng phải là `usb-flash`, `cap-chuyen-doi`.

## 2.7 Section "Vì sao nên mua tại Sintech" — bắt buộc

Đúng 2 đoạn × 2 câu. Đoạn 2 **chèn nguyên văn**:

> Sintech hiện công bố chính sách bán hàng, kiểm hàng, vận chuyển và trả góp 0% qua thẻ tín dụng đối với 1 số sản phẩm.

Dữ liệu thật được dùng: build/lắp/test trước giao · bảo hành chính hãng · đổi trả theo chính sách · trả góp 0% · tư vấn cấu hình · Hotline 0911 713 000 · 457 Trần Xuân Soạn, Q7, TP.HCM.
**Không bịa** số lượng SP, mức giảm, tồn kho, cam kết hiệu năng.

## 2.8 Signature — CỐ ĐỊNH, một câu duy nhất cho MỌI loại SP

```html
<p><em>Tư vấn cấu hình bởi team kỹ thuật Sintech — Hotline 0911 713 000 · 457 Trần Xuân Soạn, Q7, TP.HCM.</em></p>
```
Kể cả phụ kiện (USB, cáp, loa) vẫn dùng "Tư vấn **cấu hình**". **Đừng tự chế biến thể.** Nhớ **dấu chấm cuối**.

## 2.9 Khối spec `<blockquote>` — BLOCK CUỐI CÙNG

```html
<blockquote>
  <p><strong>Thông tin hàng hóa</strong></p>
  <ul><li><strong>Hãng sản xuất:</strong> VSP</li>…</ul>
  <p><strong>Thông số quạt</strong></p>
  <ul>…</ul>
</blockquote>
```
- Nằm **sau cả signature**. Không có gì đứng sau nó.
- `<blockquote>` **để trần**, KHÔNG inline style (nhồi style → đè CSS theme → không lên bảng).
- **KHÔNG nhét `<table>` vào trong blockquote** (không hiển thị trên trang SP).
- Nhãn bọc `<strong>` + **có dấu hai chấm**: `<strong>Nhãn:</strong> giá trị`.
- **Loại bỏ Tình trạng và Bảo hành** khỏi khối spec.
- ⚠️ Theme **thay hẳn thẻ** khi render → không thể verify bằng cách grep `<blockquote>` trên trang live; phải grep nội dung.

---

# PHẦN 3 — VIẾT BÀI COLLECTION

## 3.0 RULE 0 — HTML CLEAN (đọc trước, hỏng cái này là mất trắng bài)

Haravan strip sạch wrapper lạ → HTML dính wrapper ChatGPT thì bài lên web **mất hết nội dung**, chỉ còn `<div></div>` rỗng.

**Chỉ được dùng:** `<p>` `<h2>` `<h3>` `<ul>` `<ol>` `<li>` `<a>` `<strong>` `<em>` `<table>` `<tr>` `<td>` `<th>` `<br>` `<img>`

**Tuyệt đối cấm:** `<section>` · `<article>` · mọi `<div class="markdown/prose/contents/flex/text-token-…">` · mọi attribute `data-*` (`data-start`, `data-end`, `data-message-id`, `data-testid`…) · class Tailwind (`class="flex"`, `class="prose"`, `class="dark:…"`).

Body phải bắt đầu **ngay** bằng `<p>` hoặc `<h2>`, không wrap thêm gì bên ngoài. Không copy HTML từ giao diện ChatGPT — gõ lại HTML thuần.

## 3.1 Cấu trúc body (600-1200 từ, 5 section)

```
intro 2-3 câu, KHÔNG H2, có link Sintech
H2  Vì sao chọn [tên collection] tại Sintech?
H2  Các mẫu nổi bật trong [tên collection]     (nếu có SP context)
H2  Kinh nghiệm chọn …                          (+ bảng phân khúc giá)
H2  [tên collection] phù hợp với ai
H2  Câu hỏi thường gặp
signature
```

**Bắt buộc 1 bảng phân khúc giá.** Đây là ngoại lệ của luật "không nhắc giá" ở PHẦN 2 — collection được nêu range giá, bài SP thì không.

## 3.2 Title / Meta / Link

- **Title** 45-61 ký tự, sentence case, **không chứa "Sintech"** (theme tự thêm ~10 ký tự), khác câu chữ trang cùng cụm.
- **Meta** 140-160 ký tự, có lợi ích + intent mua, CTA HOA cuối câu, **CTA đa dạng**: `XEM NGAY` · `CHỌN CẤU HÌNH NGAY` · `THAM KHẢO NGAY` · `CHỌN NGAY` · `BẮT ĐẦU NGAY`.
- **Body:** mở bằng tình huống/vấn đề thật (không công thức lặp) · taxonomy rõ ở đầu · bảng phân khúc giá · bảng chọn theo nhu cầu · FAQ · signature · CTA mềm.
- **≥6 internal link**, có link sang trang gần nhất để phân hóa intent.
- **Không**: trùng outline trang cùng cụm · viết như blog · bịa số lượng SP · nhắc đối thủ/research/SEO/SERP.
- **JSON output** (khi yêu cầu): đúng 1 JSON, không bọc ```json, `body_html` bắt đầu bằng `<p>`, dùng **nháy đơn** cho thuộc tính HTML, không H1.
- ⚠️ SEO collection/article set qua **`upsert_seo_metafields`** — NGƯỢC với product.

---

# PHẦN 4 — BÀI BLOG

Không cần đủ mọi section của bài SP, nhưng vẫn cần: phân tích keyword + search intent · bảng kế hoạch internal link · 3-6 internal link · CTA Sintech intro/outro · outline cuối bài · cấu trúc linh hoạt theo chủ đề.

---

# PHẦN 5 — FORMAT & KỸ THUẬT HARAVAN

| | Bài SP | Bài BLOG |
|---|---|---|
| H2 | 18px, `#dc2626` | 17pt, `#e74c3c` |
| Ảnh | 500px | 600px |
| Bảng | viền nhẹ | viền đậm |
| Hàm | `reformat_product_desc.reformat()` | `apply_sintech_style()` |

- **Haravan strip `<style>` block** → chỉ inline style sống.
- **SEO product**: flat field `metafields_global_title_tag` / `metafields_global_description_tag` trong `update_product`. **KHÔNG** dùng `/metafields` endpoint (theme không đọc).
- **SEO collection/article**: ngược lại, phải dùng `upsert_seo_metafields`.
- **Verify bằng trang LIVE thật**, không tin response API (GET không echo lại flat field). CDN trễ vài giây → thêm `?v=1` phá cache.
- **Title SP** ≤61 ký tự, mở đầu bằng loại SP, không chứa "Sintech". **Meta** 140-160 ký tự, CTA HOA.
- Bấm **Lưu** trong admin Haravan sẽ ghi đè `body_html` → chèn ảnh SAU CÙNG, F5 chỉ để xem.

---

# PHẦN 6 — CHECKLIST TRƯỚC KHI ĐẨY

Script `qc_push` tự chặn các mục có dấu 🤖.

- [ ] Đã chạy `kw_suggest.py` và heading bám cụm có thật?
- [ ] Output đủ 2 phần: Research + angle, rồi Bài viết?
- [ ] 🤖 Không H1
- [ ] 🤖 H2 đầu = tên SP, **không dấu `:`**, ≤50 ký tự
- [ ] 🤖 Không heading nào >60 ký tự
- [ ] 🤖 Không heading trùng nhau
- [ ] 🤖 Không nhắc giá / "giá rẻ"
- [ ] 🤖 Signature đúng nguyên văn + có dấu chấm cuối
- [ ] 🤖 `<blockquote>` là block cuối, để trần, không `<table>` bên trong, không Bảo hành/Tình trạng
- [ ] 🤖 Không từ cấm: research · SERP · đối thủ · inventory · tại đây
- [ ] 🤖 Mọi internal link trả 200
- [ ] Không bôi đậm trong thân bài (chỉ trong blockquote)
- [ ] Không dấu `;`, không `---`
- [ ] 3-6 internal link, anchor mô tả, không "tại đây"
- [ ] Có câu chính sách nguyên văn ở section "Vì sao nên mua tại Sintech"
- [ ] Có mục "cần kiểm tra trước khi mua" dạng checklist H3 nhãn ngắn
- [ ] Có FAQ, câu hỏi dài đúng giọng người gõ, có tên SP
- [ ] Outro không heading, mở "Tóm lại,"
- [ ] Dùng "bạn", không dùng "anh"
- [ ] Không bịa spec — không chắc thì bỏ
- [ ] Đã backup body cũ trước khi PUT
- [ ] Đã verify trên trang LIVE

---

# PHẦN 7 — CÁC ĐIỂM ĐÃ CHỐT (9/7/2026), ghi đè rules cũ

| Điểm | Chốt |
|---|---|
| Intro | **2 đoạn ngắn** (bỏ luật "đúng 3 câu, 1 đoạn") |
| H2 kề H3 | **Được phép** ở mục "cần kiểm tra trước khi mua" và FAQ. Các H2 khác vẫn cần ≥2 câu dẫn |
| Bảng | Giữ 1-3 bảng, **có câu dẫn trước bảng**, không để bảng đứng sát heading |
| Anchor | **HTML `<a>` thường, KHÔNG in đậm** (thân bài đã bỏ hết `<strong>`) |
| Section "Thông số nổi bật cần biết" giữa bài | **BỎ.** Thay bằng bullet spec dưới H2 đầu + `<blockquote>` cuối bài |
| 4 template xoay vòng A/B/C/D | **BỎ.** Dùng một dàn chung ở mục 2.2 |
| Câu chính sách bắt buộc | **VẪN GIỮ** (mục 2.7) |
| 3-6 internal link | **VẪN GIỮ** |
| Cấm dấu `;` | **VẪN GIỮ** |

---

# PHẦN 8 — RULES SỐNG Ở ĐÂU (bản đồ, đọc khi không biết sửa chỗ nào)

| Tầng | File | Ai đọc | Sửa khi nào |
|---|---|---|---|
| 1. Rules cho người | **`SINTECH_CONTENT_RULES.md`** (file này) | Claude, vợ | Luôn sửa đầu tiên |
| 2. Rules cho prompt | **`sintech_rules.py`** | 5 writer import chung (`product_writer`, `blog_content_writer`, `collection_content_writer`, `seo.py`, `ai_writer`) | Sửa NGAY sau tầng 1, nếu không AI gen theo luật cũ |
| 3. Cổng chặn đầu ra | **`qc_content.py`** | Mọi luồng sync | Thêm luật kiểm được bằng regex |

**Nguyên tắc:** prompt có thể bị AI phớt lờ, QC thì không. Luật nào kiểm được bằng máy thì phải có trong `qc_content.py`, đừng chỉ nhét vào prompt.

**Sửa 1 luật = sửa 3 nơi.** Chưa có cơ chế đồng bộ tự động (còn nợ).

**Phụ lục (tra cứu, không đọc mỗi lần):**
- `seo_writing_rules.md` — văn phong mẫu, 4 template xoay vòng (đã bỏ), quy tắc ALT ảnh, banlist cụm SEOer.
- `seo_research_rules.md` — bản nguyên văn rules research vợ đưa 9/7.
- `collection_writing_rules.md` — bản đầy đủ rules collection cho ChatGPT Plus (ví dụ input/output).
- `docs/heading_research_prompt.md` — prompt research heading.
