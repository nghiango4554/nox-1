# -*- coding: utf-8 -*-
"""Blog Rewrite — P5E IMAGE REMEDIATION QUEUE (local-only).

Import audit 815 ảnh → bảng blog_rewrite_image_items. Per-image action + tạo draft
sạch local (gỡ ảnh chết/đối thủ) + recompute gate. KHÔNG upload/PUT/rehost/apply live.
"""
import json, re
import db
import blog_rewrite as _br
import blog_rewrite_images as im

# ─── availability_status tách khỏi source_class ───
def _avail_status(error_type, status_code, reachable):
    if reachable:
        return "REACHABLE"
    et = (error_type or "").lower()
    if et == "dead" and status_code == 410:
        return "DEAD_410"
    if et == "dead":
        return "DEAD_404"
    if et == "invalid_url":
        return "INVALID"
    if et == "timeout":
        return "UNCERTAIN_TIMEOUT"
    if status_code == 403:
        return "UNCERTAIN_403"
    if status_code == 429:
        return "UNCERTAIN_429"
    if status_code and 500 <= status_code < 600:
        return "UNCERTAIN_5XX"
    if et == "uncertain":
        return "UNCERTAIN_TIMEOUT"
    return "NOT_CHECKED" if reachable is None else "UNCERTAIN_TIMEOUT"


def _default_action(source_class, avail):
    if avail in ("DEAD_404", "DEAD_410", "INVALID"):
        return "REMOVE_DEAD_IMAGE"
    if source_class == "SINTECH_OWNED":
        return "KEEP"
    # competitor / news / unknown / other-store / official → KHÔNG auto remove
    return "MANUAL_REVIEW"


def migrate():
    conn = db.get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS blog_rewrite_image_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER, draft_id INTEGER, article_id INTEGER, image_index INTEGER,
        original_src TEXT, hostname TEXT, store_id TEXT, filename TEXT, alt TEXT,
        source_class TEXT, rights_status TEXT, reachable INTEGER, status_code INTEGER,
        error_type TEXT, availability_status TEXT,
        brand_in_alt TEXT, brand_in_filename TEXT, brand_in_url TEXT,
        recommended_action TEXT, selected_action TEXT, manual_note TEXT,
        review_status TEXT DEFAULT 'pending', reviewed_at TEXT,
        created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(candidate_id, original_src)
    );
    CREATE INDEX IF NOT EXISTS idx_brii_cand ON blog_rewrite_image_items(candidate_id);
    CREATE INDEX IF NOT EXISTS idx_brii_src ON blog_rewrite_image_items(source_class);
    CREATE INDEX IF NOT EXISTS idx_brii_avail ON blog_rewrite_image_items(availability_status);
    CREATE INDEX IF NOT EXISTS idx_brii_review ON blog_rewrite_image_items(review_status);
    CREATE INDEX IF NOT EXISTS idx_brii_action ON blog_rewrite_image_items(selected_action);
    """)
    conn.commit(); conn.close()


def import_from_csv(csv_path="docs/blog_rewrite_image_regression_audit.csv"):
    """Idempotent import từ audit CSV → image_items. Giữ selected_action nếu đã review."""
    import csv as _csv
    from pathlib import Path
    p = Path(__file__).parent / csv_path
    rows = list(_csv.DictReader(open(p, encoding="utf-8-sig")))
    conn = db.get_conn()
    n_ins = n_upd = 0
    for idx, r in enumerate(rows):
        cid = int(r["candidate_id"]); src = r["image_src"]
        reach = 1 if r["reachable"] == "True" else (0 if r["reachable"] == "False" else None)
        sc_code = int(r["status_code"]) if (r["status_code"] or "").strip().isdigit() else None
        avail = _avail_status(r["error_type"], sc_code, reach)
        rec = r["recommended_action"]
        default_act = _default_action(r["source_class"], avail)
        ex = conn.execute("SELECT id, review_status, selected_action FROM blog_rewrite_image_items "
                          "WHERE candidate_id=? AND original_src=?", (cid, src)).fetchone()
        vals = (int(r["draft_id"]) if (r["draft_id"] or "").strip().isdigit() else None,
                int(r["article_id"]) if (r["article_id"] or "").strip().isdigit() else None,
                r["hostname"], r["store_id"], r["filename"], r["alt"], r["source_class"], r["rights_status"],
                reach, sc_code, r["error_type"], avail, rec)
        if ex:
            keep_act = ex["selected_action"] if ex["review_status"] == "reviewed" else default_act
            conn.execute("""UPDATE blog_rewrite_image_items SET draft_id=?, article_id=?, hostname=?, store_id=?,
                filename=?, alt=?, source_class=?, rights_status=?, reachable=?, status_code=?, error_type=?,
                availability_status=?, recommended_action=?, selected_action=?, updated_at=datetime('now')
                WHERE id=?""", vals + (keep_act, ex["id"]))
            n_upd += 1
        else:
            conn.execute("""INSERT INTO blog_rewrite_image_items (candidate_id, original_src, image_index,
                draft_id, article_id, hostname, store_id, filename, alt, source_class, rights_status,
                reachable, status_code, error_type, availability_status, recommended_action, selected_action)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, src, idx) + vals + (default_act,))
            n_ins += 1
    conn.commit(); conn.close()
    return {"inserted": n_ins, "updated": n_upd, "total": len(rows)}


