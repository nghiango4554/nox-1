"""Routes: Dashboard + Jobs Center — 4 endpoint.

`/`         — homepage dashboard với week view + health probe + worklog
`/jobs`     — Jobs Center page
`/api/jobs` — bg jobs status JSON (merged with monitor snapshot)
`/api/dashboard/health` — gộp toàn bộ health probe

Health probes (8 helper) gọi mọi module → đặt module này CUỐI register chain.

Dep:
- db, seo as seo_mod, competitors as competitors_mod, cwv as cwv_mod,
  alt_manager, content_writer, fb_client, job_monitor (lazy)
- routes.state: JOB_CONFLICTS, JOB_CONFLICT_GROUPS, JOB_INDEPENDENT,
  _GEN_BG, _HEALTH_CACHE
- routes.posts: POST_TYPES, POST_STATUSES, _day_meta
"""

import glob
import json
import os
import subprocess
import time as _time
import urllib3
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from flask import render_template, request, jsonify

import db
import seo as seo_mod
import competitors as competitors_mod
import cwv as cwv_mod
import alt_manager
import content_writer
import fb_client

from routes.state import (
    JOB_CONFLICTS, JOB_CONFLICT_GROUPS, JOB_INDEPENDENT,
    _GEN_BG, _HEALTH_CACHE,
)
from routes.posts import POST_TYPES, POST_STATUSES, _day_meta


ROOT = Path(__file__).parent.parent  # marketing_hub/


# ─────────────────────── JOBS COLLECT ─────────────────────────────

