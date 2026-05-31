"""Sintech Marketing Hub — web app quản lý lịch đăng Facebook Page.

Run: python app.py  →  http://127.0.0.1:5055
"""

import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler

import db
import fb_client
import seo as seo_mod

# Route modules (Batch 1-8 refactor — 171 endpoint trải qua 13 module)
from routes import system as routes_system
from routes import alt as routes_alt
from routes import haravan as routes_haravan
from routes import posts as routes_posts
from routes import seo_core as routes_seo_core
from routes import seo_quality as routes_seo_quality
from routes import seo_tools as routes_seo_tools
from routes import content_product as routes_content_product
from routes import content_collection as routes_content_collection
from routes import content_blog as routes_content_blog
from routes import content_pillar as routes_content_pillar
from routes import dashboard as routes_dashboard
from routes import products as routes_products
# Re-export: _collect_jobs cho job_monitor + POST_TYPES/STATUSES/post_image_paths cho bg+template
from routes.dashboard import _collect_jobs
from routes.posts import POST_TYPES, POST_STATUSES, post_image_paths

ROOT = Path(__file__).parent

app = Flask(__name__)
_secret_file = ROOT / "state" / "flask_secret.txt"
if _secret_file.exists():
    app.secret_key = _secret_file.read_text(encoding="utf-8").strip()
else:
    # Lần đầu chạy: tạo key cố định và lưu lại
    _secret_file.parent.mkdir(parents=True, exist_ok=True)
    app.secret_key = secrets.token_hex(32)
    _secret_file.write_text(app.secret_key, encoding="utf-8")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

# Register route modules (Batch 1+ refactor)
routes_system.register(app)
routes_alt.register(app)
routes_haravan.register(app)
routes_posts.register(app)
routes_seo_core.register(app)
routes_seo_quality.register(app)
routes_seo_tools.register(app)
routes_content_product.register(app)
routes_content_collection.register(app)
routes_content_blog.register(app)
routes_content_pillar.register(app)
routes_dashboard.register(app)
routes_products.register(app)


# ─────────────────────── BACKGROUND WORKER (auto-post FB) ───────────────────────


def auto_post_due():
    """Worker chạy mỗi phút — đăng các bài 'approved' tới giờ.

    Lưu ý: có thể dùng FB native scheduling thay (đã có endpoint /schedule),
    đây chỉ là backup local trong trường hợp em muốn quản hoàn toàn từ Hub."""
    now = datetime.now()
    today = now.date().isoformat()
    posts = db.list_posts(date=today, status="approved")
    for p in posts:
        if not p.get("scheduled_time"):
            continue
        try:
            tgt = datetime.strptime(
                f"{p['scheduled_date']} {p['scheduled_time']}", "%Y-%m-%d %H:%M"
            )
        except ValueError:
            continue
        if tgt > now:
            continue
        if tgt < now - timedelta(hours=2):
            continue  # quá hạn, skip
        try:
            paths = post_image_paths(p)
            if len(paths) >= 2:
                r = fb_client.post_multi_to_page(p["caption"], paths, published=True)
            else:
                r = fb_client.post_to_page(
                    p["caption"], image_path=(paths[0] if paths else None), published=True
                )
            fb_id = r.get("post_id") or r.get("id")
            db.update_post(p["id"], {"status": "posted", "fb_post_id": fb_id})
            print(f"[auto] Đã đăng bài {p['code']} → {fb_id}")
        except Exception as e:
            print(f"[auto] Lỗi đăng bài {p['code']}: {e}")


@app.template_filter("from_json")
def jinja_from_json(value):
    if not value:
        return []
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return []


@app.context_processor
def inject_globals():
    return {
        "now": datetime.now(),
        "POST_TYPES": POST_TYPES,
        "POST_STATUSES": POST_STATUSES,
    }


if __name__ == "__main__":
    db.init_db()
    import job_monitor
    job_monitor.start_monitor(_collect_jobs)
    sched = BackgroundScheduler()
    sched.add_job(auto_post_due, "interval", minutes=1, id="auto_post_due")
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
    sched.start()
    try:
        app.run(host="127.0.0.1", port=5055, debug=False, threaded=True)
    finally:
        sched.shutdown(wait=False)
