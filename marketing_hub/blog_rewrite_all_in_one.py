# -*- coding: utf-8 -*-
"""Blog Rewrite — P8 ALL-IN-ONE ORCHESTRATOR.

classify toàn bộ bài chưa applied (title+body) → route 5 queue → xử lý theo thứ tự
STAGE 1 AUTO_RECLAIM → 2 VISUAL → 3 NEWS → 4 FPS → 5 REVIEW → reconcile → report.

REUSE engine: run_full_auto(candidate_ids=ordered) chạy đúng pipeline mỗi bài
(generate→review→auto_fix→image/fact/quality/conflict gate→backup→body-only PUT 1 lần→
verify→reconcile 500-but-write→checkpoint→CB). Mọi bài AUTO pipeline, gates tự quyết outcome.
Orchestrator chỉ: classify + sắp thứ tự stage+traffic + map nhãn outcome theo queue + report.

KHÔNG đổi field SEO ngoài body_html. KHÔNG commit/push. KHÔNG scheduler.
"""
import json, csv
from pathlib import Path

import db
import blog_rewrite as br
import blog_rewrite_full_auto as fa
import blog_rewrite_autopilot as auto
import blog_rewrite_queues as q

ALL_IN_ONE_PHRASE = "START ALL IN ONE BLOG REWRITE SYNC"
MODE_TAG = "ALL_IN_ONE"
STAGE_ORDER = [q.Q_AUTO, q.Q_VISUAL, q.Q_NEWS, q.Q_FPS, q.Q_REVIEW]
_DIR = Path(__file__).parent
DOCS = _DIR / "docs"


# ═══════════════════ build ordered queue ═══════════════════
def build_ordered(reclassify=True, skip_decided=False, emit=print):
    """classify (nếu cần) → trả list candidate_id theo thứ tự stage + traffic, kèm map queue.
    skip_decided=True: bỏ bài đã có decision cuối (chỉ retry FAILED + chưa xử) — vd retry sau limit."""
    if reclassify:
        emit("Classify title+body...")
        q.classify_all(emit=emit)
    elig = {c["id"]: c for c in fa.queue_candidates()}  # chưa applied, eligible, non-reverse
    done = fa.decided_candidate_ids() if skip_decided else set()
    conn = db.get_conn(); conn.row_factory = __import__("sqlite3").Row
    rows = conn.execute("SELECT id, blog_queue FROM blog_rewrite_candidates "
                        "WHERE rewrite_eligible=1 AND audit_reverse_copy=0 AND status!='applied'").fetchall()
    conn.close()
    qmap = {r["id"]: (r["blog_queue"] or q.Q_REVIEW) for r in rows}
    ordered = []
    per_stage = {}
    for stage in STAGE_ORDER:
        ids = [cid for cid, qq in qmap.items() if qq == stage and cid in elig and cid not in done]
        ids.sort(key=lambda cid: fa._lane_sort_key(elig[cid]))  # traffic + ít ảnh/bảng
        per_stage[stage] = ids
        ordered += ids
    return ordered, qmap, per_stage


# ═══════════════════ run (reuse run_full_auto) ═══════════════════
def run_all_in_one(confirm_phrase=None, qa=False, dry_run=False, max_articles=None, reclassify=True, skip_decided=False):
    live = (not qa) and (not dry_run)
    if live and confirm_phrase != ALL_IN_ONE_PHRASE:
        return {"ok": False, "error": "CONFIRM_PHRASE_REQUIRED", "need": ALL_IN_ONE_PHRASE}
    ordered, qmap, per_stage = build_ordered(reclassify=reclassify, skip_decided=skip_decided)
    if max_articles:
        ordered = ordered[:max_articles]
    # reuse engine — confirm nội bộ = START_PHRASE của full_auto sau khi đã verify phrase all-in-one
    res = fa.run_full_auto(confirm_phrase=fa.START_PHRASE, qa=qa, dry_run=dry_run,
                           candidate_ids=ordered, mode_tag=MODE_TAG)
    res["queue_plan"] = {k: len(v) for k, v in per_stage.items()}
    return res


