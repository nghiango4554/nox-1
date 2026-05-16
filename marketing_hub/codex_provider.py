"""Adapter gọi OpenAI Codex CLI từ Python qua subprocess.

Yêu cầu Codex CLI v0.129+ đã cài (`npm install -g @openai/codex`) + đã login
ChatGPT account (quota theo plan, KHÔNG tốn API credit).

Flow:
1. Gộp system_prompt + user_prompt thành 1 prompt duy nhất (Codex CLI không
   tách system/user message như API).
2. Subprocess `codex exec --skip-git-repo-check --output-last-message <tmpfile> -`
   với prompt qua stdin.
3. Đọc tmpfile → đó là response text thuần (đã loại header noise).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


CODEX_BIN = "codex"
DEFAULT_TIMEOUT = 180  # giây
# Reasoning effort: minimal | low | medium | high. Low = nhanh ~50% so medium,
# chất lượng vẫn tốt cho task gen content SEO theo template.
DEFAULT_REASONING_EFFORT = "low"

# Patterns Codex CLI in ra khi quota Plus hết hạn / rate limit
RATE_LIMIT_PATTERNS = [
    "you've hit your",
    "you have hit your",
    "rate limit",
    "rate-limit",
    "rate_limit",
    "quota exceeded",
    "weekly limit reached",
    "5h limit reached",
    "usage limit reached",
    "try again later",
]


class CodexRateLimitError(RuntimeError):
    """Quota Plus của ChatGPT đã hết — phải đợi reset."""
    pass


def _is_rate_limit_message(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(p in low for p in RATE_LIMIT_PATTERNS)


def is_codex_available() -> bool:
    """True nếu binary `codex` có trên PATH."""
    return shutil.which(CODEX_BIN) is not None


def call_codex(system_prompt: str, user_prompt: str,
               timeout: int = DEFAULT_TIMEOUT, model: str = None,
               reasoning_effort: str = DEFAULT_REASONING_EFFORT) -> str:
    """Gọi Codex CLI 1 lần, trả response text thuần.

    Raise RuntimeError nếu Codex chưa cài / chưa login / timeout / non-zero exit.
    """
    codex_path = shutil.which(CODEX_BIN)
    if not codex_path:
        raise RuntimeError("Codex CLI chưa cài. Chạy: npm install -g @openai/codex")

    # Combine system + user — Codex coi là 1 prompt
    combined_prompt = system_prompt.strip() + "\n\n---\n\n" + user_prompt.strip()

    # Tmpfile cho --output-last-message
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.close()
    out_path = Path(tmp.name)

    try:
        cmd = [codex_path, "exec", "--skip-git-repo-check",
               "-c", f"model_reasoning_effort={reasoning_effort}",
               "--output-last-message", str(out_path), "-"]
        if model:
            cmd.extend(["-m", model])

        proc = subprocess.run(
            cmd,
            input=combined_prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )

        # Detect rate limit từ stdout/stderr — Codex CLI in "ERROR: You've hit your..."
        combined_output = (proc.stderr or "") + "\n" + (proc.stdout or "")
        if _is_rate_limit_message(combined_output):
            raise CodexRateLimitError(
                f"Quota Codex Plus đã hết. Đợi reset rồi start worker lại. "
                f"Tail: {combined_output[-300:]}"
            )

        if proc.returncode != 0:
            err_tail = (proc.stderr or proc.stdout or "")[-500:]
            if _is_rate_limit_message(err_tail):
                raise CodexRateLimitError(f"Quota Codex Plus hết. Tail: {err_tail}")
            raise RuntimeError(f"Codex exec exit {proc.returncode}: {err_tail}")

        if not out_path.exists():
            raise RuntimeError("Codex không ghi output (file không tồn tại).")
        text = out_path.read_text(encoding="utf-8").strip()
        if not text:
            # Có thể empty vì rate limit — check stderr
            if _is_rate_limit_message(combined_output):
                raise CodexRateLimitError("Codex trả empty + rate limit message.")
            raise RuntimeError("Codex trả response rỗng.")
        # Edge case: Codex chèn rate limit message vào output
        if _is_rate_limit_message(text):
            raise CodexRateLimitError(f"Output chứa rate limit: {text[:300]}")
        return text
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    # Smoke test
    print("Available:", is_codex_available())
    if is_codex_available():
        out = call_codex(
            system_prompt="Bạn trả lời tiếng Việt, ngắn gọn.",
            user_prompt='Trả lời chỉ với JSON {"hello":"world"} và không kèm gì khác.',
        )
        print("Output:", repr(out))
