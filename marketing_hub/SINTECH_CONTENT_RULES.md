# 📕 BỘ RULES CONTENT SINTECH — FILE DUY NHẤT

> **Cập nhật 15/7/2026** (thêm PHẦN 1B: viết để được AI trích + link bài mồi → money page).
> Gốc 9/7/2026: gom từ `seo_research_rules.md` (research, vợ training 9/7) +
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

# PHẦN 1B — VIẾT ĐỂ ĐƯỢC AI TRÍCH DẪN & TRUYỀN LỰC VỀ MONEY PAGE

> **Bổ sung 15/7/2026.** Nguồn: case study Schema/E-E-A-T + bài Topical Authority + rubric SMEPlan (vợ đưa 15/7). Áp cho **cả SP, collection và blog**. Ba nguồn độc lập cùng chỉ về đây → ưu tiên cao.

## 1B.1 Block trả lời thẳng ngay dưới heading câu hỏi (để AI Overview/ChatGPT trích)

- Heading dạng câu hỏi (đã có ở 2.1) → **ngay dưới đặt 1 đoạn 40-55 từ trả lời TRỰC TIẾP, đủ nghĩa khi tách khỏi bài.**
- Đoạn này đứng **TRƯỚC** mọi giải thích dài / bullet. **Trả lời trước, diễn giải sau.**
- Có con số hoặc kết luận cụ thể ngay trong câu đầu.
  ✅ *"SSD Gen4 nhanh gấp ~2 lần Gen3 ở tốc độ tuần tự, nhưng khi chơi game / mở app thường chỉ nhanh hơn 5-10%. Chỉ nên lên Gen4 nếu main hỗ trợ và bạn hay chép file lớn."*
- **Mỗi đoạn thân bài ≤150 từ.** Đoạn 300-400 từ liền mạch = cắt nhỏ (dễ trích + dễ đọc mobile).

## 1B.2 Nội dung phải có bằng chứng, không nói chung chung (E-E-A-T)

- Thay câu định tính bằng con số / nguồn khi có:
  ❌ "bền cao" → ✅ "chịu ~50 triệu lần bấm" · ❌ "chạy mát" → ✅ "hạ 8-12°C so với tản zin" · ❌ "nhanh" → ✅ "đọc tuần tự ~5.000 MB/s".
- Ưu tiên **số liệu THẬT của Sintech** (đã build / test / đo) — SMEPlan gọi là *"số liệu tự sản xuất"*.
- Không có số thật → **viết an toàn, KHÔNG bịa** (giữ nguyên luật cấm bịa ở 1.3, 2.5).
- ⚠️ Tác giả thật + trang author/bio là việc **theme/schema**, không phải content-gen → làm riêng, xem [[project_blog_faq_schema]].

## 1B.4 Heading hạn chế dấu `-` và `:` (vợ chốt 15/7)

- **Trong heading, hạn chế tối đa dấu `-` và `:`.** Chỉ dùng khi **bất khả kháng**: tên SP, tên riêng, mã model (`Core i5 9400F`, `M.2`, `RX 7700 XT`).
- Không dùng `-`/`:` để nối 2 vế hay liệt kê trong heading. Vế giải thích đẩy xuống đoạn văn.

## 1B.5 Anchor internal link IN ĐẬM (vợ chốt 15/7)

- **Anchor bọc `<strong>` bên trong `<a>`** để chữ vừa đỏ (theme tự tô) vừa **in đậm**: `<a href='...'><strong>tên đích</strong></a>`.
- Đã test: `<strong>` trong `<a>` **sống qua `reformat`** (ra `color:#dc2626` + đậm); inline `style=font-weight` bị strip.
- ⚠️ Đây ĐẢO rule cũ ("anchor không bọc strong"). QC `check_product_body` đã sửa để CHO PHÉP.

## 1B.6 Research SPEC bằng TRÌNH DUYỆT THẬT, cửa sổ minisize (vợ chốt 15/7)

