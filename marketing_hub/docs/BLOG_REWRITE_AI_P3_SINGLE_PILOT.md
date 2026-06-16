# BLOG REWRITE AI — P3 SINGLE PILOT (10/6/2026)

> Theo spec `Desktop\Past.txt`. P3 = provider AI THẬT + prompt + parser + sanitize + quality, chạy **đúng 1 pilot bài #64**. **KHÔNG batch · KHÔNG Haravan PUT · KHÔNG apply · KHÔNG upload/rehost ảnh · KHÔNG commit/push/deploy.**

## 1. Master audit counts (từ DB local)
inventory 233 · rewrite_eligible **147** (139 image-high + 8 text-copy) · reverse-copy defense **3** (excluded) · selected 147.

## 2. Evidence export
- 8 text-copy: `docs/BLOG_TEXT_COPY_NEW_8_REVIEW.md` + `blog_text_copy_new_8_review.csv`.
- 3 reverse-copy: `docs/BLOG_REVERSE_COPY_DEFENSE_3.md` + `blog_reverse_copy_defense_3.csv`.
- Pilot #64 verify live: body còn **13× "GEARVN"** + 4 ảnh alt "GEARVN-..." + câu **"hãy cùng GEARVN tìm hiểu"** (bằng chứng copy).

## 3. DB status normalization (additive)
Cột mới: `rewrite_eligible`, `audit_text_copy`, `audit_reverse_copy` (+ `audit_risk/score/source/action/is_reverse/evidence` từ bước gộp).
- 8 text-copy: `selected=1, rewrite_eligible=1, risk_level='high', audit_text_copy=1`.
- 3 reverse: `selected=0, rewrite_eligible=0, audit_reverse_copy=1, status='reverse_copy_defense'` → **loại khỏi queue/generate**.

## 4. P2 readiness
| Hạng mục | Có thật | File | Chặn P3? |
|---|:--:|---|:--:|
| selection checkbox + top5/10/20 + clear | ✓ | template + blog_rewrite.py | không |
| job/draft/event table | ✓ | db.py | không |
| queue local + worker skeleton (sys.executable) | ✓ | run_blog_rewrite_worker.py | không |
| heartbeat / cancel / retry / stale recovery | ✓ | blog_rewrite.py | không |
| detail drawer + draft preview + event timeline | ✓ | template | không |
| apply guard (501) | ✓ | routes | không |
→ **P2 readiness PASS** — không thiếu component, build thẳng P3.

## 5. Provider adapter + config
Reuse `ai_provider.call_ai_single("claude", ...)` → `claude_provider` (Claude Code CLI qua subprocess). Health: available=True.
Config: provider=claude · model=claude-cli · batch_default=1 · **batch real tối đa 1 (pilot guard)** · retry=1 · timeout=300s · prompt_version=BLOG_REWRITE_PROMPT_V1.

## 6. Prompt / Parser / Sanitizer / Quality (`blog_rewrite_gen.py`)
- **BLOG_REWRITE_PROMPT_V1**: ép viết nguyên bản, cấm spin/paraphrase/giữ bố cục copy/giữ thương hiệu nguồn/bịa facts/đổi handle/publish, heading H2-H3, outline mới + title/meta options + summary + CTA. Output JSON strict.
- **Parser + repair**: trích JSON, validate (body_html non-empty, title/meta ≥3); lỗi → repair prompt 1 lần; lỗi nữa → candidate failed, KHÔNG lưu draft lỗi, KHÔNG fail job.
- **Sanitize (bs4 whitelist)**: chỉ p/br/h2/h3/ul/ol/li/strong/em/a/table.../blockquote/img; bỏ script/style/iframe/javascript:/data:/event handler; flag external link + external image (giữ URL, KHÔNG rehost — P4).
- **Quality**: word_count gốc/draft, heading count, normalized 5-gram overlap, longest_common_phrase, scorecard (originality/structure/coverage/html/links/manual_verification). overlap>0.15 → approval=review_required.

## 7. Worker generate THẬT
`run_blog_rewrite_worker.py` mở rộng: job.provider='mock' → mock; provider khác → `generate_real_draft` (fetch live read-only → prompt → claude CLI → parse+repair → sanitize → quality → save_real_draft). Spawn detached qua `sys.executable`. KHÔNG PUT/apply/upload.

## 8. PILOT — bài #64 (candidate 136)
- Đúng candidate: `audit_text_copy=1, audit_reverse_copy=0, selected=1`. Job #4 mode=single provider=claude (count=1).
- **KẾT QUẢ: completed 1/1.** Draft id 9 v1, approval=**draft_ready**.
  - Title mới: *"Linear, Tactile và Clicky Switch: Phân Biệt và Cách Chọn Đúng"* (khác bài gốc).
  - body_len 6355 · **5-gram overlap 1.7%** · longest_common_phrase 7 từ · **originality HIGH**.
  - 🟢 **"GEARVN" đã SẠCH khỏi draft** — AI gỡ hết dấu vết thương hiệu nguồn + alt ảnh đối thủ.
  - 0 external link flag. KHÔNG apply, KHÔNG PUT, KHÔNG upload ảnh.

## 9. UI review
Detail drawer: tab Tổng quan / Evidence / Traffic / **Draft AI** (title mới + options + outline + body preview) / **Quality** (overlap/longest phrase/word count/originality/link-image flags) / Lịch sử. Watermark **"DRAFT LOCAL — CHƯA APPLY HARAVAN"**. Apply disabled (P5/501).

## 10. QA
- compileall OK · node --check N/A (JS inline Jinja).
- Evidence export 8+3 ✓ · reverse-copy excluded khỏi queue ✓ · pilot single-only (guard real>1 reject) ✓.
- Worker spawn sys.executable ✓ · provider health ✓ · JSON parse ✓ · sanitize ✓ · quality metrics ✓ · draft saved ✓ · events saved ✓.
- Smoke 7 endpoint 200 ✓ · apply 501 ✓ · **Haravan PUT KHÔNG gọi** · **image upload KHÔNG gọi** · broken-link config **nguyên (48/8/4/2s)** · secret scan sạch.

## 11. Files
- **NEW**: `blog_rewrite_gen.py`, `docs/BLOG_REWRITE_AI_P3_SINGLE_PILOT.md`, evidence (2 MD + 2 CSV).
- **MOD**: `blog_rewrite.py` (create_job provider + save_real_draft), `routes/blog_rewrite.py` (provider-health + candidate draft + pilot), `_scripts/run_blog_rewrite_worker.py` (real mode), `templates/blog_rewrite_ai.html` (draft review).
- **Backup**: `_backup/blog-rewrite-p3-pilot-20260610-150640/`.

## 12. Deferred
- **P4**: review UI diff original↔draft đầy đủ + approve/reject thật + image rehost (download external → upload_asset → đổi src draft) + batch tăng dần (5/10).
- **P5**: apply (conflict content_hash + fetch live + backup payload + PUT Open API) + rollback per-bài.

## OUTPUT
**BLOG REWRITE AI P3 SINGLE PILOT COMPLETED** · inventory 233 · rewrite_eligible 147 · text-copy 8 · reverse-defense 3 (excluded) · provider claude-cli available · pilot #64 → draft_ready, overlap 1.7%, originality high, GEARVN sạch · apply blocked 501 · no Haravan write / no upload / no bulk / broken-link untouched · no commit/stage/push/deploy/browser.