# ─── article-level gate ───
def article_gate(candidate_id):
    conn = db.get_conn()
    items = conn.execute("SELECT source_class, availability_status, selected_action, review_status "
                         "FROM blog_rewrite_image_items WHERE candidate_id=?", (candidate_id,)).fetchall()
    conn.close()
    blocked = []
    for it in items:
        act = it["selected_action"]
        if act in ("REMOVE_DEAD_IMAGE", "REMOVE_FROM_DRAFT", "KEEP"):
            continue  # đã quyết (gỡ hoặc giữ-Sintech)
        # còn pending review trên ảnh non-Sintech → block
        if it["availability_status"] in ("DEAD_404", "DEAD_410", "INVALID"):
            blocked.append("BLOCK_DEAD_IMAGE")
        elif it["source_class"] == "COMPETITOR_SOURCE":
            blocked.append("BLOCK_COMPETITOR_IMAGE")
        elif it["source_class"] == "NEWS_MEDIA_SOURCE":
            blocked.append("BLOCK_NEWS_IMAGE")
        elif it["source_class"] == "HARAVAN_OTHER_STORE":
            blocked.append("BLOCK_OTHER_STORE_IMAGE")
        elif it["source_class"] in ("UNKNOWN_EXTERNAL", "INVALID_URL"):
            blocked.append("BLOCK_UNKNOWN_IMAGE")
        else:
            blocked.append("REVIEW_REQUIRED")
    if not items:
        return "ALLOW"
    return "ALLOW" if not blocked else sorted(set(blocked))[0]


def image_summary():
    conn = db.get_conn()
    def cnt(where="1=1", *a):
        return conn.execute(f"SELECT COUNT(*) FROM blog_rewrite_image_items WHERE {where}", a).fetchone()[0]
    sc = {r[0]: r[1] for r in conn.execute("SELECT source_class, COUNT(*) FROM blog_rewrite_image_items GROUP BY source_class")}
    av = {r[0]: r[1] for r in conn.execute("SELECT availability_status, COUNT(*) FROM blog_rewrite_image_items GROUP BY availability_status")}
    conn.close()
    cands = set()
    conn = db.get_conn()
    rows = conn.execute("SELECT DISTINCT candidate_id FROM blog_rewrite_image_items").fetchall()
    conn.close()
    blocked = review = safe = 0
    for r in rows:
        g = article_gate(r[0])
        if g == "ALLOW": safe += 1
        elif g == "REVIEW_REQUIRED": review += 1
        else: blocked += 1
    return {
        "total_images": sum(sc.values()), "by_source": sc, "by_availability": av,
        "candidates": len(rows), "safe": safe, "review": review, "blocked": blocked,
        "dead": av.get("DEAD_404", 0) + av.get("DEAD_410", 0),
        "uncertain": sum(v for k, v in av.items() if k.startswith("UNCERTAIN")),
    }