- Trang hãng (Gigabyte, Intel, TechPowerUp…) hay chặn WebFetch/headless (**403 Access Denied**).
- **Bắt buộc research bằng Playwright + Chrome THẬT**: `chromium.launch(headless=False, channel="chrome")`, **thu nhỏ cửa sổ (minimize)** để không che màn hình vợ. Xem [[feedback_browser_research_autonomy]].
- **Đánh mạnh tính năng thật của SP** (1B.2): moi đủ spec từ trang hãng (clock, mem, kích thước, cổng, TBW…) rồi nhồi vào blockquote + thân bài, đừng để spec thiếu thốn.

## 1B.7 XOAY wording heading các mục cố định — chống trùng cấu trúc (vợ chốt 15/7)

> Bẫy: unique về TỪ NGỮ (98%) nhưng heading đuôi bài **dập khuôn giống hệt** giữa các bài SP → nhìn như auto-gen. Đo unique phải xét CẢ cấu trúc heading, không chỉ từ.

- Các mục **KHÔNG được để 1 câu heading cứng lặp verbatim** giữa các bài. Mỗi bài rút 1 cách diễn đạt khác:
  - *Phù hợp với ai* → "Ai nên chọn [SP]" · "[SP] hợp gu người dùng nào" · "[SP] hợp với ai"
  - *Cần kiểm tra trước khi mua* → "Trước khi mua cần xem gì" · "Chọn [SP] cần lưu ý gì" · "Vài điểm nên cân nhắc"
  - *Vì sao nên mua tại Sintech* → "Mua [SP] tại Sintech được gì" · "Chọn Sintech có lợi gì" (câu chính sách VẪN giữ trong đoạn)
- ✅ **NGOẠI LỆ: FAQ giữ NGUYÊN "Câu hỏi thường gặp"** (vợ chốt — không xoay).
- **Bắt buộc có ≥1 H2 riêng theo loại SP** ở giữa bài (VGA "cần nguồn gì", CPU "vì sao cần card rời", phím "gasket có gì hay") để khung giữa cũng khác nhau.
- Kiểm chéo: 2 bài SP bất kỳ **không được trùng >1 heading** (trừ FAQ). Đo Jaccard heading, không chỉ đo từ.

## 1B.3 Internal link BÀI MỒI → MONEY PAGE — bắt buộc (gap đã ĐO 15/7)

> 🚨 Lỗ hổng nặng nhất đã verify live: **5/6 bài guide đang có 0 link** về collection/product → khách vào rồi thoát, không kéo được về trang bán, PageRank không truyền.

- **Mọi bài blog / guide phải có ≥2 link theo ngữ cảnh về đúng money page** (collection hoặc product) mà bài phục vụ intent:
  - "Cấu hình chơi GTA 5" → `/collections/vga`, `/collections/ram-may-tinh`, tool Build PC.
  - "Card đồ họa laptop là gì" → collection laptop / VGA liên quan.
  - "Kích thước bàn phím cơ" → `/collections/ban-phim-co`.
- Anchor **mô tả đúng đích** (≤30 ký tự), KHÔNG "tại đây". Verify slug trả 200 trước khi đẩy.
- Đặt link **ngay chỗ người đọc đang có nhu cầu mua** (giữa/cuối đoạn giải quyết vấn đề), KHÔNG dồn hết xuống cuối bài.
- Nguyên tắc: **bài mồi tồn tại để kéo khách + truyền lực về money page, không phải ngõ cụt.**

---

# PHẦN 2 — VIẾT BÀI SẢN PHẨM

## 2.1 Heading

- **Không H1.** Chỉ H2/H3.
- **H2 đầu tiên = tên SP + model + biến thể. KHÔNG dấu `:`**
  ✅ `Fan case VSP SF-1225M12S Đen` · `Loa 2.0 SoundMax A140 Xám bạc`
  ❌ `Fan case VSP SF-1225M12S: 120mm, 1200rpm, 38 CFM`
