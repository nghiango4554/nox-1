"""Routes: SEO Core — 20 endpoint (overview + url detail + rules + export +
snapshot save/load/delete + clear + recrawl + seed + status + history×4 +
crawl × 3 + recompute-dup).

Tách từ app.py (Batch 5A refactor). Helpers `_open_snapshot` + `_list_seo_snapshots`
move chung (chỉ dùng nội bộ SEO).

⚠️ Smoke test: KHÔNG bấm /seo/clear hoặc /seo/crawl-fresh — sẽ xoá toàn bộ data.
KHÔNG crawl toàn site (chỉ /seo/crawl với limit nhỏ nếu cần test).

Dep:
- seo as seo_mod (state_snapshot, ISSUE_LABELS, enrich_issue, recompute_dup_flags,
  start_crawl_async, stop_crawl, fetch_sitemap_urls, classify_url, crawl_one,
  load_rules_config, save_rules_config, link_check_state)
- db.seo_* (export/import snapshot + history + pages + dup + indexability + inlinks)
- routes.state.SEO_SNAPSHOT_DIR
- werkzeug.utils.secure_filename
"""

import csv
import io
import json
import re
import gzip
from datetime import datetime

from flask import (
    render_template, request, jsonify,
    redirect, url_for, flash, Response,
)
from werkzeug.utils import secure_filename

import db
import seo as seo_mod
from routes.state import SEO_SNAPSHOT_DIR


# ─────────────────────── HELPERS ─────────────────────────────────

