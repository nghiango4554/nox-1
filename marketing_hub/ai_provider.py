"""Lớp AI dùng chung với FALLBACK CHAIN: Codex → Claude → Gemini.

Mục đích: gen content KHÔNG bị đứng khi 1 provider hết quota / treo / chưa cài.
Tự nhảy provider kế tiếp khi gặp rate-limit, lỗi, hoặc provider không khả dụng.

Dùng: thay `codex_provider.call_codex(sys, user, timeout=T)` bằng
       `ai_provider.call_ai(sys, user, timeout=T)`.
Bắt quota cạn: `except ai_provider.AIQuotaError`.
"""
from __future__ import annotations

import codex_provider
import claude_provider
import gemini_provider

DEFAULT_TIMEOUT = 120

# Thứ tự ưu tiên mặc định. Codex (Plus) trước → Claude (Pro CLI) → Gemini (free API).
_ORDER = ("codex", "claude", "gemini")


class AIQuotaError(RuntimeError):
    """Tất cả provider đều fail / hết quota / không khả dụng."""


def _spec(name: str):
    """Trả (is_available_fn, call_fn, rate_limit_exc) cho 1 provider."""
    if name == "codex":
        return (
            codex_provider.is_codex_available,
            lambda s, u, t, eff, temp: codex_provider.call_codex(s, u, timeout=t, reasoning_effort=eff),
            codex_provider.CodexRateLimitError,
        )
    if name == "claude":
        return (
            claude_provider.is_claude_available,
            lambda s, u, t, eff, temp: claude_provider.call_claude(s, u, timeout=t),
            claude_provider.ClaudeRateLimitError,
        )
    if name == "gemini":
        return (
            gemini_provider.is_gemini_available,
            lambda s, u, t, eff, temp: gemini_provider.call_gemini(
                s, u, timeout=t, temperature=(0.7 if temp is None else temp)),
            gemini_provider.GeminiRateLimitError,
        )
    raise ValueError(f"Unknown provider: {name}")


def available_providers() -> list[str]:
    """List provider đang khả dụng (theo thứ tự ưu tiên)."""
    out = []
    for name in _ORDER:
        avail, _, _ = _spec(name)
        try:
            if avail():
                out.append(name)
        except Exception:
            pass
    return out


def call_ai(system_prompt: str, user_prompt: str,
            timeout: int = DEFAULT_TIMEOUT,
            reasoning_effort: str = "low",
            temperature: float | None = None,
            prefer: str | None = None) -> str:
    """Gọi AI với fallback chain. Trả text thuần.

    - `prefer`: tên provider muốn thử TRƯỚC (vd "claude"); phần còn lại theo thứ tự mặc định.
    - Raise AIQuotaError nếu TẤT CẢ provider fail/hết quota.
    """
    order = list(_ORDER)
    if prefer and prefer in order:
        order.remove(prefer)
        order.insert(0, prefer)

    errors = []
    for name in order:
        avail, call, rate_exc = _spec(name)
        try:
            if not avail():
                errors.append(f"{name}: không khả dụng")
                continue
        except Exception as e:
            errors.append(f"{name}: lỗi check ({str(e)[:60]})")
            continue
        try:
            out = call(system_prompt, user_prompt, timeout, reasoning_effort, temperature)
            if out and out.strip():
                return out
            errors.append(f"{name}: output rỗng")
        except rate_exc as e:
            errors.append(f"{name}: hết quota/rate limit ({str(e)[:60]})")
            continue
        except Exception as e:
            errors.append(f"{name}: lỗi ({str(e)[:60]})")
            continue

    raise AIQuotaError("Tất cả provider AI đều fail/hết quota. " + " | ".join(errors))


def call_ai_single(provider: str, system_prompt: str, user_prompt: str,
                   timeout: int = DEFAULT_TIMEOUT,
                   reasoning_effort: str = "low",
                   temperature: float | None = None) -> str:
    """Gọi DUY NHẤT 1 provider — KHÔNG fallback chéo. Dùng cho dual-AI (mỗi worker
    ghim cứng 1 provider). Raise AIQuotaError nếu provider này không khả dụng / hết
    quota / output rỗng (để worker tự dừng, không đụng quota provider kia)."""
    if provider not in _ORDER:
        raise ValueError(f"Unknown provider: {provider}")
    avail, call, rate_exc = _spec(provider)
    try:
        if not avail():
            raise AIQuotaError(f"{provider}: không khả dụng")
    except AIQuotaError:
        raise
    except Exception as e:
        raise AIQuotaError(f"{provider}: lỗi check ({str(e)[:60]})")
    try:
        out = call(system_prompt, user_prompt, timeout, reasoning_effort, temperature)
    except rate_exc as e:
        raise AIQuotaError(f"{provider}: hết quota/rate limit ({str(e)[:80]})")
    except Exception as e:
        raise RuntimeError(f"{provider}: lỗi ({str(e)[:80]})")
    if out and out.strip():
        return out
    raise AIQuotaError(f"{provider}: output rỗng")