- Ngay dưới H2 đầu: **1 câu dẫn + 5-6 bullet tóm spec**.
- **Mỗi heading MỘT mệnh đề, ≤55 ký tự.** Đừng nối 2 vế bằng `:` `,` `-` — vế sau vốn là câu giải thích, đẩy xuống đoạn văn. Dấu `-`/`:` trong heading CHỈ dùng khi bất khả kháng (tên SP, tên riêng, mã model) — xem 1B.4.
- Heading thân bài = **nguyên văn cách người ta gõ Google**.
  ✅ `LED Rainbow và LED RGB khác nhau như thế nào?`
  ❌ `Phân biệt ba loại đèn quạt để không mua nhầm`
- Heading phải unique trong bài (dễ đẻ heading trùng khi chèn H2 mới mà quên xoá cũ).
- Mục "phù hợp với ai" và "cần kiểm tra"/"vì sao Sintech" phải **XOAY wording, không lặp verbatim giữa bài** (1B.7). FAQ giữ nguyên **"Câu hỏi thường gặp"**.

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
- **KHÔNG bôi đậm câu chữ trong thân bài.** `<strong>` chỉ dùng cho: nhãn trong khối spec, VÀ **anchor internal link** (1B.5).
  (⚠️ Khi đếm `<strong>` để so sánh, phải LOẠI blockquote và anchor ra.)
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
- Anchor là cụm danh từ mô tả, ≤30 ký tự, **bọc `<strong>` để in đậm** (1B.5): `<a href='...'><strong>...</strong></a>`.
- **CẤM** "tại đây", "xem thêm", "click here".
- Vị trí tự nhiên: 1 ở cuối intro (anchor "Sintech" hoặc collection), 1-2 giữa bài (SP/collection liên quan), 1 ở outro (anchor "Sintech").
- ⚠️ Slug collection phải verify tồn tại — AI hay bịa. `usb`, `cap-sac`, `hub-argb` là 404; đúng phải là `usb-flash`, `cap-chuyen-doi`.

## 2.7 Section "Vì sao nên mua tại Sintech" — bắt buộc

Đúng 2 đoạn × 2 câu. Đoạn 2 **chèn nguyên văn**:

> Sintech hiện công bố chính sách bán hàng, kiểm hàng, vận chuyển và trả góp 0% qua thẻ tín dụng đối với 1 số sản phẩm.

Dữ liệu thật được dùng: build/lắp/test trước giao · bảo hành chính hãng · đổi trả theo chính sách · trả góp 0% · tư vấn cấu hình · Hotline 0911 713 000 · 457 Trần Xuân Soạn, Phường Tân Hưng, Thành phố Hồ Chí Minh.
**Không bịa** số lượng SP, mức giảm, tồn kho, cam kết hiệu năng.

## 2.8 Signature — CỐ ĐỊNH, một câu duy nhất cho MỌI loại SP

```html
<p><em>Tư vấn cấu hình bởi team kỹ thuật Sintech — Hotline 0911 713 000 · 457 Trần Xuân Soạn, Phường Tân Hưng, Thành phố Hồ Chí Minh.</em></p>
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

- **Title** 40-51 ký tự, sentence case, **không chứa "Sintech"** — theme tự nối `" – Sintech"` = **đúng 10 ký tự**, nên Google thấy = phần mình viết + 10. Trần 51c là để live vừa 61c; viết 61c thì live thành 71c và **bị cắt cụt**. Khác câu chữ trang cùng cụm.
- **Meta** 140-160 ký tự, có lợi ích + intent mua, CTA HOA cuối câu, **CTA đa dạng**: `XEM NGAY` · `CHỌN CẤU HÌNH NGAY` · `THAM KHẢO NGAY` · `CHỌN NGAY` · `BẮT ĐẦU NGAY`.
- **Body:** mở bằng tình huống/vấn đề thật (không công thức lặp) · taxonomy rõ ở đầu · bảng phân khúc giá · bảng chọn theo nhu cầu · FAQ · signature · CTA mềm.
- **≥6 internal link**, có link sang trang gần nhất để phân hóa intent.
- **Không**: trùng outline trang cùng cụm · viết như blog · bịa số lượng SP · nhắc đối thủ/research/SEO/SERP.
- **JSON output** (khi yêu cầu): đúng 1 JSON, không bọc ```json, `body_html` bắt đầu bằng `<p>`, dùng **nháy đơn** cho thuộc tính HTML, không H1.
- ⚠️ SEO collection/article set qua **`upsert_seo_metafields`** — NGƯỢC với product.

