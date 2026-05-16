"""Telegram notification bot — gửi message tới chat_id của Nghĩa khi pipeline xong."""
import os
import json
import logging
from pathlib import Path
import requests

logger = logging.getLogger(__name__)

# Default chat_id của Nghĩa (Telegram sender_id từ metadata conversation)
DEFAULT_CHAT_ID = "6593753113"

OPENCLAW_CONFIG = Path(os.environ["USERPROFILE"]) / ".openclaw" / "openclaw.json" \
    if os.environ.get("USERPROFILE") else Path.home() / ".openclaw" / "openclaw.json"


_cached_token = None


def _load_token() -> str:
    """Lấy bot token: ưu tiên env var, fallback đọc từ openclaw.json."""
    global _cached_token
    if _cached_token:
        return _cached_token
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        _cached_token = token
        return token
    if OPENCLAW_CONFIG.exists():
        try:
            with open(OPENCLAW_CONFIG, "r", encoding="utf-8") as f:
                data = json.load(f)
            token = data.get("channels", {}).get("telegram", {}).get("botToken")
            if token:
                _cached_token = token
                return token
        except (ValueError, OSError) as e:
            logger.warning(f"Đọc openclaw.json fail: {e}")
    return ""


def send_telegram(text: str, chat_id: str = None, parse_mode: str = "HTML") -> bool:
    """Gửi message qua Telegram bot. Trả True nếu thành công."""
    token = _load_token()
    if not token:
        logger.warning("Telegram bot token chưa setup, skip notification")
        return False
    cid = chat_id or DEFAULT_CHAT_ID
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": cid,
            "text": text[:4000],  # Telegram limit 4096
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }, timeout=10)
        if r.status_code == 200:
            return True
        logger.error(f"Telegram API error {r.status_code}: {r.text[:200]}")
        return False
    except requests.RequestException as e:
        logger.error(f"Telegram send fail: {e}")
        return False


def notify_crawl_done(state: dict, broken_summary: dict = None) -> bool:
    """Báo khi crawl SEO xong (Phase 1)."""
    msg = (
        f"✅ <b>Crawl SEO xong</b>\n"
        f"📊 {state.get('success', 0)}/{state.get('total', 0)} URL OK · "
        f"❌ {state.get('failed', 0)} lỗi\n"
        f"⏱ {state.get('message', '')}\n"
        f"🔗 http://127.0.0.1:5055/seo"
    )
    return send_telegram(msg)


def notify_link_check_done(link_state: dict, broken_summary: dict = None) -> bool:
    """Báo khi check broken external links xong (Phase 2)."""
    bs = broken_summary or {}
    msg = (
        f"✅ <b>Check broken link xong</b>\n"
        f"🔗 {link_state.get('checked', 0)}/{link_state.get('total', 0)} link đã check\n"
        f"💀 <b>{bs.get('broken', link_state.get('broken', 0))}</b> link gãy · "
        f"✅ {bs.get('ok', 0)} OK\n"
        f"🔗 http://127.0.0.1:5055/seo/broken-links"
    )
    return send_telegram(msg)


def notify_haravan_sync_done(state: dict, stats: dict = None) -> bool:
    """Báo khi sync Haravan products xong."""
    s = stats or {}
    msg = (
        f"✅ <b>Sync Haravan xong</b>\n"
        f"📦 {state.get('fetched', 0)}/{state.get('total', 0)} SP · "
        f"❌ {state.get('failed', 0)} lỗi\n"
        f"📊 Điểm SEO TB: <b>{s.get('avg_score', '?')}/100</b>\n"
        f"🔴 {s.get('bad', 0)} SP cần sửa (&lt;60đ)\n"
        f"🔗 http://127.0.0.1:5055/haravan"
    )
    return send_telegram(msg)


def notify_pipeline_complete(state: dict, link_state: dict, broken_summary: dict, stats: dict) -> bool:
    """Báo khi cả Pipeline crawl + link check xong."""
    msg = (
        f"🎉 <b>Pipeline SEO hoàn tất</b>\n\n"
        f"<b>Phase 1 — Crawl URL:</b>\n"
        f"  📊 {state.get('success', 0)}/{state.get('total', 0)} OK · "
        f"❌ {state.get('failed', 0)} lỗi\n"
        f"  🟢 {stats.get('good', 0)} tốt · 🟡 {stats.get('ok', 0)} OK · "
        f"🔴 {stats.get('bad', 0)} cần sửa\n"
        f"  📈 Điểm TB: <b>{stats.get('avg_score', '?')}/100</b>\n\n"
        f"<b>Phase 2 — Check broken links:</b>\n"
        f"  🔗 {link_state.get('total', 0)} external · "
        f"💀 <b>{broken_summary.get('broken', 0)}</b> gãy · "
        f"✅ {broken_summary.get('ok', 0)} OK\n\n"
        f"🔗 http://127.0.0.1:5055/seo"
    )
    return send_telegram(msg)
