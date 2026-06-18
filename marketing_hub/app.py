"""Sintech Marketing Hub — web app quản lý lịch đăng Facebook Page.

Run: python app.py  →  http://127.0.0.1:5055
"""

import json
import secrets
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

import db
import seo as seo_mod

# Route modules — 171 endpoint trải 13 module
from routes import system as routes_system
from routes import alt as routes_alt
from routes import haravan as routes_haravan
from routes import posts as routes_posts
from routes import seo_core as routes_seo_core
from routes import seo_quality as routes_seo_quality
from routes import seo_tools as routes_seo_tools
from routes import ga4 as routes_ga4
from routes import gsc_api as routes_gsc_api
from routes import tracking as routes_tracking
from routes import tasks as routes_tasks
from routes import ops as routes_ops
from routes import content_product as routes_content_product
from routes import content_collection as routes_content_collection
from routes import content_blog as routes_content_blog
from routes import content_pillar as routes_content_pillar
from routes import dashboard as routes_dashboard
from routes import products as routes_products
from routes import blog_content_center as routes_blog_content_center
# ARCHIVED 2026-06-16: blog_rewrite (AI Viết Lại Blog) gỡ khỏi UI/nav.
# Module + DB (blog_rewrite_*) GIỮ NGUYÊN, chỉ không register route nữa.
# from routes import blog_rewrite as routes_blog_rewrite

ROOT = Path(__file__).parent

app = Flask(__name__)
_secret_file = ROOT / "state" / "flask_secret.txt"
if _secret_file.exists():
    app.secret_key = _secret_file.read_text(encoding="utf-8").strip()
else:
    _secret_file.parent.mkdir(parents=True, exist_ok=True)
    app.secret_key = secrets.token_hex(32)
    _secret_file.write_text(app.secret_key, encoding="utf-8")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Register route modules — order matters cho dashboard health probe (đặt cuối)
routes_system.register(app)
routes_alt.register(app)
routes_haravan.register(app)
routes_posts.register(app)
routes_seo_core.register(app)
routes_seo_quality.register(app)
routes_seo_tools.register(app)
routes_ga4.register(app)
routes_gsc_api.register(app)
routes_tracking.register(app)
routes_tasks.register(app)
routes_ops.register(app)
routes_content_product.register(app)
routes_content_collection.register(app)
routes_content_blog.register(app)
routes_content_pillar.register(app)
routes_dashboard.register(app)
routes_products.register(app)
# content_blog đăng ký TRƯỚC (giữ sub-route legacy), center chiếm trang chính /blog-content
routes_blog_content_center.register(app)
# routes_blog_rewrite.register(app)  # ARCHIVED — xem ghi chú phần import


@app.template_filter("from_json")
def jinja_from_json(value):
    if not value:
        return []
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return []


@app.context_processor
def inject_now():
    return {"now": datetime.now()}


if __name__ == "__main__":
    db.init_db()
    # Spawn worker nền (hàng đợi job — crawl/gen chạy tách khỏi web).
    # Worker tự singleton qua cổng 5056 → spawn dư cũng tự thoát, luôn đúng 1 worker.
    # DETACHED + DEVNULL: worker KHÔNG là con-chặn của Flask → watchdog (cmd) thoát được
    #   lệnh `python app.py` khi Flask chết → relaunch bình thường (fix bug treo watchdog 2/6).
    try:
        import os as _os
        import subprocess
        import sys as _sys
        _flags = 0
        if _os.name == "nt":
            _flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [_sys.executable, str(ROOT / "worker.py")], cwd=str(ROOT),
            creationflags=_flags,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except Exception as _e:
        print("worker spawn err:", _e)
    routes_dashboard.start_job_monitor()

    # Auto-resume job gen title/meta nếu Flask sập/restart giữa chừng (marker file còn).
    # Chạy nền + delay để server lên hẳn rồi mới gánh job nặng (gen AI per SP).
    def _resume_tm_job():
        import time as _t
        _t.sleep(8)
        try:
            r = seo_mod.resume_interrupted_title_meta_job()
            if r.get("resumed"):
                print(f"[auto-resume] tiếp job title/meta dở: {r}")
        except Exception as _e:
            print("auto-resume title/meta err:", _e)
        try:
            rc = seo_mod.resume_interrupted_crawl()
            if rc.get("resumed"):
                print(f"[auto-resume] tiếp crawl SEO dở (phase {rc.get('phase')})")
        except Exception as _e:
            print("auto-resume crawl err:", _e)
    threading.Thread(target=_resume_tm_job, daemon=True).start()

    sched = BackgroundScheduler()
    routes_posts.register_runtime(app, sched)
    sched.add_job(
        lambda: seo_mod.start_crawl_async(),
        "cron", day_of_week="sun", hour=3, minute=0,
        id="seo_weekly_crawl",
    )
    sched.add_job(
        lambda: db.seo_capture_history(note="weekly_auto"),
        "cron", day_of_week="sun", hour=4, minute=0,
        id="seo_weekly_history_capture",
    )
    # Analytics daily orchestration — chỉ chạy khi config enabled (kiểm tại fire time)
    def _analytics_daily_job():
        from services import analytics_daily_service as _ops
        if _ops.load_config().get("enabled"):
            _ops.run_orchestration(trigger="scheduler")
    _adc = __import__("services.analytics_daily_service", fromlist=["load_config"]).load_config()
    sched.add_job(_analytics_daily_job, "cron", hour=_adc.get("hour", 6), minute=_adc.get("minute", 30),
                  id="analytics_daily_orchestration")
    sched.start()
    try:
        app.run(host="127.0.0.1", port=5055, debug=False, threaded=True)
    finally:
        sched.shutdown(wait=False)
