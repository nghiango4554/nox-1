"""Adapter gọi Claude Code CLI từ Python qua subprocess.

Yêu cầu Claude Code CLI đã login Pro/Max subscription (OAuth keychain).
Test trước: `claude -p "OK"` phải trả response.

Khác với Codex CLI:
- Claude CLI default chạy interactive — phải dùng `-p` cho non-interactive
- `--system-prompt <text>` REPLACE default Claude Code system prompt
  (tránh load CLAUDE.md + plugins làm bias output)
- KHÔNG dùng `--bare` vì cần OAuth keychain (Pro/Max session)

Dùng làm AI provider cho gen title/meta SEO khi Codex hết quota.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


CLAUDE_BIN = "claude"
DEFAULT_TIMEOUT = 120  # giây
DEFAULT_MODEL = None  # None = dùng default model từ Claude config (Sonnet/Opus tùy plan)

# Patterns Claude CLI / Anthropic API in ra khi quota hết
RATE_LIMIT_PATTERNS = [
    "rate limit",
    "rate_limit",
    "usage limit",
    "you have hit",
    "you've hit",
    "5-hour limit",
    "5h limit",
    "weekly limit",
    "monthly limit",
    "too many requests",
    "session limit",
    "quota exceeded",
    "please run /login",  # CLI chưa login
]


class ClaudeRateLimitError(RuntimeError):
    """Quota Claude session đã hết — đợi reset."""
    pass


def _is_rate_limit_message(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(p in low for p in RATE_LIMIT_PATTERNS)


def is_claude_available() -> bool:
    """True nếu binary `claude` có trên PATH."""
    return shutil.which(CLAUDE_BIN) is not None


def call_claude(system_prompt: str, user_prompt: str,
                timeout: int = DEFAULT_TIMEOUT, model: str = DEFAULT_MODEL) -> str:
    """Gọi Claude CLI 1 lần, trả response text thuần.

    Raise ClaudeRateLimitError nếu quota hết / CLI chưa login.
    Raise RuntimeError nếu lỗi khác.
    """
    claude_path = shutil.which(CLAUDE_BIN)
    if not claude_path:
        raise RuntimeError("Claude CLI chưa cài. Chạy: npm install -g @anthropic-ai/claude-code")

    # System prompt dài (vài KB) → ghi tempfile + dùng --system-prompt-file
    # Tránh lỗi Windows "command line too long" (limit ~8KB cho cmd.exe args).
    sys_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    try:
        sys_file.write(system_prompt)
        sys_file.close()
        sys_path = sys_file.name

        cmd = [claude_path, "-p", "--system-prompt-file", sys_path]
        if model:
            cmd.extend(["--model", model])

        # Gửi user_prompt qua stdin để tránh issue tương tự với prompt dài
        try:
            proc = subprocess.run(
                cmd,
                input=user_prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude CLI timeout sau {timeout}s.")
    finally:
        try:
            Path(sys_file.name).unlink(missing_ok=True)
        except Exception:
            pass

    combined_output = (proc.stderr or "") + "\n" + (proc.stdout or "")
    if _is_rate_limit_message(combined_output):
        raise ClaudeRateLimitError(
            f"Quota Claude session hết. Đợi reset rồi start lại. "
            f"Tail: {combined_output[-300:]}"
        )

    if proc.returncode != 0:
        err_tail = (proc.stderr or proc.stdout or "")[-500:]
        if _is_rate_limit_message(err_tail):
            raise ClaudeRateLimitError(f"Quota Claude hết. Tail: {err_tail}")
        raise RuntimeError(f"Claude CLI exit {proc.returncode}: {err_tail}")

    text = (proc.stdout or "").strip()
    if not text:
        if _is_rate_limit_message(combined_output):
            raise ClaudeRateLimitError("Claude trả empty + rate limit message.")
        raise RuntimeError("Claude trả response rỗng.")

    if _is_rate_limit_message(text):
        raise ClaudeRateLimitError(f"Output chứa rate limit: {text[:300]}")

    return text


if __name__ == "__main__":
    print("Available:", is_claude_available())
    if is_claude_available():
        out = call_claude(
            system_prompt="Bạn trả lời tiếng Việt ngắn gọn.",
            user_prompt='Trả lời chỉ JSON {"hello":"world"} không kèm gì khác.',
        )
        print("Output:", repr(out))
