# OPS — Vận hành 24/7

> Marketing Hub chạy 4 layer auto-start trên Windows: **Web Flask** + **Bot Telegram** + **DB Backup daily**. Task Scheduler trigger tất cả qua VBS wrapper hidden (không có CMD window).

Setup chi tiết step-by-step: xem [`../marketing_hub/_scripts/INSTALL.md`](../marketing_hub/_scripts/INSTALL.md). Doc này giải thích **kiến trúc + cách debug + troubleshoot**.

---

## 🏗 Layer overview

| Layer | Service                          | Trigger            | Status hiện tại                            |
| ----- | -------------------------------- | ------------------ | ------------------------------------------ |
| 1     | Web Flask `localhost:5055`       | At startup         | 🟢 Active (PID baseline 14796 từ 12/5)     |
| 3     | DB Backup `posts_YYYY-MM-DD.db.zip` | Daily 3:00 AM   | 🟢 Active, giữ 30 ngày trong `data/backups/` |
| 4     | Telegram Bot `@Web_Sintech_bot`  | At startup         | 🔴 Token revoked 12/5 — vợ paste lại để resume |

Layer 2 (Cloudflare Tunnel public) — KHÔNG dùng. Web chỉ accessible local 127.0.0.1.

---

## 🪟 Task Scheduler — 3 task chính

| Task name              | Trigger        | Program                                         |
| ---------------------- | -------------- | ----------------------------------------------- |
| `Marketing Hub Web`    | At startup     | `_scripts/start_marketing_hub_hidden.vbs`       |
| `Marketing Hub Bot`    | At startup     | `_scripts/start_telegram_bot_hidden.vbs`        |
| `Marketing Hub DB Backup` | Daily 3:00 AM | `python _scripts/backup_db.py`                |

**Flag bắt buộc** cho cả 3:
- ✅ "Run whether user is logged on or not" — chạy ngay khi boot, không cần login.
- ✅ "Run with highest privileges" — tránh permission denied khi ghi `data/`.

Verify task chạy: Right-click task → **Last Run Result** = `0x0` là OK.

---

## 🎭 VBS hidden wrapper — tại sao cần

**Vấn đề**: gọi thẳng `.bat` từ Task Scheduler → mỗi lần boot/restart hiện CMD window 5-10s rồi mới ẩn → khó chịu.

**Giải pháp**: `.vbs` wrapper gọi `cmd /c <batch>` qua `WScript.Shell.Run(cmd, 0, false)` — flag `0` = hidden, `false` = không đợi.

**File**:
- `_scripts/start_marketing_hub_hidden.vbs` → gọi `start_marketing_hub.bat`
- `_scripts/start_telegram_bot_hidden.vbs` → gọi `start_telegram_bot.bat`

Task Scheduler trỏ tới `.vbs` qua `wscript.exe`, KHÔNG trỏ thẳng `.bat`.

---

## 🔄 Restart manual

Cần restart Flask sau khi modify code Python (Flask không hot-reload trong production mode):

```powershell
# Option 1: qua VBS wrapper (giữ hidden)
& "C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub\_scripts\start_marketing_hub_hidden.vbs"

# Option 2: kill PID cũ + start mới
Get-Process python | Where-Object { $_.MainWindowTitle -like "*marketing_hub*" } | Stop-Process -Force
# rồi gọi VBS như trên
```

Health check sau restart:
```powershell
Invoke-WebRequest http://127.0.0.1:5055 -UseBasicParsing | Select-Object StatusCode
# → StatusCode : 200
```

---

## 💾 DB Backup — schema + restore

**Script**: `_scripts/backup_db.py`
- Source: `data/posts.db` (~339MB)
- Output: `data/backups/posts_YYYY-MM-DD.db.zip` (~44MB sau nén)
- Rotation: giữ 30 ngày gần nhất, auto xóa cũ hơn

**Restore khi cần** (sample DB corruption / vợ muốn rollback):
```powershell
# 1. STOP Flask (tránh write lock)
Stop-Process -Name python -Force

# 2. Unzip backup
Expand-Archive data\backups\posts_2026-05-15.db.zip data\restore_tmp\

# 3. Copy ra location production
Copy-Item data\restore_tmp\posts.db data\posts.db -Force

# 4. START lại Flask qua VBS
& marketing_hub\_scripts\start_marketing_hub_hidden.vbs
```

