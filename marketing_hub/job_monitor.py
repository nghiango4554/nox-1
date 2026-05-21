"""Job monitor — độ bền cho job nền.

#7 — Snapshot trạng thái mọi job ra file mỗi POLL_SEC giây → sau restart vẫn xem lại
     được (đánh dấu job nào "bị ngắt do restart").
#6 — Phát hiện job TREO: 1 item chạy quá STUCK_WARN_SEC mà không đổi → gắn cờ stuck
     + log cảnh báo (KHÔNG auto-kill vì khó phân biệt job chậm vs treo — vợ bấm Dừng
     trên Job Center khi thấy cảnh báo).
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "job_state" / "snapshot.json"
STUCK_WARN_SEC = 360   # 6 phút item không đổi → coi là treo
POLL_SEC = 20

_track: dict = {}        # key -> {"current": str, "since": float}
_lock = threading.Lock()
_started = False
_prev_snapshot = None     # snapshot của process TRƯỚC (để detect job bị ngắt do restart)


def read_snapshot():
    try:
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_snapshot(jobs, running_count):
    try:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(json.dumps({
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "running_count": running_count,
            "jobs": jobs,
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def enrich(jobs):
    """Gắn stuck / stuck_seconds cho mỗi job dựa theo thời gian item hiện tại không đổi."""
    now = time.time()
    with _lock:
        for j in jobs:
            key = j.get("key")
            cur = (j.get("current") or "").strip()
            if j.get("running") and cur:
                t = _track.get(key)
                if not t or t["current"] != cur:
                    _track[key] = {"current": cur, "since": now}
                secs = int(now - _track[key]["since"])
                j["stuck_seconds"] = secs
                j["stuck"] = secs >= STUCK_WARN_SEC
            else:
                _track.pop(key, None)
                j["stuck_seconds"] = 0
                j["stuck"] = False
    return jobs


def merge_with_snapshot(live_jobs):
    """Job đang idle nhưng phiên trước (snapshot) đang chạy → đánh dấu 'bị ngắt do restart'."""
    if not _prev_snapshot:
        return live_jobs
    snap_by_key = {j.get("key"): j for j in _prev_snapshot.get("jobs", [])}
    saved_at = _prev_snapshot.get("saved_at")
    for j in live_jobs:
        s = snap_by_key.get(j.get("key"))
        if not s:
            continue
        live_idle = (not j.get("running")) and not j.get("started_at") and not j.get("finished_at")
        if live_idle and s.get("running"):
            j["interrupted"] = True
            j["done"] = s.get("done", 0)
            j["total"] = s.get("total", 0)
            j["finished_at"] = saved_at
            j["message"] = (f"⚠️ Bị ngắt do restart — phiên trước {s.get('done',0)}/"
                            f"{s.get('total',0)} (lúc {saved_at})")
    return live_jobs


def start_monitor(collect_fn):
    """Khởi động thread nền. `collect_fn()` trả list job (chưa enrich)."""
    global _started, _prev_snapshot
    if _started:
        return
    _started = True
    _prev_snapshot = read_snapshot()   # state của process TRƯỚC khi restart

    def loop():
        while True:
            try:
                jobs = enrich(collect_fn())
                rc = sum(1 for j in jobs if j.get("running"))
                write_snapshot(jobs, rc)
                for j in jobs:
                    if j.get("stuck"):
                        print(f"[job_monitor] STUCK {j.get('key')} "
                              f"{j.get('stuck_seconds')}s on {str(j.get('current',''))[:60]}",
                              flush=True)
            except Exception:
                pass
            time.sleep(POLL_SEC)

    threading.Thread(target=loop, daemon=True).start()