def _open_snapshot(path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def _list_seo_snapshots() -> list:
    SEO_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    paths = list(SEO_SNAPSHOT_DIR.glob("*.json")) + list(SEO_SNAPSHOT_DIR.glob("*.json.gz"))
    for p in sorted(paths, key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with _open_snapshot(p) as f:
                data = json.load(f)
            counts = data.get("counts") or {}
            out.append({
                "filename": p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "exported_at": data.get("exported_at") or "",
                "label": data.get("label") or "",
                "pages": counts.get("pages", 0),
                "links": counts.get("links", 0),
                "runs": counts.get("runs", 0),
            })
        except (ValueError, OSError):
            continue
    return out


# ─────────────────────── OVERVIEW + URL DETAIL ───────────────────

def seo_dashboard():
    stats = db.seo_stats()
    latest_run = db.seo_latest_run()
    state = seo_mod.state_snapshot()
    snapshots = _list_seo_snapshots()
    top_issues = db.seo_top_issues(limit=10)
    for it in top_issues:
        icon, label, fix = seo_mod.ISSUE_LABELS.get(it["code"], ("⚪", it["code"], ""))
        it["icon"] = icon
        it["label"] = label
        it["fix"] = fix

    f_type = request.args.get("type") or None
    f_band = request.args.get("band") or None
    f_issue = request.args.get("issue") or None
    f_search = (request.args.get("q") or "").strip() or None
    f_sort = request.args.get("sort") or "score_asc"
    try:
        page_num = max(1, int(request.args.get("page") or 1))
    except (TypeError, ValueError):
        page_num = 1
    per_page = 50

    band_map = {"good": (80, None), "ok": (60, 79), "bad": (None, 59)}
    min_score, max_score = band_map.get(f_band, (None, None))

    list_kwargs = dict(
        url_type=f_type, min_score=min_score, max_score=max_score,
        issue_code=f_issue, search=f_search, sort=f_sort,
    )
    total_filtered = db.seo_count_pages(**list_kwargs)
    pages_list = db.seo_list_pages(**list_kwargs, limit=per_page, offset=(page_num - 1) * per_page)
    total_pages = max(1, (total_filtered + per_page - 1) // per_page)

    return render_template(
        "seo.html",
        stats=stats, latest_run=latest_run, state=state,
        link_state=seo_mod.link_check_state(),
        pages=pages_list, top_issues=top_issues, snapshots=snapshots,
        filters={
            "type": f_type, "band": f_band, "issue": f_issue,
            "q": f_search or "", "sort": f_sort,
        },
        page_num=page_num, total_pages=total_pages,
        total_filtered=total_filtered,
    )


def seo_url_detail(page_id):
    page = db.seo_get_page(page_id)
    if not page:
        flash("Không tìm thấy URL.", "error")
        return redirect(url_for("seo_dashboard"))
    raw_issues = []
    if page.get("issues"):
        try:
            raw_issues = json.loads(page["issues"])
        except (ValueError, TypeError):
            raw_issues = []
    issues = [seo_mod.enrich_issue(it) for it in raw_issues]
    return render_template("seo_detail.html", p=page, issues=issues)


# ─────────────────────── RULES PAGE + SAVE ───────────────────────

def seo_rules_page():
    """UI quản lý SEO rules: enable/disable, edit threshold/score/label/message."""
    cfg = seo_mod.load_rules_config()
    return render_template("seo_rules.html", config=cfg)


def seo_rules_save():
    """Lưu config rules từ form. Field name format: rule_<code>_<field>."""
    cfg = seo_mod.load_rules_config(force=True)
    try:
        cfg["thresholds"]["good"] = int(request.form.get("threshold_good") or 65)
        cfg["thresholds"]["ok"] = int(request.form.get("threshold_ok") or 50)
    except ValueError:
        pass

    for rule in cfg.get("rules", []):
        code = rule.get("code")
        if not code:
            continue
        rule["enabled"] = bool(request.form.get(f"rule_{code}_enabled"))
        name = (request.form.get(f"rule_{code}_name") or "").strip()
        if name:
            rule["name"] = name
        lvl = request.form.get(f"rule_{code}_level")
        if lvl in ("error", "warn", "info"):
            rule["level"] = lvl
        try:
            score_str = request.form.get(f"rule_{code}_score")
            if score_str is not None and score_str != "":
                rule["score"] = int(score_str)
        except ValueError:
            pass
        thr_str = request.form.get(f"rule_{code}_threshold")
        if thr_str is not None and thr_str != "":
            try:
                rule["threshold"] = int(thr_str)
            except ValueError:
                try:
                    rule["threshold"] = float(thr_str)
                except ValueError:
                    rule["threshold"] = thr_str
        msg = request.form.get(f"rule_{code}_msg")
        if msg is not None:
            rule["msg"] = msg

    cfg["last_edited"] = datetime.now().isoformat(timespec="seconds")
    seo_mod.save_rules_config(cfg)
    flash(f"✅ Đã lưu {len(cfg.get('rules', []))} rules. Crawl sau sẽ apply ngay.", "success")
    return redirect(url_for("seo_rules_page"))


# ─────────────────────── EXPORT ──────────────────────────────────

def seo_export(kind):
    """kind = pages | issues | summary"""
    if kind == "summary":
        summary = {
            "stats": db.seo_stats(),
            "indexability": db.seo_indexability_stats(),
            "inlinks": db.seo_inlinks_summary(),
            "duplicates": {
                "title": len(db.seo_find_duplicates("title")),
                "meta_desc": len(db.seo_find_duplicates("meta_desc")),
                "h1": len(db.seo_find_duplicates("h1")),
            },
            "broken_links": db.seo_broken_link_summary(),
            "top_issues": db.seo_top_issues(limit=20),
            "exported_at": datetime.now().isoformat(timespec="seconds"),
        }
        return Response(
            json.dumps(summary, ensure_ascii=False, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=seo-summary.json"},
        )

    buf = io.StringIO()
    writer = csv.writer(buf)

    if kind == "pages":
        writer.writerow([
            "url", "url_type", "status_code", "indexable", "indexability_reason",
            "title", "title_len", "meta_desc", "meta_desc_len",
            "h1", "h1_count", "word_count", "score",
            "internal_links", "external_links", "images_total", "images_no_alt",
            "has_canonical", "canonical_url", "has_og", "has_schema",
            "load_ms", "page_size_bytes", "last_crawled",
        ])
        pages_all = db.seo_list_pages(limit=10000, sort="score_asc")
        for p in pages_all:
            writer.writerow([
                p.get("url"), p.get("url_type"), p.get("status_code"),
                p.get("indexable"), p.get("indexability_reason"),
                p.get("title"), p.get("title_len"),
                p.get("meta_desc"), p.get("meta_desc_len"),
                p.get("h1"), p.get("h1_count"), p.get("word_count"), p.get("score"),
                p.get("internal_links"), p.get("external_links"),
                p.get("images_total"), p.get("images_no_alt"),
                p.get("has_canonical"), p.get("canonical_url"),
                p.get("has_og"), p.get("has_schema"),
                p.get("load_ms"), p.get("page_size_bytes"), p.get("last_crawled"),
            ])
        return Response(
            "﻿" + buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=seo-pages.csv"},
        )

    if kind == "issues":
        writer.writerow(["url", "url_type", "score", "issue_code", "level", "message", "fix"])
        pages_all = db.seo_list_pages(limit=10000, sort="score_asc")
        for p in pages_all:
            try:
                issue_arr = json.loads(p.get("issues") or "[]")
            except (ValueError, TypeError):
                issue_arr = []
            for it in issue_arr:
                _icon, label, fix = seo_mod.ISSUE_LABELS.get(it.get("code", ""), ("", it.get("code", ""), ""))
                writer.writerow([
                    p.get("url"), p.get("url_type"), p.get("score"),
                    it.get("code"), it.get("level"),
                    f"{label} — {it.get('msg', '')}", fix,
                ])
        return Response(
            "﻿" + buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=seo-issues.csv"},
        )

    flash("Loại export không hợp lệ. Chọn: pages / issues / summary.", "error")
    return redirect(url_for("seo_dashboard"))


# ─────────────────────── SNAPSHOT SAVE/LOAD/DELETE ───────────────

def seo_snapshot_save():
    SEO_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    label_raw = (request.form.get("label") or "").strip()
    label_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", label_raw)[:40] if label_raw else ""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"seo_{stamp}{('_' + label_slug) if label_slug else ''}.json.gz"
    snapshot = db.seo_export_snapshot()
    snapshot["label"] = label_raw
    path = SEO_SNAPSHOT_DIR / fname
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False)
    counts = snapshot["counts"]
    size_mb = round(path.stat().st_size / 1024 / 1024, 1)
    flash(
        f"💾 Đã save snapshot: {fname} ({size_mb} MB) — {counts['pages']} URL, {counts['links']} link, {counts['runs']} run.",
        "success",
    )
    return redirect(url_for("seo_dashboard"))


def seo_snapshot_load(filename):
    safe = secure_filename(filename)
    path = SEO_SNAPSHOT_DIR / safe
    if not path.exists() or not (safe.endswith(".json") or safe.endswith(".json.gz")):
        flash("Không tìm thấy snapshot.", "error")
        return redirect(url_for("seo_dashboard"))
    try:
        with _open_snapshot(path) as f:
            data = json.load(f)
        db.seo_import_snapshot(data)
        counts = data.get("counts") or {}
        flash(
            f"📂 Đã load snapshot {safe} — {counts.get('pages', 0)} URL, {counts.get('links', 0)} link.",
            "success",
        )
    except (ValueError, OSError) as e:
        flash(f"Lỗi load snapshot: {e}", "error")
    return redirect(url_for("seo_dashboard"))


def seo_snapshot_delete(filename):
    safe = secure_filename(filename)
    path = SEO_SNAPSHOT_DIR / safe
    if path.exists() and (safe.endswith(".json") or safe.endswith(".json.gz")):
        path.unlink()
        flash(f"🗑️ Đã xoá snapshot {safe}.", "success")
    else:
        flash("Không tìm thấy snapshot.", "error")
    return redirect(url_for("seo_dashboard"))


# ─────────────────────── CLEAR + RECRAWL + SEED + STATUS ────────

def seo_clear():
    if request.form.get("confirm") != "yes":
        flash("Cần xác nhận xoá. Click lại nút Clear.", "error")
        return redirect(url_for("seo_dashboard"))
    db.seo_clear_all()
    flash("⚠️ Đã clear toàn bộ data crawl SEO.", "success")
    return redirect(url_for("seo_dashboard"))


def seo_url_recrawl(page_id):
    page = db.seo_get_page(page_id)
    if not page:
        flash("Không tìm thấy URL.", "error")
        return redirect(url_for("seo_dashboard"))
    result = seo_mod.crawl_one(page["url"])
    result["last_run_id"] = page.get("last_run_id")
    links = result.pop("_links", [])
    db.seo_upsert_page(result)
    if links:
        db.seo_replace_links(result["url"], links)
    flash(f"Đã crawl lại — điểm: {result.get('score', 0)}.", "success")
    return redirect(url_for("seo_url_detail", page_id=page_id))


def seo_seed():
    try:
        urls = seo_mod.fetch_sitemap_urls()
    except Exception as e:
        flash(f"Lỗi fetch sitemap: {e.__class__.__name__}: {e}", "error")
        return redirect(url_for("seo_dashboard"))
    pairs = [(u, seo_mod.classify_url(u)) for u in urls]
    res = db.seo_seed_urls(pairs)
    flash(
        f"Đã quét sitemap: {len(urls)} URL — thêm mới {res['added']}, đã có sẵn {res['existing']}.",
        "success",
    )
    return redirect(url_for("seo_dashboard"))


def seo_status():
    return jsonify({
        "state": seo_mod.state_snapshot(),
        "link_state": seo_mod.link_check_state(),
        "stats": db.seo_stats(),
        "broken_summary": db.seo_broken_link_summary(),
    })


def seo_recompute_dup():
    """Detect dup title/meta cross-site, trừ điểm + cập nhật issues vào seo_pages."""
    try:
        stats = seo_mod.recompute_dup_flags()
        return jsonify({"ok": True, **stats})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e.__class__.__name__}: {e}"}), 500


# ─────────────────────── HISTORY (4 endpoint) ────────────────────

def seo_history_page():
    history = db.seo_history_list(limit=200)
    chart_data = db.seo_history_chart_data(limit=52)
    cwv_timeline = db.cwv_history_timeline(limit=52)
    schema_timeline = db.seo_schema_history_timeline(limit=52)
    regression = db.seo_history_regression_check()
    return render_template(
        "seo_history.html",
        history=history,
        chart_data=chart_data,
        cwv_timeline=cwv_timeline,
        schema_timeline=schema_timeline,
        regression=regression,
    )


def seo_history_export_csv():
    rows = db.seo_history_list(limit=10000)
    if not rows:
        flash("⚠️ Chưa có snapshot nào để export", "warning")
        return redirect(url_for("seo_history_page"))
    keys = [
        "id", "captured_at", "total", "avg_score",
        "avg_score_product", "avg_score_blog", "avg_score_collection",
        "good", "ok_count", "bad", "broken_links", "note",
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k) or "" for k in keys})
    csv_text = buf.getvalue()
    fname = f"seo_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_text.encode("utf-8-sig"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


