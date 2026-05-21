# PROVIDERS — 3 AI provider (Claude / Codex / Gemini)

> Marketing Hub có **3 adapter** chạy song song để gen content SEO. Default hiện tại (20/5/2026): **Codex CLI** — toàn bộ task gen (`product_writer`, `collection_content_writer`, `seo`, `content_writer`, `blog_content_writer`, `ai_writer`) gọi `codex_provider`. `claude_provider.py` + `gemini_provider.py` giữ nguyên làm fallback — đổi `import` để switch.

---

## 🎯 Quick decision matrix

| Provider              | Khi nào dùng                                                     | Chất lượng meta length | Cost / quota                          |
| --------------------- | ---------------------------------------------------------------- | ---------------------- | ------------------------------------- |
| **Claude CLI (Pro)** ★ | Mặc định 17/5 — vợ chốt vì Pro/Max session còn dư              | Cao, validate fail ít  | Free trong session Pro, reset 5h     |
| **Codex CLI (Plus)**  | Khi Claude weekly hit limit, hoặc cần reasoning sâu cho money SP | Cao nhất, gần như 5/5  | Free Plus, reset 22/5 (weekly limit)  |
| **Gemini 2.0/2.5-flash** | Khi cả 2 trên hết, hoặc cần batch nhanh không cần fidelity cao | Trung — meta hay > 160c | Free 200 RPD (2.0) / 20 RPD (2.5)     |
| Anthropic API key     | KHÔNG dùng — chưa setup credit, Claude CLI dùng OAuth Pro       | —                      | $3/M input, $15/M output (chưa nạp)   |

---

## 🟪 Claude CLI — `claude_provider.py`

**Yêu cầu**:
- `npm install -g @anthropic-ai/claude-code`
- Đã login Pro/Max: chạy `claude` interactive → `/login` → OAuth browser flow → token lưu keychain.
- Test: `claude -p "OK"` phải trả `OK` (hoặc gần đó).

**Pattern subprocess**:
```python
import claude_provider
ok, raw, err = claude_provider.call_claude(
    system_prompt=...,    # bị --system-prompt REPLACE default Claude Code SP
    user_prompt=...,
    timeout=120,
)
```

**Lưu ý quan trọng**:
- Dùng `claude -p <prompt> --system-prompt <text>` cho non-interactive.
- `--system-prompt` REPLACE default Claude Code SP → tránh load `CLAUDE.md` + plugins làm bias output.
- KHÔNG dùng `--bare` (cần OAuth keychain Pro/Max).
- Detect rate limit qua patterns: `"rate limit"`, `"5-hour limit"`, `"weekly limit"`, `"session limit"`, `"please run /login"`.

**Reset**: 5h sliding window (Pro), weekly cap soft.

---

## 🟧 Codex CLI — `codex_provider.py`

**Yêu cầu**:
- `npm install -g @openai/codex` (v0.129+)
- Đã login ChatGPT Plus subscription.
- Test: `codex exec "OK" --skip-git-repo-check` phải trả response.

**Pattern subprocess**:
```python
import codex_provider
raw = codex_provider.call_codex(
    system_prompt=...,    # gộp với user_prompt thành 1 prompt
    user_prompt=...,
    timeout=180,
)  # RAISE CodexRateLimitError khi quota hết
```

**Lưu ý**:
- Codex CLI KHÔNG tách system/user → adapter gộp `system_prompt + "\n\n" + user_prompt`.
- Flag: `codex exec --skip-git-repo-check --output-last-message <tmpfile> -` (prompt qua stdin).
- Reasoning effort default `low` — đủ chất cho gen SEO theo template, nhanh ~50% so `medium`.
- Detect rate limit: `"you've hit your"`, `"rate limit"`, `"weekly limit"`.

**Reset**: Weekly (mỗi thứ 5/6) — hiện reset gần nhất **22/5/2026**.

---

## 🟦 Gemini API — `gemini_provider.py`

**Yêu cầu**:
- `pip install google-genai` (v2.3.0+) — SDK mới, `google.generativeai` cũ đã deprecated.
- API key:
  - Ưu tiên: env var `GOOGLE_API_KEY`
  - Fallback: `.secrets/google.env` chứa line `GOOGLE_API_KEY=...`
- Test:
  ```bash
  python marketing_hub/gemini_provider.py
  # → "Available: True" + JSON output
  ```

**Pattern**:
```python
import gemini_provider
raw = gemini_provider.call_gemini(
    system_prompt=...,
    user_prompt=...,
    model="gemini-2.0-flash",  # hoặc "gemini-2.5-flash"
    timeout=60,
    temperature=0.7,
)  # RAISE GeminiRateLimitError khi 429
```

**Trade-off (16/5 verified)**:
- Gemini 2.5-flash có xu hướng viết meta **>160c hoặc <140c** thường xuyên hơn Codex.
- ~3-4/5 SP fail length validate lần đầu, retry 1 lần thường vẫn fail.
- → Cần tighten prompt length constraint + nâng số retry attempts nếu dùng lâu dài.

**Quota free tier**:
- gemini-2.0-flash: 200 RPD
- gemini-2.5-flash: 20 RPD (đã hit 16/5)

---

## 🔄 Cách switch provider

Hiện tại chỉ 1 chỗ trong `seo.py` quyết định provider cho gen flow chính:

**`marketing_hub/seo.py:_gen_title_meta_with_angle`** (~line 2041):
```python
import claude_provider              # ← đổi sang codex_provider / gemini_provider
...
raw = claude_provider.call_claude(  # ← đổi tên hàm tương ứng
    _TITLE_META_SYSTEM_PROMPT, user_msg, timeout=120,
)
```

Catch exception cũng đổi tên: `ClaudeRateLimitError` ↔ `CodexRateLimitError` ↔ `GeminiRateLimitError`.

**Legacy `_gen_title_meta_via_codex`** (line 1770) GIỮ NGUYÊN — dùng cho `/seo/title-meta/fix` single-URL fallback.

**`recompute_dup_flags`** (line 2204) cũng dùng `claude_provider` (17/5) — cần sync khi switch.

---

## 🧪 Smoke test quick

```bash
# Claude
claude -p "OK ping"

# Codex
codex exec "OK ping" --skip-git-repo-check

# Gemini
python marketing_hub/gemini_provider.py
```

3 lệnh trên đều phải trả response < 5s. Nếu fail → check login / API key trước khi gen batch.

---

## 📍 File liên quan

| File                                          | Vai trò                                                   |
| --------------------------------------------- | --------------------------------------------------------- |
| `marketing_hub/claude_provider.py`            | Adapter Claude CLI subprocess (default 17/5)              |
| `marketing_hub/codex_provider.py`             | Adapter Codex CLI subprocess (legacy default)             |
| `marketing_hub/gemini_provider.py`            | Adapter Gemini API qua google-genai SDK                   |
| `marketing_hub/seo.py:_gen_title_meta_with_angle` | Gen flow MỚI (5 angle + anti-dup), point switch tại đây |
| `marketing_hub/seo.py:_gen_title_meta_via_codex`  | Legacy fix single-URL, GIỮ NGUYÊN dùng Codex          |
| `.secrets/google.env`                         | Gemini API key                                            |
