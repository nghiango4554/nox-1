# TOOLS_CHEATSHEET — Commands hay dùng

> Lookup nhanh. Sau /clear, mở file này thay vì scroll WORKLOG tìm lệnh.
>
> Quy ước: lệnh chạy ở **root workspace** (`C:\Users\Nghia Dep Gai\.openclaw\workspace`) trừ khi note khác. Python path mặc định `C:\Users\Nghia Dep Gai\AppData\Local\Programs\Python\Python312\python.exe`.

---

## 🔄 LIVE state refresh

Refresh block `<!-- LIVE:BEGIN/END -->` trong `docs/CURRENT_STATE.md` (git + Flask + bot):

```powershell
python marketing_hub/_scripts/generate_current_state.py
```

→ Chạy bất cứ lúc nào để có snapshot mới. KHÔNG đụng các section khác trong CURRENT_STATE.md.

---

## 🌐 Web Flask `localhost:5055`

| Việc                | Lệnh                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------- |
| Health check        | `Invoke-WebRequest http://127.0.0.1:5055 -UseBasicParsing \| Select StatusCode`                          |
| Restart (giữ hidden) | `& "marketing_hub\_scripts\start_marketing_hub_hidden.vbs"`                                              |
| Kill + restart      | `Get-Process python \| Stop-Process -Force` rồi gọi VBS                                                  |
| Logs Flask          | `Get-Content marketing_hub\server.log -Tail 50`                                                          |
| Logs error          | `Get-Content marketing_hub\server.err.log -Tail 50`                                                      |

Chi tiết kiến trúc: [`OPS.md`](OPS.md).

---

## 📑 Routes hay dùng trên web

| URL                                  | Mục đích                                                          |
| ------------------------------------ | ----------------------------------------------------------------- |
| `/`                                  | Dashboard chính                                                   |
| `/content-jobs`                      | Gen content SP (Codex/Claude pipeline)                            |
| `/collection-content`                | Gen content cate (5 angle, 4 bảng)                                |
| `/seo`                               | Crawl + score 1923 URL, dashboard SEO                             |
| `/seo/title-meta`                    | Stream gen 1679 title/meta SP, push F/G/H Google Sheet            |
| `/seo/gsc`                           | Google Search Console 8 task action                               |
| `/posts/<id>/update`                 | Upload ảnh + sync post FB                                         |

---

## 🤖 AI providers — switch

Default 17/5: **Claude CLI Pro/Max**. Switch ở `marketing_hub/app.py` (hàm `_gen_title_meta_with_angle` + `recompute_dup_flags`):

| Provider     | Module                          | Trigger                            |
| ------------ | ------------------------------- | ---------------------------------- |
| Claude CLI   | `claude_provider.py` ★          | OAuth keychain (đã login)          |
| Codex CLI    | `codex_provider.py`             | Hết quota, reset 22/5              |
| Gemini       | `gemini_provider.py`            | Hết 20 RPD free                    |

Test 1 provider standalone:

```powershell
python -c "from marketing_hub.claude_provider import gen_title_meta; print(gen_title_meta('test prompt'))"
```

Chi tiết: [`PROVIDERS.md`](PROVIDERS.md).

---

## 💾 DB ops

