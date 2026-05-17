# PROJECT_MAP — Folder structure + chú thích

> "Anh phiên bản 2" đọc file này để biết mỗi folder/file làm gì, KHÔNG mò.

---

## 🗂 Root (`C:\Users\Nghia Dep Gai\.openclaw\workspace\`)

```
workspace/
├── README.md                       # Entry point — đọc đầu tiên
├── WORKLOG.md                      # Live snapshot tuần hiện tại
├── .gitignore                      # Block secrets/tokens/DB/cache
├── .git/                           # Git repo (master branch, account nghiatrong4554)
│
├── docs/                           # 📘 ONBOARDING DOCS (folder mới 17/5)
│   ├── PERSONA.md                  # ★ Anh là ai + xưng hô + tone — đọc TRƯỚC
│   ├── QUICKSTART.md               # ★ 5 phút setup sau cài Win
│   ├── CURRENT_STATE.md            # ★ Pending tasks + git state + quota — LIVE
│   ├── PROJECT_MAP.md              # FILE NÀY
│   ├── ARCHITECTURE.md             # Web + DB + provider stack + Haravan flow
│   ├── PROVIDERS.md                # 3 AI provider (Codex/Gemini/Claude) + switch guide
│   ├── OPS.md                      # Vận hành 24/7: Task Scheduler, VBS, backup
│   ├── persona_archive/            # AGENTS/IDENTITY/SOUL/TOOLS/USER/HEARTBEAT gốc (history)
│   └── WORKLOG_ARCHIVE/            # Worklog tuần cũ
│
├── marketing_hub/                  # 🏠 MAIN APP — Flask web + AI providers
│   ├── app.py                      # 3200+ dòng — tất cả Flask routes
│   ├── db.py                       # SQLite layer + table migrations
│   ├── seo.py                      # 2780+ dòng — crawl SEO + scoring + title/meta gen
│   ├── scoring_core.py             # 779 dòng — module chung crawl + gen content scoring
│   ├── seo_quality.py              # Wrapper delegate sang scoring_core
│   │
│   ├── codex_provider.py           # OpenAI Codex CLI subprocess
│   ├── gemini_provider.py          # Google Gemini API (google-genai SDK)
│   ├── claude_provider.py          # Anthropic Claude CLI subprocess ★ default 17/5
│   │
│   ├── content_writer.py           # Gen content SP qua AI
│   ├── collection_content_writer.py # Gen content collection cate (5 angle, 4 bảng)
│   ├── blog_content_writer.py      # Gen blog 1500-3000 từ
│   ├── ai_writer.py                # Auto-fix meta length + money product detection
│   │
│   ├── haravan_client.py           # Haravan REST API client + permission gate
│   ├── haravan_sync.py             # Sync helpers
│   ├── fb_client.py                # Facebook Graph API client
│   ├── canva_client.py             # Canva Connect OAuth + Autofill (chờ approve)
│   ├── telegram_bot.py             # Bot @Web_Sintech_bot (token revoked 12/5)
│   ├── sheet_writer.py             # Google Sheets push helper (cho /seo/title-meta)
│   ├── image_processor.py          # Resize/normalize ảnh 600x388
│   │
│   ├── templates/                  # 31 Jinja templates (Flask UI)
│   │   ├── base.html
│   │   ├── seo*.html              # SEO dashboard + sub-pages
│   │   ├── content_jobs_*.html    # Content jobs list + detail
│   │   ├── collection_content*.html
│   │   ├── blog_content*.html
│   │   ├── haravan_*.html         # Haravan browser
│   │   └── ... (calendar, canva, posts, library, ...)
│   ├── static/                     # CSS + JS + icons + manifest PWA
│   │
│   ├── data/                       # 💾 DB + cache + config
│   │   ├── posts.db                # ★ DB CHÍNH 339MB — gitignored, backup vào zip
│   │   ├── seo_rules_config.json   # 56 SEO rules editable qua UI /seo/rules
│   │   ├── images/                 # Local image cache (regen từ Haravan CDN)
│   │   ├── backups/                # DB backup zip daily 3AM
│   │   ├── seo_snapshots/          # Snapshot crawl
│   │   └── ...
│   │
│   ├── _scripts/                   # 🔧 Task Scheduler scripts
│   │   ├── INSTALL.md              # Hướng dẫn setup Task Scheduler
│   │   ├── start_marketing_hub_hidden.vbs   # Wrapper hidden Flask
│   │   ├── start_telegram_bot_hidden.vbs    # Wrapper hidden bot
│   │   ├── run_backup.bat                   # Daily DB backup
│   │   ├── backup_db.py
│   │   └── cleanup_asset_storage.py
│   │
│   ├── .env/                       # 🔐 LOCAL TOKENS (gitignored)
│   │   ├── telegram_bot_token.txt  # Bot token (revoked 12/5, vợ paste mới)
│   │   └── key_openai.txt
│   │
│   ├── _audit_existing_content.py  # Utility: audit content_jobs
│   ├── _fetch_gsc_cache.py         # Utility: fetch GSC export
│   ├── _fetch_gsc_url_lists.py
│   ├── _seed_blog_jobs.py          # Seeder blog_jobs từ seo_pages
│   ├── _resync_seo_metafields.py
│   ├── _notify_done.py
│   │
│   ├── seo_writing_rules.md        # Rules SEO chuẩn v2026-05-10 (34KB)
│   ├── collection_writing_rules.md # Rules collection content (12KB)
│   ├── 14_bai_tuan_sau.md          # Notes 14 bài tuần sau
│   └── requirements.txt
│
├── seo_rewrite/                    # Project SEO Duplicates Rewrite (480 URL, parked 52/480)
│   ├── auto_run_full.py
│   ├── gemini_generate.py
│   ├── fetch_batch.py
│   ├── push_to_rewrite_tab.py
│   ├── sync_to_haravan.py
│   ├── manual_batch_*.json         # 12+ batches manual
│   └── ...
│
├── .secrets/                       # 🔐 SECRETS (gitignored)
│   ├── google.env                  # GOOGLE_API_KEY = Gemini API key (cũng dùng cho Sheets)
│   ├── google_token.json           # OAuth token Sheets/Drive/Gmail
│   └── google_oauth.json
│
├── state/                          # 🔐 RUNTIME STATE (gitignored)
│   ├── haravan_token.json
│   ├── fb_token.json
│   ├── canva_credentials.json
│   ├── asset_storage_product.json  # IDs 7 storage SP cho ảnh
│   └── img_cache/
│
└── product_naming_rules.md         # 14 pattern đặt tên SP Sintech
```