# ═══════════════════ report (map nhãn theo queue) ═══════════════════
def _spec_label(queue, decision):
    if decision == "APPLIED":
        return "visual_fixed" if queue == q.Q_VISUAL else "applied"
    if decision == "APPLIED_RECONCILED":
        return "applied_reconciled"
    if decision == "NOT_APPLIED_RETRYABLE":
        return "not_applied_retryable"
    if decision == "BLOCKED_IMAGE":
        return "blocked_image"
    if decision == "HOLD_TIME_SENSITIVE":
        return "hold_news"
    if decision == "BLOCKED_FACT":
        return "hold_benchmark" if queue == q.Q_FPS else "hold_news"
    if decision in ("HOLD_QUALITY", "MANUAL_REVIEW", "MANUAL_COMPLEX"):
        return "manual_complex"
    if decision == "CONFLICT":
        return "conflict"
    if decision in ("FAILED", "UNCERTAIN_POST_PUT"):
        return "failed"
    return (decision or "pending").lower()


def last_run_id():
    conn = db.get_conn()
    r = conn.execute("SELECT id FROM blog_rewrite_autopilot_runs WHERE mode LIKE ? ORDER BY id DESC LIMIT 1",
                     (MODE_TAG + "%",)).fetchone()
    conn.close()
    return r[0] if r else None


def report(run_id=None):
    run_id = run_id or last_run_id()
    if not run_id:
        return {"ok": False, "error": "chưa có run ALL_IN_ONE"}
    conn = db.get_conn(); conn.row_factory = __import__("sqlite3").Row
    items = conn.execute(
        "SELECT i.candidate_id, i.article_id, i.decision, i.decision_reason, i.apply_json, i.verify_json, "
        "c.title, c.blog_queue, c.traffic_tier "
        "FROM blog_rewrite_autopilot_items i JOIN blog_rewrite_candidates c ON c.id=i.candidate_id "
        "WHERE i.run_id=? ORDER BY i.id", (run_id,)).fetchall()
    conn.close()
    from collections import Counter
    rows = []
    labels = Counter()
    put_count = recon = 0
    for it in items:
        aj = json.loads(it["apply_json"] or "{}")
        vj = json.loads(it["verify_json"] or "{}")
        lbl = _spec_label(it["blog_queue"], it["decision"])
        labels[lbl] += 1
        if aj.get("http"):
            put_count += 1
        if lbl == "applied_reconciled":
            recon += 1
        rows.append({"candidate_id": it["candidate_id"], "article_id": it["article_id"],
                     "title": it["title"], "queue": it["blog_queue"], "tier": it["traffic_tier"],
                     "decision": it["decision"], "label": lbl, "http": aj.get("http"),
                     "verify": vj.get("verify"), "verify_source": aj.get("verify_source") or vj.get("source"),
                     "reason": it["decision_reason"]})
    return {"ok": True, "run_id": run_id, "labels": dict(labels), "put_count": put_count,
            "applied_reconciled": recon, "rows": rows}


def export_csvs(run_id=None):
    rep = report(run_id)
    if not rep.get("ok"):
        return rep
    DOCS.mkdir(parents=True, exist_ok=True)
    rows = rep["rows"]

    def _w(name, filt):
        p = DOCS / name
        sel = [r for r in rows if filt(r)]
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["candidate_id", "article_id", "title", "queue", "tier",
                                              "decision", "label", "http", "verify", "verify_source", "reason"])
            w.writeheader()
            for r in sel:
                w.writerow(r)
        return len(sel)

    counts = {
        "items": _w("blog_rewrite_ai_p8_all_in_one_items.csv", lambda r: True),
        "blocked_images": _w("blog_rewrite_ai_p8_all_in_one_blocked_images.csv", lambda r: r["label"] == "blocked_image"),
        "hold_news": _w("blog_rewrite_ai_p8_all_in_one_hold_news.csv", lambda r: r["label"] == "hold_news"),
        "hold_benchmark": _w("blog_rewrite_ai_p8_all_in_one_hold_benchmark.csv", lambda r: r["label"] == "hold_benchmark"),
        "manual_complex": _w("blog_rewrite_ai_p8_all_in_one_manual_complex.csv", lambda r: r["label"] == "manual_complex"),
    }
    return {"ok": True, "run_id": rep["run_id"], "csv_counts": counts, "labels": rep["labels"]}


def status():
    """Reuse full_auto checkpoint/CB (run all-in-one chính là full_auto run candidate_ids)."""
    st = fa.status()
    st["all_in_one_last_run"] = last_run_id()
    return st


if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print("Plan:", build_ordered(reclassify=False)[2])