def list_items(candidate_id=None, source_class=None, availability=None, selected_action=None,
               review_status=None, gate=None, q=None, limit=200, offset=0):
    conn = db.get_conn()
    where, args = ["1=1"], []
    if candidate_id: where.append("candidate_id=?"); args.append(int(candidate_id))
    if source_class: where.append("source_class=?"); args.append(source_class)
    if availability: where.append("availability_status=?"); args.append(availability)
    if selected_action: where.append("selected_action=?"); args.append(selected_action)
    if review_status: where.append("review_status=?"); args.append(review_status)
    if q: where.append("(original_src LIKE ? OR alt LIKE ? OR filename LIKE ?)"); args += [f"%{q}%"] * 3
    total = conn.execute(f"SELECT COUNT(*) FROM blog_rewrite_image_items WHERE {' AND '.join(where)}", args).fetchone()[0]
    rows = conn.execute(f"SELECT * FROM blog_rewrite_image_items WHERE {' AND '.join(where)} "
                        f"ORDER BY candidate_id, image_index LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
    conn.close()
    return {"total": total, "items": [dict(r) for r in rows]}


_ACTIONS = ("KEEP", "REMOVE_DEAD_IMAGE", "REMOVE_FROM_DRAFT", "REPLACE_WITH_OFFICIAL_IMAGE_LATER",
            "CREATE_ORIGINAL_IMAGE_LATER", "MANUAL_REVIEW")


def set_action(item_id, action, note=None):
    if action not in _ACTIONS:
        return {"ok": False, "error": "action không hợp lệ"}
    conn = db.get_conn()
    conn.execute("UPDATE blog_rewrite_image_items SET selected_action=?, manual_note=?, "
                 "review_status='reviewed', reviewed_at=datetime('now'), updated_at=datetime('now') WHERE id=?",
                 (action, (note or "")[:300], item_id))
    conn.commit(); conn.close()
    return {"ok": True}


def bulk_dead_local(confirm_phrase):
    """Mark all DEAD/INVALID → REMOVE_DEAD_IMAGE (local only, cần confirm phrase)."""
    if confirm_phrase.strip() != "REMOVE DEAD IMAGES FROM LOCAL DRAFTS":
        return {"ok": False, "error": "Confirm phrase sai."}
    conn = db.get_conn()
    n = conn.execute("UPDATE blog_rewrite_image_items SET selected_action='REMOVE_DEAD_IMAGE', "
                     "review_status='reviewed', reviewed_at=datetime('now') "
                     "WHERE availability_status IN ('DEAD_404','DEAD_410','INVALID')").rowcount
    conn.commit(); conn.close()
    return {"ok": True, "marked": n}


_REMOVE_ACTIONS = ("REMOVE_DEAD_IMAGE", "REMOVE_FROM_DRAFT")


def build_remediated_draft_local(candidate_id, source_draft_id=None):
    """Tạo draft sạch local: gỡ ảnh có action REMOVE_*, sanitize, recompute. Clone version mới.
    Pending (competitor/news/unknown/manual) → giữ blocked. KHÔNG upload/PUT."""
    import blog_rewrite_gen as gen
    d = _br.get_draft(source_draft_id) if source_draft_id else _br.latest_draft_for_candidate(candidate_id)
    if not d:
        return {"ok": False, "error": "không có draft nguồn"}
    body = d["draft_body_html"] or ""
    conn = db.get_conn()
    items = conn.execute("SELECT original_src, selected_action FROM blog_rewrite_image_items WHERE candidate_id=?",
                         (candidate_id,)).fetchall()
    conn.close()
    removed = pending = 0
    for it in items:
        src = it["original_src"]; act = it["selected_action"]
        if act in _REMOVE_ACTIONS:
            esc = re.escape(src)
            body = re.sub(r'<p>\s*<img[^>]*src="' + esc + r'"[^>]*>\s*</p>', '', body, flags=re.I)
            body = re.sub(r'<img[^>]*src="' + esc + r'"[^>]*>', '', body, flags=re.I)
            removed += 1
        elif act not in ("KEEP",):
            pending += 1
    clean, _, _ = gen.sanitize_html(body)  # table border + responsive + clean
    qm = gen.quality_metrics(d.get("original_body_html") or "", clean)
    conn = db.get_conn()
    ver = (conn.execute("SELECT COALESCE(MAX(version),0) FROM blog_rewrite_drafts WHERE candidate_id=?",
                        (candidate_id,)).fetchone()[0] or 0) + 1
    cur = conn.execute("""INSERT INTO blog_rewrite_drafts (candidate_id, job_id, version, original_title,
        original_body_html, original_handle, original_content_hash, draft_title, draft_body_html,
        draft_summary_html, draft_tags, seo_title_suggestions_json, meta_description_suggestions_json,
        outline_json, quality_json, approval_status)
        SELECT candidate_id, job_id, ?, original_title, original_body_html, original_handle,
        original_content_hash, draft_title, ?, draft_summary_html, draft_tags,
        seo_title_suggestions_json, meta_description_suggestions_json, outline_json, ?, 'draft_ready'
        FROM blog_rewrite_drafts WHERE id=?""", (ver, clean, json.dumps(qm, ensure_ascii=False), d["id"]))
    nid = cur.lastrowid
    conn.commit(); conn.close()
    _br.record_event("image_remediation_draft_created", candidate_id=candidate_id, draft_id=nid,
                     detail={"removed": removed, "pending": pending, "version": ver})
    gate = article_gate(candidate_id)
    return {"ok": True, "draft_id": nid, "version": ver, "removed": removed, "pending": pending,
            "gate_after": gate, "images_left": clean.count("<img")}


# ═══════════════════════ P5F — QUICK-WIN SPRINT ═══════════════════════
import math


def _article_image_counts(candidate_id):
    conn = db.get_conn()
    items = conn.execute("SELECT source_class, availability_status, selected_action FROM blog_rewrite_image_items WHERE candidate_id=?",
                         (candidate_id,)).fetchall()
    conn.close()
    c = {"total": len(items), "safe": 0, "dead": 0, "uncertain": 0, "competitor": 0,
         "news": 0, "unknown": 0, "other_store": 0, "official": 0, "pending": 0}
    for it in items:
        sc, av, act = it["source_class"], it["availability_status"], it["selected_action"]
        if av in ("DEAD_404", "DEAD_410", "INVALID"):
            c["dead"] += 1
        elif av and av.startswith("UNCERTAIN"):
            c["uncertain"] += 1
        if sc == "SINTECH_OWNED":
            c["safe"] += 1
        elif sc == "COMPETITOR_SOURCE":
            c["competitor"] += 1
        elif sc == "NEWS_MEDIA_SOURCE":
            c["news"] += 1
        elif sc == "UNKNOWN_EXTERNAL":
            c["unknown"] += 1
        elif sc == "HARAVAN_OTHER_STORE":
            c["other_store"] += 1
        elif sc == "OFFICIAL_MANUFACTURER":
            c["official"] += 1
        if act not in ("KEEP", "REMOVE_DEAD_IMAGE", "REMOVE_FROM_DRAFT"):
            c["pending"] += 1
    return c


def _remediation_group(counts, gate):
    if gate == "ALLOW":
        return "SAFE_NOW"
    blocked_non_dead = counts["competitor"] + counts["news"] + counts["unknown"] + counts["other_store"]
    if blocked_non_dead == 0 and counts["dead"] > 0:
        return "DEAD_ONLY_CLEANUP"
    if counts["unknown"] >= 3 or (counts["total"] and counts["unknown"] > counts["total"] * 0.5):
        return "UNKNOWN_HEAVY"
    if blocked_non_dead <= 2 and counts["unknown"] <= 2:
        return "LOW_COMPLEXITY_REVIEW"
    if counts["competitor"] > 0 or counts["news"] > 0:
        return "REPLACEMENT_NEEDED"
    return "MANUAL_COMPLEX"


def _quick_win_score(clicks, sessions, group, counts, has_draft):
    s = 10 * math.log10(1 + (clicks or 0)) + 6 * math.log10(1 + (sessions or 0))
    s += {"SAFE_NOW": 100, "DEAD_ONLY_CLEANUP": 70}.get(group, 0)
    blocked_non_dead = counts["competitor"] + counts["news"] + counts["unknown"] + counts["other_store"]
    if blocked_non_dead <= 1: s += 40
    elif blocked_non_dead <= 2: s += 20
    if has_draft: s += 20
    s -= 8 * counts["unknown"] + 6 * counts["competitor"] + 5 * counts["news"] + 6 * counts["other_store"] + 3 * counts["uncertain"]
    if group == "MANUAL_COMPLEX": s -= 40
    return round(s, 1)


_NEXT_ACTION = {
    "SAFE_NOW": "Sẵn sàng review + apply", "DEAD_ONLY_CLEANUP": "Gỡ ảnh chết local → ALLOW",
    "LOW_COMPLEXITY_REVIEW": "Review ≤2 ảnh blocked", "REPLACEMENT_NEEDED": "Thay ảnh đối thủ/news",
    "UNKNOWN_HEAVY": "Soi nhiều ảnh unknown", "MANUAL_COMPLEX": "Xử lý thủ công phức tạp",
}


def article_remediation_summary(candidate_id):
    c = _br.get_candidate(candidate_id)
    if not c:
        return None
    counts = _article_image_counts(candidate_id)
    gate = article_gate(candidate_id)
    group = _remediation_group(counts, gate)
    d = _br.latest_draft_for_candidate(candidate_id)
    score = _quick_win_score(c.get("gsc_clicks_28d"), c.get("ga4_organic_sessions_28d"), group, counts, bool(d))
    return {
        "candidate_id": candidate_id, "article_id": c.get("article_id"), "title": c.get("title"),
        "article_url": c.get("article_url"), "latest_draft_id": d["id"] if d else None,
        "gsc_clicks_28d": c.get("gsc_clicks_28d"), "ga4_organic_sessions_28d": c.get("ga4_organic_sessions_28d"),
        "total_images": counts["total"], "safe_images": counts["safe"], "dead_images": counts["dead"],
        "uncertain_images": counts["uncertain"], "competitor_images": counts["competitor"],
        "news_images": counts["news"], "unknown_images": counts["unknown"],
        "other_store_images": counts["other_store"], "official_images": counts["official"],
        "pending_review_images": counts["pending"], "gate_status": gate,
        "remediation_group": group, "quick_win_score": score,
        "recommended_next_action": _NEXT_ACTION.get(group, "review"),
    }


def list_article_remediation():
    conn = db.get_conn()
    cids = [r[0] for r in conn.execute("SELECT DISTINCT candidate_id FROM blog_rewrite_image_items").fetchall()]
    conn.close()
    out = [article_remediation_summary(c) for c in cids]
    out = [x for x in out if x]
    out.sort(key=lambda x: -x["quick_win_score"])
    return out


def remediation_group_counts():
    from collections import Counter
    arts = list_article_remediation()
    return dict(Counter(a["remediation_group"] for a in arts)), len(arts)


def bulk_remove_dead_and_clone():
    """P5F: mark all dead → REMOVE + clone draft sạch cho bài bị ảnh chết. Local only."""
    bd = bulk_dead_local("REMOVE DEAD IMAGES FROM LOCAL DRAFTS")
    conn = db.get_conn()
    affected = [r[0] for r in conn.execute(
        "SELECT DISTINCT candidate_id FROM blog_rewrite_image_items WHERE selected_action='REMOVE_DEAD_IMAGE' "
        "AND availability_status IN ('DEAD_404','DEAD_410','INVALID')").fetchall()]
    conn.close()
    new_drafts = []; newly_safe = 0; still_blocked = 0
    for cid in affected:
        d = _br.latest_draft_for_candidate(cid)
        if not d:
            continue
        res = build_remediated_draft_local(cid, d["id"])
        if res.get("ok"):
            new_drafts.append(res["draft_id"])
            _br.record_event("dead_image_removed_local", candidate_id=cid, detail={"removed": res["removed"]})
            if res["gate_after"] == "ALLOW":
                newly_safe += 1
            else:
                still_blocked += 1
    return {"ok": True, "dead_marked": bd.get("marked", 0), "candidates_affected": len(affected),
            "new_draft_versions": len(new_drafts), "newly_safe": newly_safe, "still_blocked": still_blocked}


def top20():
    arts = list_article_remediation()
    order = {"SAFE_NOW": 0, "DEAD_ONLY_CLEANUP": 1, "LOW_COMPLEXITY_REVIEW": 2,
             "REPLACEMENT_NEEDED": 3, "UNKNOWN_HEAVY": 4, "MANUAL_COMPLEX": 5}
    arts.sort(key=lambda x: (order.get(x["remediation_group"], 9), -x["quick_win_score"]))
    top = arts[:20]
    import csv as _csv
    from pathlib import Path
    out = Path(__file__).parent / "docs" / "blog_rewrite_quick_win_top20.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = _csv.writer(f)
        w.writerow(["rank", "candidate_id", "article_id", "title", "article_url", "latest_draft_id",
                    "gsc_clicks_28d", "ga4_organic_sessions_28d", "total_images", "dead_images",
                    "competitor_images", "news_images", "unknown_images", "other_store_images",
                    "uncertain_images", "gate_status", "remediation_group", "quick_win_score", "recommended_next_action"])
        for i, a in enumerate(top, 1):
            w.writerow([i, a["candidate_id"], a["article_id"], (a["title"] or "")[:60], a["article_url"],
                        a["latest_draft_id"], a["gsc_clicks_28d"], a["ga4_organic_sessions_28d"], a["total_images"],
                        a["dead_images"], a["competitor_images"], a["news_images"], a["unknown_images"],
                        a["other_store_images"], a["uncertain_images"], a["gate_status"], a["remediation_group"],
                        a["quick_win_score"], a["recommended_next_action"]])
    return top


def canary_prep():
    """P5G-1: phân tích pool canary. SAFE_NOW (gate ALLOW) + có draft + chưa apply + non-reverse."""
    import blog_rewrite_apply as ap
    import re as _re
    safe_now = [a for a in list_article_remediation() if a["remediation_group"] == "SAFE_NOW"]
    conn = db.get_conn()
    drafted = [r[0] for r in conn.execute("SELECT DISTINCT candidate_id FROM blog_rewrite_drafts").fetchall()]
    conn.close()
    OVERLAP_MAX = 0.12
    ready, review = [], []
    # quét MỌI bài có draft + gate ALLOW + chưa apply (không chỉ group SAFE_NOW)
    for cid in drafted:
        d = _br.latest_draft_for_candidate(cid)
        c = _br.get_candidate(cid)
        if not d or d.get("applied_at") or (c or {}).get("audit_reverse_copy"):
            continue
        if article_gate(cid) != "ALLOW":
            continue
        body = d["draft_body_html"] or ""
        try:
            q = json.loads(d["quality_json"] or "{}")
        except Exception:
            q = {}
        ps = ap.apply_preview(d["id"])
        ov = q.get("normalized_5gram_overlap")
        vis = _re.sub(r"<[^>]+>", " ", body).lower()
        brand_ok = not any(b in vis for b in ("gearvn", "fptshop", "cellphones", "memoryzone", "tgdd", "hacom"))
        html_ok = not any(x in body.lower() for x in ("<script", "javascript:", "<iframe"))
        rec = {
            "candidate_id": cid, "article_id": c.get("article_id"), "title": c.get("title"),
            "article_url": c.get("article_url"), "latest_draft_id": d["id"], "version": d["version"],
            "gsc_clicks_28d": c.get("gsc_clicks_28d"), "ga4_sessions_28d": c.get("ga4_organic_sessions_28d"),
            "image_count": len(_re.findall(r"<img", body, _re.I)),
            "internal_link_count": len(_re.findall(r'href="(/|[^"]*sintech\.vn)', body)),
            "table_count": body.count("<table"), "gate_status": "ALLOW",
            "conflict": ps["conflict_status"], "approval_status": d["approval_status"],
            "approved_local": d["approval_status"] == "approved_local",
            "overlap": ov, "verify_preview": ps["conflict_status"],
            "html_safety": "PASS" if html_ok else "FAIL", "brand_cleanup": "PASS" if brand_ok else "FAIL",
            "facts_manual_verify": "needs_check",  # bài tech: spec/driver/date cần verify tay
            "longest_phrase": q.get("longest_common_phrase"),
        }
        if brand_ok and html_ok and ps["conflict_status"] == "SAFE_TO_APPLY" and (ov or 0) <= OVERLAP_MAX:
            ready.append(rec)
        else:
            rec["rollout_status"] = "REVIEW_REQUIRED"
            review.append(rec)
    ready.sort(key=lambda x: (0 if x["approved_local"] else 1, x["image_count"], x["table_count"],
                              (x["gsc_clicks_28d"] or 0), (x["overlap"] or 0)))
    for r in ready:
        r["rollout_status"] = "READY"
    return {
        "safe_now_total": len(safe_now),
        "safe_now_no_draft": [a["candidate_id"] for a in safe_now if a["candidate_id"] not in drafted],
        "canary_ready": ready, "review_required": review,
        "selected_canary": [r["candidate_id"] for r in ready[:2]],
        "note": "canary-ready = draft + gate ALLOW + conflict SAFE + overlap≤12% + brand/HTML sạch. "
                "Facts tech cần vợ verify tay trước apply. Flags live VẪN KHÓA.",
    }


def export_workload():
    import csv as _csv
    from pathlib import Path
    conn = db.get_conn()
    rows = conn.execute("""SELECT i.*, c.title, c.handle FROM blog_rewrite_image_items i
        LEFT JOIN blog_rewrite_candidates c ON c.id=i.candidate_id ORDER BY i.candidate_id, i.image_index""").fetchall()
    conn.close()
    out = Path(__file__).parent / "docs" / "blog_rewrite_image_remediation_workload.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = _csv.writer(f)
        w.writerow(["candidate_id", "article_id", "article_title", "article_url", "draft_id", "image_index",
                    "original_src", "hostname", "store_id", "alt", "source_class", "availability_status",
                    "rights_status", "recommended_action", "selected_action", "manual_note", "review_status", "apply_gate"])
        gcache = {}
        for r in rows:
            cid = r["candidate_id"]
            if cid not in gcache:
                gcache[cid] = article_gate(cid)
            w.writerow([cid, r["article_id"], (r["title"] or "")[:60],
                        f"https://sintech.vn/blogs/news/{r['handle']}", r["draft_id"], r["image_index"],
                        r["original_src"], r["hostname"], r["store_id"], (r["alt"] or "")[:40], r["source_class"],
                        r["availability_status"], r["rights_status"], r["recommended_action"], r["selected_action"],
                        r["manual_note"] or "", r["review_status"], gcache[cid]])
    return {"ok": True, "rows": len(rows), "csv": str(out)}