---

# PHẦN 4 — BÀI BLOG

Không cần đủ mọi section của bài SP, nhưng vẫn cần: phân tích keyword + search intent · bảng kế hoạch internal link · 3-6 internal link · CTA Sintech intro/outro · outline cuối bài · cấu trúc linh hoạt theo chủ đề.

- **BẮT BUỘC (1B.3): ≥2 internal link về đúng money page** (collection/product) mà bài phục vụ intent — bài blog/guide KHÔNG được là ngõ cụt.
- **Áp 1B.1 + 1B.2**: heading câu hỏi có block trả lời thẳng 40-55 từ ngay dưới; thay câu chung chung bằng số liệu cụ thể.
- Bài dạng **tin tức** ("ra mắt / rò rỉ / lộ diện") giá trị topical-authority thấp → hạn chế; nếu viết vẫn phải gắn link về money page liên quan.

---

# PHẦN 5 — FORMAT & KỸ THUẬT HARAVAN

| | Bài SP | Bài BLOG |
|---|---|---|
| H2 | 18px, `#dc2626` | 17pt, `#e74c3c` |
| Ảnh | 500px | 600px |
| Bảng | viền nhẹ | viền đậm |
| Hàm | `reformat_product_desc.reformat()` | `apply_sintech_style()` |

- **Format SP mới (vợ chốt 15/7, dễ nhìn như khuôn combo PC):** `reformat()` tự áp —
  H2 **đỏ #dc2626 + viền trái đỏ** cỡ **20px**; H3 **18px**; body/bullet **16px** (giãn dòng thoáng);
  `<ul>` tóm tắt đầu bài **đóng khung** (box nền xám bo góc); **nhãn đầu bullet in đậm** (viết dạng `Nhãn: giá trị`);
  **signature đóng khung đỏ nhạt + viền trái đỏ**; **SĐT `0911 713 000` tự thành NÚT bấm gọi** (`tel:`, icon SVG trắng).
  QC cho phép `<strong>` trong `<li>` + strip tag khi soi signature (vì có nút SĐT chèn tag).
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
- [ ] 🤖 **Bài blog/guide có ≥2 link về money page** (collection/product) đúng intent (1B.3)
- [ ] Mỗi heading câu hỏi có block trả lời thẳng 40-55 từ ngay dưới (1B.1)
- [ ] Câu định tính đã thay bằng số liệu cụ thể khi có (1B.2)
- [ ] Đã backup body cũ trước khi PUT
- [ ] Đã verify trên trang LIVE

---

# PHẦN 7 — CÁC ĐIỂM ĐÃ CHỐT (9/7/2026), ghi đè rules cũ

| Điểm | Chốt |
|---|---|
| Intro | **2 đoạn ngắn** (bỏ luật "đúng 3 câu, 1 đoạn") |
| H2 kề H3 | **Được phép** ở mục "cần kiểm tra trước khi mua" và FAQ. Các H2 khác vẫn cần ≥2 câu dẫn |
| Bảng | Giữ 1-3 bảng, **có câu dẫn trước bảng**, không để bảng đứng sát heading |
| Anchor | **Bọc `<strong>` trong `<a>` → đỏ + IN ĐẬM** (1B.5, đổi rule 15/7) |
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

