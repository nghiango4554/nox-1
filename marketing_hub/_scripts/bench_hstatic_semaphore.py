"""Benchmark host-specific semaphore cho hstatic CDN (Phase 3, validation-only).

KHÔNG ghi DB production. Đọc fixed sample hstatic từ DB (read-only), replicate
hành vi _check_link (HEAD→GET 405/403, thread-local Session, pool_block=True,
per-host semaphore) ở các mức per-host 4/8/12/16. global workers=48, timeout giữ nguyên.
Warmup 1 lượt trước để cân bằng cache CDN → so sánh công bằng giữa các mức.

Đo mỗi mức: duration, links/s, healthy/broken/uncertain/timeout, status dist,
avg/p50/p95 latency, + Flask endpoint latency (monitor thread) trong lúc chạy.
"""
import sys, os, time, threading, statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from requests.adapters import HTTPAdapter

import db

SAMPLE_PER_HOST = 200            # 200 cdn + 200 product = 400 URL
TIMEOUT_HEAD = 2                 # giữ nguyên LINK_CHECK_TIMEOUT
TIMEOUT_GET = 3                  # giữ nguyên LINK_CHECK_TIMEOUT_GET
GLOBAL_WORKERS = 48              # giữ nguyên global workers
LEVELS = [4, 8, 12, 16]
UA = "Mozilla/5.0 (compatible; SintechLinkCheck/1.0)"
FLASK = "http://127.0.0.1:5055"
ENDPOINTS = ["/", "/api/jobs", "/seo/title-meta", "/seo/broken-links", "/jobs"]


def load_sample():
    c = db.get_conn()
    urls = []
    for h in ("cdn.hstatic.net", "product.hstatic.net"):
        rows = c.execute(
            "SELECT DISTINCT target_url FROM seo_links WHERE is_internal=0 "
            "AND target_url LIKE ? AND status_code=200 LIMIT ?",
            (f"https://{h}/%", SAMPLE_PER_HOST)).fetchall()
        urls += [r[0] for r in rows]
    c.close()
    return urls


# thread-local session (giống production)
_tls = threading.local()
def _session(per_host):
    s = getattr(_tls, "s", None)
    if s is None:
        s = requests.Session()
        ad = HTTPAdapter(pool_connections=8, pool_maxsize=per_host, max_retries=0, pool_block=True)
        s.mount("http://", ad); s.mount("https://", ad)
        _tls.s = s
    return s

def _host_of(u):
    from urllib.parse import urlparse
    try: return urlparse(u).hostname or ""
    except Exception: return ""


def check(target, sema_map, per_host):
    host = _host_of(target)
    sem = sema_map.get(host)
    t0 = time.time()
    if sem: sem.acquire()
    try:
        sess = _session(per_host)
        r = sess.head(target, headers={"User-Agent": UA}, timeout=TIMEOUT_HEAD, allow_redirects=True)
        sc = r.status_code
        try: r.close()
        except Exception: pass
        if sc in (405, 403):
            r2 = sess.get(target, headers={"User-Agent": UA}, timeout=TIMEOUT_GET, allow_redirects=True, stream=True)
            sc = r2.status_code
            try: r2.close()
            except Exception: pass
        return sc, None, time.time() - t0
    except Exception as e:
        kind = "read_timeout" if "Read timed out" in str(e) else ("conn_timeout" if "timed out" in str(e) else "err")
        return 0, kind, time.time() - t0
    finally:
        if sem: sem.release()


def flask_monitor(stop_evt, out):
    import itertools
    cyc = itertools.cycle(ENDPOINTS)
    while not stop_evt.is_set():
        ep = next(cyc)
        try:
            t0 = time.time()
            requests.get(FLASK + ep, timeout=15)
            out.setdefault(ep, []).append(time.time() - t0)
        except Exception:
            out.setdefault(ep, []).append(None)
        time.sleep(0.3)


def pctl(v, p):
    v = sorted(x for x in v if x is not None)
    if not v: return 0
    k = (len(v) - 1) * p; f = int(k)
    return v[f] if f + 1 >= len(v) else v[f] + (v[f + 1] - v[f]) * (k - f)


def run_level(urls, per_host):
    # reset thread-local sessions per level (pool_maxsize đổi theo per_host)
    global _tls; _tls = threading.local()
    sema_map = {h: threading.Semaphore(per_host) for h in ("cdn.hstatic.net", "product.hstatic.net")}
    healthy = broken = uncertain = timeout = 0
    status = {}; lat = []
    fl_out = {}; stop_evt = threading.Event()
    mon = threading.Thread(target=flask_monitor, args=(stop_evt, fl_out), daemon=True); mon.start()
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=GLOBAL_WORKERS) as ex:
        futs = {ex.submit(check, u, sema_map, per_host): u for u in urls}
        for fut in as_completed(futs):
            sc, kind, dt = fut.result()
            lat.append(dt); status[sc] = status.get(sc, 0) + 1
            if kind in ("read_timeout", "conn_timeout"): timeout += 1; uncertain += 1
            elif sc in (404, 410): broken += 1
            elif sc and 200 <= sc <= 399: healthy += 1
            else: uncertain += 1
    dur = time.time() - t0
    stop_evt.set(); mon.join(timeout=2)
    fl_p95 = {ep: round(pctl(v, .95) * 1000) for ep, v in fl_out.items()}
    fl_to = sum(1 for v in fl_out.values() for x in v if x is None)
    return {
        "per_host": per_host, "n": len(urls), "dur": round(dur, 2),
        "rate": round(len(urls) / dur, 1), "healthy": healthy, "broken": broken,
        "uncertain": uncertain, "timeout": timeout,
        "timeout_rate": round(timeout / len(urls) * 100, 1),
        "avg_ms": round(statistics.mean(lat) * 1000), "p50_ms": round(pctl(lat, .5) * 1000),
        "p95_ms": round(pctl(lat, .95) * 1000), "status": status,
        "flask_p95": fl_p95, "flask_timeout": fl_to,
    }


def main():
    urls = load_sample()
    print(f"sample: {len(urls)} hstatic URLs (cdn+product)")
    print("warmup pass (cân bằng cache CDN, không tính)...")
    run_level(urls, 8)  # warmup
    results = []
    for lv in LEVELS:
        print(f"benchmark per-host={lv} ...")
        r = run_level(urls, lv)
        results.append(r)
        print(f"  dur={r['dur']}s rate={r['rate']}/s healthy={r['healthy']} "
              f"broken={r['broken']} uncertain={r['uncertain']} timeout={r['timeout']} "
              f"({r['timeout_rate']}%) p95={r['p95_ms']}ms flask_p95={r['flask_p95']} "
              f"flask_to={r['flask_timeout']}")
    print("\n=== SUMMARY TABLE ===")
    print(f"{'per-host':>8}{'rate/s':>8}{'timeout%':>9}{'p95ms':>7}{'flask/p95':>26}{'flask_to':>9}")
    for r in results:
        fp = max(r['flask_p95'].values()) if r['flask_p95'] else 0
        print(f"{r['per_host']:>8}{r['rate']:>8}{r['timeout_rate']:>9}{r['p95_ms']:>7}{str(fp)+'ms (worst ep)':>26}{r['flask_timeout']:>9}")
    import json
    open("docs/_bench_hstatic_result.json", "w", encoding="utf-8").write(json.dumps(results, ensure_ascii=False, indent=1))
    print("\nsaved docs/_bench_hstatic_result.json")


if __name__ == "__main__":
    main()
