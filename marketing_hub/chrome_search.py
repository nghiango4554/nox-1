"""Search Google bằng CHROME THẬT chạy từ script — dùng khi hết quota Serper.

Vợ chốt 22/7: "hết serper anh có thể dùng hẳn chrome".
- Chrome thật (channel="chrome"), profile riêng, cửa sổ đẩy ra ngoài màn hình
  → KHÔNG giành tab Chrome vợ đang dùng, KHÔNG gửi ảnh về (không tốn session).
- CHẠY MỘT LUỒNG: Playwright sync API không an toàn khi chia nhiều thread.
- Gặp CAPTCHA thì DỪNG và báo, tuyệt đối không tự giải.
"""

import random
import re
import threading
import time
from urllib.parse import quote_plus

_LOCK = threading.Lock()
_PW = _BROWSER = _CTX = None
CAPTCHA_HIT = {"n": 0}


class CaptchaBlocked(RuntimeError):
    pass


def _ensure():
    global _PW, _BROWSER, _CTX
    if _CTX:
        return _CTX
    from playwright.sync_api import sync_playwright
    _PW = sync_playwright().start()
    _BROWSER = _PW.chromium.launch(
        headless=False, channel="chrome",
        args=["--disable-blink-features=AutomationControlled", "--window-position=2400,0",
              "--window-size=1200,900"])
    _CTX = _BROWSER.new_context(locale="vi-VN", viewport={"width": 1200, "height": 900})
    _CTX.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return _CTX


def close():
    global _PW, _BROWSER, _CTX
    try:
        if _BROWSER:
            _BROWSER.close()
        if _PW:
            _PW.stop()
    except Exception:  # noqa: BLE001
        pass
    _PW = _BROWSER = _CTX = None


def search(query: str, num: int = 8) -> list[dict]:
    """Trả [{title, link}] lấy từ trang kết quả Google. Ném CaptchaBlocked nếu bị chặn."""
    with _LOCK:
        ctx = _ensure()
        pg = ctx.new_page()
        try:
            pg.goto(f"https://www.google.com/search?q={quote_plus(query)}&num={num}&hl=vi",
                    wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(random.randint(700, 1400))
            body = pg.content()
            if re.search(r"(?i)unusual traffic|xác minh rằng bạn|recaptcha|/sorry/", body):
                CAPTCHA_HIT["n"] += 1
                raise CaptchaBlocked("Google chặn bằng CAPTCHA — dừng, không tự giải")
            hits = pg.evaluate("""() => {
              const out = [];
              document.querySelectorAll('a[href^="http"]').forEach(a => {
                const h3 = a.querySelector('h3');
                if (h3 && h3.innerText.trim()) out.push({title: h3.innerText.trim(), link: a.href});
              });
              return out;
            }""")
            seen, res = set(), []
            for h in hits:
                u = h["link"].split("&")[0]
                if "google.com" in u or u in seen:
                    continue
                seen.add(u)
                res.append({"title": h["title"], "link": u})
                if len(res) >= num:
                    break
            return res
        finally:
            pg.close()
            time.sleep(random.uniform(1.2, 2.6))     # giãn nhịp cho giống người
