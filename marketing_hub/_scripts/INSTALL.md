# Cài đặt Marketing Hub — Combo Layer 1+3+4

Mục tiêu: web tự chạy 24/7, có backup DB, có Telegram bot self-service. Vợ Nghia chỉ cần cài 1 lần, sau đó không phải đụng nữa.

## ✅ Layer 1 — Auto-start Flask khi máy boot

**Bước 1:** Mở **Task Scheduler** (gõ `taskschd.msc` vào Run / Win+R)

**Bước 2:** Action → **Create Basic Task...**
- Name: `Marketing Hub Web`
- Trigger: **When the computer starts**
- Action: **Start a program**
- Program: `C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub\_scripts\start_marketing_hub.bat`
- Tick **"Run whether user is logged on or not"** → khi máy boot, web bật ngay (không cần login)
- Tick **"Run with highest privileges"**

**Bước 3:** Test — Right-click task → **Run** → mở browser http://127.0.0.1:5055 xem web up chưa.

→ Từ đây bật máy là web tự lên. Nếu Flask crash, batch script tự restart sau 5s.

---

## ✅ Layer 3 — Backup DB tự động daily

**Bước 1:** Test backup script chạy được:
```
python "C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub\_scripts\backup_db.py"
```
→ Sẽ tạo file `data/backups/posts_2026-MM-DD.db.zip` (~44MB)

**Bước 2:** Task Scheduler → Create Basic Task...
- Name: `Marketing Hub DB Backup`
- Trigger: **Daily** at **3:00 AM**
- Action: **Start a program**
- Program: `python`
- Arguments: `"C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub\_scripts\backup_db.py"`
- Tick **"Run whether user is logged on or not"**

**Cách restore:** unzip file `posts_YYYY-MM-DD.db.zip` → copy ra `data/posts.db` (stop Flask trước khi copy).

→ Auto giữ 30 ngày backup gần nhất, tự xóa cũ. Disk tốn ~1.3GB.

---

## ✅ Layer 3b — Backup chùm chìa khóa (.secrets + .env) daily

**Bước 1:** Test backup script chạy được:
```
python "C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub\_scripts\backup_secrets.py"
```
→ Tạo file `data/backups/secrets_YYYY-MM-DD.zip` (~2KB). Chứa Google OAuth + Telegram + OpenAI key.

**Bước 2:** Task Scheduler → Create Basic Task...
- Name: `Marketing Hub Secrets Backup`
- Trigger: **Daily** at **3:05 AM** (lệch 5 phút với DB backup)
- Action: **Start a program**
- Program: `python`
- Arguments: `"C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub\_scripts\backup_secrets.py"`
- Tick **"Run whether user is logged on or not"**

**Cách restore:** unzip `secrets_YYYY-MM-DD.zip` ở root workspace → 2 folder `.secrets/` + `marketing_hub/.env/` tự về chỗ cũ.

⚠️ **SECURITY**: file zip này CHỨA TOKEN GỐC, KHÔNG sync lên cloud public. Để backup ngoài máy: nén lại với 7-Zip + password rồi upload Google Drive private.

---

## ✅ Layer 4 — Telegram bot self-service

**Bước 1:** Tạo bot mới qua **@BotFather** trên Telegram:
- Chat với @BotFather
- Gõ `/newbot`
- Đặt tên (vd: "Sintech Marketing Hub")
- Username (vd: `sintech_hub_bot` — phải kết thúc bằng `_bot`)
- BotFather trả về **token** dạng `1234567890:AAExxxxx...`

**Bước 2:** Paste token vào file:
```
C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub\.env\telegram_bot_token.txt
```
Mở bằng Notepad → xóa text mẫu → paste token → save (UTF-8).

**Bước 3:** Test bot chạy:
```
python "C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub\telegram_bot.py"
```
→ Console log "Logged in as @sintech_hub_bot ... Polling..."

**Bước 4:** Mở Telegram → search `@sintech_hub_bot` → bấm Start → gõ `/help`. Bot trả về danh sách lệnh:
- `/status` — web up/down + jobs count + DB size
- `/jobs` — 5 job mới nhất
- `/audit` — audit kho AI gen (count meta sai length, filler)
- `/help` — danh sách lệnh

**Bước 5:** Auto-start bot khi máy boot — Task Scheduler:
- Name: `Marketing Hub Bot`
- Trigger: **At startup**
- Program: `C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub\_scripts\start_telegram_bot.bat`
- Tick **"Run whether user is logged on or not"**

→ Vợ chat bot là biết status, không cần mở Claude Code → tiết kiệm session.

---

## 🔧 Troubleshooting

| Vấn đề | Cách xử |
|---|---|
| Web không lên sau boot | Mở Task Scheduler → check "Marketing Hub Web" → Last Run Result |
| Bot không phản hồi | Check `telegram_bot.err.log`, có thể token sai hoặc bot bị BotFather revoke |
| DB backup fail | Disk full? Path Python sai? Chạy thủ công `python backup_db.py` xem lỗi |
| Restore từ backup | Stop Service → unzip `posts_YYYY-MM-DD.db.zip` → copy ra `data/posts.db` → Start Service |

## 📝 Logs

- `server.log` / `server.err.log` — Flask web
- `telegram_bot.log` / `telegram_bot.err.log` — bot
- `data/backups/posts_*.db.zip` — backups DB

## 🛡️ Security

- Bot chỉ accept chat_id `6593753113` (vợ Nghia). Người khác chat → bot reject.
- File token (`.env/telegram_bot_token.txt`) trong `.env/` đã gitignore — KHÔNG commit lên Git.
- Web `127.0.0.1:5055` chỉ accessible từ máy local (không expose ra Internet).
