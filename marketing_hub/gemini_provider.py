"""Adapter gọi Google Gemini API. Pattern tương tự codex_provider.py.

Yêu cầu:
- google-genai package (pip install google-genai)
- API key trong .secrets/google.env hoặc env var GOOGLE_API_KEY

Dùng tạm thay Codex CLI khi quota Plus hết (reset 22/5). Provider mặc định
gemini-2.0-flash (free tier 200 RPD, đủ chất cho gen title/meta SEO).
"""
from __future__ import annotations

import os
from pathlib import Path


DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_TIMEOUT = 60  # giây

# Patterns nhận dạng rate limit / quota exhausted trong error response
RATE_LIMIT_PATTERNS = [
    "rate limit",
    "rate-limit",
    "rate_limit",
    "quota exceeded",
    "resource_exhausted",
    "resource exhausted",
    "429",
    "too many requests",
    "quota",
]


class GeminiRateLimitError(RuntimeError):
    """Quota Gemini API đã hết — phải đợi reset."""
    pass


def _load_api_key() -> str | None:
    """Ưu tiên env var GOOGLE_API_KEY, fallback đọc .secrets/google.env."""
    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        return key.strip()
    env_path = Path(__file__).parent.parent / ".secrets" / "google.env"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("GOOGLE_API_KEY="):
                    val = line.split("=", 1)[1].strip()
                    # Strip optional quotes
                    if (val.startswith('"') and val.endswith('"')) or \
                       (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    return val
        except Exception:
            return None
    return None


def is_gemini_available() -> bool:
    """True nếu SDK install được + API key load được."""
    try:
        from google import genai  # noqa: F401
    except ImportError:
        return False
    return _load_api_key() is not None


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(p in msg for p in RATE_LIMIT_PATTERNS)


def call_gemini(system_prompt: str, user_prompt: str,
                timeout: int = DEFAULT_TIMEOUT, model: str = DEFAULT_MODEL,
                temperature: float = 0.7) -> str:
    """Gọi Gemini API 1 lần, trả response text thuần.

    Raise GeminiRateLimitError nếu hit rate limit / quota exhausted.
    Raise RuntimeError nếu lỗi khác (network, invalid key, empty response...).
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise RuntimeError(
            "google-genai SDK chưa cài. Chạy: pip install google-genai"
        ) from e

    api_key = _load_api_key()
    if not api_key:
        raise RuntimeError(
            "Không tìm thấy GOOGLE_API_KEY (env var hoặc .secrets/google.env)."
        )

    client = genai.Client(api_key=api_key)

    # Gemini support system_instruction qua GenerateContentConfig.
    try:
        resp = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            ),
        )
    except Exception as e:
        if _is_rate_limit_error(e):
            raise GeminiRateLimitError(f"Quota Gemini hết: {e}") from e
        raise RuntimeError(f"Gemini API error: {e}") from e

    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError("Gemini trả response rỗng.")
    return text


if __name__ == "__main__":
    # Smoke test
    print("Available:", is_gemini_available())
    if is_gemini_available():
        out = call_gemini(
            system_prompt="Bạn trả lời tiếng Việt, ngắn gọn.",
            user_prompt='Trả lời chỉ với JSON {"hello":"world"} và không kèm gì khác.',
        )
        print("Output:", repr(out))
