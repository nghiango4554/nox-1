"""Weekly CWV scan — chạy trên GitHub Actions cloud (không cần máy local bật).

Flow:
1. Fetch sitemap.xml Sintech (gồm 6 sub-sitemap: products/blogs/pages/collections).
2. Gọi PSI API mobile + desktop cho mỗi URL (ThreadPoolExecutor 16 workers).
3. Save snapshot vào data/cwv_history/YYYY-Www.json.
4. Diff vs snapshot tuần trước → tính URL regress/improve.
5. Format Markdown summary → gửi Telegram bot.

Env vars:
- PSI_API_KEY      — Google PageSpeed API key (free, lấy ở Cloud Console)
- TELEGRAM_BOT_TOKEN — bot token (cần rotate vì 401 từ 12/5)
- TELEGRAM_CHAT_ID  — chat ID nhận report
- MAX_URLS         — limit số URL test (default 0 = unlimited)
- SEND_TELEGRAM    — 'true'/'false' (default 'true')
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

PSI_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
SITEMAP_URL = "https://sintech.vn/sitemap.xml"
PSI_API_KEY = os.getenv("PSI_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
MAX_URLS = int(os.getenv("MAX_URLS", "0") or "0")
SEND_TELEGRAM = os.getenv("SEND_TELEGRAM", "true").lower() == "true"

WORKERS = 16 if PSI_API_KEY else 2
PSI_TIMEOUT = 60
PSI_RATE_LIMIT_WAIT = 35
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


# ─── Sitemap ────────────────────────────────────────────────────────────────

def fetch_urls_from_sitemap(url: str, _depth: int = 0) -> list[str]:
    """Recursive: nếu sitemap index → đệ quy vào sub-sitemap."""
    if _depth > 3:
        return []
    print(f"  [sitemap] GET {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    urls: list[str] = []
    for sm in root.findall("sm:sitemap/sm:loc", SITEMAP_NS):
        if sm.text:
            urls.extend(fetch_urls_from_sitemap(sm.text, _depth + 1))
    for loc in root.findall("sm:url/sm:loc", SITEMAP_NS):
        if loc.text:
            urls.append(loc.text)
    return urls


# ─── PSI scan ───────────────────────────────────────────────────────────────

def scan_psi(url: str, strategy: str) -> dict:
    params = {"url": url, "strategy": strategy, "category": "performance"}
    if PSI_API_KEY:
        params["key"] = PSI_API_KEY

    for attempt in range(3):
        try:
            r = requests.get(PSI_API_URL, params=params, timeout=PSI_TIMEOUT)
            if r.status_code == 429:
                wait = PSI_RATE_LIMIT_WAIT * (attempt + 1)
                print(f"  [429] {url[:60]} — wait {wait}s")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return {"url": url, "strategy": strategy, "ok": False,
                        "error": f"HTTP {r.status_code}"}
            data = r.json()
            break
        except Exception as e:
            return {"url": url, "strategy": strategy, "ok": False, "error": str(e)[:200]}
    else:
        return {"url": url, "strategy": strategy, "ok": False, "error": "Rate limit 429 sau 3 lần"}

    lhr = data.get("lighthouseResult", {})
    audits = lhr.get("audits", {})

    try:
        score = int(lhr["categories"]["performance"]["score"] * 100)
    except Exception:
        score = None

    def num_int(key: str) -> int | None:
        try:
            return int(audits[key]["numericValue"])
        except Exception:
            return None

    def num_float(key: str) -> float | None:
        try:
            return round(float(audits[key]["numericValue"]), 4)
        except Exception:
            return None

    return {
        "url": url,
        "strategy": strategy,
        "ok": True,
        "performance_score": score,
        "lcp_ms": num_int("largest-contentful-paint"),
        "cls_score": num_float("cumulative-layout-shift"),
        "tbt_ms": num_int("total-blocking-time"),
        "fcp_ms": num_int("first-contentful-paint"),
    }


# ─── Snapshot + diff ────────────────────────────────────────────────────────

def isoweek_filename(d: datetime.date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}.json"


def load_prev_snapshot(snap_dir: Path, today: datetime.date) -> list[dict] | None:
    """Load snapshot tuần trước (hoặc tuần gần nhất có file)."""
    for back in range(1, 6):
        d = today - datetime.timedelta(days=back * 7)
        candidate = snap_dir / isoweek_filename(d)
        if candidate.exists():
            print(f"[*] Prev snapshot: {candidate}")
            return json.loads(candidate.read_text(encoding="utf-8"))
    return None


def compute_diff(current: list[dict], prev: list[dict]) -> dict:
    """So sánh score mỗi (url, strategy). Regress = giảm ≥10đ, Improve = tăng ≥10đ."""
    prev_map = {(r["url"], r["strategy"]): r.get("performance_score")
                for r in prev if r.get("ok") and r.get("performance_score") is not None}
    regressions: list[tuple] = []
    improvements: list[tuple] = []
    for r in current:
        if not r.get("ok") or r.get("performance_score") is None:
            continue
        key = (r["url"], r["strategy"])
        if key not in prev_map:
            continue
        delta = r["performance_score"] - prev_map[key]
        if delta <= -10:
            regressions.append((r["url"], r["strategy"], prev_map[key], r["performance_score"]))
        elif delta >= 10:
            improvements.append((r["url"], r["strategy"], prev_map[key], r["performance_score"]))
    regressions.sort(key=lambda x: x[3] - x[2])  # tệ nhất lên đầu
    improvements.sort(key=lambda x: x[2] - x[3])
    return {"regressions": regressions, "improvements": improvements}


def summarize(results: list[dict]) -> dict:
    ok = [r for r in results if r.get("ok") and r.get("performance_score") is not None]
    out: dict = {"total_calls": len(results), "ok_calls": len(ok),
                 "failed_calls": len(results) - len(ok), "by_strategy": {}}
    for strat in ("mobile", "desktop"):
        scores = [r["performance_score"] for r in ok if r["strategy"] == strat]
        if not scores:
            out["by_strategy"][strat] = None
            continue
        out["by_strategy"][strat] = {
            "n": len(scores),
            "avg": round(sum(scores) / len(scores), 1),
            "min": min(scores), "max": max(scores),
            "bad": sum(1 for s in scores if s < 50),
            "mid": sum(1 for s in scores if 50 <= s < 90),
            "good": sum(1 for s in scores if s >= 90),
        }
    return out


def format_telegram(today: datetime.date, summary: dict, diff: dict | None,
                    elapsed_s: float, max_urls_note: str) -> str:
    parts = [
        "🤖 *CWV Weekly Report — Sintech*",
        f"📅 {today.isoformat()} · ⏱ {int(elapsed_s)}s",
        f"🔍 {summary['total_calls']} scan · ✅ {summary['ok_calls']} OK · "
        f"❌ {summary['failed_calls']} lỗi{max_urls_note}",
        "",
    ]
    for strat in ("mobile", "desktop"):
        s = summary["by_strategy"].get(strat)
        if not s:
            continue
        icon = "📱" if strat == "mobile" else "🖥"
        parts.append(
            f"{icon} *{strat}*: avg `{s['avg']}/100` "
            f"(tệ<50: `{s['bad']}` · TB 50-89: `{s['mid']}` · tốt≥90: `{s['good']}`)"
        )

    if diff is None:
        parts.append("\n_Chưa có baseline tuần trước — đây là snapshot đầu._")
    else:
        r_n = len(diff["regressions"])
        i_n = len(diff["improvements"])
        parts.append(f"\n📉 *{r_n} URL tệ đi ≥10đ* · 📈 *{i_n} URL khá hơn ≥10đ*")
        if diff["regressions"][:5]:
            parts.append("\n*TOP REGRESSION:*")
            for url, strat, old, new in diff["regressions"][:5]:
                short = url.replace("https://sintech.vn", "")[:55]
                parts.append(f"  • `{strat}` {short}: {old}→{new} ({new-old:+d})")

    return "\n".join(parts)


def send_telegram(msg: str) -> None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("[!] Skip Telegram — thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }, timeout=30)
        print(f"[*] Telegram: HTTP {r.status_code} — {r.text[:200]}")
    except Exception as e:
        print(f"[!] Telegram fail: {e}")


# ─── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 60)
    print("CWV Weekly Scan")
    print(f"PSI key: {'yes' if PSI_API_KEY else 'NO (sẽ rất chậm)'}")
    print(f"Workers: {WORKERS}")
    print(f"MAX_URLS: {MAX_URLS or 'unlimited'}")
    print(f"Send Telegram: {SEND_TELEGRAM}")
    print("=" * 60)

    started = time.time()

    print("[1/3] Fetch sitemap...")
    try:
        urls = fetch_urls_from_sitemap(SITEMAP_URL)
    except Exception as e:
        print(f"[!] Fetch sitemap fail: {e}")
        return 1
    urls = sorted({u for u in urls if u and "sintech.vn" in u})
    print(f"[*] {len(urls)} URL unique từ sitemap")

    if MAX_URLS and MAX_URLS > 0:
        urls = urls[:MAX_URLS]
        print(f"[*] Limit MAX_URLS={MAX_URLS} → còn {len(urls)} URL")

    jobs = [(u, s) for u in urls for s in ("mobile", "desktop")]
    print(f"[2/3] PSI scan: {len(jobs)} calls ({WORKERS} workers)...")

    results: list[dict] = []
    done = 0
    last_log = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(scan_psi, u, s): (u, s) for u, s in jobs}
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            done += 1
            if time.time() - last_log >= 15:
                elapsed = time.time() - started
                eta = elapsed / done * (len(jobs) - done) if done else 0
                print(f"  [{done}/{len(jobs)}] elapsed={elapsed:.0f}s eta={eta:.0f}s")
                last_log = time.time()

    elapsed = time.time() - started
    print(f"[*] Scan xong sau {elapsed:.0f}s")

    print("[3/3] Save snapshot + diff + Telegram...")
    today = datetime.date.today()
    snap_dir = Path("data/cwv_history")
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_file = snap_dir / isoweek_filename(today)
    snap_file.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[*] Saved {snap_file} ({snap_file.stat().st_size:,} bytes)")

    summary = summarize(results)
    prev = load_prev_snapshot(snap_dir, today)
    diff = compute_diff(results, prev) if prev else None

    max_urls_note = f" · `MAX_URLS={MAX_URLS}` (smoke test)" if MAX_URLS else ""
    msg = format_telegram(today, summary, diff, elapsed, max_urls_note)
    print("\n" + "=" * 60)
    print(msg)
    print("=" * 60)

    if SEND_TELEGRAM:
        send_telegram(msg)
    else:
        print("[*] SEND_TELEGRAM=false → skip gửi")

    return 0


if __name__ == "__main__":
    sys.exit(main())
