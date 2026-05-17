# QUICKSTART — 5 phút setup sau cài Win

> Anh phiên bản 2: theo checklist này restore môi trường sau cài lại Win.

---

## ✅ Pre-checklist (5 phút) — Install tools

```powershell
# 1. Python 3.12 — download từ https://www.python.org/downloads/
python --version  # phải 3.12.x

# 2. Node.js LTS — download từ https://nodejs.org/
node --version

# 3. Git for Windows — download từ https://git-scm.com/download/win
git --version

# 4. Claude Code CLI
npm install -g @anthropic-ai/claude-code
claude --version

# 5. (Optional) Codex CLI nếu muốn dùng OpenAI
npm install -g @openai/codex
codex --version
```

## 📦 Extract backup zip

```powershell
# Giả sử file zip ở Desktop
cd "C:\Users\Nghia Dep Gai\"
mkdir .openclaw -ErrorAction SilentlyContinue
# Extract sintech_backup_*.zip vào .openclaw\workspace\
# (dùng 7-Zip / WinRAR / built-in extract)
```

Cấu trúc sau extract:
```
C:\Users\Nghia Dep Gai\.openclaw\workspace\
├── marketing_hub\
├── .secrets\
├── state\
├── docs\
├── claude_memory\           ← MOVE folder này
├── claude_settings.json     ← MOVE file này
└── README_RESTORE.md
```

## 🧠 Restore Claude memory

```powershell
mkdir "C:\Users\Nghia Dep Gai\.claude\projects\C--Users-Nghia-Dep-Gai--openclaw-workspace\" -Force

# Move memory folder
Move-Item "C:\Users\Nghia Dep Gai\.openclaw\workspace\claude_memory\" "C:\Users\Nghia Dep Gai\.claude\projects\C--Users-Nghia-Dep-Gai--openclaw-workspace\memory\"

# Move settings
Move-Item "C:\Users\Nghia Dep Gai\.openclaw\workspace\claude_settings.json" "C:\Users\Nghia Dep Gai\.claude\settings.json"
```

## 🐍 Install Python deps

```powershell
cd "C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub"
pip install -r requirements.txt
pip install google-genai   # provider Gemini mới (deprecated 'google-generativeai')
```

## 🔓 Login Claude CLI

```powershell
# Test:
claude -p "OK"
# Nếu báo "Not logged in" → chạy:
claude
# Bấm /login → browser tự mở → login Pro/Max account
```

## ▶️ Start Flask web

```powershell
# Option A: foreground (test)
cd "C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub"
python app.py
# → mở browser http://localhost:5055

# Option B: hidden background qua VBS
wscript.exe "C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub\_scripts\start_marketing_hub_hidden.vbs"
```

Verify: `curl http://localhost:5055/` phải HTTP 200.

## ⚙️ Setup Task Scheduler (auto-start 24/7)

Xem chi tiết: `marketing_hub/_scripts/INSTALL.md`

Tóm tắt:
1. Mở Task Scheduler
2. Import 3 task: `Marketing Hub Web`, `Telegram Bot`, `DB Backup Daily 3AM`
3. Triggers: At startup (web + bot) + Daily 3AM (backup)
4. Action: `wscript.exe <path>\start_*_hidden.vbs`

## 🤖 Re-bind Telegram bot

Token cũ revoked 12/5 → vợ paste token mới vào `marketing_hub/.env/telegram_bot_token.txt` (chat với BotFather → /mybots → @Web_Sintech_bot → API Token).

## ✅ Verify checklist

- [ ] `curl http://localhost:5055/` → HTTP 200
- [ ] Vào `/seo` → thấy stats 2459 page crawled
- [ ] Vào `/content-jobs` → thấy 314 jobs
- [ ] Vào `/collection-content` → thấy 70 collection jobs
- [ ] Vào `/seo/title-meta` → thấy 1679 SP có lỗi title/meta + 2 cột mới (✓ Tay | 🗑)
- [ ] DB `marketing_hub/data/posts.db` đúng ~339MB
- [ ] Memory anh có 28+ file trong `~/.claude/projects/.../memory/`
- [ ] Claude CLI login → `claude -p "OK"` trả "OK"
- [ ] (Optional) Codex CLI login → `codex exec --skip-git-repo-check -p "OK"`

## 🆘 Nếu gặp lỗi

- **Flask không start:** check `marketing_hub/server.err.log` + thử `python app.py` foreground để xem stacktrace
- **DB error:** verify `posts.db` không corrupt (`sqlite3 posts.db "SELECT COUNT(*) FROM seo_pages"` → phải ~2459)
- **Claude CLI fail "Not logged in":** chạy `claude /login` rồi `claude -p "OK"`
- **Gemini quota:** check `.secrets/google.env` có `GOOGLE_API_KEY` không
- **Haravan API 401:** check `state/haravan_token.json` token còn valid không

→ Đọc tiếp `docs/CURRENT_STATE.md` để biết pending tasks và priority.

---

*Last updated: 2026-05-17*