def _collect_jobs():
    """Thu thập trạng thái mọi job nền → list chuẩn hoá (dùng cho /api/jobs + job_monitor)."""
    def J(key, name, icon, page, running, total, done, extra, message,
          started_at, finished_at, current, stop):
        return {"key": key, "name": name, "icon": icon, "page": page,
                "running": bool(running), "total": int(total or 0), "done": int(done or 0),
                "extra": extra or "", "message": message or "",
                "started_at": started_at, "finished_at": finished_at,
                "current": current or "", "stop": stop,
                "conflicts_with": JOB_CONFLICTS.get(key, [])}

    jobs = []
    try:
        s = seo_mod.state_snapshot()
        run = s.get("status") in ("fetching_sitemap", "crawling", "stopping")
        jobs.append(J("crawl", "SEO Crawl", "🕷️", "/seo", run, s.get("total"), s.get("done"),
                      f"✅ {s.get('success',0)} · ❌ {s.get('failed',0)} · {s.get('status','')}",
                      s.get("message"), s.get("started_at"), None, "",
                      "/seo/stop-crawl" if run else None))
    except Exception:
        pass
    try:
        s = seo_mod.link_check_state()
        jobs.append(J("links", "Kiểm tra link gãy", "🔗", "/seo/broken-links", s.get("running"),
                      s.get("total"), s.get("checked"), f"🔴 gãy: {s.get('broken',0)}",
                      "", None, None, "", None))
    except Exception:
        pass
    try:
        s = seo_mod.title_meta_fix_state()
        jobs.append(J("title_meta", "Auto-fix Title/Meta", "📝", "/seo/title-meta", s.get("running"),
                      s.get("total"), s.get("checked"),
                      f"✅ {s.get('success',0)} · ❌ {s.get('failed',0)} · ⏭️ {s.get('skipped',0)}",
                      s.get("message"), s.get("started_at"), s.get("finished_at"),
                      s.get("current_url", ""),
                      "/seo/title-meta/fix-all/stop" if s.get("running") else None))
    except Exception:
        pass
    try:
        s = seo_mod.desc_h1_state()
        jobs.append(J("h1_scan", "Quét H1 trong mô tả", "🔎", "/seo/h1-in-desc", s.get("running"),
                      s.get("total"), s.get("checked"), f"⚠️ vi phạm: {s.get('violations',0)}",
                      s.get("message"), s.get("started_at"), None, "", None))
    except Exception:
        pass
    try:
        s = seo_mod.h1_fix_all_state()
        jobs.append(J("h1_fix", "Auto-fix H1", "🔧", "/seo/h1-in-desc", s.get("running"),
                      s.get("total"), s.get("checked"),
                      f"✅ {s.get('success',0)} · ◐ {s.get('partial',0)} · ❌ {s.get('failed',0)}",
                      s.get("message"), s.get("started_at"), s.get("finished_at"),
                      s.get("current_url", ""),
                      "/seo/h1-in-desc/fix-all/stop" if s.get("running") else None))
    except Exception:
        pass
    try:
        s = seo_mod.empty_desc_state()
        jobs.append(J("empty_desc", "Quét SP thiếu mô tả", "📭", "/seo/empty-desc", s.get("running"),
                      s.get("total"), s.get("checked"),
                      f"rỗng {s.get('empty',0)} · ngắn {s.get('short',0)} · đủ {s.get('ok',0)}",
                      s.get("message"), s.get("started_at"), None, "", None))
    except Exception:
        pass
    try:
        s = content_writer.queue_state()
        pend = s.get("pending_in_db", 0) or 0
        done = s.get("completed", 0) or 0
        jobs.append(J("content_queue", "Hàng đợi gen Content SP", "🏭", "/content-jobs", s.get("running"),
                      done + (s.get("failed", 0) or 0) + pend, done,
                      f"❌ {s.get('failed',0)} · ⏳ chờ: {pend}",
                      s.get("last_message"), s.get("started_at"), None,
                      s.get("current_job_url", ""),
                      "/content-jobs/queue/stop" if s.get("running") else None))
    except Exception:
        pass
    try:
        s = dict(_GEN_BG)
        jobs.append(J("collection_gen", "Gen Content Collection", "📂", "/collection-content", s.get("running"),
                      s.get("total"), s.get("done"),
                      f"✅ {s.get('ok',0)} · ❌ {s.get('fail',0)}",
                      "", s.get("started_at"), s.get("finished_at"),
                      s.get("current_name") or "",
                      "/collection-content/gen-stop" if s.get("running") else None))
    except Exception:
        pass
    try:
        s = competitors_mod.state_snapshot()
        jobs.append(J("competitors", "Crawl đối thủ", "🥷", "/competitors", s.get("running"),
                      s.get("total"), s.get("fetched"), s.get("competitor") or "",
                      s.get("message"), s.get("started_at"), None, "", None))
    except Exception:
        pass
    try:
        s = cwv_mod.state_snapshot()
        run = bool(s.get("running") or s.get("chain_active"))
        if s.get("chain_active"):
            extra = (f"📡 phase {s.get('phase_idx',0)}/{s.get('phase_total',0)} "
                     f"{s.get('phase_label','')} · ✅ {s.get('chain_total_ok',0)} · "
                     f"❌ {s.get('chain_total_failed',0)}")
        else:
            extra = (f"strategy {s.get('strategy','mobile')} · "
                     f"✅ {s.get('ok',0)} · ❌ {s.get('failed',0)}")
        jobs.append(J("cwv_scan", "CWV Scanner (PageSpeed)", "🐢", "/seo/cwv", run,
                      s.get("total"), s.get("done"), extra,
                      s.get("message"), s.get("started_at"), s.get("finished_at"),
                      s.get("current_url", ""),
                      "/api/seo/cwv/scan/stop" if run else None))
    except Exception:
        pass

    return jobs


# ─────────────────────── HEALTH PROBES ───────────────────────────

def _health_cached(key, ttl, fn):
    now = _time.time()
    hit = _HEALTH_CACHE.get(key)
    if hit and hit[0] > now:
        return hit[1]
    try:
        val = fn()
    except Exception as e:
        val = {"error": str(e)[:120]}
    _HEALTH_CACHE[key] = (now + ttl, val)
    return val


def _backup_info(pattern):
    """File backup mới nhất khớp pattern trong data/backups/ (chỉ trả thời gian)."""
    bdir = ROOT / "data" / "backups"
    files = glob.glob(str(bdir / pattern))
    if not files:
        return {"ok": False}
    newest = max(files, key=os.path.getmtime)
    mt = os.path.getmtime(newest)
    return {
        "ok": True,
        "file": os.path.basename(newest),
        "at": datetime.fromtimestamp(mt).isoformat(timespec="seconds"),
        "age_hours": round((datetime.now().timestamp() - mt) / 3600, 1),
    }