def seo_history_compare_page():
    try:
        a_id = int(request.args.get("a", 0))
        b_id = int(request.args.get("b", 0))
    except (TypeError, ValueError):
        a_id = b_id = 0
    a = db.seo_history_get(a_id) if a_id else None
    b = db.seo_history_get(b_id) if b_id else None
    if not a or not b:
        flash("⚠️ Cần chọn cả 2 snapshot A và B (chọn ở bảng /seo/history)", "warning")
        return redirect(url_for("seo_history_page"))

    metric_keys = [
        ("avg_score", "Điểm SEO TB", "score"),
        ("avg_score_product", "Avg SP (product)", "score"),
        ("avg_score_blog", "Avg blog", "score"),
        ("avg_score_collection", "Avg collection", "score"),
        ("good", "🟢 Tốt", "count_up"),
        ("ok_count", "🟡 OK", "count_up"),
        ("bad", "🔴 Cần sửa", "count_down"),
        ("total", "Tổng URL", "count"),
        ("broken_links", "🔗 Link gãy", "count_down"),
    ]
    diffs = []
    for key, label, direction in metric_keys:
        va = a.get(key) or 0
        vb = b.get(key) or 0
        delta = round(vb - va, 1)
        if direction == "count_up":
            trend = "good" if delta > 0 else ("bad" if delta < 0 else "neutral")
        elif direction == "count_down":
            trend = "good" if delta < 0 else ("bad" if delta > 0 else "neutral")
        elif direction == "score":
            if delta >= 5:
                trend = "good"
            elif delta <= -5:
                trend = "bad"
            else:
                trend = "neutral"
        else:
            trend = "neutral"
        diffs.append({"key": key, "label": label, "a": va, "b": vb,
                      "delta": delta, "trend": trend})
    return render_template("seo_history_compare.html", a=a, b=b, diffs=diffs)