> ⏳ **PHẦN 1B (thêm 15/7) mới ở Tier 1.** Để có hiệu lực thật cần đồng bộ:
> - **Tier 2 `sintech_rules.py`**: nhét chỉ dẫn 1B.1/1B.2/1B.3 vào prompt của `blog_content_writer` + `product_writer` (nếu không AI vẫn gen theo luật cũ).
> - **Tier 3 `qc_content.py`**: thêm check máy cho **1B.3** (đếm link `/collections/` + `/products/` trong body blog ≥2) — đây là luật kiểm được bằng regex, PHẢI có ở QC. (1B.1/1B.2 khó regex → chủ yếu dựa prompt + review tay.)

**Phụ lục (tra cứu, không đọc mỗi lần):**
- `seo_writing_rules.md` — văn phong mẫu, 4 template xoay vòng (đã bỏ), quy tắc ALT ảnh, banlist cụm SEOer.
- `seo_research_rules.md` — bản nguyên văn rules research vợ đưa 9/7.
- `collection_writing_rules.md` — bản đầy đủ rules collection cho ChatGPT Plus (ví dụ input/output).
- `docs/heading_research_prompt.md` — prompt research heading.

---

# PHẦN 9 — LUẬT CẤU TRÚC HEADING & NHÃN (vợ chốt 26/8/2026)

## 9.1 🚨 CẤM H3 ĐƠN LẺ dưới một H2

**Dưới mỗi H2: hoặc KHÔNG có H3 nào, hoặc phải có TỪ 2 H3 TRỞ LÊN.**
Chia mà chỉ ra đúng một mục con là chia vô nghĩa, đọc bị hẫng.

Ba cách xử khi lỡ có H3 đơn lẻ:
1. **Thêm H3 thứ hai** nếu phần nội dung vốn đã tách được (vd mục GDDR7 tách thành
   "GDDR7 nhanh hơn GDDR6 ở chỗ nào" + "VRAM 8GB hay 16GB nên hiểu thế nào").
2. **Bỏ H3 đó đi**, gộp nội dung vào thẳng phần H2 (dùng khi phần con quá ngắn).
3. **Nâng H3 lên H2** nếu nó thực sự là một ý ngang hàng.

⚠️ Ngoại lệ đã có sẵn ở mục 358: FAQ và mục "cần kiểm tra trước khi mua" được phép H2 kề H3.

**Cách tự kiểm trước khi đẩy** (dựng cây rồi đếm, đừng nhìn bằng mắt):
```python
tree, cur = [], None
for m in re.finditer(r'<h([23])[^>]*>(.*?)</h\1>', body, re.S):
    lv = m.group(1)
    if lv == '2': cur = [m.group(2), []]; tree.append(cur)
    elif cur: cur[1].append(m.group(2))
don_le = [h for h, x in tree if len(x) == 1]
assert not don_le, f"H3 don le: {don_le}"
```

## 9.2 🚨 KHÔNG dùng `<p><strong>Nhãn</strong></p>` làm tiêu đề giả

Đoạn in đậm đứng riêng một dòng **trông y hệt H3** (cùng đen, cùng đậm), đặt ngay dưới một
H3 thật thì người đọc không biết đâu là mục, đâu là nhãn.

✅ **Dùng caption nhỏ, chữ HOA, màu đỏ** cho nhãn dẫn vào danh sách hoặc checklist:
```html
<p style="font-family:Arial,sans-serif;font-size:10pt;font-weight:700;color:#e74c3c;
letter-spacing:.7px;text-transform:uppercase;margin:18px 0 6px">Kiểm 6 thứ này trước khi chốt</p>
```
Nhỏ hơn H3 (10pt so với 13pt), khác màu, chữ HOA giãn chữ → nhìn phát biết là nhãn.

