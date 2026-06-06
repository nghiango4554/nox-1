# -*- coding: utf-8 -*-
"""CWV-P0A/P0C — Phân tích LCP READ-ONLY (không sửa theme).

- Lấy top N URL LCP Lab tệ nhất (mobile + desktop) từ data ĐÃ LƯU (seo_cwv).
- Enrich bằng 1 lần đo PSI → trích Lab (lcp/fcp/tbt/ttfb/score) + Field (CrUX P75, scope url/origin/none)
  + top audit opportunity + LCP element/asset.
- Ghi THẲNG canonical: mỗi lần đo append 1 dòng `seo_cwv_lcp_runs`; summary `seo_cwv_lcp` cập nhật
  lab_lcp_latest / lab_lcp_median (3 lần gần nhất) / lab_run_count. KHÔNG phụ thuộc backfill.

Chạy:  py -3.12 _scripts/cwv_lcp_analysis.py --top 20
       py -3.12 _scripts/cwv_lcp_analysis.py --url <url> --strategy mobile   (đo 1 URL)
"""
import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import db          # noqa: E402
import requests    # noqa: E402

PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
WORKERS = 8
POLICY_KW = ("chinh-sach", "bao-mat", "dieu-khoan", "bao-hanh", "doi-tra",
             "thanh-toan", "van-chuyen", "quy-dinh")
UTILITY_KW = ("/cart", "/account", "/search", "lien-he", "gio-hang", "tai-khoan",
              "tim-kiem", "checkout", "danh-sach-yeu-thich")


def page_type(url: str) -> str:
    p = urlparse(url).path.rstrip("/")
    if p in ("", "/"):
        return "homepage"
    if "/products/" in p:
        return "product"
    if "/collections/" in p:
        return "collection"
    if "/blogs/" in p:
        return "blog"
    if any(k in p for k in UTILITY_KW):
        return "utility"
    if "/pages/" in p:
        return "policy" if any(k in p for k in POLICY_KW) else "other"
    return "other"


def _opportunities(au: dict):
    out = []
    for k, v in au.items():
        det = v.get("details", {}) or {}
        if det.get("type") == "opportunity":
            sav = det.get("overallSavingsMs") or 0
            if sav and sav > 0:
                out.append((round(sav), k))
    out.sort(reverse=True)
    return out


def _lcp_element(au: dict):
    le = au.get("largest-contentful-paint-element", {})
    items = (le.get("details", {}) or {}).get("items", [])
    snippet = asset = ""
    try:
        node = items[0]["items"][0].get("node", {})
        snippet = (node.get("snippet") or node.get("nodeLabel") or "")[:200]
    except Exception:
        pass
    m = re.search(r'src=["\']([^"\']+)', snippet)
    if m:
        asset = m.group(1)
    return snippet, asset


def _field(data: dict):
    """Trích field LCP P75 + scope (url|origin|none) + source + category từ CrUX."""
    le = data.get("loadingExperience") or {}
    ole = data.get("originLoadingExperience") or {}

    def lcp_of(exp):
        try:
            return exp["metrics"]["LARGEST_CONTENTFUL_PAINT_MS"]["percentile"]
        except Exception:
            return None

    le_lcp = lcp_of(le)
    if le_lcp is not None:
        if le.get("origin_fallback"):
            return le_lcp, "origin", "originLoadingExperience", le.get("overall_category") or "none"
        return le_lcp, "url", "loadingExperience", le.get("overall_category") or "none"
    ole_lcp = lcp_of(ole)
    if ole_lcp is not None:
        return ole_lcp, "origin", "originLoadingExperience", ole.get("overall_category") or "none"
    return None, "none", "none", "none"


def enrich(url: str, strategy: str, key: str) -> dict:
    """1 lần đo PSI → dict canonical (raise-safe: trả {err} nếu lỗi)."""
    try:
        r = requests.get(PSI_URL, params={"url": url, "strategy": strategy,
                                          "category": "performance", "key": key}, timeout=75)
        if r.status_code != 200:
            return {"url": url, "strategy": strategy, "err": f"HTTP {r.status_code}"}
        data = r.json()
    except Exception as e:
        return {"url": url, "strategy": strategy, "err": str(e)[:80]}

    lhr = data.get("lighthouseResult", {})
    au = lhr.get("audits", {})

    def num(k):
        try:
            return round(au[k]["numericValue"])
        except Exception:
            return None

    try:
        perf = round(lhr["categories"]["performance"]["score"] * 100)
    except Exception:
        perf = None

    snippet, asset = _lcp_element(au)
    opps = _opportunities(au)
    fp75, scope, source, cat = _field(data)
    return {
        "url": url, "strategy": strategy, "page_type": page_type(url),
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "lcp": num("largest-contentful-paint"),
        "fcp": num("first-contentful-paint"),
        "tbt": num("total-blocking-time"),
        "ttfb": num("server-response-time"),
        "performance_score": perf,
        "primary_opportunity": opps[0][1] if opps else "",
        "opportunity_saving_ms": opps[0][0] if opps else 0,
        "lcp_element": snippet,
        "lcp_asset_url": asset,
        "field_lcp_p75": fp75,
        "field_scope": scope,
        "field_source": source,
        "field_category": cat,
        "err": "",
    }


def top_worst(strategy: str, n: int):
    conn = db.get_conn()
    rows = conn.execute("""
        SELECT c.url FROM seo_cwv c
        WHERE c.strategy=? AND c.lcp_ms IS NOT NULL
        ORDER BY c.lcp_ms DESC LIMIT ?
    """, (strategy, n)).fetchall()
    conn.close()
    return [(r["url"], strategy) for r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--url", default=None, help="Đo đúng 1 URL (test)")
    ap.add_argument("--strategy", default="mobile")
    args = ap.parse_args()

    import importlib
    importlib.import_module("routes.seo_tools")
    from routes.seo_tools import _load_psi_key
    key = _load_psi_key()

    db.cwv_lcp_harden_schema()   # đảm bảo bảng canonical + runs tồn tại

    if args.url:
        targets = [(args.url, args.strategy)]
    else:
        targets = top_worst("mobile", args.top) + top_worst("desktop", args.top)
    print(f"[CWV-P0C] enrich {len(targets)} URL", flush=True)

    done = ok = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(enrich, u, s, key): (u, s) for u, s in targets}
        for fu in as_completed(futs):
            d = fu.result()
            done += 1
            if d.get("err"):
                print(f"  ERR {d['strategy']} {d['url'][:50]}: {d['err']}", flush=True)
                continue
            db.cwv_lcp_record_run(d)
            ok += 1
            if done % 8 == 0:
                print(f"  {done}/{len(targets)}", flush=True)
    print(f"[OK] recorded {ok}/{len(targets)} runs vào seo_cwv_lcp_runs + cập nhật seo_cwv_lcp", flush=True)


if __name__ == "__main__":
    main()