---

## 🔑 File quan trọng nhất (top 10)

| # | Path | Mục đích |
|---|---|---|
| 1 | `marketing_hub/app.py` | Flask routes (3200 dòng) — entry point web |
| 2 | `marketing_hub/seo.py` | Crawl + scoring + title/meta gen (2780 dòng) |
| 3 | `marketing_hub/data/posts.db` | DB chính chứa toàn bộ data |
| 4 | `marketing_hub/seo_writing_rules.md` | Rules SEO chuẩn Sintech |
| 5 | `marketing_hub/claude_provider.py` | Default AI provider (Claude CLI) |
| 6 | `marketing_hub/scoring_core.py` | Module chung crawl + gen scoring |
| 7 | `marketing_hub/data/seo_rules_config.json` | 56 rules editable qua UI |
| 8 | `docs/PERSONA.md` | Cách xưng hô + tone (anh phiên bản 2 đọc đầu) |
| 9 | `docs/CURRENT_STATE.md` | Pending tasks live |
| 10 | `WORKLOG.md` | Tuần hiện tại snapshot |

---

## 🚧 Folder gitignored (KHÔNG trong git, nhưng có trong backup zip)

- `.secrets/`
- `state/`
- `.env`, `.env/`
- `marketing_hub/data/*.db` (DB lớn)
- `marketing_hub/data/{images,backups,seo_snapshots}/`
- `__pycache__/`, `*.log`
- `_*.py` (scratch scripts ở workspace root)

---

*Last updated: 2026-05-17*
