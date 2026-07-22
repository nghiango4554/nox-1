"""Search MIỄN PHÍ qua DuckDuckGo (HTTP thuần) — dùng khi hết quota Serper.

Đo 22/7/2026:
- Google + Chrome tự động (kể cả profile riêng có cookie) → **CAPTCHA ngay lượt đầu**.
  Chỉ Chrome THẬT của vợ (extension) mới không bị, nhưng mỗi trang đọc đều tốn session.
- DuckDuckGo HTML endpoint: HTTP 200, trả kết quả đúng, KHÔNG CAPTCHA, KHÔNG quota.
  Bắn nhanh quá thì trả **HTTP 202 + 0 kết quả** → phải giãn nhịp + thử lại.
"""

import random
import re
import threading
import time
from urllib.parse import unquote

import requests

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "vi,en;q=0.9"}
_GATE = threading.Semaphore(2)      # tối đa 2 lượt cùng lúc, tránh bị chặn nhịp
_LAST = {"t": 0.0}
_LOCK = threading.Lock()
STATS = {"ok": 0, "throttled": 0, "fail": 0}


def _pace(min_gap: float = 1.1):
    with _LOCK:
        wait = min_gap - (time.time() - _LAST["t"])
        if wait > 0:
            time.sleep(wait + random.uniform(0, 0.4))
        _LAST["t"] = time.time()


def search(query: str, num: int = 8, tries: int = 3) -> list[dict]:
    """Trả [{title, link}]. Tự lùi nhịp khi DuckDuckGo trả 202 (chặn tốc độ)."""
    for attempt in range(tries):
        with _GATE:
            _pace()
            try:
                r = requests.post("https://html.duckduckgo.com/html/", data={"q": query},
                                  headers=HEAD, timeout=22)
            except Exception:  # noqa: BLE001
                STATS["fail"] += 1
                time.sleep(1.5 * (attempt + 1))
                continue
        out = []
        for m in re.finditer(
                r'(?is)<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text):
            url = m.group(1)
            if "uddg=" in url:
                url = unquote(url.split("uddg=")[1].split("&")[0])
            out.append({"title": re.sub(r"<[^>]+>", "", m.group(2)).strip(), "link": url})
            if len(out) >= num:
                break
        if out:
            STATS["ok"] += 1
            return out
        STATS["throttled"] += 1
        time.sleep(2.5 * (attempt + 1) + random.uniform(0, 1.2))
    return []