def _git_health():
    repo = str(ROOT)

    def _g(*args):
        return subprocess.run(["git", "-C", repo, *args],
                              capture_output=True, text=True, timeout=8).stdout.strip()

    branch = _g("rev-parse", "--abbrev-ref", "HEAD")
    if not branch:
        return {"available": False}
    dirty = _g("status", "--porcelain")
    uncommitted = len([l for l in dirty.splitlines() if l.strip()])
    ahead = behind = None
    counts = _g("rev-list", "--left-right", "--count", "@{upstream}...HEAD")
    if counts and "\t" in counts:
        b, a = counts.split("\t")[:2]
        try:
            behind, ahead = int(b), int(a)
        except ValueError:
            pass
    return {"available": True, "branch": branch, "uncommitted": uncommitted,
            "ahead": ahead, "behind": behind}


def _bot_health():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not tok:
        tf = ROOT / ".env" / "telegram_bot_token.txt"
        if tf.exists():
            tok = tf.read_text(encoding="utf-8").strip()
    if not tok:
        return {"status": "no_token"}
    try:
        r = requests.get(f"https://api.telegram.org/bot{tok}/getMe", timeout=5, verify=False)
        j = r.json() if r.text else {}
        if r.status_code == 200 and j.get("ok"):
            return {"status": "ok", "username": j.get("result", {}).get("username")}
        return {"status": "down", "detail": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "down", "detail": str(e)[:80]}


def _provider_health():
    import ai_provider
    av = ai_provider.available_providers()
    return {"primary": av[0] if av else None, "available": av}