## 9.3 Checklist phải TẮT chấm đầu dòng NGAY TRÊN `<li>`

Đặt `list-style:none` ở thẻ `<ul>` là **KHÔNG ĐỦ**: CSS theme nhắm thẳng vào `li` nên đè lại,
kết quả ra vừa chấm tròn vừa dấu tích. Phải để inline trên **từng `<li>`**:
`style="list-style:none;list-style-type:none;margin-bottom:8px;padding-left:0"`

## 9.4 🚨 CẤM `<thead>` và `<tbody>` — Haravan xoá làm CÁC BẢNG LỒNG VÀO NHAU

Mục 256 đã liệt kê thẻ được phép (`<table> <tr> <td> <th>`), nhưng chưa nói **hậu quả**:

Bộ lọc Haravan **xoá `</thead>`** rồi dời `</table>` đi chỗ khác. Kết quả 26/8/2026 trên bài RTX 5060:
bảng 1 nuốt luôn bảng 2 và bảng 3 vào trong nó, thành **73 ô dồn vào một bảng**.
Trang vẫn hiện 3 bảng nên **nhìn bằng mắt KHÔNG phát hiện được**.

→ Dựng bảng phẳng: `<table><caption>…</caption><tr><th>…</th></tr><tr><td>…</td></tr></table>`.

⚠️ Đã vá bảng hỏng bằng regex 2 lần đều không sạch (dư 1 `<th>` mỗi bảng).
**Bảng đã bị bẻ cấu trúc thì DỰNG LẠI TỪ DỮ LIỆU GỐC, đừng vá.**

## 9.5 Khuôn bảng bài BLOG (chốt 26/8/2026)

```
div bọc : overflow-x:auto;-webkit-overflow-scrolling:touch;margin:16px 0   ← thiếu cái này là vỡ trên điện thoại
table   : border-collapse:collapse;width:100%;min-width:560px;font-size:10.5pt;border:2px solid #e74c3c
caption : chữ HOA, đỏ #e74c3c, font-weight:800, 10.5pt
th      : nền #e74c3c, chữ trắng, padding:10px 12px, white-space:nowrap
td      : border:1px solid #d9d9d9, padding:9px 12px
cột đầu : font-weight:700 + nền #fdf2f2
kẻ sọc  : dòng chẵn nền #fafafa (đặt inline trên từng <td>, KHÔNG dùng nth-child)
```
Luật cũ chỉ ghi "bảng blog viền đậm" mà không nói đậm bao nhiêu → nay chốt **2px màu đỏ**.

## 9.6 Nhãn dẫn vào danh sách: đã có MÀU thì phải IN ĐẬM (vợ chốt 26/8)

Nhãn đỏ 10pt font-weight:700 nhìn vẫn mảnh, chìm so với nội dung.
→ Chuẩn: **`font-size:11.5pt;font-weight:800;color:#e74c3c;letter-spacing:.4px;text-transform:uppercase`**

## 9.7 🚨 Cách NGHIỆM THU bảng — đếm cấu trúc, đừng so chuỗi

Hai cách kiểm SAI đã dính trong cùng một buổi:
1. **So chuỗi tuyệt đối** `body_gui == body_web` → báo "chưa ghi" trong khi **đã ghi rồi**,
   vì Haravan tự chuẩn hoá vài ký tự. Nhớ: [[reference_haravan_content_api]] PUT article
   **trả HTTP 500 mà VẪN GHI**.
2. **Đếm bằng regex** `len(re.findall('<table'))` → ra 3 bảng dù ba bảng đang lồng nhau.
   Regex `<th` còn đếm nhầm cả `<thead>`.

✅ Đúng: parse bằng BeautifulSoup rồi đối chiếu số mong đợi:
```python
for t, (cot, dong) in zip(soup.find_all("table"), MONG_DOI):
    assert len(t.find_all("th")) == cot
    assert len(t.find_all("td")) == cot * dong
    assert not t.find("table")        # <<< bắt bảng lồng nhau
```

