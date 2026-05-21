# WORKLOG — Sintech Marketing Hub

> File anh (Claude) tự update sau mỗi milestone. Sau /clear, anh đọc file này là biết task tuần này tới đâu, file nào đã edit, bug đang debug. Vợ Nghia có thể scan nhanh để xem anh đang làm gì.

## ✅ Task #8 — Gộp rule content về 1 nguồn (Phase 1 + 1.5 + 1b) — 21/5 19:xx

- **Phase 1.5 (provider) — gần như đã xong từ trước**: `ai_provider.call_ai` là điểm switch DUY NHẤT (chain Codex→Claude→Gemini). Mọi writer reach nó: blog/collection/product/seo qua `call_ai`; `ai_writer._call_codex` cũng delegate sang `ai_provider`. content_writer route gen qua ai_writer + đã catch `AIQuotaError` (713-718). Còn lại (low-pri, KHÔNG đụng vì risk): ai_writer còn nhánh `_call_openai/_call_anthropic` (chỉ chạy nếu vợ set key OpenAI/Anthropic — hiện không).
- **Dead import cleanup**: xóa `import codex_provider` chết ở `blog_content_writer.py` + `product_writer.py` (`as cp`, 0 dùng). GIỮ ở collection (dùng `is_codex_available()` 528/640) + content_writer (dùng `_is_rate_limit_message`).
- **Phase 1 (rule chung) — `sintech_rules.py` là nguồn chân lý**:
  - Thêm param `common_rules_block(include_length=False)` → bỏ rule độ dài title/meta chung để KHỎI mâu thuẫn với writer có length riêng chặt hơn (collection 48-58, title-meta 45-58). Vẫn giữ: chống bịa spec / filler / xưng hô / CTA link / signature.
  - Append `common_rules_block(include_length=False)` vào **product / collection / ai_writer** (blog đã dùng từ trước). Sửa filler/CTA/spec-safety/hotline/signature ở `sintech_rules.py` 1 lần → ăn cả 4 writer body.
  - **Zero behavior change**: đã verify cả 4 writer vốn tuân thủ y hệt từng dòng common block (signature verbatim, pronoun, filler superset, spec-safety) — append = reinforcement, KHÔNG nới/đổi rule. Length riêng từng loại giữ nguyên.
- **✅ Phase 1b (gộp block title/meta) — XONG 21/5**: thêm `sintech_rules.title_meta_rules_block()` (KHÔNG kèm length/schema/angle — chỉ phần GIỐNG nhau: cấm 'Sintech' trong title, pool CTA HOA, chống bịa spec, filler, cấm bịa giá). Rút phần trùng khỏi `seo.py _TITLE_META_SYSTEM_PROMPT` + `collection_content_writer._TITLE_META_SYSTEM_PROMPT`, mỗi nơi GIỮ length riêng (seo 45-58/145-158 + 3 meta M1/M2/M3; collection 48-58/140-160 + 1 meta) + schema + angle inline. Sửa filler/CTA/spec-safety 1 lần ở `sintech_rules.py` → giờ ăn cả **body + title/meta**.
  - **Thêm filler canonical**: `FORBIDDEN_FILLER` += "vượt trội", "đỉnh cao" (trước chỉ collection title/meta cấm 2 cụm này inline → giờ mọi writer cấm). Collection title/meta GỘP THÊM được spec-safety (trước không có). Không mất rule nào.
- **product_writer.py KHÔNG phải legacy** (đã verify): `app.py` gọi `pw.organize_spec` (3429) + `pw.generate` (3456) cho route `/products/new`. 2 writer cố ý tách: `ai_writer`=/content-jobs (viết mô tả SP đã có), `product_writer`=/products/new (tạo SP mới từ spec nhập tay).
- **Verify**: py_compile 7 file OK; import + render dưới Python 3.12 OK (cả body-writer RULE CHUNG inject đúng 1 lần/writer + 2 prompt title/meta có block chung, length riêng giữ nguyên 45-58/145-158 & 48-58/140-160, schema JSON nguyên); restart server (watchdog .bat, PID mới **12488**) → routes `/content-jobs /collection-content /blog-content /products/new /seo/title-meta /` = **200**. **Đã commit** Task #8 Phase 1+1.5+1b.

## 🚧 Đang dở (active) — snapshot trước /clear LẦN 2 (16/5 21:00)

### 🔴 Active — có thể trigger NGAY (anh hoặc vợ 1-click)
- [ ] **Bấm "✨ Gen vào Sheet" trên `/seo/title-meta`** — stream gen 1679 SP, push F/G/H Sheet `Meta des + Title Errors`. Auto stop khi quota Claude hit.
- [ ] **Re-crawl 1923 URL trên `/seo`** để DB cập nhật score mới (logic A+B+C+D+E) — chạy nền 15-30 phút. Không bắt buộc (DB đã crawl 16/5 15:55 với code MỚI: avg 67.3 / max 85).
- [ ] **Test pattern lazy upload thực tế**: gen 1 SP mới → verify body có URL `/local-images/`, sync → upload Haravan thật. Anh tự test được.