def _dashboard_health():
    """Gộp toàn bộ chỉ số sức khỏe (data thật + fallback). Không bao giờ raise."""
    out = {"ts": datetime.now().isoformat(timespec="seconds"), "flask": {"status": "up"}}

    try:
        out["content_jobs"] = db.content_jobs_stats()
    except Exception as e:
        out["content_jobs"] = {"error": str(e)[:100]}
    try:
        s = db.seo_stats()
        out["seo"] = {k: s.get(k) for k in ("total", "avg_score", "good", "ok", "bad", "broken")}
    except Exception as e:
        out["seo"] = {"error": str(e)[:100]}
    try:
        h = db.hv_stats()
        out["haravan"] = {"total": h.get("total"), "avg_score": h.get("avg_score"),
                          "by_status": h.get("by_status")}
    except Exception as e:
        out["haravan"] = {"error": str(e)[:100]}
    try:
        out["fb_posts"] = db.stats()
    except Exception as e:
        out["fb_posts"] = {"error": str(e)[:100]}

    try:
        conn = db.get_conn()
        blog_draft = conn.execute("SELECT COUNT(*) FROM blog_jobs WHERE status='draft'").fetchone()[0]
        content_review = conn.execute(
            "SELECT COUNT(*) FROM content_jobs WHERE status IN ('text_done','draft','approved')").fetchone()[0]
        pil_total = conn.execute("SELECT COUNT(*) FROM blog_jobs WHERE source='ai_pillar'").fetchone()[0]
        pil_done = conn.execute(
            "SELECT COUNT(*) FROM blog_jobs WHERE source='ai_pillar' AND status IN ('draft','synced')").fetchone()[0]
        conn.close()
        out["review_queue"] = {"blog_draft": blog_draft, "content_review": content_review,
                               "total": blog_draft + content_review}
        out["pillar"] = {"total": pil_total, "done": pil_done, "pending": pil_total - pil_done}
    except Exception as e:
        out["review_queue"] = {"error": str(e)[:100]}
        out["pillar"] = {"error": str(e)[:100]}

    try:
        s = alt_manager.summarize_alt_coverage()
        out["alt"] = {
            "total_images": s.get("total_images", 0),
            "good": s.get("good", 0),
            "none": s.get("none", 0),
            "weak": s.get("weak", 0),
            "coverage_percent": s.get("coverage_percent", 0.0),
        }
    except Exception as e:
        out["alt"] = {"error": str(e)[:100]}

    try:
        m = db.cwv_stats("mobile")
        d = db.cwv_stats("desktop")
        m_total = db.cwv_count("mobile")
        d_total = db.cwv_count("desktop")
        sync_state = None
        sync_path = ROOT / "data" / "cwv_last_sync.json"
        if sync_path.exists():
            try:
                sync_state = json.loads(sync_path.read_text(encoding="utf-8"))
            except Exception:
                sync_state = None
        out["cwv"] = {
            "total": (m_total or 0) + (d_total or 0),
            "mobile_total": m_total or 0,
            "desktop_total": d_total or 0,
            "mobile_bad": (m.get("perf_bad") or 0) if isinstance(m, dict) else 0,
            "desktop_bad": (d.get("perf_bad") or 0) if isinstance(d, dict) else 0,
            "mobile_avg": m.get("avg_perf") if isinstance(m, dict) else None,
            "desktop_avg": d.get("avg_perf") if isinstance(d, dict) else None,
            "last_sync": sync_state,
        }
    except Exception as e:
        out["cwv"] = {"error": str(e)[:100]}

    try:
        diff_path = ROOT / "data" / "cwv_weekly_diff.json"
        if diff_path.exists():
            diff_data = json.loads(diff_path.read_text(encoding="utf-8"))
            mob = diff_data.get("strategies", {}).get("mobile", {}) or {}
            out["cwv_diff"] = {
                "generated_at": diff_data.get("generated_at"),
                "current_week": diff_data.get("current_week"),
                "prev_week": diff_data.get("prev_week"),
                "mobile_avg_change": mob.get("avg_change"),
                "mobile_current_avg": mob.get("current_avg_score"),
                "mobile_prev_avg": mob.get("prev_avg_score"),
                "improved_count": mob.get("improved_count"),
                "regressed_count": mob.get("regressed_count"),
            }
        else:
            out["cwv_diff"] = None
    except Exception as e:
        out["cwv_diff"] = {"error": str(e)[:100]}

    try:
        sp_stats = db.seo_schema_stats(url_type="product")
        bl_stats = db.seo_schema_stats(url_type="blog")
        col_stats = db.seo_schema_stats(url_type="collection")
        conn_s = db.get_conn()
        col_missing_itemlist = conn_s.execute("""
            SELECT COUNT(*) FROM seo_pages
            WHERE url_type='collection' AND status_code=200 AND indexable=1
            AND schema_scanned_at IS NOT NULL
            AND (schema_types IS NULL OR schema_types NOT LIKE '%ItemList%')
        """).fetchone()[0]
        conn_s.close()
        total_audited_all = (sp_stats.get("total_audited") or 0) + \
                            (bl_stats.get("total_audited") or 0) + \
                            (col_stats.get("total_audited") or 0)
        out["schema"] = {
            "total_audited": total_audited_all,
            "sp_pct_product": sp_stats.get("pct_has_product") or 0,
            "sp_missing_product": (sp_stats.get("total_audited") or 0) - (sp_stats.get("has_product") or 0),
            "blog_pct_article": bl_stats.get("pct_has_article") or 0,
            "blog_pct_faq": bl_stats.get("pct_has_faq") or 0,
            "blog_missing_faq": (bl_stats.get("total_audited") or 0) - (bl_stats.get("has_faq") or 0),
            "col_total": col_stats.get("total_audited") or 0,
            "col_missing_itemlist": col_missing_itemlist,
        }
    except Exception as e:
        out["schema"] = {"error": str(e)[:100]}

    out["backups"] = {"db": _backup_info("posts_*.db.zip"), "secrets": _backup_info("secrets_*.zip")}
    out["git"] = _health_cached("git", 30, _git_health)
    out["bot"] = _health_cached("bot", 120, _bot_health)
    out["provider"] = _health_cached("provider", 120, _provider_health)
    return out


def _worklog_tasks(limit=8):
    """Parse NHẸ WORKLOG.md: lấy mục chưa xong '- [ ]' + gắn nhãn active/blocked."""
    import re
    p = ROOT.parent / "WORKLOG.md"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {"ok": False, "tasks": []}
    bucket = "active"
    tasks = []
    for ln in lines:
        stripped = ln.lstrip()
        if stripped.startswith("#") or stripped.startswith(">"):
            low = ln.lower()
            if "🟡" in ln or "blocked" in low or "chờ vợ" in low:
                bucket = "blocked"
            elif "🔴" in ln or "active" in low:
                bucket = "active"
            continue
        m = re.match(r"\s*-\s*\[\s\]\s*(.+)", ln)
        if m:
            txt = re.sub(r"[*`\[\]]", "", m.group(1))
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                tasks.append({"text": txt[:150], "bucket": bucket})
            if len(tasks) >= limit:
                break
    return {"ok": True, "tasks": tasks}


