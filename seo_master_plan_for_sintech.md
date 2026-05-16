# SEO Master Plan cho Sintech (v2026-05-09)

**Nguồn:** Tổng hợp từ tài liệu master plan của vợ Nghĩa (`Past.txt`) + đánh giá + đề xuất tối ưu cho Sintech.

---

## Triết lý cốt lõi

> Hướng đúng cho Sintech KHÔNG phải làm "1 con AI tự viết SEO toàn quyền", mà là **SEO operating system gồm nhiều agent nhỏ**, mỗi agent 1 task rõ ràng. AI Mode/AI Overviews của Google ưu tiên content rõ ngữ cảnh, có so sánh, FAQ, trải nghiệm thực, entity rõ — không nhồi keyword.

**Nguyên tắc cứng:**
- **Rule engine TRƯỚC AI**: đếm ký tự / check H1 / check schema / check canonical bằng code. AI chỉ giải thích, ưu tiên, viết lại. Không bao giờ để AI tự "đoán" trạng thái kỹ thuật.
- **Tool crawl, AI phân tích**: AI không nên crawl thay tool. Tool crawl trước, AI chỉ đọc dữ liệu đã crawl.
- **Không tự publish**: AI không apply thay đổi lên theme/Haravan production trực tiếp. Luôn diff → duyệt → apply.

---

## 9 Agent đề xuất

| # | Agent | Việc làm | Tự apply? |
|---|---|---|---|
| 1 | **Crawl Agent** | Quét URL, lấy HTML, title/meta/H1/schema | ✅ Có |
| 2 | **Audit Agent** | Phát hiện lỗi rule-based | ✅ Có |
| 3 | **GSC Agent** | Lấy click/impression/CTR/position | ✅ Có |
| 4 | **PSI Agent** | Check Core Web Vitals | ✅ Có |
| 5 | **Title/Meta Agent** | Viết 3 title + 3 meta theo rule | ❌ Cần duyệt |
| 6 | **Content Agent** | Viết bài SEO sản phẩm | ❌ Cần duyệt |
| 7 | **Internal Link Agent** | Gợi ý anchor + URL | ❌ Cần duyệt |
| 8 | **Schema Agent** | Check/gợi ý JSON-LD | ❌ Cần duyệt |
| 9 | **Code Fix Agent** | Sửa Liquid/CSS/JS bằng Claude Code/Codex | ❌ Cần diff + duyệt |

---

## Đã có / Chưa có trong app `marketing_hub` hiện tại

### ✅ Đã có (Python Flask, ~70% plan)

- `seo.py` — Crawl Agent + Audit Agent: sitemap, title/meta/H1/H2/schema/canonical/redirect/alt
- Title/Meta workflow — qua flow SEO duplicates 480 URL (sheet → Haravan metafields)
- `content_writer.py` + Codex CLI — Content Agent với auto-image 600x388 white bg
- `internal_links.py` — Internal Link Agent (vendor + product_type + collection priority)
- DB SQLite (`seo_pages`, `content_jobs`, `haravan_products`)
- Dashboard Flask + Telegram bot notify

### ❌ Còn thiếu (theo thứ tự ROI)

1. **GSC API integration** — quan trọng nhất. Chưa có data thật về click/impression/CTR/position
2. **Schema Agent với `extruct` lib** — parse JSON-LD, check Product/Article/Breadcrumb/FAQ
3. **PageSpeed API agent** — track Core Web Vitals 50 trang chủ lực hàng tuần
4. **Code Fix Agent** (Claude Code) — cần local theme Haravan + git repo riêng
5. **AI Search/GEO readiness** — robots cho AI bots (OAI-SearchBot, GPTBot, ClaudeBot, Perplexity)

### 🚫 Skip / down-prio

- ❌ `/llms.txt`, `/llms-full.txt` — standard chưa adopted, premature
- ❌ Rebuild Node.js stack — duplicate effort với Python đã có. Tận dụng `marketing_hub` thay vì viết lại.
- ❌ Monitoring agent phức tạp — chỉ cần sau khi có GSC baseline 4-8 tuần

---

## Roadmap 3 tháng đề xuất

### Tuần 1-2: Setup Code Fix Agent
- Download theme Haravan zip
- Push lên git repo private
- Setup CLAUDE.md với rules theme (1 H1, không phá mobile, accessibility, không bịa spec)
- Workflow: Claude Code sửa branch test → diff → vợ duyệt → upload lại Haravan