Disk tốn: 30 file × ~44MB = **~1.3GB** trong `data/backups/`.

---

## 📜 Logs

| File                       | Source                       | Khi nào check                          |
| -------------------------- | ---------------------------- | -------------------------------------- |
| `server.log`               | Flask stdout                 | Request log, AI gen log, sync Haravan  |
| `server.err.log`           | Flask stderr                 | Exception trace, 500 error             |
| `telegram_bot.log`         | Bot stdout                   | Command nhận, response gửi             |
| `telegram_bot.err.log`     | Bot stderr                   | Token error, polling fail              |
| `data/backups/posts_*.db.zip` | Backup script             | Verify backup ngày X có tồn tại        |

Log location: root workspace (`server.log`, `server.err.log`), KHÔNG trong `marketing_hub/`.

---

## 🔐 Security baseline

- **Bot Telegram** chỉ accept `chat_id=6593753113` (vợ Nghia). Người khác chat → bot reject silently.
- **Web Flask** bind `127.0.0.1:5055` → KHÔNG expose ra Internet, chỉ accessible từ máy local.
- **Token file** `marketing_hub/.env/telegram_bot_token.txt` đã gitignore.
- **API keys** ở `.secrets/` (Google OAuth token, Gemini API) đã gitignore.
- **Haravan permission gate** ở `haravan_client._check_permission()` BLOCK:
  - `POST /products.json`, `DELETE /products/{id}.json`
  - `POST /blogs/*/articles.json`, `DELETE /articles/{id}.json`
- ALLOW: GET, PUT/PATCH, POST `/products/{id}/images.json`, DELETE images.

---

## 🛠 Troubleshooting

| Triệu chứng                          | Nguyên nhân thường gặp                          | Fix                                                                    |
| ------------------------------------ | ----------------------------------------------- | ---------------------------------------------------------------------- |
| Web 502 / không lên sau boot         | Task Scheduler không chạy / VBS path sai        | Task Scheduler → Last Run Result; mở `server.err.log`                  |
| Web port 5055 đã bị chiếm            | Crash trước đó chưa free port                   | `Get-NetTCPConnection -LocalPort 5055` → kill PID owner                |
| Bot không phản hồi                   | Token revoked 401 / BotFather revoke            | `telegram_bot.err.log`; paste token mới vào `.env/telegram_bot_token.txt` |
| DB backup zip 0 byte                 | Disk full / Flask đang write lock DB            | Check disk free; backup script handle SQLite lock đúng không?          |
| AI gen fail "quota exceeded"         | Provider hit weekly limit                       | Xem [`PROVIDERS.md`](PROVIDERS.md) → switch provider                  |
| Haravan PUT 401/403                  | Token expired / scope thiếu                     | Verify token ở `marketing_hub/.env/haravan_token.txt`                 |
| Haravan asset storage đầy            | 7 storage SP đã full 91/90                      | KHÔNG auto-create (incident 10/5). Vợ tạo SP manual + paste haravan_id vào `state/asset_storage_product.json` |

---

## 📍 File liên quan

| Path                                          | Vai trò                                          |
| --------------------------------------------- | ------------------------------------------------ |
| `marketing_hub/_scripts/INSTALL.md`           | Step-by-step setup Task Scheduler từ đầu         |
| `marketing_hub/_scripts/start_*_hidden.vbs`   | VBS wrapper hidden cho Flask + Bot               |
| `marketing_hub/_scripts/start_*.bat`          | Batch script gọi python (loop restart on crash)  |
| `marketing_hub/_scripts/backup_db.py`         | DB backup daily với rotation 30 ngày             |
| `marketing_hub/_scripts/cleanup_asset_storage.py` | Cleanup orphan images trong asset storage    |
| `marketing_hub/haravan_client.py`             | `_check_permission()` gate POST/DELETE           |
| `state/asset_storage_product.json`            | Danh sách 7 storage SP (cập nhật manual khi đầy) |