# ─────────────────────── ROUTES ──────────────────────────────────

def dashboard():
    s = db.stats()
    today = date.today()

    week_param = request.args.get("week")
    month_param = request.args.get("month")
    year_param = request.args.get("year")

    monday = None
    if month_param and year_param:
        try:
            target = date(int(year_param), int(month_param), 1)
            days_to_mon = (7 - target.weekday()) % 7
            monday = target + timedelta(days=days_to_mon)
        except (ValueError, TypeError):
            monday = None
    if monday is None and week_param:
        try:
            wd = date.fromisoformat(week_param)
            monday = wd - timedelta(days=wd.weekday())
        except ValueError:
            monday = None
    if monday is None:
        monday = today - timedelta(days=today.weekday())

    sunday = monday + timedelta(days=6)
    prev_week = (monday - timedelta(days=7)).isoformat()
    next_week = (monday + timedelta(days=7)).isoformat()
    this_week = (today - timedelta(days=today.weekday())).isoformat()

    upcoming = []
    for i in range(7):
        d = monday + timedelta(days=i)
        posts = db.list_posts(date=d.isoformat())
        meta = _day_meta(d, today)
        meta["posts"] = posts
        upcoming.append(meta)

    display_month = monday.month
    display_year = monday.year
    year_options = list(range(today.year - 1, today.year + 4))

    try:
        page = fb_client.page_info()
    except Exception as e:
        page = {"error": str(e)}
    recent_activity = db.activity_recent(limit=12)
    return render_template(
        "dashboard.html",
        stats=s,
        health=_dashboard_health(),
        worklog_tasks=_worklog_tasks(),
        upcoming=upcoming,
        page=page,
        types=POST_TYPES,
        statuses=POST_STATUSES,
        today=today.isoformat(),
        week_start=monday.isoformat(),
        week_end=sunday.isoformat(),
        week_start_disp=f"{monday.day:02d}/{monday.month:02d}",
        recent_activity=recent_activity,
        week_end_disp=f"{sunday.day:02d}/{sunday.month:02d}",
        prev_week=prev_week,
        next_week=next_week,
        this_week=this_week,
        display_month=display_month,
        display_year=display_year,
        year_options=year_options,
        is_current_week=(monday.isoformat() == this_week),
    )


def jobs_center_page():
    return render_template("jobs_center.html")


def api_jobs():
    import job_monitor
    jobs = job_monitor.enrich(_collect_jobs())
    merged = job_monitor.merge_with_snapshot(jobs)
    snap = job_monitor.read_snapshot()
    name_icon = {j["key"]: (j["name"], j["icon"]) for j in merged}
    groups_meta = []
    for g in JOB_CONFLICT_GROUPS:
        groups_meta.append({
            "label": g["label"],
            "reason": g["reason"],
            "members": [
                {"key": k,
                 "name": name_icon.get(k, (k, "⚙️"))[0],
                 "icon": name_icon.get(k, (k, "⚙️"))[1]}
                for k in g["jobs"]
            ],
        })
    indep_meta = [
        {"key": ind["key"], "reason": ind["reason"],
         "name": name_icon.get(ind["key"], (ind["key"], "⚙️"))[0],
         "icon": name_icon.get(ind["key"], (ind["key"], "⚙️"))[1]}
        for ind in JOB_INDEPENDENT
    ]
    return jsonify({
        "jobs": merged,
        "running_count": sum(1 for j in merged if j.get("running")),
        "snapshot_saved_at": (snap or {}).get("saved_at"),
        "conflict_groups": groups_meta,
        "independent_jobs": indep_meta,
    })


def api_dashboard_health():
    return jsonify(_dashboard_health())


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 4 route Dashboard."""
    app.add_url_rule("/", "dashboard", dashboard)
    app.add_url_rule("/jobs", "jobs_center_page", jobs_center_page)
    app.add_url_rule("/api/jobs", "api_jobs", api_jobs)
    app.add_url_rule("/api/dashboard/health", "api_dashboard_health", api_dashboard_health)


def start_job_monitor():
    """Khởi động job_monitor với _collect_jobs callback (gọi từ app.py __main__)."""
    import job_monitor
    job_monitor.start_monitor(_collect_jobs)