### Tuần 2-3: GSC API integrate
- Setup OAuth Search Console API
- Sync click/impression/CTR/position vào DB
- Thêm dashboard `/seo/gsc` hiện top URL by click + URL tụt position

### Tuần 3-4: Schema Agent
- Python `extruct` lib parse JSON-LD
- Audit Product/Breadcrumb/FAQ schema
- Flag schema sai / thiếu / không khớp visible content

### Tuần 5-6: Hoàn thành SEO content backlog
- 480 SEO duplicates còn (~52/480 đã làm)
- 1629 empty desc (đang gen tự động qua Codex CLI)

### Tuần 7-8: Internal link map mở rộng
- Auto-detect SP thiếu inbound link
- Map keyword → URL tự động
- Phát hiện anchor lặp + bài không link về cate chính

### Tháng 3: AI Search/GEO + monitoring

#### Robots cho AI bots (cập nhật `robots.txt`):
```
User-agent: OAI-SearchBot
Allow: /

User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /
```
(Quyết định cuối cùng tùy mục tiêu Sintech.)

#### Monitoring hằng ngày:
- URL mới index / chưa index
- URL tụt click/impression
- Title/meta trùng lặp sau khi update
- Schema biến mất
- Sản phẩm hết hàng nhưng vẫn index mạnh

---

## Stack đề xuất cho Sintech

**Tận dụng cái đã có (Python):**
- Flask + SQLite + BeautifulSoup + lxml + Pillow + Anthropic + Codex CLI

**Thêm:**
- `google-api-python-client` cho GSC + PSI API
- `extruct` cho schema parsing
- Git + CLAUDE.md cho theme work
- (Tùy chọn) `playwright` cho test rendering JS-heavy pages

---

## Key insights cuối

1. **Plan gốc rất tốt** nhưng được viết kiểu "agency làm cho nhiều khách". Với Sintech (1 site duy nhất), **tận dụng tool hiện có > rebuild**.
2. **Data > Agent**: GSC API trước → biết SP nào đáng tối ưu → agent sau làm đúng việc, không đoán mò.
3. **Theme local + git diff workflow** là điều kiện tiên quyết cho Code Fix Agent — không có thì Claude Code không sửa Liquid được.
4. **YMYL không phải vấn đề**: Sintech bán PC/laptop, không phải y tế/tài chính → không cần author bác sĩ. Trust signal đến từ: brand Sintech, kinh nghiệm 2000+ bộ PC build, hotline + địa chỉ thật, ảnh shop thật.
5. **Spin AI lấy sườn → edit như tự viết**: realistic approach. Cái tạo khác biệt là **kinh nghiệm thực + cá nhân hóa + ảnh real + ký tên team thật**.

---

## Folder project mẫu (nếu sau này cần rebuild riêng)

```text
sintech-seo-agent/
  config/
    rules.haravan.json
    internal-links.json
    prompts/
      title-meta.md
      content-brief.md
      schema-check.md
      code-fix.md
  src/
    crawler/         # sitemap, page-fetcher, html-parser
    audits/          # title-meta, heading, schema, canonical, alt, internal-link
    integrations/    # gsc, pagespeed, haravan, telegram, openai, anthropic, ollama
    agents/          # titleMeta, contentBrief, internalLink, schema, codeFix
    reports/         # csv-export, html-report
  data/
    crawls/
    reports/
  CLAUDE.md
  AGENTS.md
```

(Hiện không cần — đang dùng `marketing_hub/` Python.)

---

## CLAUDE.md mẫu cho theme work

```text
Bạn là SEO technical engineer cho website Sintech trên Haravan.

Nguyên tắc:
- Không sửa production trực tiếp
- Luôn đọc file liên quan trước khi sửa
- Không tạo file mới nếu có thể sửa trong file hiện có
- Không phá layout mobile
- Không đổi logic wishlist/cart/header nếu không liên quan
- Với SEO, ưu tiên: 1 H1, schema đúng visible content, title/meta đúng rule Haravan, accessibility tốt
- Sau mỗi lần sửa phải xuất diff và giải thích ngắn
- Không bịa thông số sản phẩm
- Không thêm ưu đãi/chính sách nếu không có trong rule Sintech
```

---

**File này dùng để tham chiếu khi vợ Nghĩa quay lại chốt làm hướng nào tiếp theo.** Khi triển khai, anh sẽ extend `marketing_hub` Python, không rebuild Node.js stack.