def seo_history_capture():
    note = (request.form.get("note") or "").strip()
    rid = db.seo_capture_history(note=note)
    db.activity_log(
        kind="seo_snapshot", icon="📸",
        title=f"Chụp snapshot SEO #{rid}",
        description=f"Note: {note or 'manual'}",
        href=url_for("seo_history_page"),
    )
    flash(f"📸 Đã chụp snapshot lịch sử #{rid}", "success")
    return redirect(url_for("seo_history_page"))


# ─────────────────────── CRAWL (3 endpoint) ──────────────────────

def seo_crawl():
    try:
        limit = int(request.form.get("limit") or 0) or None
    except (TypeError, ValueError):
        limit = None
    started = seo_mod.start_crawl_async(limit=limit)
    if started:
        flash(f"Đã bắt đầu crawl {'(' + str(limit) + ' URL test)' if limit else '(toàn bộ sitemap)'}.", "success")
    else:
        flash("Đang có run khác — chờ xong rồi crawl tiếp.", "error")
    return redirect(url_for("seo_dashboard"))


def seo_stop_crawl():
    """Stop crawl đang chạy (graceful — đợi các request đang fly xong)."""
    stopped = seo_mod.stop_crawl()
    if stopped:
        flash("🛑 Đã gửi signal stop — crawl sẽ dừng sau khi xong các URL đang fetch.", "info")
    else:
        flash("Crawl đang idle — không có gì để stop.", "info")
    return redirect(url_for("seo_dashboard"))


