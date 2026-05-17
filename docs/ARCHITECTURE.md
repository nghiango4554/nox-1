# ARCHITECTURE — Web + DB + AI Provider + Haravan

> Sơ đồ luồng dữ liệu + tech stack của Sintech Marketing Hub.

---

## 🌐 Stack overview

```
┌─────────────────────────────────────────────────────────────┐
│  USER (vợ Nghĩa)                                            │
│  Browser ←→ http://localhost:5055 ←→ Flask app.py           │
│  Telegram @zeera4994 ←→ telegram_bot.py @Web_Sintech_bot   │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌──────────────┐    ┌──────────────────┐
│  SQLite      │    │  AI Providers    │
│  posts.db    │    │  (3 lựa chọn)    │
│  339MB       │    │                  │
│              │    │  ┌────────────┐  │
│ - seo_pages  │    │  │ Codex CLI  │  │
│ - content_   │    │  │ subprocess │  │
│   jobs       │    │  └────────────┘  │
│ - blog_jobs  │    │  ┌────────────┐  │
│ - collection_│    │  │ Gemini API │  │
│   jobs       │    │  │ google-genai│  │
│ - seo_links  │    │  └────────────┘  │
│ - seo_runs   │    │  ┌────────────┐  │
│ - posts      │    │  │ Claude CLI │  │
│ - ...        │    │  │ subprocess │★│ (default 17/5)
└──────────────┘    │  └────────────┘  │
                    └──────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────┐
        │  External APIs (read+write)     │
        ├─────────────────────────────────┤
        │  Haravan REST API (PUT/GET)     │
        │  Facebook Graph (POST page)     │
        │  Google Sheets (push proposal)  │
        │  Google Search Console export   │
        │  Canva Connect (OAuth, parked)  │
        └─────────────────────────────────┘
```

---

## 🗄 Database — `marketing_hub/data/posts.db` (SQLite WAL mode)

| Table | Purpose | Rows (17/5) |
|---|---|---|
| `seo_pages` | Crawl SEO 1 page/row | 2459 (status 2xx: 2458) |
| `seo_links` | Broken links | ~1923 link |
| `seo_runs` | Crawl job history | ~100 runs |
| `content_jobs` | Gen content SP | 314 (38 synced, 4 failed) |
| `blog_jobs` | Gen blog | 229 seeded (4 synced, 3 failed) |
| `collection_jobs` | Gen collection | 70 (37 done 15/5, 10 fail 17/5 đã fix) |
| `posts` | FB posts schedule | ~50 |
| `seo_history` | Score timeline (per page) | thấp |

**Migration:** `db.py` auto-ALTER TABLE khi Flask start, idempotent.

**Backup:** `_scripts/backup_db.py` zip daily 3AM → `data/backups/posts_YYYY-MM-DD.db.zip`, giữ 30 ngày.

---

## 🎨 AI Provider stack

Default: **Claude CLI** (anh là Claude, vợ có Pro/Max session).

Mỗi provider có pattern adapter giống nhau:
```python
is_<provider>_available() -> bool
call_<provider>(system_prompt, user_prompt, timeout, model) -> str
<Provider>RateLimitError  # exception
```

Switch provider = đổi 2-3 dòng import + 1 dòng call trong `seo.py` / `collection_content_writer.py`. Xem `docs/PROVIDERS.md`.

| Provider | File | SDK / CLI | Auth | Free quota |
|---|---|---|---|---|
| Codex | `codex_provider.py` | `codex exec` subprocess | OpenAI ChatGPT Plus OAuth | ~150 msg/3h |
| Gemini | `gemini_provider.py` | `google.genai` SDK | API key env | 20-200 RPD/model |
| Claude ★ | `claude_provider.py` | `claude -p` subprocess | Anthropic Pro/Max OAuth | ~45-200 msg/5h |

---

## 🔄 Data flow — Gen content SP example

