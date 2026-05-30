"""CWV scanner standalone — chạy trên GitHub Actions.

Fetch sitemap Sintech → parse theo url_type → gọi PSI API → output JSON.
KHÔNG phụ thuộc marketing_hub/db.py (Action không có SQLite local).

Usage:
    python cwv_scan.py --strategy mobile --url-type product --limit 300 \
        --output data/cwv_results/2026-05-30/mobile_product.json

Env:
    PSI_API_KEY  Google PageSpeed Insights API key (bắt buộc để tránh 429)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

# Windows console (cp1252) đôi khi không in được emoji — force UTF-8 stdout
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ─── Config ─────────────────────────────────────────────────────────────────
SITEMAP_INDEX = "https://sintech.vn/sitemap.xml"
PSI_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PSI_TIMEOUT = 60
KEY_DELAY = 0.4          # giây giữa request (có API key)
NOKEY_DELAY = 6.0        # giây giữa request (không có key — gần như chắc 429)
RATE_LIMIT_WAIT = 35
WORKERS_WITH_KEY = 6     # song song khi có key
WORKERS_NO_KEY = 1

# Sitemap filename pattern → url_type
TYPE_MAP = {
    "products": "product",
    "collections": "collection",
    "blogs": "blog",
    "pages": "page",
}

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


# ─── Sitemap fetch ──────────────────────────────────────────────────────────
def fetch_sitemap_index() -> list[tuple[str, str]]:
    """Return list of (sitemap_url, url_type) from sitemap index."""
    r = requests.get(SITEMAP_INDEX, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for sm in root.findall("sm:sitemap", NS):
        loc = sm.find("sm:loc", NS)
        if loc is None or not loc.text:
            continue
        url = loc.text.strip()
        utype = None
        for key, val in TYPE_MAP.items():
            if f"sitemap_{key}" in url:
                utype = val
                break
        if utype:
            out.append((url, utype))
    return out


def fetch_urls_for_type(url_type: str) -> list[str]:
    """Fetch tất cả URL từ các sitemap con khớp url_type."""
    index = fetch_sitemap_index()
    target_sitemaps = [u for u, t in index if t == url_type]
    if not target_sitemaps:
        print(f"⚠️ No sitemap found for url_type={url_type}", file=sys.stderr)
        return []

    urls: list[str] = []
    for sm_url in target_sitemaps:
        try:
            r = requests.get(sm_url, timeout=30)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            for u in root.findall("sm:url", NS):
                loc = u.find("sm:loc", NS)
                if loc is not None and loc.text:
                    urls.append(loc.text.strip())
        except Exception as e:
            print(f"⚠️ Failed to fetch {sm_url}: {e}", file=sys.stderr)

    # Dedup keep order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# ─── PSI scan ───────────────────────────────────────────────────────────────
def _safe_int(audits: dict, key: str) -> int | None:
    try:
        return int(audits[key]["numericValue"])
    except Exception:
        return None


def _safe_float(audits: dict, key: str) -> float | None:
    try:
        return round(float(audits[key]["numericValue"]), 4)
    except Exception:
        return None


def scan_url_psi(url: str, api_key: str, strategy: str) -> dict:
    """Gọi PSI API cho 1 URL. Trả dict result theo schema seo_cwv."""
    params = {"url": url, "strategy": strategy, "category": "performance"}
    if api_key:
        params["key"] = api_key

    data = None
    for attempt in range(3):
        try:
            r = requests.get(PSI_API_URL, params=params, timeout=PSI_TIMEOUT)
            if r.status_code == 429:
                wait = RATE_LIMIT_WAIT * (attempt + 1)
                print(f"⚠️ 429 rate limit — sleep {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return {
                    "url": url, "strategy": strategy, "ok": False,
                    "error": f"HTTP {r.status_code}: {r.text[:200]}",
                }
            data = r.json()
            break
        except Exception as e:
            if attempt == 2:
                return {"url": url, "strategy": strategy, "ok": False, "error": str(e)[:200]}
            time.sleep(5)
    if data is None:
        return {"url": url, "strategy": strategy, "ok": False, "error": "PSI failed after 3 retries"}

    lhr = data.get("lighthouseResult", {})
    audits = lhr.get("audits", {})
    perf_score = None
    try:
        perf_score = int(lhr["categories"]["performance"]["score"] * 100)
    except Exception:
        pass

    le = data.get("loadingExperience", {}) or {}
    le_metrics = le.get("metrics", {}) or {}
    field_ok = bool(le_metrics)
    lcp_field = cls_field = inp_field = fcp_field = None
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
        "scanned_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "performance_score": perf_score,
        "lcp_ms": _safe_int(audits, "largest-contentful-paint"),
        "cls_score": _safe_float(audits, "cumulative-layout-shift"),
        "tbt_ms": _safe_int(audits, "total-blocking-time"),
        "fcp_ms": _safe_int(audits, "first-contentful-paint"),
        "tti_ms": _safe_int(audits, "interactive"),
        "speed_index_ms": _safe_int(audits, "speed-index"),
        "field_data_ok": 1 if field_ok else 0,
        "lcp_field_ms": lcp_field,
        "cls_field": cls_field,
        "inp_field_ms": inp_field,
        "fcp_field_ms": fcp_field,
        "overall_category": le.get("overall_category", ""),
    }


# ─── Batch ──────────────────────────────────────────────────────────────────
def run_batch(urls: list[str], api_key: str, strategy: str) -> list[dict]:
    workers = WORKERS_WITH_KEY if api_key else WORKERS_NO_KEY
    delay = KEY_DELAY if api_key else NOKEY_DELAY
    total = len(urls)
    print(f"🚀 Scan {total} URL · {strategy} · {workers} workers · delay {delay}s")

    results: list[dict] = []
    done = ok = fail = 0

    def _scan(url: str) -> dict:
        time.sleep(delay)
        return scan_url_psi(url, api_key=api_key, strategy=strategy)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_scan, u): u for u in urls}
        for fut in as_completed(futures):
            url = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                res = {"url": url, "strategy": strategy, "ok": False, "error": str(e)[:200]}
            done += 1
            if res.get("ok"):
                ok += 1
            else:
                fail += 1
            results.append(res)
            if done % 10 == 0 or done == total:
                print(f"  [{done}/{total}] ok={ok} fail={fail}")

    return results


# ─── Main ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", choices=["mobile", "desktop"], required=True)
    ap.add_argument("--url-type", choices=["product", "collection", "blog", "page"], required=True)
    ap.add_argument("--limit", type=int, default=300, help="Max URL per run (Action job limit ~6h)")
    ap.add_argument("--output", required=True, help="Output JSON path")
    args = ap.parse_args()

    api_key = os.environ.get("PSI_API_KEY", "").strip()
    if not api_key:
        print("⚠️ PSI_API_KEY not set — sẽ chậm và dễ 429", file=sys.stderr)

    print(f"📥 Fetching sitemap for url_type={args.url_type} ...")
    urls = fetch_urls_for_type(args.url_type)
    print(f"   → {len(urls)} URL từ sitemap")

    if args.limit and len(urls) > args.limit:
        urls = urls[: args.limit]
        print(f"   → cắt còn {args.limit} URL theo --limit")

    if not urls:
        print("❌ Không có URL — bỏ qua")
        return

    results = run_batch(urls, api_key=api_key, strategy=args.strategy)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "strategy": args.strategy,
        "url_type": args.url_type,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "total": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "failed": sum(1 for r in results if not r.get("ok")),
        "results": results,
    }
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"✅ Wrote {out_path} · {payload['ok']} ok · {payload['failed']} fail")


if __name__ == "__main__":
    main()