def seo_crawl_fresh():
    """Stop crawl đang chạy + xóa toàn bộ data + start crawl mới fresh.
    Hữu ích khi muốn re-crawl từ đầu, không bị data cũ ảnh hưởng."""
    import time
    seo_mod.stop_crawl()
    for _ in range(20):
        snap = seo_mod.state_snapshot()
        if snap["status"] not in ("fetching_sitemap", "crawling", "stopping"):
            break
        time.sleep(0.5)
    db.seo_clear_all()
    started = seo_mod.start_crawl_async(limit=None)
    if started:
        flash("🆕 Đã xóa toàn bộ data cũ + bắt đầu crawl mới fresh. Refresh trang để xem tiến độ realtime.", "success")
    else:
        flash("Vẫn còn run khác chưa stop hết — đợi 30s rồi thử lại.", "error")
    return redirect(url_for("seo_dashboard"))


# ─────────────────────── REGISTRATION ────────────────────────────

def register(app):
    """Đăng ký 20 route SEO Core — giữ nguyên endpoint name."""
    # Overview + URL detail
    app.add_url_rule("/seo", "seo_dashboard", seo_dashboard)
    app.add_url_rule("/seo/url/<int:page_id>", "seo_url_detail", seo_url_detail)

    # Rules
    app.add_url_rule("/seo/rules", "seo_rules_page", seo_rules_page)
    app.add_url_rule("/seo/rules/save", "seo_rules_save", seo_rules_save, methods=["POST"])

    # Export
    app.add_url_rule("/seo/export/<kind>", "seo_export", seo_export)

    # Snapshot
    app.add_url_rule("/seo/snapshot/save", "seo_snapshot_save", seo_snapshot_save, methods=["POST"])
    app.add_url_rule("/seo/snapshot/load/<filename>", "seo_snapshot_load", seo_snapshot_load, methods=["POST"])
    app.add_url_rule("/seo/snapshot/delete/<filename>", "seo_snapshot_delete", seo_snapshot_delete, methods=["POST"])

    # Clear + recrawl + seed + status
    app.add_url_rule("/seo/clear", "seo_clear", seo_clear, methods=["POST"])
    app.add_url_rule("/seo/url/<int:page_id>/recrawl", "seo_url_recrawl", seo_url_recrawl, methods=["POST"])
    app.add_url_rule("/seo/seed", "seo_seed", seo_seed, methods=["POST"])
    app.add_url_rule("/api/seo/status", "seo_status", seo_status)
    app.add_url_rule("/seo/recompute-dup", "seo_recompute_dup", seo_recompute_dup, methods=["POST"])

    # History
    app.add_url_rule("/seo/history", "seo_history_page", seo_history_page)
    app.add_url_rule("/seo/history/export.csv", "seo_history_export_csv", seo_history_export_csv)
    app.add_url_rule("/seo/history/compare", "seo_history_compare_page", seo_history_compare_page)
    app.add_url_rule("/seo/history/capture", "seo_history_capture", seo_history_capture, methods=["POST"])

    # Crawl
    app.add_url_rule("/seo/crawl", "seo_crawl", seo_crawl, methods=["POST"])
    app.add_url_rule("/seo/stop-crawl", "seo_stop_crawl", seo_stop_crawl, methods=["POST"])
    app.add_url_rule("/seo/crawl-fresh", "seo_crawl_fresh", seo_crawl_fresh, methods=["POST"])