| Việc            | Lệnh                                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------------------- |
| Backup DB manual    | `python marketing_hub/_scripts/backup_db.py`                                                            |
| Backup secrets manual | `python marketing_hub/_scripts/backup_secrets.py` (zip .secrets/ + .env/ ra `secrets_YYYY-MM-DD.zip` ~2KB) |
| List backups        | `Get-ChildItem marketing_hub\data\backups\ \| Sort-Object LastWriteTime -Descending`                    |
| Restore DB          | Stop Flask → `Expand-Archive posts_YYYY-MM-DD.db.zip` → copy `posts.db` ra `marketing_hub\data\` → start |
| Restore secrets     | Unzip `secrets_YYYY-MM-DD.zip` ở **root workspace** → 2 folder `.secrets/` + `marketing_hub/.env/` tự về chỗ cũ |
| Inspect DB      | `python -c "import sqlite3; c=sqlite3.connect('marketing_hub/data/posts.db'); print(c.execute('SELECT COUNT(*) FROM content_jobs').fetchone())"` |

Schedule: daily 3AM, giữ 30 ngày. Path zip: `marketing_hub/data/backups/posts_YYYY-MM-DD.db.zip`.

---

## 📱 Telegram bot `@Web_Sintech_bot`

| Việc              | Lệnh                                                                                |
| ----------------- | ----------------------------------------------------------------------------------- |
| Test token live   | `python marketing_hub/_scripts/generate_current_state.py` (xem dòng Bot Telegram)   |
| Restart bot       | `& "marketing_hub\_scripts\start_telegram_bot_hidden.vbs"`                          |
| Paste token mới   | Edit `marketing_hub/.env/telegram_bot_token.txt` (UTF-8, KHÔNG commit)              |
| Logs              | `Get-Content marketing_hub\telegram_bot.log -Tail 50`                               |
| Bot commands      | `/status`, `/jobs`, `/audit`, `/help` (chat từ chat_id `6593753113`)                |

---

## 🔧 Git common ops

| Việc                          | Lệnh                                                              |
| ----------------------------- | ----------------------------------------------------------------- |
| Status                        | `git status --short`                                              |
| Diff uncommitted              | `git diff` / `git diff --staged`                                  |
| Log gọn                       | `git log --oneline -10`                                           |
| Commit (KHÔNG `git add -A`)   | `git add <file...>` rồi `git commit -m "..."` (chọn file rõ ràng) |
| Set author cho commit         | Đã set global `nghiango4554`, không cần override                  |

⚠️ Repo có nhiều dev work uncommitted song song (claude_provider, gemini_provider, sheet_writer, app.py modify...). **Luôn add file cụ thể**, không bulk add, tránh bundle nhầm.

---

## 📊 SEO Dup Rewrite

Folder: `seo_rewrite/` ngoài root. Workflow: edit 1 hàng N trong sheet `Meta des + Title Errors` → sync Haravan SP qua metafields `global.title_tag` + `global.description_tag` → verify trang web.

```powershell
# Sync 1 SP từ row N sheet (giả định script đã có)
python seo_rewrite/sync_row.py --row N

# Stream gen từ web: bấm "✨ Gen vào Sheet" trên /seo/title-meta
```

Pattern title ≤61c, meta 140-160c, đủ 4 CTA gồm "KHÁM PHÁ NGAY". Detail: memory `feedback_seo_rewrite_pattern.md`.

---

## 🖼 FB posting — caption + ảnh

1. Drop ảnh vào `Desktop\Sintech\PIC đăng page\<DD-M>\`
2. Upload qua web `/posts/<id>/update` (upload form)
3. Footer chuẩn: Hotline `0911 713 000` + Địa chỉ `457 Trần Xuân Soạn Q7` + hashtag cluster
4. Che giá: dùng pattern `1Tr8xx`, `7x.xxx`
5. UTF-8 POST: dùng Python script, KHÔNG `curl -F` (Windows fail emoji)

Detail rules: memory `feedback_footer_post.md`, `feedback_che_gia.md`, `feedback_image_pattern.md`.

---

## 🧪 Provider quota check (manual)

```powershell
# Codex
codex --version  # xem login state
# Claude
claude --version
claude /status   # xem usage % nếu đang trong session
# Gemini — không có CLI, check qua test gen
python -c "from marketing_hub.gemini_provider import gen_title_meta; print(gen_title_meta('test'))"
```

---

## 📝 Memory + docs hay đụng

| File                                | Khi nào edit                                              |
| ----------------------------------- | --------------------------------------------------------- |
| `WORKLOG.md`                        | Cuối session — snapshot Active/Blocked + checkpoint       |
| `docs/CURRENT_STATE.md`             | Provider switch / task done / commit lớn (manual + LIVE) |
| `docs/PROJECT_MAP.md`               | Thêm file/folder mới                                      |
| `docs/RESILIENCE.md`                | Học rule mới về execution / session resume                |
| Memory files (`~/.claude/.../memory/`) | Lesson mới về vợ / project / pattern                    |

---

## 🆘 Khi mọi thứ hỏng

1. Chạy LIVE state script → xem git/flask/bot status nhanh.
2. Đọc `docs/RESILIENCE.md` — execution-vs-discussion mode + session resume.
3. Check `WORKLOG.md` section **Blocked** — task nào đang chờ.
4. Nếu Flask down: VBS restart → kiểm tra `server.err.log`.
5. Nếu bot down: token có thể revoke → vợ paste lại qua BotFather.
6. Nếu git lộn xộn: `git status` + `git log -5` trước khi đụng `reset`/`checkout`.
