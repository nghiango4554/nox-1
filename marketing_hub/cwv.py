"""Core Web Vitals scanner — gọi PageSpeed Insights API (Google Lighthouse).

Không cần install Chrome/Node. Chỉ cần HTTP request tới PSI API.
API key tuỳ chọn — không có key vẫn chạy nhưng rate limit 1 req/2s.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

import db

PSI_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PSI_TIMEOUT = 60          # PSI mất 15-30s / request
DEFAULT_DELAY = 6.0       # seconds giữa các request (không có key) — 429 nếu quá nhanh
KEY_DELAY = 0.8           # seconds giữa các request (có API key)
RATE_LIMIT_WAIT = 35      # seconds chờ khi nhận 429

# ─── State ─────────────────────────────────────────────────────────────────
_lock = threading.Lock()
_state = {
    "running": False,
    "stop_requested": False,
    "total": 0,
    "done": 0,
    "ok": 0,
    "failed": 0,
    "current_url": "",
    "strategy": "mobile",
    "started_at": None,
    "finished_at": None,
    "message": "",
}


def _set(**kw):
    with _lock:
        _state.update(kw)


def state_snapshot() -> dict:
    with _lock:
        return dict(_state)


# ─── PSI API ────────────────────────────────────────────────────────────────

def _safe_num(audits: dict, key: str, factor: float = 1.0) -> int | None:
    try:
        return int(audits[key]["numericValue"] * factor)
    except Exception:
        return None


def _safe_float(audits: dict, key: str) -> float | None:
    try:
        return round(float(audits[key]["numericValue"]), 4)
    except Exception:
        return None


def scan_url_psi(url: str, api_key: str = "", strategy: str = "mobile") -> dict:
    """Gọi PSI API cho 1 URL. Trả dict result (hoặc dict với error)."""
    params = {"url": url, "strategy": strategy, "category": "performance"}
    if api_key:
        params["key"] = api_key

    for attempt in range(3):
        try:
            r = requests.get(PSI_API_URL, params=params, timeout=PSI_TIMEOUT)
            if r.status_code == 429:
                wait = RATE_LIMIT_WAIT * (attempt + 1)
                _set(message=f"⚠️ Rate limit 429 — chờ {wait}s rồi thử lại... (cần API key để tránh)")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return {"url": url, "strategy": strategy, "error": f"HTTP {r.status_code}: {r.text[:200]}", "ok": False}
            data = r.json()
            break
        except Exception as e:
            return {"url": url, "strategy": strategy, "error": str(e)[:200], "ok": False}
    else:
        return {"url": url, "strategy": strategy, "error": "Rate limit 429 sau 3 lần thử — cần API key", "ok": False}

    # ── Lab data (Lighthouse) ─────────────────────────────────────────────
    lhr = data.get("lighthouseResult", {})
    audits = lhr.get("audits", {})
    perf_score = None
    try:
        perf_score = int(lhr["categories"]["performance"]["score"] * 100)
    except Exception:
        pass

    lcp_ms   = _safe_num(audits, "largest-contentful-paint")
    cls_val  = _safe_float(audits, "cumulative-layout-shift")
    tbt_ms   = _safe_num(audits, "total-blocking-time")
    fcp_ms   = _safe_num(audits, "first-contentful-paint")
    tti_ms   = _safe_num(audits, "interactive")
    si_ms    = _safe_num(audits, "speed-index")

    # ── Field data (real users — CrUX) ───────────────────────────────────
    le = data.get("loadingExperience", {})
    le_metrics = le.get("metrics", {})
    field_ok = bool(le_metrics)
    lcp_field = None
    cls_field = None
    inp_field = None
    fcp_field = None
    overall_cat = le.get("overall_category", "")
    try:
        lcp_field = le_metrics["LARGEST_CONTENTFUL_PAINT_MS"]["percentile"]
    except Exception:
        pass
    try:
        cls_raw = le_metrics["CUMULATIVE_LAYOUT_SHIFT_SCORE"]["percentile"]
        cls_field = round(cls_raw / 100, 4) if cls_raw > 1 else round(cls_raw, 4)
    except Exception:
        pass
    try:
        inp_field = le_metrics["INTERACTION_TO_NEXT_PAINT"]["percentile"]
    except Exception:
        pass
    try:
        fcp_field = le_metrics["FIRST_CONTENTFUL_PAINT_MS"]["percentile"]
    except Exception:
        pass

    return {
        "url": url,
        "strategy": strategy,
        "ok": True,
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        # Lab
        "performance_score": perf_score,
        "lcp_ms": lcp_ms,
        "cls_score": cls_val,
        "tbt_ms": tbt_ms,
        "fcp_ms": fcp_ms,
        "tti_ms": tti_ms,
        "speed_index_ms": si_ms,
        # Field
        "field_data_ok": 1 if field_ok else 0,
        "lcp_field_ms": lcp_field,
        "cls_field": cls_field,
        "inp_field_ms": inp_field,
        "fcp_field_ms": fcp_field,
        "overall_category": overall_cat,
    }


# ─── Batch scan ─────────────────────────────────────────────────────────────

WORKERS_WITH_KEY = 8   # 8 luồng song song khi có API key
WORKERS_NO_KEY   = 1   # tuần tự khi không có key (tránh 429)

def _run_scan(urls: list, api_key: str, strategy: str):
    workers = WORKERS_WITH_KEY if api_key else WORKERS_NO_KEY
    total = len(urls)
    _set(running=True, stop_requested=False, total=total, done=0, ok=0, failed=0,
         strategy=strategy, started_at=datetime.now().isoformat(timespec="seconds"),
         finished_at=None, message=f"Đang scan {total} URL ({strategy}) — {workers} luồng song song...")

    ok_count = failed_count = done_count = 0
    _counter_lock = threading.Lock()

    def _scan_one(url):
        if _state["stop_requested"]:
            return None
        _set(current_url=url)
        return scan_url_psi(url, api_key=api_key, strategy=strategy)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_scan_one, url): url for url in urls}
        for future in as_completed(futures):
            if _state["stop_requested"]:
                # Cancel pending futures
                for f in futures:
                    f.cancel()
                break
            result = future.result()
            url = futures[future]
            with _counter_lock:
                done_count += 1
                if result and result.get("ok"):
                    db.cwv_upsert(result)
                    ok_count += 1
                else:
                    failed_count += 1
                _set(done=done_count, ok=ok_count, failed=failed_count,
                     message=f"[{done_count}/{total}] {url}")

    if _state["stop_requested"]:
        _set(running=False, current_url="",
             finished_at=datetime.now().isoformat(timespec="seconds"),
             message=f"⏹ Đã dừng — {ok_count} OK · {failed_count} lỗi")
    else:
        _set(running=False, current_url="",
             finished_at=datetime.now().isoformat(timespec="seconds"),
             message=f"✅ Xong! {ok_count} OK · {failed_count} lỗi")


def start_scan_async(urls: list, api_key: str = "", strategy: str = "mobile") -> bool:
    if _state["running"]:
        return False
    t = threading.Thread(target=_run_scan, args=(urls, api_key, strategy), daemon=True)
    t.start()
    return True


def stop_scan():
    _set(stop_requested=True)


def get_top_urls(limit: int = 50, url_type: str = "product", skip_scanned: bool = False, strategy: str = "mobile") -> list[str]:
    """Lấy top N URL từ seo_pages (theo internal_links desc) để scan CWV."""
    return db.cwv_top_urls(limit=limit, url_type=url_type, skip_scanned=skip_scanned, strategy=strategy)
