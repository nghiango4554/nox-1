"""Routes: Content Pillar (T4) — 4 endpoint (list + generate + stop + status).

Tách từ app.py (Batch 6D). Low risk — chỉ gen Pillar+Cluster (seed blog_jobs),
KHÔNG gen nội dung (việc viết bài ở routes/content_blog.py).

Move kèm:
- _pillar_progress, _pillar_bg_worker (BG worker callable)

Dep:
- db
- routes.state (_PILLAR_BG, _PILLAR_BG_LOCK)
- blog_pillar_writer (lazy)
"""

import threading
from datetime import datetime

from flask import render_template, request, jsonify

import db
from routes.state import _PILLAR_BG, _PILLAR_BG_LOCK


# ─────────────────────── BG WORKER ───────────────────────────────

def _pillar_progress(d):
    with _PILLAR_BG_LOCK:
        _PILLAR_BG.update(d)


def _pillar_bg_worker(n_pillars, clusters_per_pillar):
    """Chỉ gen Pillar + Cluster (đề xuất chủ đề) → seed blog_jobs status='pending'.
    KHÔNG gen nội dung — viết bài là bước riêng ở /blog-content."""
    import blog_pillar_writer as bpw
    try:
        res = bpw.generate_plan(n_pillars, clusters_per_pillar, progress=_pillar_progress)
        with _PILLAR_BG_LOCK:
            _PILLAR_BG["result"] = res
            _PILLAR_BG["jobs_created"] = res["jobs_created"]
            _PILLAR_BG["n_clusters"] = res["n_clusters"]
            _PILLAR_BG["n_pillars"] = res["n_pillars"]
    except Exception as e:
        with _PILLAR_BG_LOCK:
            _PILLAR_BG["error"] = str(e)[:300]
    finally:
        with _PILLAR_BG_LOCK:
            _PILLAR_BG["running"] = False
            _PILLAR_BG["phase"] = "done"
            _PILLAR_BG["finished_at"] = datetime.now().isoformat(timespec="seconds")


# ─────────────────────── ROUTES ──────────────────────────────────

def blog_pillars_page():
    conn = db.get_conn()
    pillars = [dict(r) for r in conn.execute(
        "SELECT * FROM blog_pillars ORDER BY id DESC").fetchall()]
    for p in pillars:
        rows = conn.execute(
            "SELECT id, article_title, content_layer, article_type, priority, status, is_external "
            "FROM blog_jobs WHERE pillar_id=? ORDER BY id", (p["id"],)).fetchall()
        p["clusters"] = [dict(r) for r in rows]
    total_jobs = conn.execute(
        "SELECT COUNT(*) FROM blog_jobs WHERE source='ai_pillar'").fetchone()[0]
    conn.close()
    return render_template("blog_pillars.html", pillars=pillars, total_jobs=total_jobs)


def blog_pillars_generate():
    with _PILLAR_BG_LOCK:
        if _PILLAR_BG["running"]:
            return jsonify({"ok": False, "error": "Đang chạy rồi — đợi lượt này xong."}), 409
        data = request.get_json(silent=True) or {}
        try:
            n_pillars = max(1, min(int(data.get("n_pillars") or 12), 20))
            cpp = max(1, min(int(data.get("clusters_per_pillar") or 10), 15))
        except (TypeError, ValueError):
            n_pillars, cpp = 12, 10
        _PILLAR_BG.update({
            "running": True, "stopped": False, "phase": "starting", "msg": "Khởi động...",
            "n_pillars": 0, "pillar_idx": 0, "pillar_total": n_pillars, "pillar_title": "",
            "jobs_created": 0, "n_clusters": 0,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None, "error": None, "result": None,
        })
    t = threading.Thread(target=_pillar_bg_worker, args=(n_pillars, cpp), daemon=True)
    t.start()
    return jsonify({"ok": True, "msg": f"Bắt đầu gen {n_pillars} pillar × ~{cpp} cluster (chạy nền)."})


def blog_pillars_stop():
    with _PILLAR_BG_LOCK:
        _PILLAR_BG["stopped"] = True
    return jsonify({"ok": True, "msg": "Đã yêu cầu dừng — sẽ dừng sau bài đang gen."})


def blog_pillars_status():
    with _PILLAR_BG_LOCK:
        return jsonify(dict(_PILLAR_BG))


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 4 route Blog Pillars."""
    app.add_url_rule("/blog-pillars", "blog_pillars_page", blog_pillars_page)
    app.add_url_rule("/blog-pillars/generate", "blog_pillars_generate",
                     blog_pillars_generate, methods=["POST"])
    app.add_url_rule("/blog-pillars/stop", "blog_pillars_stop",
                     blog_pillars_stop, methods=["POST"])
    app.add_url_rule("/blog-pillars/status", "blog_pillars_status", blog_pillars_status)