## 9.8 🚨 Ép `font-family:Arial` là VÔ HIỆU HOÁ mọi nét đậm trên 700

Arial **chỉ có 2 nét: 400 và 700**. Khai `font-weight:800` trên chữ Arial thì trình duyệt
vẫn chỉ vẽ 700. Đây là lý do 26/8/2026 vợ nói "chưa đủ đậm" hai lần liền mà sửa số không ăn.

Giao diện Sintech nạp **Nunito Sans biến thiên, dải nét `200..1000`**
(`fonts.googleapis.com/css2?family=Nunito+Sans:...wght@...200..1000`).

→ **Muốn nét trên 700 thì ĐỪNG đặt `font-family`**, để thừa hưởng phông giao diện.
Áp cho: nhãn chữ HOA, caption bảng, ô tiêu đề bảng, heading.
`apply_sintech_style()` tự nhét `font-family:Arial,sans-serif` vào mọi thứ → **phải gỡ lại** ở
những chỗ cần nét dày.

**Cách kiểm nhanh phông có nét dày không:**
```python
"200..1000" in html_trang_live      # dai net cua Nunito Sans
```

## 9.9 Khuôn CSS HEADING chuẩn cho bài blog (chốt 26/8/2026, mẫu là bài The Isle)

```
H2: font-size:18px;color:#dc2626;font-weight:800;border-left:4px solid #dc2626;
    padding-left:10px;margin:26px 0 12px
H3: font-size:16px;color:#1a1a1a;font-weight:800;margin:18px 0 8px;
    padding-left:9px;border-left:3px solid #f0a5a5
```
Cả hai **KHÔNG đặt font-family** (xem 9.8). Bài mẫu: `/blogs/news/the-isle-ra-mat-nam-nao-lich-su`.

⚠️ **Sắc đỏ chuẩn là `#dc2626`.** `apply_sintech_style()` và code cũ hay dùng `#e74c3c`,
để lẫn hai sắc trên một trang là lệch tông. Gom hết về `#dc2626`.

**Cách đối chiếu với bài mẫu** (đừng nhìn bằng mắt):
```python
kieu_mau  = set(re.findall(r'<h2 style="([^"]*)"', body_bai_mau))
kieu_minh = set(re.findall(r'<h2 style="([^"]*)"', body_bai_minh))
assert kieu_mau == kieu_minh and len(kieu_minh) == 1
```

## 9.10 🚨 ĐÓNG DẤU ẢNH: chọn loại dấu THEO NỀN ẢNH (vợ chốt 26/8/2026)

> Vợ: *"nếu ảnh đa dạng màu sắc thế này thì chèn watermark xoá nền, nhỏ nhỏ, mờ mờ chứ,
> sao lại để cái kia to đùng, xấu ảnh"* và *"chỉ khi ảnh là nền trắng chiếm đa số thì anh mới
> chèn logo màu này nha, mà cũng nên chèn nhỏ thôi"*.

**Đo trước, chọn sau.** Tính tỉ lệ điểm ảnh gần trắng (độ sáng ≥ 238):

| Tỉ lệ nền trắng | Dùng dấu | Thông số |
|---|---|---|
| **≥ 55%** | `sintech.png` (logo MÀU) | rộng **92px**, mờ 88% |
| **< 55%** | `logo xóa nền.png` (trong suốt) | rộng **84px**, mờ **38-42%** |

⚠️ **`logo xóa nền.png` là chữ TRẮNG** → dán thẳng lên nền sáng là mất tăm (bẫy 25/8).
Phải **tự tô lại màu theo nền chỗ dán**: nền tối tô trắng, nền sáng tô xám đậm `#334155`.
```python
lg = Image.new("RGBA", base.size, mau + (0,))
lg.putalpha(base.split()[3].point(lambda v: int(v * mo)))   # giu hinh dang, doi mau
```