### 🟡 Blocked — chờ vợ confirm / paste data / chốt hướng
- [ ] **3 bài FB pending đăng** — chờ vợ drop ảnh vào `Desktop\Sintech\PIC đăng page\16-5\`:
  1. Thanh lý nguyên bộ PC i5-10400 + RTX 2060 + 16GB + Cooler Master 212
  2. Loa Edifier R1855DB Bluetooth (~2Tr9xx) — handle `loa-edifier-r1855db-bluetooth`
  3. Tai Nghe Gaming Xiberia X20 RGB 7.1 (~5xx.xxx) — handle `tai-nghe-gaming-xiberia-x20-den-rgb-7-1-virtual-overear`
- [ ] **Bot Telegram token revoked (401)** từ 12/5 14:00 — vợ paste token mới để resume `@Web_Sintech_bot`.
- [x] **Collection content — blueprint heading kiểu Minh Tuấn Mobile (20/5)** — `collection_content_writer._SYSTEM_PROMPT` rework: H2 NGẮN (avg ~6-7 từ), trộn taxonomy + topical + câu hỏi volume cao; 2 H2 đầu = TAXONOMY có H3 ("Các dòng [SP]" 4-6 H3 + "Phân loại [SP] theo..." 3-5 H3), bảng giá ở H2#3; dùng TÊN SP NGẮN không nhồi full title; bỏ ép "Lỗi dễ gặp"/"4 góc nhìn". Verified gen Màn Hình Asus + Laptop Acer: H2#1/#2 taxonomy có H3 (15 H3/bài), bảng từ H2#3, heading ngắn gọn. (Trước đó 20/5 đã có rule text-first, nay nâng cấp lên taxonomy-first.)
- [x] **Auto-fix meta length collection (20/5)** — thêm `_fix_meta_length()` vào `gen_collection_content`: quick-suffix chèn cụm ngữ cảnh trước CTA (138c→157c, 135c→154c, giữ CTA HOA cuối) → fallback AI regen qua Codex 145-158c → giữ nguyên nếu fail. Trả thêm field `meta_fix`. Prompt cũng nhắm meta 148-158c (viết dài tay). Unit-test PASS. Server restart PID 22076 16:12.
  → Mai vợ gen lại 10 bài (#19-28) trên web là ăn luôn blueprint heading mới + meta chuẩn 140-160. (Anh KHÔNG regen hôm nay theo yêu cầu vợ.)
- [x] **AI provider cho gen** — 20/5 vợ chốt: TẤT CẢ task gen về Codex CLI. Đã swap `product_writer.py`, `collection_content_writer.py`, `app.py` (catch `CodexRateLimitError`). `seo.py`/`content_writer.py`/`blog_content_writer.py`/`ai_writer.py` vốn đã Codex. `claude_provider.py` giữ làm fallback (chỉ chạy khi Codex chưa cài).
- [ ] **Chia Codex 3 project** — vợ chưa chốt (1 quota chung / 3 account riêng / khác).
- [ ] **Regen 7 jobs failed** — 4 content_jobs + 3 blog_jobs (status=failed). Chờ vợ ưu tiên.
- [ ] **Push GitHub** — repo `git@github.com:nghiango4554/nox-1.git` đã accessible SSH. Vợ chốt: push full workspace hay split repo.
- [ ] **Re-sync 38 jobs đã synced** — cập nhật ALT mới + body với CDN URL khi vợ sẵn sàng.
- [ ] **Nâng cấp bot Telegram v2** — nếu vợ chốt (commands `/regen`, `/sync`, `/caption`...).

### Git state
- Branch: `master`, 2 commits:
  - `d2a5260` — "Initial: Sintech marketing_hub baseline + SEO scoring refactor" (175 files, 16/5 15:56)
  - `9eee935` — "WORKLOG: snapshot trước /clear — pending tasks + git state" (16/5 16:00)
- Author: `nghiango4554 <nghiatrong4554@gmail.com>` (name = ngo, không phải trong)
- Remote: **chưa setup** (chưa push GitHub)
- Sau /clear lần 1: nhiều file uncommitted (gemini_provider.py, refactor seo.py + seo_title_meta.html, sheet_writer.py). Khi vợ muốn commit lại thì check `git status`.

### Sheet ops đã setup
- Tab `"Meta des + Title Errors"` (sheet 13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU gid 971701509): 1679 product URL có lỗi title/meta đã fill A-K, helper cột L (Len Title) + M (Len Meta) auto-count với conditional format 🟢🟡🔴. Khi gen → push F/G/H.
- Tab `"W2/M5"` (sheet 1Pta9sA9Aq9Pva6uDpmqjn7RA4h07Sn6wDquwC81KWTE gid 103516100): báo cáo tuần đã fill cột K (Thứ 7 16/5) cho row 9, 10, 12, 15.

### Provider/quota state
- **Codex Plus**: hết quota, reset 22/5 (weekly limit)
- **Gemini 2.5-flash free**: hết 20 RPD hôm nay 16/5
- **Gemini 2.0-flash free**: 200 RPD (chưa thử nhưng phỏng đoán cũng share quota với 2.5)
- **Anthropic API**: chưa setup credit, KHÔNG có `ANTHROPIC_API_KEY` trong `.env`

## 📅 Tuần này (12/5 - 18/5)

### Thứ 7 (16/5) — TODAY

- ✅ **Sheet ops + reports + Haravan ops** (session sau /clear lần 1, 16/5 16:30-21:00):
  - **Chèn 6 ảnh CDN `_grande` 600x388 vào mô tả SP Card Zotac RTX 4070 Super Twin Edge** (haravan_id 1056283679)
    - Pattern feedback_image_pattern.md: URL gốc + suffix `_grande` + inline CSS object-fit:contain bg:#fff
    - Body 38,200 → 40,325 chars (+2,125), 6 `<img>` mới với ALT 6 vị trí
    - Section heading "Hình ảnh thực tế Zotac RTX 4070 Super Twin Edge" (H2 17pt bold)
    - PUT Haravan API thành công, verify admin OK (public chờ CDN purge 1-5 phút)
  - **Push 1679 product URL có lỗi title/meta vào Sheet "Meta des + Title Errors"** (gid 971701509)
    - Schema 11 cột (A loại lỗi/B URL/C tên/D-E title-meta hiện tại/F-G đề xuất/H trạng thái/I-J apply date/K chồng iu)
    - Sort: nhiều issue trước + score asc (worst at top)
    - Cột A đổi từ join "|" → bullet list xuống dòng, wrap text TOP
    - Helper cột L (Len Title) + M (Len Meta) auto-count + conditional format (45-58 🟢/59-61 🟡/>61 🔴; 140-160 🟢/161-180 🟡/>180 🔴)
  - **Refactor `/seo/title-meta` flow** (xem entry chi tiết bên dưới)
  - **Multi-provider switching** Codex ↔ Gemini (xem entry bên dưới)
  - **Fill weekly report W2/M5 cột K (Thứ 7)**: 4 cell K9/K10/K12/K15 (Content sp mới + Audit + Cấu trúc web + AI Training)

- ✅ **Multi-provider switching Codex CLI ↔ Gemini API** (Codex Plus quota hết, vợ thử Gemini → revert vì free tier hẹp):
  - **TẠO MỚI** `marketing_hub/gemini_provider.py` (129 dòng) — mimic pattern codex_provider.py với google-genai SDK v2.3.0:
    - `is_gemini_available()`, `call_gemini(system_prompt, user_prompt, model, timeout, temperature)`
    - `GeminiRateLimitError` exception (catch 429 RESOURCE_EXHAUSTED)
    - Load `GOOGLE_API_KEY` từ env hoặc `.secrets/google.env`
    - DEFAULT_MODEL = "gemini-2.0-flash" (free 200 RPD) hoặc "gemini-2.5-flash" (free 20 RPD)
  - **`seo.py:_gen_title_meta_with_angle`** swap provider:
    - Sáng: Codex → Gemini (test 5/5 SP success với prompt mới + retry 4)
    - Tối: revert về Codex (vì Gemini 2.5-flash chỉ 20 RPD, không đủ 1679 SP)
    - **Hiện tại**: dùng Codex (đợi reset 22/5)
  - **Prompt tighten**: thêm 3 ví dụ Title length + 2 ví dụ Meta length đẹp + quy trình "draft→đếm→cắt→đếm lại" + mẹo căn 145-158c
  - **Retry logic**: 1 → 4 lần với hint feedback cụ thể (lần trước title=Xc fail vì..., meta=Yc fail vì..., viết khác)
  - Template `seo_title_meta.html` 3 chỗ text: hiển thị Codex CLI / "Codex Plus quota hết" trong popup
  - Verify gen 5 SP với Gemini 2.0-flash + retry 4: **5/5 success** (vs 30-50% trước fix), avg 1.8 attempt/SP

- ✅ **Refactor `/seo/title-meta` — bỏ PUT Haravan, gen → push thẳng Sheet F/G/H** (vợ chốt flow an toàn):
  - Approach: streaming push Sheet (gen xong 1 SP push ngay, không đợi batch) + **5 angle rotate deterministic**
    (`SPEC / USE_CASE / AUDIENCE / PAIN_POINT / COMPARISON` pick theo `hash(url) % 5` → cùng URL → cùng angle)
    + **anti-dup** (pass `recent_titles` deque(10) vào prompt + post-validation `SequenceMatcher` ≥80% retry 1 lần)
    + **quota detect** (catch `CodexRateLimitError` → set `quota_hit=True` + auto stop + popup browser alert).
  - **TẠO MỚI** `marketing_hub/sheet_writer.py` (145 dòng) — module tách logic Google Sheets:
    `_build_url_to_row_index()` cache 1680 URL→row (TTL 5 phút), `push_proposal(url, title, meta, status)` update F/G/H,
    `read_proposal(url)` verify. Token reuse từ `.secrets/google_token.json` (đã có sẵn từ GSC + push 269).
  - **SỬA** `marketing_hub/seo.py` (2379→2749, +370 dòng):
    - GIỮ NGUYÊN `fix_title_meta_for_url()` + `_gen_title_meta_via_codex()` (legacy reference / future Apply)
    - THÊM `_pick_angle_for_url(url)` MD5-based deterministic (verified 20-sample: SPEC=3, USE_CASE=5, AUDIENCE=6, PAIN_POINT=4, COMPARISON=2)
    - THÊM `_gen_title_meta_with_angle()` + `_ANGLE_INSTRUCTIONS` dict 5 prompt blocks + `_ANGLE_DEFAULT_CTA` mapping
    - THÊM `_validate_gen_output()` length (45-58 / 145-158) + similarity check
    - THÊM `_fetch_product_desc_snippet()` lấy 200c body_html Haravan (best-effort)
    - REPLACE `_title_meta_fix_state` → `_title_meta_gen_state` thêm fields `quota_hit`, `last_gen_title`, `last_gen_meta`, `last_gen_angle`
    - REPLACE `run_title_meta_fix_all` → `run_title_meta_gen_all` streaming + 1s delay/Sheet write (tránh 429)
    - RENAME `start_title_meta_fix_all_async` → `start_title_meta_gen_all_async`, `stop_title_meta_fix` → `stop_title_meta_gen`, `title_meta_fix_state` → `title_meta_gen_state`
  - **SỬA** `marketing_hub/app.py` (+3 dòng): GIỮ `/seo/title-meta/fix` (legacy fallback), rename
    `/seo/title-meta/fix-all/{start,stop}` → `/seo/title-meta/gen/{start,stop}` +
    `/api/seo/title-meta/fix-all/status` → `/api/seo/title-meta/gen/status`. Page render dùng `gen_state` thay `fix_state`.
  - **REFACTOR** `marketing_hub/templates/seo_title_meta.html` (502→489, -13 dòng):
    - XÓA per-row "🔧 Auto-fix" + bulk "🚀 Auto-fix tất cả" + "⏹️ Dừng job" cũ
    - THÊM "✨ Gen title+meta vào Sheet" + "⏹️ Dừng Gen" + link "📊 Mở Sheet"
    - Status bar realtime hiển thị `last_gen_title` + `last_gen_angle` (badge OK gắn ✨ ANGLE_NAME per row)
    - Popup `alert()` 1 lần khi `quota_hit=true` ("Codex Plus đã hết quota. Đợi reset ~5h...")
    - Polling 3s, rename JS `startFixAllJob`→`startGenJob`, `stopFixAllJob`→`stopGenJob`
  - **VERIFY**:
    - `_pick_angle_for_url`: 20 URL → distribution {AUDIENCE:6, USE_CASE:5, PAIN_POINT:4, SPEC:3, COMPARISON:2} ✓ phân bố cả 5
    - Determinism: cùng URL gọi 2 lần → cùng angle ✓
    - `sheet_writer.get_url_row_index(url_thật)` → row 2 ✓ (1680 URL trong sheet, cache build OK)
    - `sheet_writer.push_proposal` + `read_proposal` round-trip cell F/G/H thật trên Sheet ✓ (cleanup OK)
    - Flask restart qua VBS (PID 17412 port 5055) + 4 route 200:
      - GET `/seo/title-meta` → 200 ✓
      - GET `/api/seo/title-meta/gen/status` → 200 ✓ JSON đủ fields (`running, total, success, failed, current_url, quota_hit, last_gen_title, last_gen_angle, ...`)
      - POST `/seo/title-meta/gen/start` body `{type:product, issue:meta_long}` → `{ok:true, message:"Đã start job gen vào Sheet"}` (queue 1679 SP, skip 422)
      - POST `/seo/title-meta/gen/stop` → `{ok:true}`
    - **Quota detect end-to-end**: Codex thật đã hết quota (reset 22/5) → start job → fail 1/1 SP đầu →
      `quota_hit=true`, `running=false`, `message="⚠️ Codex Plus quota hết — auto stop"`, loop break đúng ✓
  - KHÔNG modify `db.py` (không cần DB column mới). KHÔNG commit. Đợi vợ confirm/test.

- ✅ **Swap provider Codex → Gemini API tạm (Codex quota Plus reset 22/5)**:
  - **TẠO MỚI** `marketing_hub/gemini_provider.py` (122 dòng) — adapter pattern y hệt `codex_provider.py`:
    `is_gemini_available()` check SDK + key, `call_gemini(system, user, timeout, model, temperature)` gọi
    `client.models.generate_content()` qua `google.genai`, `GeminiRateLimitError` cho quota detect
    (patterns: rate limit / quota exceeded / resource_exhausted / 429 / too many requests).
    Default model `gemini-2.5-flash`, load key từ env `GOOGLE_API_KEY` → fallback `.secrets/google.env`.
  - **SỬA** `marketing_hub/seo.py` (+5 dòng net) — chỉ replace provider trong gen flow MỚI, GIỮ NGUYÊN legacy:
    - `_gen_title_meta_with_angle()`: `import codex_provider` → `import gemini_provider`,
      `call_codex(...)` → `call_gemini(...)`, catch `CodexRateLimitError` → `GeminiRateLimitError`.
      Prompt 5 angle + anti-dup logic GIỮ NGUYÊN 100%.
    - `run_title_meta_gen_all()`: catch + message "⚠️ Gemini quota hết — auto stop" (thay "Codex Plus").
    - `_gen_title_meta_via_codex()` legacy (line 1731) GIỮ NGUYÊN — dùng cho `/seo/title-meta/fix` single-URL.
  - **PKG**: `pip install google-genai` (v2.3.0) — `google.generativeai` cũ deprecated.
  - **VERIFY**:
    - Smoke test `python marketing_hub/gemini_provider.py` → `Available: True` + Output JSON ✓
    - Gen 1 SP thật (`vo-case-magic-gm-08l-pro-m-atx-...`) angle COMPARISON → ok=True, title 60c, meta 187c
      (validate fail length, retry pipeline hoạt động đúng).
    - Gen + push Sheet thật cho `ram-may-tinh-kingston-fury-beast-black-16gb-3200mhz-...`:
      angle=USE_CASE, title 58c "Kingston Fury Beast Black 16GB 3200MHz DDR4: Tối ưu Gaming",
      meta 157c "RAM Kingston Fury Beast Black 16GB 3200MHz DDR4 nâng tầm trải nghiệm gaming…
      KHÁM PHÁ NGAY tại Sintech." → validate=True → push_proposal cell F/G/H row 3 → `read_proposal` round-trip OK ✓
    - Flask restart VBS hidden → `GET /seo/title-meta` 200 ✓
  - **Trade-off**: Gemini 2.5-flash có xu hướng viết meta > 160c hoặc < 140c thường xuyên hơn Codex
    (~3-4/5 SP fail validate lần đầu, retry 1 lần thường vẫn fail). Sau 22/5 nên switch lại Codex,
    hoặc nếu muốn dùng Gemini lâu dài thì cần tighten prompt length constraint + nâng số retry attempts.
  - KHÔNG commit. KHÔNG modify file ngoài scope.

- ✅ **Refactor C — unify 2 hệ thống chấm điểm thành `scoring_core.py`** (backward compat verified):
  - Tách `marketing_hub/scoring_core.py` (~600 dòng) — module pure chứa 6 score function dùng chung:
    `score_title` / `score_meta` / `score_structure` / `score_links` / `score_readability` /
    `score_sintech_sections` / `score_technical_seo`. Mỗi function nhận `max_score` weight để caller scale.
  - `seo_quality.py:rate_content()` refactor 100% → delegate sang scoring_core. Output schema GIỮ NGUYÊN
    (`score/max/tier/breakdown.{title,meta,structure,links,readability}/issues_high/med/low/readability`).
    UI templates 3 trang (content-jobs/blog/collection) KHÔNG đổi.
  - `seo.py`: chuyển import `readability_score` từ `seo_quality` → `scoring_core` (loại circular dep tiềm ẩn),
    re-export `readability_score = readability_metrics` để backward compat.
  - Verify content_jobs: chấm 12 sample → avg Δ(new vs old algorithm) = **+0.00**, max |Δ| = **0** (bit-identical).
    Δ vs DB stored = -2.4 trung bình (DB từ revision cũ với 6 category 'content' tách riêng — expected).
  - Verify crawl seo_pages: re-fetch 5 URL → schema check pass (only `desc_h1_scanned_at` extra, intentional),
    avg Δ = +5.2 (real pages updated since DB last crawl — expected).
  - Flask restart qua VBS wrapper: tất cả route 200 (`/`, `/seo`, `/seo/rules`, `/content-jobs`,
    `/blog-content`, `/collection-content`) + detail page (`/content-jobs/315`, `/blog-content/229`,
    `/collection-content/60`) cũng 200. KHÔNG commit.
  - Files: TẠO `scoring_core.py` (779 dòng), SỬA `seo_quality.py` (285→155 dòng, -130), `seo.py` (2372→2379, +7 dòng import).

- ✅ **Refactor scoring engine `seo.py` — 4 fix A/B/D/E nâng max thực tế 85→100đ**:
  - [x] **Fix A — Cộng điểm Sintech-specific (+15đ cho product)**: thêm 5 hidden_pass rule
    `sintech_section_ok` (+4) / `meta_cta_ok` (+3) / `faq_ok` (+3) / `signature_ok` (+3) / `real_experience_ok` (+2).
    Trước đây 5 rule này chỉ flag warn/info → giờ pass thì cộng điểm. Thêm rule `missing_signature` info-only.
  - [x] **Fix B — Tích hợp readability (+10đ)**: import `readability_score()` từ `seo_quality.py`.
    Map: ≥70→+10, ≥55→+7, ≥40→+4, <40→0 + issue warn. Skip nếu word_count <50. Thêm rule `readability_ok` (hidden_pass) + `readability_weak` vào config.
  - [x] **Fix D — Word count threshold theo url_type**: thay logic cứng (low<500 / thin<800) bằng map theo type.
    blog: 700/1500 | product: 500/800 (giữ) | collection: 150/300 | page+other: 500/800.
    Đưa vào config key `word_count_thresholds` qua helper `_word_thresholds(url_type)`.
  - [x] **Fix E — Dup title/meta cross-site post-process**: function mới `recompute_dup_flags()`.
    Group theo normalized title (strip suffix ` - Sintech`) + meta, ≥2 page = dup, trừ -5/-5 (cap -10), thêm issue `dup_title`/`dup_meta` liệt kê tối đa 3 URL trùng. Có logic restore điểm cho page không còn dup nữa khi re-run.
    Expose route mới `POST /seo/recompute-dup` (`app.py`) trả JSON stats.
  - Config `data/seo_rules_config.json` bump `version: "2026-05-16-1"`, thêm 9 rule mới + key `word_count_thresholds`.
  - **Stats sample re-analyze 10 product page**: avg **76.6** (62-82) vs DB cũ max 75đ — confirm cộng điểm mới hoạt động.
  - **recompute_dup run đầu**: dup_title_count=0, dup_meta_count=3 group, affected_pages=7, total_deducted=35.
  - **DB stats 2460 page 2xx**: avg before 62.06 → after recompute 62.04 (chỉ recompute_dup, chưa re-crawl). Distribution 50-65: 1284 | 65-80: 1169. Sau khi re-crawl đại trà sẽ dịch lên ~70-90.
  - Files modified: `seo.py` (+~110 dòng), `app.py` (+10 dòng route), `data/seo_rules_config.json` (+~95 dòng).
  - Verify: Flask restart qua VBS (port 5055 HTTP 200), route `/seo/recompute-dup` trả JSON valid. KHÔNG commit (vợ review trước).

### Thứ 6 (15/5)

- ✅ **Bỏ scoring dựa trên word count + thêm toolbar Căn giữa đồng bộ 3 trang** (theo yêu cầu vợ — bài AI sẽ không bị loãng do ép wordcount):
  - `seo_quality.py`: bỏ category "content" (30 điểm chấm theo target wordcount). Redistribute → title 20, meta 20, structure 25 (+ thin content gate <100 từ), links 15, readability 20 = 100
  - 3 writer (`content_writer`/`collection_content_writer`/`blog_content_writer` + `ai_writer.py`): bỏ ép độ dài cụ thể (cũ "800-2700 từ", "600-1200", "1500-3000") → đổi sang "viết đủ ý theo cấu trúc, hết ý thì dừng, không lặp/filler"
  - Toolbar WYSIWYG: thêm 3 nút **⬅ Trái / ⬌ Giữa / ➡ Phải** cho cả `/collection-content` + `/blog-content` + `/content-jobs` (detail) — helper `alignText(dir)` smart: nếu selection đang trong `<td>/<th>` → set `text-align` trên cell đó (giữ inline style cho Haravan); ngoài table → dùng `execCommand justifyXxx`
  - `/content-jobs` detail trước đây thiếu toolbar format → thêm full toolbar (B/I/U/S, H2/H3, list, align, link, color, undo/redo) + ẩn khi switch sang Edit raw HTML
  - List page bỏ logic màu cột word count (good/warn/bad theo threshold): `content_jobs_list.html` + `blog_content.html` chỉ hiển thị số neutral, không đánh giá
  - Restart Flask (PID 25004) → 5 category total = 100 verified

- ✅ **Trang `/blog-content` quản lý + gen content cho blog/news** (mới, mirror pattern `/collection-content`):
  - DB table `blog_jobs` schema đầy đủ (haravan_article_id/blog_id, edited_*, status, quality_score, click/imp/pos)
  - Routes app.py: `/blog-content` (list), `/blog-content/<id>` (detail WYSIWYG), `/blog-content/<id>/gen|save|sync`, `/blog-content/sync-all`
  - Templates: `blog_content.html` (KPI + cột Title/Meta len + Words + ⭐ Q + 📖 R + 👆 GSC click + 📊 Pos), `blog_content_detail.html` (WYSIWYG editor giống collection)
  - Writer `blog_content_writer.py`: Codex CLI sinh blog 1500-3000 từ (intro + 4-6 H2 + FAQ + outro + signature Sintech), CTA HOA, prohibit filler "bền bỉ"/"tốt nhất 2026", ép ≥3 internal link
  - Sync PUT `/blogs/{blog_id}/articles/{article_id}` với body_html + metafields title/desc, GIỮ slug (không đổi field `title`)
  - **Seeder `_seed_blog_jobs.py` v2**: pull từ `seo_pages` (229 URL crawled) thay vì Haravan API (vì `/blogs.json` 502) — cross-match GSC → 69/229 bài có click data
  - **Top traffic**: PC bị giật điện (85 click pos 4.9), Command Prompt tự mở (61 click), Bảng mã Mainboard Huananzhi x99 (56 click)
  - Restart Flask qua VBS wrapper (PID 17460) sau khi sửa code; routes verify 200

### Thứ 5 (14/5)

- ✅ **Trang `/seo/gsc` Google Search Console hub** (mới):
  - Fetch + cache 2 sheet GSC export (Performance + Coverage) vào `data/gsc_cache.json`
  - 8 task action với count + URL list chi tiết (404=664, crawled-not-indexed=1465, noindex=188, discovered=60, duplicate-canonical=11, CTR thấp, pos 11-20, cash cow)
  - Fetch 1923 URL list từ 5 drilldown sheets vợ export
  - KPI bar, top 10 keyword, top 10 URL preview
  - Routes: `/seo/gsc`, `/seo/gsc/task/<id>`, `/seo/gsc/refresh`
  - Files: `seo_gsc.html`, `seo_gsc_task.html`, `_fetch_gsc_cache.py`, `_fetch_gsc_url_lists.py`

- ✅ **Trang `/collection-content` (tạm) cho gen content collection** (mới):
  - DB table `collection_jobs` — seed 136 URL từ tab Carte chưa có Date up
  - Codex CLI gen title + meta + body_html (rule SEO Sintech adapted cho collection)
  - Detail page với rich-text WYSIWYG editor (contentEditable)
  - **Nút 🎨 Format full**: áp font Arial 12pt weight 500, H2 17pt, H3 13pt, link đỏ #e74c3c bold underline, viền bảng 1px #ccc, list 12pt
  - Compress HTML aggressive (strip Google Doc inline styles defaults) → giảm 30-70% size
  - Haravan body_html limit ~50,000 chars — cảnh báo realtime raw → compressed
  - PUT smart_collection/custom_collection
  - Files: `collection_content.html`, `collection_content_detail.html`, `collection_content_writer.py`, `collection_writing_rules.md`

- ✅ **Port SEO Machine module**: Readability VN + SEO Quality Rater 0-100:
  - `seo_quality.py` — 6 category (content, title, meta, structure, links, readability)
  - VN-specific: passive voice (được/bị), filler list cấm, complex sentence (>25 từ)
  - Auto-compute on save edit → DB column quality_score, readability_score, quality_breakdown
  - Bulk score 314 content_jobs (avg 87.8/100) + 4 collection_jobs (avg 88-96)
  - UI: list page thêm cột ⭐ Quality + 📖 Read, detail page hiện 6 mini cards + issues_high/med

- ✅ **Sync sheet Carte vs Haravan collections** (210 smart collections):
  - Backup tab Carte_bak_20260514_154737 (giữ rich-text hyperlinks F)
  - Fill 95 URL match, xóa 51 row không match, add 58 Haravan mới
  - Resync giữ thứ tự backup → preserve Doc hyperlinks cột F

- ✅ **Excel báo cáo Sintech `BaoCaoTuan_Sintech_v3_DEMO_20260514.xlsx`** (5 sheet với formula + chart + conditional format)

- ✅ **Fix nhiều bug:**
  - `**read` override `score` của breakdown → quality > 100
  - Word count branch sai (2457>1500 báo "hơi ngắn")
  - Sync fail nhưng status giữ 'synced' → reset 'failed'
  - "Mô tả quá dài" Haravan 50k → compress aggressive (Google Doc CSS defaults)
  - `event.target` undefined khi `saveEdit()` chain từ `syncJob()` → pass `this` qua param

- ✅ **Phân tích SEO Machine README** (TheCraigHewitt/seomachine) → đề xuất 5 module port, Phase 1 done

### Thứ 3 (12/5)
- ✅ **Tab `/seo/rules`** UI quản lý SEO rules (option C đầy đủ):
  - Config JSON `data/seo_rules_config.json` 47 rules + thresholds good/ok
  - Mỗi rule: enabled, level, score, threshold, msg template, applies_to
  - UI table edit inline + nút Lưu
  - Atomic write + auto-reload config (cache mtime)
  - Phase 1 wrap: 8 rule chính (title/meta/h1) đã apply config; 39 rule còn lại hardcoded nhưng vẫn disable được qua `enabled` flag
- ✅ **Phase 1 crawl audit + fix** (combo A+B+C):
  - **A (Score):** fix `sintech_in_title` false positive (regex bỏ suffix Haravan " - Sintech"); adjust threshold "good ≥65" cho Sintech-on-Haravan (cũ ≥80, max page chỉ đạt 70)
  - **B (URL miss):** sitemap có 2423 URLs, DB chỉ 1120 (46%) → last run failed midway, miss 847 product + 229 blog + 209 collection
  - **C (Speed):** WORKERS 8→20, DELAY_PER_WORKER 0.25→0.05, TIMEOUT 15→12s, batch DB progress 20→50 → expected ~4-6x nhanh hơn
  - Em re-run crawl ngon nha
- ✅ **Broken link check tăng tốc 5-8x** (combo B): WORKERS 8→30, TIMEOUT 15→8s, HEAD-only (chỉ retry GET cho 405/403), batch DB write 50/transaction, host circuit breaker, dedup targets. File modified: `seo.py` + `db.py:seo_link_status_update_batch`
- ✅ Resume Haravan (xóa pause flag) sau khi vợ confirm
- ✅ Setup permission gate trong `haravan_client._check_permission()`:
  - BLOCK: `POST /products.json`, `DELETE /products/{id}.json`, `POST /blogs/*/articles.json`, `DELETE /articles/{id}.json`
  - ALLOW: GET, PUT/PATCH, POST `/products/{id}/images.json`, DELETE images
- ✅ Lazy upload pattern hoàn chỉnh:
  - `process_and_upload_images()` → save LOCAL `data/images/<handle>/img_N.jpg`
  - Flask route `/local-images/<handle>/<file>` serve trực tiếp
  - `upload_local_images_in_body_to_haravan()` chạy KHI bấm SYNC: scan body → upload Haravan asset_storage (sequential) → replace URL
- ✅ VBS hidden wrapper `_scripts/start_*_hidden.vbs` → Task Scheduler dùng `wscript.exe` thay batch trực tiếp → KHÔNG còn CMD window visible
- ✅ Fill weekly report sheet `W1/M5` (Thứ 7 + CN cho rows 9, 10, 15)
- ✅ Update WORKLOG.md + memory `project_status.md` (để recover context sau /clear)

## 📅 Tuần trước

Đã archive sang `docs/WORKLOG_ARCHIVE/`:
- [`2026-W1-M5.md`](docs/WORKLOG_ARCHIVE/2026-W1-M5.md) — Tuần 5-11/5 (CN bão lớn nhất 10/5, T7 9/5, T6 8/5)

## 📂 File modified gần đây (tuần này)

### `marketing_hub/haravan_client.py`
- Thêm `_check_permission()` block POST/DELETE SP+article
- Sửa `upload_to_asset_storage()` RAISE khi tất cả storage đầy (KHÔNG auto-create — tránh incident 10/5)
- `_create_new_asset_storage()` marked DEPRECATED auto-call

### `marketing_hub/content_writer.py`
- Thêm `IMAGES_LOCAL_DIR`, `_clean_product_name()`, `_gen_alt_for_position()`
- Refactor `process_and_upload_images()` → save LOCAL thay vì upload Haravan
- Thêm `upload_local_images_in_body_to_haravan()` — chạy khi SYNC
- Thêm `pick_target_image_count()`, `count_main_h2()`

### `marketing_hub/app.py`
- Route `/local-images/<handle>/<filename>` — Flask serve local images
- `content_jobs_sync()`: gọi `upload_local_images_in_body_to_haravan()` trước khi PUT
- `/content-jobs/<id>/toggle-money` endpoint
- Category filter trong `/content-jobs`

### `marketing_hub/_scripts/`
- `start_marketing_hub_hidden.vbs` — VBS wrapper hidden cho web
- `start_telegram_bot_hidden.vbs` — VBS wrapper hidden cho bot
- `run_backup.bat`, `backup_db.py` — DB backup daily
- `INSTALL.md` — hướng dẫn setup Task Scheduler

### Memory (`~/.claude/projects/.../memory/`)
- `feedback_haravan_permission.md` — permission gate + lazy upload + incident race condition
- `reference_marketing_hub_ops.md` — Task Scheduler 24/7 + bot self-service
- `project_status.md` (mới) — overview 4 mảng project

## 🏗️ State hệ thống

### Services
- 🟢 Web Flask `port 5055` — auto-start Task Scheduler (PID 14796 từ 12:11 PM 12/5)
- 🔴 Bot Telegram @Web_Sintech_bot — token revoked 401, vợ paste lại nếu cần
- 🟢 DB Backup — schedule 3AM daily, giữ 30 ngày, path `data/backups/posts_YYYY-MM-DD.db.zip`
- 🟢 Haravan API — RESUMED, permission gate active

### Storage Haravan (7 storage SP)
- 1074465986 (cũ, đầy 91/90)
- 1074494220, 1074495782, 1074495817, 1074495857, 1074495866, 1074495883 (sau incident)
- ⚠️ KHÔNG auto-create nữa — đầy = vợ tạo SP manual + paste haravan_id vào `state/asset_storage_product.json`

### Quyền Claude với Haravan
- ❌ Tạo SP / xóa SP / tạo article / xóa article
- ✅ PUT/PATCH SP+article, upload ảnh vào SP existing, GET *

## 📌 Quy ước update file này
1. Anh tự update CUỐI mỗi response khi vừa xong 1 milestone lớn (≥3 actions hoặc 1 commit-worthy change)
2. Move items từ "Đang dở" → "Hôm nay" khi xong
3. Mỗi cuối tuần (CN), move "Tuần này" → "Tuần trước"
4. Vợ có thể edit thẳng tay vào file này nếu thấy thiếu việc của vợ

---

## 📸 Checkpoint snapshot template (copy khi cần)

> Anh dùng template này TRƯỚC mỗi `/clear`, `/compact`, hoặc handoff task dài. Copy block dưới → fill → paste lên đầu section "Đang dở" hoặc commit riêng `git commit -m "checkpoint: <ngắn>"`.

```markdown
## 📸 Checkpoint YYYY-MM-DD HH:MM

### ✅ What completed (since last checkpoint)
- ...

### 🔴 Current blockers
- ...

### 📝 Modified files (uncommitted)
- `path/to/file` — gì đã đổi
- ...

### ⏭ Exact next action
- Bước cụ thể tiếp theo, không vague ("test", "review") mà cụ thể ("chạy `python X.py` rồi verify Y").

### 🔁 Resume prompt (paste vào session mới)
> "Tiếp tục task <tên>. Anh đã làm xong A+B, đang kẹt ở C vì <reason>. File modified: <list>. Next: <bước cụ thể>. Đọc WORKLOG.md checkpoint <timestamp> để full context."
```

**Quy ước:**
- Mỗi checkpoint = 1 commit riêng `git commit -m "checkpoint: <ngắn>"` để git log dễ scan
- KHÔNG tạo file riêng trong `checkpoints/` folder — append vào WORKLOG.md để 1 nguồn truth
- Sau khi session sau resume xong → có thể xóa checkpoint cũ (giữ ≤3 checkpoint gần nhất trong WORKLOG)
