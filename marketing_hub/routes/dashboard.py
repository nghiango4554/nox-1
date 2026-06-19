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


def _dashboard_health(with_probes=True):
    """Gộp toàn bộ chỉ số sức khỏe (data thật + fallback). Không bao giờ raise.
    with_probes=False → BỎ git/bot/provider (subprocess+HTTP ~2s) để render nhanh; nạp sau qua AJAX."""
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
    if with_probes:
        out["git"] = _health_cached("git", 30, _git_health)
        out["bot"] = _health_cached("bot", 120, _bot_health)
        out["provider"] = _health_cached("provider", 120, _provider_health)
    else:
        # Lấy cache nếu có (không block); cold → pending, JS sẽ nạp sau
        now_t = _time.time()
        for k in ("git", "bot", "provider"):
            hit = _HEALTH_CACHE.get(k)
            out[k] = hit[1] if (hit and hit[0] > now_t) else {"pending": True}
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


def _num(x, d=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return d


def _fmt1(x):
    try:
        return f"{float(x):.1f}"
    except (TypeError, ValueError):
        return "—"


# icon theo key job (khớp bộ icon sintech-icons*.js)
_JOB_ICON = {
    "crawl": "search", "links": "link", "title_meta": "file-text",
    "h1_scan": "search", "h1_fix": "wrench", "empty_desc": "file-text",
    "content_queue": "package", "collection_gen": "folder-tree",
    "competitors": "swords", "cwv_scan": "gauge",
}
_JOB_TONE = {
    "crawl": "emerald", "links": "rose", "title_meta": "violet",
    "h1_scan": "amber", "h1_fix": "amber", "empty_desc": "amber",
    "content_queue": "sky", "collection_gen": "indigo",
    "competitors": "slate", "cwv_scan": "amber",
}


def _v2_dashboard_ctx():
    """Gộp data thật cho dashboard redesign — list sạch để template chỉ loop.
    BỎ probe chậm (git/bot/provider) → render nhanh; JS nạp 3 row đó sau qua /api/dashboard/health."""
    h = _dashboard_health(with_probes=False)
    jobs = _collect_jobs()

    cj = h.get("content_jobs") or {}
    cj_by = cj.get("by_status") or {}
    seo = h.get("seo") or {}
    hv = h.get("haravan") or {}
    rq = h.get("review_queue") or {}
    alt = h.get("alt") or {}
    cwv = h.get("cwv") or {}
    pillar = h.get("pillar") or {}
    git = h.get("git") or {}
    bot = h.get("bot") or {}
    prov = h.get("provider") or {}
    bk = h.get("backups") or {}

    cwv_bad = _num(cwv.get("mobile_bad")) + _num(cwv.get("desktop_bad"))
    alt_good = _num(alt.get("good"))
    alt_bad = _num(alt.get("none")) + _num(alt.get("weak"))

    kpis = [
        {"tone": "sky", "grad": "coral", "icon": "package", "pill_tone": "sky", "pill": "jobs",
         "val": _num(cj.get("total")), "title": "Content jobs",
         "sub": f"synced {_num(cj_by.get('synced'))} · chờ {_num(cj_by.get('queued'))}"},
        {"tone": "teal", "grad": "teal", "icon": "search", "pill_tone": "teal",
         "pill": f"TB {_fmt1(seo.get('avg_score'))}",
         "val": _num(seo.get("bad")), "title": "SEO trang điểm kém",
         "sub": f"{_num(seo.get('total'))} trang · tốt {_num(seo.get('good'))}"},
        {"tone": "violet", "grad": "violet", "icon": "square-check-big", "pill_tone": "amber",
         "pill": "chờ duyệt", "val": _num(rq.get("total")), "title": "Bài chờ duyệt",
         "sub": f"blog {_num(rq.get('blog_draft'))} · content {_num(rq.get('content_review'))}"},
        {"tone": "indigo", "grad": "blue", "icon": "shopping-bag", "pill_tone": "indigo",
         "pill": f"audit {_fmt1(hv.get('avg_score'))}",
         "val": _num(hv.get("total")), "title": "SP Haravan",
         "sub": f"điểm audit TB {_fmt1(hv.get('avg_score'))}"},
        {"tone": "rose", "grad": "red", "icon": "image", "pill_tone": "rose", "pill": "cần sửa",
         "val": _fmt1(alt.get("coverage_percent")), "unit": "%", "title": "Alt coverage",
         "sub": f"{alt_good} good · {alt_bad} cần sửa"},
        {"tone": "amber", "grad": "amber", "icon": "gauge", "pill_tone": "rose", "pill": "cần fix",
         "val": cwv_bad, "title": "CWV perf kém",
         "sub": f"{_num(cwv.get('total'))} URL · TB {_fmt1(cwv.get('mobile_avg'))}"},
    ]

    alerts = []
    if bot.get("status") and bot.get("status") != "ok":
        d = "chưa có token" if bot.get("status") == "no_token" else (bot.get("detail") or "down")
        alerts.append({"tone": "rose", "icon": "wifi-off", "text": "Telegram bot lỗi", "small": d})
    bdb = bk.get("db") or {}
    if not bdb.get("ok"):
        alerts.append({"tone": "rose", "icon": "database-backup", "text": "Backup DB chưa có", "small": ""})
    elif _num(bdb.get("age_hours")) > 72:
        alerts.append({"tone": "rose", "icon": "database-backup", "text": "Backup DB quá cũ",
                       "small": f"{_num(bdb.get('age_hours'))}h"})
    if cwv_bad > 0:
        alerts.append({"tone": "amber", "icon": "gauge", "text": f"{cwv_bad} URL CWV kém", "small": "cần fix"})
    if _num(git.get("uncommitted")) > 0:
        alerts.append({"tone": "amber", "icon": "git-branch",
                       "text": f"{_num(git.get('uncommitted'))} chưa commit",
                       "small": f"Git {git.get('branch', '')}"})

    health_rows = [
        {"tone": "emerald", "icon": "server", "name": "Flask web", "desc": "ứng dụng chính",
         "pill": "Up", "pill_tone": "emerald"},
    ]
    if prov.get("pending"):
        health_rows.append({"hk": "provider", "tone": "slate", "icon": "bot", "name": "AI provider",
                            "desc": "đang kiểm tra…", "pill": "…", "pill_tone": "slate"})
    else:
        prim = prov.get("primary")
        health_rows.append({"hk": "provider", "tone": "emerald" if prim else "amber", "icon": "bot", "name": "AI provider",
                            "desc": prim or "chưa cấu hình", "pill": "sẵn sàng" if prim else "thiếu",
                            "pill_tone": "emerald" if prim else "amber"})
    if bot.get("pending"):
        health_rows.append({"hk": "bot", "tone": "slate", "icon": "send", "name": "Telegram bot",
                            "desc": "đang kiểm tra…", "pill": "…", "pill_tone": "slate"})
    else:
        bot_ok = bot.get("status") == "ok"
        health_rows.append({"hk": "bot", "tone": "emerald" if bot_ok else "rose", "icon": "send", "name": "Telegram bot",
                            "desc": bot.get("username") or "thông báo",
                            "pill": "Up" if bot_ok else (bot.get("detail") or "down"),
                            "pill_tone": "emerald" if bot_ok else "rose"})
    if git.get("pending"):
        health_rows.append({"hk": "git", "tone": "slate", "icon": "git-branch", "name": "Git",
                            "desc": "đang kiểm tra…", "pill": "…", "pill_tone": "slate"})
    elif git.get("available"):
        unc = _num(git.get("uncommitted"))
        health_rows.append({"hk": "git", "tone": "amber" if unc else "emerald", "icon": "git-branch",
                            "name": f"Git ({git.get('branch', '')})",
                            "desc": f"↑{_num(git.get('ahead'))} · {unc} chưa commit",
                            "pill": "lệch" if unc else "sạch",
                            "pill_tone": "amber" if unc else "emerald"})
    db_age = _num(bdb.get("age_hours")) if bdb.get("ok") else None
    health_rows.append({"tone": "rose" if (db_age is None or db_age > 72) else "emerald",
                        "icon": "database-backup", "name": "Backup DB",
                        "desc": f"{db_age}h trước" if db_age is not None else "chưa có",
                        "pill": f"{db_age}h" if db_age is not None else "thiếu",
                        "pill_tone": "rose" if (db_age is None or db_age > 72) else "emerald"})
    p_total = _num(pillar.get("total"))
    p_done = _num(pillar.get("done"))
    health_rows.append({"tone": "amber", "icon": "layers", "name": "Pillar gen",
                        "desc": f"{p_done} / {p_total} · {_num(pillar.get('pending'))} chờ",
                        "pill": f"{int(p_done * 100 / p_total) if p_total else 0}%",
                        "pill_tone": "amber",
                        "progress": int(p_done * 100 / p_total) if p_total else 0})

    # Hàng đợi xử lý — running trước, cap 6
    jobs_sorted = sorted(jobs, key=lambda j: (not j.get("running"), -(j.get("done") or 0)))
    queue = []
    for j in jobs_sorted[:6]:
        total = _num(j.get("total"))
        done = _num(j.get("done"))
        pct = int(done * 100 / total) if total else (100 if done else 0)
        run = j.get("running")
        queue.append({
            "icon": _JOB_ICON.get(j.get("key"), "inbox"),
            "tone": _JOB_TONE.get(j.get("key"), "slate"),
            "title": j.get("name"), "sub": (j.get("extra") or j.get("message") or "")[:70],
            "status": "đang chạy" if run else ("xong" if done and not total else "nghỉ"),
            "status_tone": "sky" if run else ("emerald" if done else "slate"),
            "pulse": bool(run), "pct": pct,
        })

    # GA4 — lưu lượng 7 ngày thật (sessions + organic)
    ga4_series = {"labels": [], "sessions": [], "organic": [], "has": False}
    try:
        gconn = db.get_conn()
        grows = list(reversed(gconn.execute(
            "SELECT date, sessions, engaged_sessions FROM ga4_daily_summary ORDER BY date DESC LIMIT 7").fetchall()))
        gdates = [r["date"] for r in grows]
        org = {}
        if gdates:
            qm = ",".join("?" * len(gdates))
            for r in gconn.execute(
                f"SELECT date, SUM(sessions) s FROM ga4_channels_daily WHERE date IN ({qm}) "
                f"AND session_default_channel_group='Organic Search' GROUP BY date", gdates).fetchall():
                org[r["date"]] = r["s"] or 0
        gconn.close()
        for r in grows:
            ga4_series["labels"].append((r["date"] or "")[5:].replace("-", "/"))
            ga4_series["sessions"].append(_num(r["sessions"]))
            ga4_series["organic"].append(org.get(r["date"], 0))
        ga4_series["has"] = bool(grows)
    except Exception:
        pass

    # Data cho các chart (đúng loại: donut = thành phần, bar = so sánh)
    cj_by_top = sorted(((k, v) for k, v in cj_by.items() if v), key=lambda x: -x[1])[:5]
    charts = {
        "ga4": ga4_series,
        "seo_dist": {"good": _num(seo.get("good")), "ok": _num(seo.get("ok")), "bad": _num(seo.get("bad"))},
        "cj_status": {"labels": [k for k, _ in cj_by_top], "values": [v for _, v in cj_by_top]},
        "cwv": {"mobile": cwv.get("mobile_avg") or 0, "desktop": cwv.get("desktop_avg") or 0},
    }

    return {"kpis": kpis, "alerts": alerts, "health_rows": health_rows, "queue": queue,
            "charts": charts, "updated": datetime.now().strftime("%H:%M")}


def dashboard_v2():
    ctx = _v2_dashboard_ctx()
    return render_template("redesign_dashboard.html", active="dashboard", **ctx)


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
    app.add_url_rule("/", "dashboard", dashboard_v2)          # giao diện mới = trang chủ
    app.add_url_rule("/v2", "dashboard_v2", dashboard_v2)     # alias
    app.add_url_rule("/old", "dashboard_old", dashboard)      # dashboard cũ (backup)
    app.add_url_rule("/jobs", "jobs_center_page", jobs_center_page)
    app.add_url_rule("/api/jobs", "api_jobs", api_jobs)
    app.add_url_rule("/api/dashboard/health", "api_dashboard_health", api_dashboard_health)


def start_job_monitor():
    """Khởi động job_monitor với _collect_jobs callback (gọi từ app.py __main__)."""
    import job_monitor
    job_monitor.start_monitor(_collect_jobs)