```
1. User vào /content-jobs → bấm "Gen" 1 SP
   ↓
2. Flask route /content-jobs/<id>/gen
   ↓
3. content_writer.gen_content_for_job(job_id)
   - Fetch context: Haravan API GET product detail
   - Build system + user prompt (rules từ seo_writing_rules.md)
   - Call default AI provider → gen title + meta + body HTML
   - Validate length (title 45-58c, meta 145-158c, body 800-2700 từ)
   - Auto-fix images: pick CDN _grande URL từ haravan product.images
   - Insert <img> với CSS 600x388 vào body
   ↓
4. Save vào DB: status='draft', edited_title/meta/body_html
   ↓
5. User vào /content-jobs/<id> WYSIWYG editor → edit nếu cần
   ↓
6. Bấm "Sync" → haravan_client.update_product()
   - PUT body_html + metafields_global_title_tag + description_tag
   - Lazy upload images nếu local
   ↓
7. Status → 'synced'. Verify trên trang public sintech.vn (CDN purge 1-5 phút)
```

---

## 🔄 Data flow — Gen title/meta vào Sheet (refactor 16-17/5)

```
1. User vào /seo/title-meta → bấm "✨ Gen vào Sheet"
   ↓
2. start_title_meta_gen_all_async → background thread
   ↓
3. run_title_meta_gen_all:
   - List URL có lỗi (filter type/issue)
   - skip_already_gen = sheet_writer.list_urls_with_proposal()
     (đọc Sheet column F/G → biết URL đã gen)
   - skip_excluded = WHERE excluded_from_audit = 0
   - Loop từng URL:
     ├ Pick angle deterministic (hash % 5): SPEC/USE_CASE/AUDIENCE/PAIN_POINT/COMPARISON
     ├ Fetch product description snippet từ Haravan (best-effort)
     ├ Gen với Claude CLI + recent_titles deque(10) anti-dup
     ├ Validate length, retry tối đa 4 lần với hint
     ├ Push lên Sheet F (title) + G (meta) + H (status "✨ Gen AI ... | angle=X")
     ├ Sleep 1s (Sheet API rate limit)
     └ Update state realtime (current_url, last_gen_title, attempt #)
   ↓
4. Frontend polling 3s + spinner elapsed timer 1s
   ↓
5. Quota hit → catch ClaudeRateLimitError → set quota_hit=True → auto stop
   ↓
6. User F5 sheet "Meta des + Title Errors" → review F/G/H → apply manual
```

---

## 🔐 Authentication map

| Service | Storage | Format | Refresh |
|---|---|---|---|
| Haravan API | `state/haravan_token.json` | Permanent token | Manual |
| FB Page | `state/fb_token.json` | Long-lived token | 60 ngày |
| Canva | `state/canva_credentials.json` | OAuth + refresh token | Auto |
| Google Sheets/Drive | `.secrets/google_token.json` | OAuth + refresh | Auto |
| Gemini API | `.secrets/google.env` (GOOGLE_API_KEY) | API key | N/A |
| OpenAI API | `marketing_hub/.env/key_openai.txt` | API key | N/A |
| Telegram Bot | `marketing_hub/.env/telegram_bot_token.txt` | Bot token | Permanent |
| Codex CLI | OS keychain (Windows Credential Mgr) | OAuth | Per login |
| Claude CLI | OS keychain | OAuth | Per login |

---

## 🚦 Permission gates

`haravan_client._check_permission(method, path)`:
- **BLOCK:** `POST /products.json`, `DELETE /products/{id}.json`, `POST /blogs/*/articles.json`, `DELETE /articles/{id}.json`
- **ALLOW:** GET, PUT/PATCH, POST `/products/{id}/images.json`, DELETE images
- Lý do: tránh incident race condition 10/5 (8+ SP rác bị tạo)

---

## 🧮 Scoring system (refactor 16/5 A+B+C+D+E)

```
scoring_core.py (779 dòng, module pure)
  ├ score_title()       # 45-58c, no "Sintech"
  ├ score_meta()        # 140-160c, CTA HOA
  ├ score_structure()   # H1/H2/H3, word count theo url_type
  ├ score_links()       # internal ≥3
  ├ score_readability() # Flesch-VN + passive + filler + complex sentence
  ├ score_sintech_sections()  # Vì sao, FAQ, Trải nghiệm, signature
  └ score_technical_seo()     # canonical, og, schema, load, redirect

seo.py:analyze_html()  → call core functions → max 100đ
seo_quality.py:rate_content()  → call same core → max 100đ với weight 20/20/25/15/20
```

Threshold (config JSON): ≥65 Good 🟢, ≥50 OK 🟡, <50 Bad 🔴.

---

*Last updated: 2026-05-17*