**Đừng mặc định badge đỏ cho mọi ảnh.** Badge đỏ hợp ảnh CHỤP nền tối (bài Minisforum 25/8),
KHÔNG hợp ảnh đồ hoạ nhiều màu, dán vào là phá bố cục.

## 9.11 Vị trí đóng dấu: TRƯỢT DỌC MÉP, đừng chấm 4 góc

Cách chấm độ nhiễu ở 4 góc rồi chọn góc phẳng nhất **ĐÃ HỎNG 26/8**: cả 4 góc đều bận thì
nó vẫn chọn góc ít tệ nhất, kết quả **dấu đè thẳng lên chữ tiêu đề** 2 tấm. Số liệu không báo lỗi,
chỉ nhìn ảnh mới thấy (đúng luật [[feedback_chi_vao_anh_dung_ta_bang_loi]]).

✅ Đúng: **trượt dấu dọc 4 mép**, bước 6px, chấm độ lệch chuẩn từng vị trí, cộng phạt nhẹ khi xa góc:
```python
diem = do_lech_chuan + khoang_cach_toi_goc * 0.012
```
Nhận vị trí khi độ nhiễu < 10. Bận quá thì thu nhỏ dấu rồi quét lại.
**BẮT BUỘC ghép ảnh contact sheet rồi NHÌN trước khi up.**

## 9.12 🚨 TRƯỚC KHI VIẾT BÀI MỚI: bắt buộc kiểm site đã có bài chưa

26/8/2026 anh viết bài **"So sánh các loại DLSS"** trong khi site **đã có sẵn**
*"DLSS 4 là gì, cách bật DLSS 4"* từ 9/2025. Anh có kiểm `site:sintech.vn` cho chủ đề nguồn
và mini PC, **nhưng quên kiểm cho DLSS**. May là hai bài đủ khác nhau nên không giẫm chân,
nhưng đó là may chứ không phải do làm đúng.

**Bắt buộc chạy 2 lệnh này TRƯỚC KHI viết, không có ngoại lệ:**
```
site:sintech.vn <từ khoá chính>
site:sintech.vn <từ khoá phụ>
```
Quét cả bằng API cho chắc, vì Google có thể chưa index bài mới:
```python
for blog in (1000906526, 1000960873):
    for a in hc.list_articles(blog, page=pg, limit=50):   # co san body_html
        if TU_KHOA in (a['title'] + a['body_html']): ...
```

**Nếu đã có bài:** ưu tiên **CẬP NHẬT bài cũ** thay vì viết mới. Chỉ viết mới khi bài cũ phục vụ
truy vấn khác hẳn, và khi đó **hai bài phải trỏ sang nhau**.

## 9.13 🚨 Bài mới đăng xong là MỒ CÔI, phải gắn link vào ngay

Đăng xong mà không bài nào trỏ tới thì bài nằm chết một góc. 26/8/2026 kiểm 278 bài:
hai bài vừa đăng có **0 bài trỏ tới**.

**Việc bắt buộc ngay sau khi đăng:**
1. Quét toàn blog tìm bài liên quan (dùng `list_articles`, xem [[reference_haravan_list_articles_co_body]])
2. Chấm điểm theo số lần khớp từ khoá trong `title` (nhân 4) và trong thân bài
3. Chọn **3 bài chủ** điểm cao nhất, chèn **một câu dẫn có ngữ cảnh** kèm link
4. Đặt link **giữa bài, đúng chỗ người đọc đang có nhu cầu**, không dồn xuống cuối
5. Anchor bọc `<strong>`, gắn `?ref=lien-ket-noi-bo` để đo được
6. Backup body cũ từng bài trước khi ghi

**Nghiệm thu:** quét lại toàn blog, mỗi bài mới phải có **≥3 bài trỏ tới**.
