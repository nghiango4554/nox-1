"""worker.py — tiến trình NỀN chạy job từ hàng đợi `jobs` (tách khỏi web Flask).

Mục đích: crawl/gen nặng chạy Ở ĐÂY (tiến trình riêng) → GIL/ổ ghi DB không bóp Flask
→ web luôn mượt, không treo khi crawl, hết 'database is locked'.

Singleton: bind cổng 127.0.0.1:5056 — nếu cổng bận = đã có worker khác → thoát.
Flask (app.py __main__) tự spawn worker này; hoặc chạy tay: `python worker.py`.
"""
import json
import socket
import sys
import time
import traceback
from pathlib import Path

# stdout/stderr UTF-8 + replace — tránh UnicodeEncodeError trên Windows cp1252 (làm crash worker)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
import db
import seo as seo_mod

WORKER_PORT = 5056


def acquire_singleton():
    """Bind cổng để đảm bảo CHỈ 1 worker. Trả socket (giữ ref) hoặc None nếu đã có worker."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", WORKER_PORT))
        s.listen(1)
        return s
    except OSError:
        s.close()
        return None


def handle_tm_recrawl(job):
    payload = json.loads(job.get("payload") or "{}")
    jid = job["id"]
    seo_mod.run_tm_recrawl(
        payload.get("scope", "full_sp_col"),
        payload.get("workers"),
        progress_cb=lambda p: db.job_update_progress(jid, p),
        stop_cb=lambda: db.job_stop_requested(jid),
    )


HANDLERS = {
    "tm_recrawl": handle_tm_recrawl,
}


def main():
    lock = acquire_singleton()
    if not lock:
        print("[worker] đã có worker khác đang chạy (cổng 5056 bận) — thoát.")
        return
    print(f"[worker] started, pid={__import__('os').getpid()}, types={list(HANDLERS)}")
    db.init_db()
    db.jobs_requeue_stale_running()  # job 'running' mồ côi từ lần trước → failed
    while True:
        try:
            job = db.job_claim_next(list(HANDLERS.keys()))
            if not job:
                time.sleep(2)
                continue
            print(f"[worker] >> job #{job['id']} type={job['type']}")
            try:
                HANDLERS[job["type"]](job)
                db.job_finish(job["id"], "done")
                print(f"[worker] OK job #{job['id']} done")
            except Exception as e:
                traceback.print_exc()
                db.job_finish(job["id"], "failed", str(e)[:300])
        except Exception:
            traceback.print_exc()
            time.sleep(3)


if __name__ == "__main__":
    main()
