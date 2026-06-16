"""Core Web Vitals scanner — gọi PageSpeed Insights API (Google Lighthouse).

Không cần install Chrome/Node. Chỉ cần HTTP request tới PSI API.
API key tuỳ chọn — không có key vẫn chạy nhưng rate limit 1 req/2s.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

import db

# File lưu mốc bắt đầu ĐỢT quét hiện tại (sống sót qua restart → resume được).
_PASS_FILE = Path(__file__).parent / "data" / "cwv_pass.json"


def current_pass() -> str | None:
    """Mốc ISO bắt đầu đợt quét đang dở (None nếu không có đợt nào)."""
    try:
        return json.loads(_PASS_FILE.read_text(encoding="utf-8")).get("pass_start")
    except Exception:
        return None


def _save_pass(ts: str):
    try:
        _PASS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PASS_FILE.write_text(json.dumps({"pass_start": ts}), encoding="utf-8")
    except Exception:
        pass


def _clear_pass():
    try:
        _PASS_FILE.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass

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
    # All Batch chain fields
    "chain_active": False,
    "phase_idx": 0,
    "phase_total": 0,
    "phase_label": "",
    "chain_total_ok": 0,
    "chain_total_failed": 0,
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

def _run_scan_core(urls: list, api_key: str, strategy: str, prefix: str = ""):
    """Core batch scan — không touch running/started_at/finished_at/chain_active.
    Dùng được cho cả single-batch lẫn từng phase của chain."""
    workers = WORKERS_WITH_KEY if api_key else WORKERS_NO_KEY
    total = len(urls)
    _set(total=total, done=0, ok=0, failed=0, strategy=strategy,
         message=f"{prefix}Đang scan {total} URL ({strategy}) — {workers} luồng song song...")

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
                     message=f"{prefix}[{done_count}/{total}] {url}")

    return ok_count, failed_count


def _run_scan(urls: list, api_key: str, strategy: str):
    """Single batch — set running on/off."""
    _set(running=True, stop_requested=False, chain_active=False,
         started_at=datetime.now().isoformat(timespec="seconds"),
         finished_at=None)
    ok_count, failed_count = _run_scan_core(urls, api_key, strategy)

    tail = f"{ok_count} OK · {failed_count} lỗi"
    if _state["stop_requested"]:
        _set(running=False, current_url="",
             finished_at=datetime.now().isoformat(timespec="seconds"),
             message=f"⏹ Đã dừng — {tail}")
    else:
        _set(running=False, current_url="",
             finished_at=datetime.now().isoformat(timespec="seconds"),
             message=f"✅ Xong! {tail}")


# ─── ALL BATCH chain ────────────────────────────────────────────────────────

ALL_PHASES = [
    ("mobile",  "product"),
    ("mobile",  "collection"),
    ("mobile",  "blog"),
    ("mobile",  "page"),
    ("desktop", "product"),
    ("desktop", "collection"),
    ("desktop", "blog"),
    ("desktop", "page"),
]


def _snapshot_completed_pass():
    """Đợt quét xong → lưu kết quả vào seo_cwv_history (tuần ISO hiện tại, đè nếu trùng tuần)
    để tab /seo/history so sánh đợt này với các đợt trước."""
    try:
        iso = datetime.now().isocalendar()
        n = db.cwv_history_snapshot(iso.week, iso.year, replace=True)
        return n
    except Exception:
        return 0


def _run_chain(api_key: str, pass_start: str):
    """Quét toàn bộ 1 ĐỢT: 8 phase mobile×(product→collection→blog→page) → desktop×(...).
    Mỗi phase chỉ quét URL CHƯA quét trong đợt này (since=pass_start) → resume tự nhiên.
    Xong sạch (không bị dừng) → snapshot history + xoá mốc đợt. Bị dừng → giữ mốc để quét tiếp."""
    n_phases = len(ALL_PHASES)
    _set(running=True, stop_requested=False, chain_active=True,
         phase_idx=0, phase_total=n_phases, phase_label="",
         chain_total_ok=0, chain_total_failed=0,
         total=0, done=0, ok=0, failed=0,
         started_at=datetime.now().isoformat(timespec="seconds"),
         finished_at=None,
         message=f"🚀 Bắt đầu quét toàn bộ — {n_phases} phase (mobile × 4 + desktop × 4)")

    chain_ok = chain_failed = 0

    for idx, (strat, utype) in enumerate(ALL_PHASES):
        if _state["stop_requested"]:
            break

        label = f"{strat}/{utype}"
        urls = db.cwv_top_urls(limit=99999, url_type=utype, strategy=strat, since=pass_start)

        if not urls:
            _set(phase_idx=idx + 1, phase_label=label, strategy=strat,
                 message=f"[Phase {idx + 1}/{n_phases}] {label} — đã quét xong, bỏ qua")
            continue

        _set(phase_idx=idx + 1, phase_label=label, strategy=strat,
             message=f"[Phase {idx + 1}/{n_phases}] {label} — {len(urls)} URL")

        prefix = f"[Phase {idx + 1}/{n_phases}] {label} · "
        ok_n, failed_n = _run_scan_core(urls, api_key, strat, prefix=prefix)
        chain_ok += ok_n
        chain_failed += failed_n
        _set(chain_total_ok=chain_ok, chain_total_failed=chain_failed)

    tail = f"{chain_ok} OK · {chain_failed} lỗi (tổng đợt)"
    if _state["stop_requested"]:
        # Giữ mốc đợt → lần sau bấm "Quét toàn bộ" sẽ quét tiếp phần còn lại.
        _set(running=False, chain_active=False, current_url="",
             finished_at=datetime.now().isoformat(timespec="seconds"),
             message=f"⏹ Đã dừng — đã lưu tiến độ, bấm Quét toàn bộ để quét tiếp. {tail}")
    else:
        snap_n = _snapshot_completed_pass()
        _clear_pass()
        _set(running=False, chain_active=False, current_url="",
             finished_at=datetime.now().isoformat(timespec="seconds"),
             message=f"✅ Hoàn tất quét toàn bộ! {tail} · đã lưu {snap_n} dòng vào lịch sử")


def start_scan_async(urls: list, api_key: str = "", strategy: str = "mobile") -> bool:
    if _state["running"]:
        return False
    t = threading.Thread(target=_run_scan, args=(urls, api_key, strategy), daemon=True)
    t.start()
    return True


def start_full_scan_async(api_key: str = "", force_new: bool = False) -> dict:
    """1 nút "Quét toàn bộ" — tự quyết RESUME hay ĐỢT MỚI:
    - Có mốc đợt cũ + còn URL chưa quét → resume (quét tiếp phần dở).
    - Không có mốc / đợt cũ đã xong → bắt đầu ĐỢT MỚI (quét lại tất cả, mobile→desktop).
    - force_new=True → LUÔN bắt đầu đợt mới (crawl lại toàn bộ từ đầu), bỏ qua resume.
    Trả {ok, mode, remaining}."""
    if _state["running"]:
        return {"ok": False, "mode": "running", "message": "Đang quét rồi"}

    pass_start = current_pass()
    mode = "resume"
    if not force_new and pass_start and db.cwv_pass_stats(pass_start)["remaining"] > 0:
        mode = "resume"          # đợt cũ còn dở → quét tiếp
    else:
        pass_start = datetime.now().isoformat(timespec="seconds")
        _save_pass(pass_start)
        mode = "new"             # đợt mới → quét lại toàn bộ

    t = threading.Thread(target=_run_chain, args=(api_key, pass_start), daemon=True)
    t.start()
    return {"ok": True, "mode": mode}


# Alias tương thích ngược (code/test cũ còn gọi tên này)
def start_chain_async(api_key: str = "") -> bool:
    return start_full_scan_async(api_key).get("ok", False)


def stop_scan():
    _set(stop_requested=True)


def get_top_urls(limit: int = 50, url_type: str = "product", skip_scanned: bool = False, strategy: str = "mobile") -> list[str]:
    """Lấy top N URL từ seo_pages (theo internal_links desc) để scan CWV."""
    return db.cwv_top_urls(limit=limit, url_type=url_type, skip_scanned=skip_scanned, strategy=strategy)
