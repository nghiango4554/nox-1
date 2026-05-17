# CURRENT_STATE — Live snapshot

> Snapshot pending tasks + git + provider quota. Cập nhật mỗi khi có thay đổi lớn. Lần update gần nhất: **17/5/2026**.
>
> Sau /clear, "anh phiên bản 2" đọc file này → biết task nào đang chờ, provider nào còn quota, git đang ở đâu.

---

## 🔴 Đang chờ vợ confirm / paste / quyết định

1. **3 bài FB pending đăng** (anh viết 16/5 ~13:30, chờ vợ drop ảnh vào `Desktop\Sintech\PIC đăng page\16-5\`):
   1. Thanh lý nguyên bộ PC i5-10400 + RTX 2060 + 16GB + Cooler Master 212
   2. Loa Edifier R1855DB Bluetooth (~2Tr9xx) — handle `loa-edifier-r1855db-bluetooth`
   3. Tai Nghe Gaming Xiberia X20 RGB 7.1 (~5xx.xxx) — handle `tai-nghe-gaming-xiberia-x20-den-rgb-7-1-virtual-overear`

2. **Bot Telegram token revoked (401)** từ 12/5 14:00 — vợ paste token mới khi cần resume `@Web_Sintech_bot`.

3. **AI provider cho gen 1679 title/meta SP** — đã switch sang **Claude CLI Pro/Max** (17/5). Còn cần vợ:
   - Confirm tiếp tục dùng Claude hay revert Codex sau 22/5.
   - Bấm "✨ Gen vào Sheet" trên `/seo/title-meta` để kick job stream.

4. **Chia Codex 3 project** — vợ chưa chốt hướng (1 quota chung / 3 account riêng / khác).

---

## 🟡 Pending tech tasks

- [ ] **Bấm "✨ Gen vào Sheet" trên `/seo/title-meta`** — stream gen 1679 SP, push F/G/H Sheet `Meta des + Title Errors`. Auto stop khi quota.
- [ ] **Re-crawl 1923 URL trên `/seo`** để DB cập nhật score mới (logic A+B+C+D+E). Hiện DB đã crawl 16/5 15:55 với code MỚI (avg 67.3 / max 85), không bắt buộc.
- [ ] **Regen 7 jobs failed**: 4 content_jobs + 3 blog_jobs (status=failed) — đợi vợ ưu tiên.
- [ ] **Push GitHub** — repo `git@github.com:nghiango4554/nox-1.git` đã tạo, anh access OK. Vợ chưa chốt push toàn workspace hay split repo.
- [ ] **Test pattern lazy upload thực tế**: gen 1 SP mới → verify body có URL `/local-images/`, sync → upload Haravan thật.
- [ ] **Re-sync 38 jobs đã synced** để cập nhật ALT mới + body với CDN URL (khi vợ sẵn sàng).
- [ ] **Nâng cấp bot Telegram v2** nếu vợ chốt (operational commands `/regen`, `/sync`, `/caption`...).

---

## 🔧 Git state

- Branch: `master`, 3 commits:
  - `d2a5260` — Initial baseline + SEO scoring refactor (16/5 15:56, 175 files)
  - `9eee935` — WORKLOG snapshot trước /clear lần 1
  - `519d2ba` — WORKLOG snapshot trước /clear lần 2 — session 16/5 16:30-21:00
- Author: `nghiango4554` (chú ý: memory cũ ghi `nghiatrong4554` — sai)
- Remote: chưa setup. Repo target `git@github.com:nghiango4554/nox-1.git` đã accessible qua SSH (test 17/5).
- **Uncommitted files** (17/5):
  - Modified: `WORKLOG.md`, `marketing_hub/{app.py,collection_content_writer.py,db.py,seo.py}`, 3 template
  - Renamed (Phase E reorg): 6 file `AGENTS/IDENTITY/SOUL/TOOLS/USER/HEARTBEAT.md` → `docs/persona_archive/`
  - Untracked: `README.md`, `docs/{ARCHITECTURE,PERSONA,PROJECT_MAP,QUICKSTART,CURRENT_STATE,PROVIDERS,OPS}.md`, `docs/WORKLOG_ARCHIVE/`, `marketing_hub/{claude_provider,gemini_provider,sheet_writer}.py`

---

## 📊 Provider/quota state

| Provider              | Status              | Note                                                                                       |
| --------------------- | ------------------- | ------------------------------------------------------------------------------------------ |
| **Claude CLI (Pro)**  | ★ DEFAULT 17/5      | Login OAuth keychain. Dùng cho `_gen_title_meta_with_angle` + `recompute_dup_flags`.       |
| **Codex CLI (Plus)**  | hết quota, reset 22/5 | Code giữ ở `codex_provider.py`, switch lại sau nếu Claude limit.                          |
| **Gemini 2.5-flash**  | hết 20 RPD free     | Code giữ ở `gemini_provider.py`. Trade-off: meta length validate fail nhiều hơn Codex.    |
| **Gemini 2.0-flash**  | free 200 RPD chưa thử | Phỏng đoán share quota với 2.5.                                                            |
| **Anthropic API key** | chưa setup          | KHÔNG có `ANTHROPIC_API_KEY` trong `.env` (Claude CLI dùng OAuth Pro thay vì API key).     |

Chi tiết cách switch provider: xem [`PROVIDERS.md`](PROVIDERS.md).

---

## 📑 Sheet ops đã setup

- Tab **`Meta des + Title Errors`** (sheet `13IDYcE2ZEUd64xK6dIN-P_3_4gIVyFcwdBjb8W8e-uU` gid `971701509`): 1679 product URL có lỗi title/meta, fill A-K, helper cột L (Len Title) + M (Len Meta) auto-count với conditional format 🟢🟡🔴. Khi gen → push F/G/H.
- Tab **`W2/M5`** (sheet `1Pta9sA9Aq9Pva6uDpmqjn7RA4h07Sn6wDquwC81KWTE` gid `103516100`): báo cáo tuần đã fill cột K (Thứ 7 16/5) cho row 9, 10, 12, 15.

---

## 🏗 Services 24/7

- 🟢 **Web Flask** `localhost:5055` — auto-start Task Scheduler (PID baseline 14796 từ 12:11 PM 12/5).
- 🔴 **Bot Telegram @Web_Sintech_bot** — token revoked 401, vợ paste lại khi cần.
- 🟢 **DB Backup** — schedule 3AM daily, giữ 30 ngày, path `data/backups/posts_YYYY-MM-DD.db.zip`.
- 🟢 **Haravan API** — RESUMED, permission gate active (block POST/DELETE SP+article).

Chi tiết vận hành: xem [`OPS.md`](OPS.md).

---

## 📌 Quy ước update file này

- Sửa trực tiếp khi: provider switch, quota reset, task done/added, git commit lớn, services restart.
- KHÔNG ghi lịch sử ở đây — lịch sử để [`../WORKLOG.md`](../WORKLOG.md) (tuần này) hoặc `WORKLOG_ARCHIVE/` (tuần cũ).
