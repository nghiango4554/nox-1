"""Shared mutable state cho marketing_hub.

Các route module dùng chung 1 ref tới các dict/lock background worker,
conflict matrix, cache health, snapshot dir. Constants thuần để ở
module route tương ứng (POST_TYPES → posts, BLOG_TOPICS → blog_topics, ...).
"""

import threading
from pathlib import Path

# ─── Paths ─────────────────────────────────────────────────────────
# state.py nằm ở marketing_hub/routes/ → ROOT = marketing_hub/
ROOT = Path(__file__).resolve().parent.parent
SEO_SNAPSHOT_DIR = ROOT / "data" / "seo_snapshots"


# ─── Job conflict matrix (job_monitor) ─────────────────────────────
JOB_CONFLICT_GROUPS = [
    {
        "label": "🌐 HTTP fetch Sintech.vn",
        "reason": "Tránh overload site khi crawl mass · 1 chạy → 3 còn lại đợi",
        "jobs": ["crawl", "links", "h1_scan", "empty_desc"],
    },
    {
        "label": "🤖 Codex CLI quota",
        "reason": "Share 1 Plus account · 1 chạy → 3 còn lại đợi quota",
        "jobs": ["title_meta", "h1_fix", "content_queue", "collection_gen"],
    },
]
JOB_INDEPENDENT = [
    {"key": "cwv_scan", "reason": "PSI API riêng (Google)"},
    {"key": "competitors", "reason": "Crawl external sites"},
]
# Build pairwise lookup từ groups (mỗi job → list các job cùng group)
JOB_CONFLICTS = {}
for _g in JOB_CONFLICT_GROUPS:
    for _k in _g["jobs"]:
        JOB_CONFLICTS[_k] = [k for k in _g["jobs"] if k != _k]
for _ind in JOB_INDEPENDENT:
    JOB_CONFLICTS.setdefault(_ind["key"], [])


# ─── Background gen Collection Content ─────────────────────────────
_GEN_BG = {
    "running": False, "stopped": False, "kind": None,
    "queue": [], "total": 0,
    "current_id": None, "current_name": None, "job_started_at": None,
    "started_at": None, "finished_at": None,
    "ok": 0, "fail": 0, "done": 0,
    "completed_durations": [], "errors": [],
}
_GEN_BG_LOCK = threading.Lock()


# ─── Background gen Blog Pillars (T4) ──────────────────────────────
_PILLAR_BG = {
    "running": False, "stopped": False, "phase": None, "msg": "",
    "n_pillars": 0, "pillar_idx": 0, "pillar_total": 0, "pillar_title": "",
    "jobs_created": 0, "n_clusters": 0,
    "started_at": None, "finished_at": None, "error": None, "result": None,
}
_PILLAR_BG_LOCK = threading.Lock()


# ─── Dashboard health cache (TTL by key) ───────────────────────────
_HEALTH_CACHE = {}  # key -> (expires_ts, value)
