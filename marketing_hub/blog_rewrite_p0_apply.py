# -*- coding: utf-8 -*-
"""P9.1 — BLOG P0 QUICKWIN APPLY (SAFE ONLY).

Chỉ apply LIVE body_html cho các bài P0 nhóm AUTO_SAFE đã preview-ready + pass gate,
nguồn là draft `p0_preview` (marker p0_executor). TÁI DÙNG engine đã kiểm chứng (P7.2):
ap._put_article / reconcile_post_put / backup_preview / _get_live / _hash_body.

HARD RULES: PUT chỉ body_html · 1 PUT/bài · KHÔNG retry PUT · KHÔNG đổi
title/handle/summary/tags/author/published/featured · KHÔNG upload/rehost/theme/scheduler/commit.
Gate apply = confirm phrase "APPLY P0 QUICKWINS BODY ONLY" + eligible ĐÚNG 5 bài.
KHÔNG đụng flag/luồng blog-rewrite thường (latest_draft_for_candidate đã bỏ qua p0_preview).
500-but-write → reconcile read-only, KHÔNG re-PUT. CB OPEN → PAUSE.
"""
import csv, json, time
from pathlib import Path

import db
import blog_rewrite as br
import blog_rewrite_apply as ap
import blog_rewrite_gen as gen
import blog_rewrite_images as imgs
import blog_rewrite_p0_executor as p9

CONFIRM_PHRASE = "APPLY P0 QUICKWINS BODY ONLY"
ROLLBACK_PHRASE = "ROLLBACK P0 QUICKWINS BODY ONLY"
EXPECTED_ELIGIBLE = 5

STATE_DIR = Path(__file__).parent / "state"
CHECKPOINT = STATE_DIR / "blog_p0_quickwin_apply_checkpoint.json"
BACKUP_ROOT = STATE_DIR / "backups" / "p0_quickwin_apply"
DOCS = Path(__file__).parent.parent / "docs"

O_COMPLETE_MD = DOCS / "BLOG_PERFORMANCE_P0_APPLY_COMPLETE.md"
O_ITEMS_CSV = DOCS / "blog_performance_p0_apply_items.csv"
O_SKIPPED_CSV = DOCS / "blog_performance_p0_apply_skipped.csv"
O_BACKUPS_CSV = DOCS / "blog_performance_p0_apply_backups.csv"

TEXT_PRESERVE_MIN = p9.TEXT_PRESERVE_MIN


# ═══════════════════════ eligibility (scope cực hẹp) ═══════════════════════
def _draft_is_p0(d):
    """Marker rõ: draft_type=p0_preview + source=P9 executor."""
    if not d or d.get("approval_status") != "p0_preview":
        return False, {}
    try:
        q = json.loads(d.get("quality_json") or "{}")
    except Exception:
        return False, {}
    return bool(q.get("p0_executor")), q


def eligible():
    """Trả (list[(item,draft)], excluded dict). Gate cứng theo spec §1."""
    items = p9.run_preview(force=False)
    elig, excluded = [], {"blocked_image": [], "theme_only": [], "manual_review": [], "other": []}
    for i in items:
        rank = i["p0_rank"]
        if i["group"] == p9.GROUP_THEME:
            excluded["theme_only"].append(rank); continue
        if i["group"] == p9.GROUP_MANUAL:
            excluded["manual_review"].append(rank); continue
        if i["group"] != p9.GROUP_AUTO:
            excluded["other"].append(rank); continue
        if i["status"] == "blocked_image":
            excluded["blocked_image"].append(rank); continue
        did = i.get("local_draft_id")
        d = br.get_draft(did) if did else None
        is_p0, q = _draft_is_p0(d)
        g = q.get("gate", {})
        ok = (is_p0 and i["status"] == "preview_ready"
              and g.get("html_safety") == "PASS" and g.get("semantic_preserved")
              and g.get("broken_inline_after") == 0 and not g.get("thin_content")
              and g.get("blocked_image") == 0 and not g.get("competitor_href")
              and g.get("status") == "preview_ready")
        if ok:
            elig.append((i, d))
        else:
            excluded["other"].append(rank)
    return elig, excluded


# ═══════════════════════ preflight (trước PUT từng bài) ═══════════════════════
def preflight(item, draft):
    cid = draft["candidate_id"]
    c = br.get_candidate(cid) or {}
    blog_id, article_id = c.get("blog_id"), c.get("article_id")
    body = draft.get("draft_body_html") or ""
    orig = draft.get("original_body_html") or ""

    res = {"p0_rank": item["p0_rank"], "article_id": article_id, "blog_id": blog_id,
           "draft_id": draft["id"], "title": item["title"], "url": item["url"],
           "decision": "PROCEED", "reason": "", "live_hash_before": "", "live_art": None,
           "checks": {}}

    # body checks (local, trước GET)
    if not body.strip():
        res.update(decision="SKIP", reason="preview body rỗng"); return res
    low = body.lower()
    if "<script" in low or "<iframe" in low:
        res.update(decision="SKIP", reason="có script/iframe nguy hiểm"); return res
    audit, gate = imgs.audit_body_images(body, check_availability=True)
    blocked = [a for a in audit if str(a.get("apply_gate_status", "")).startswith("BLOCK")]
    if blocked:
        res.update(decision="SKIP", reason="image gate BLOCK (%d ảnh)" % len(blocked)); return res
    # semantic preserved vs original (text hiển thị)
    qm = gen.quality_metrics(p9._strip_noncontent(orig), body)
    wo, wd = qm["word_count_original"], qm["word_count_draft"]
    preserve = round(wd / wo, 4) if wo else 0.0
    res["checks"]["semantic_preserve"] = preserve
    if preserve < TEXT_PRESERVE_MIN:
        res.update(decision="SKIP", reason="semantic preserve %.3f < %.2f" % (preserve, TEXT_PRESERVE_MIN)); return res
    res["checks"]["tables_responsive"] = body.count("overflow-x")

    # fresh GET live + conflict
    try:
        code, art = ap._get_live(blog_id, article_id)
    except Exception as e:
        res.update(decision="SKIP", reason="GET live lỗi: %s" % str(e)[:80]); return res
    if code != 200 or not art:
        res.update(decision="SKIP", reason="GET live HTTP %s" % code); return res
    live_hash = ap._hash_body(art.get("body_html") or "")
    p0_hash = ap._hash_body(body)
    orig_hash = ap._hash_body(orig)
    res["live_hash_before"] = live_hash
    res["live_art"] = art
    if live_hash == p0_hash:
        res.update(decision="ALREADY_APPLIED", reason="live == p0_preview (idempotent)"); return res
    if live_hash != orig_hash:
        res.update(decision="CONFLICT_SKIP", reason="live đã đổi từ lúc tạo p0_preview"); return res
    return res  # PROCEED


# ═══════════════════════ backup ═══════════════════════
def _save_backup_file(ts, article_id, blog_id, live_art):
    d = BACKUP_ROOT / ts
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "article_id": article_id, "blog_id": blog_id, "saved_at": ts,
        "live_body_html": live_art.get("body_html"),
        "live_title": live_art.get("title"), "live_handle": live_art.get("handle"),
        "note": "P9.1 backup body_html GỐC trước apply — dùng cho rollback manual.",
    }
    p = d / ("%s.json" % article_id)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)


# ═══════════════════════ apply 1 bài ═══════════════════════
def apply_one(item, draft, ts):
    pf = preflight(item, draft)
    rec = {"p0_rank": pf["p0_rank"], "article_id": pf["article_id"], "title": pf["title"],
           "url": pf["url"], "draft_id": pf["draft_id"], "decision": pf["decision"],
           "reason": pf["reason"], "put": 0, "state": "", "verify": "", "http": None,
           "verify_source": None, "backup_path": "", "checks": pf.get("checks", {})}

    if pf["decision"] not in ("PROCEED", "ALREADY_APPLIED"):
        rec["state"] = pf["decision"]
        return rec

    blog_id, article_id = pf["blog_id"], pf["article_id"]
    body = draft.get("draft_body_html") or ""
    draft_hash = ap._hash_body(body)

    # backup TRƯỚC PUT (file riêng + lưu trong draft)
    rec["backup_path"] = _save_backup_file(ts, article_id, blog_id, pf["live_art"])
    try:
        ap.backup_preview(draft["id"])
    except Exception:
        pass
    br.record_event("p0_apply_backup_saved", candidate_id=draft["candidate_id"], draft_id=draft["id"],
                    detail={"backup": rec["backup_path"]})

    if pf["decision"] == "ALREADY_APPLIED":
        rec["state"] = "APPLIED"
        rec["verify"] = "VERIFIED"
        rec["put"] = 0
        return rec

    # PUT body-only ĐÚNG 1 LẦN
    nonce = draft_hash[:12]
    put_fields = {"id": article_id, "body_html": body}  # body-only — KHÔNG field khác
    br.record_event("p0_apply_put_sent", candidate_id=draft["candidate_id"], draft_id=draft["id"],
                    detail={"nonce": nonce, "state": "PUT_SENT"})
    put_exc = None
    try:
        status, _resp = ap._put_article(blog_id, article_id, put_fields)
    except Exception as e:
        status, put_exc = None, str(e)[:160]
    rec["put"] = 1
    rec["http"] = status
    # 500-but-write: KHÔNG re-PUT, reconcile read-only
    uncertain = (put_exc is not None) or (status not in (200, 201))
    reconc = ap.reconcile_post_put(draft["id"], draft_hash, nonce, pf["live_hash_before"],
                                   http=status, uncertain=uncertain)
    rec["state"] = reconc["state"]
    rec["verify"] = reconc["verify"]
    rec["verify_source"] = reconc.get("verify_source")
    return rec


# ═══════════════════════ run apply (gate confirm + eligible==5) ═══════════════════════
def _cb_open():
    try:
        import blog_rewrite_autopilot as auto
        return bool(auto.cb_state().get("open"))
    except Exception:
        return False


def run_apply(confirm_phrase="", dry_run=False):
    if confirm_phrase.strip() != CONFIRM_PHRASE:
        return {"ok": False, "error": "Confirm phrase sai. Cần đúng: %s" % CONFIRM_PHRASE,
                "put_count": 0, "applied": 0}
    elig, excluded = eligible()
    ranks = [i["p0_rank"] for i, _ in elig]
    if len(elig) != EXPECTED_ELIGIBLE:
        return {"ok": False, "error": "eligible = %d ≠ %d → DỪNG, KHÔNG PUT" % (len(elig), EXPECTED_ELIGIBLE),
                "eligible_ranks": ranks, "excluded": excluded, "put_count": 0, "applied": 0}
    if _cb_open():
        return {"ok": False, "error": "Circuit breaker đang OPEN → DỪNG, KHÔNG PUT",
                "eligible_ranks": ranks, "put_count": 0, "applied": 0}

    ts = time.strftime("%Y%m%d-%H%M%S")
    records, put_count = [], 0
    cp = {"ts": ts, "phase": "P9.1", "dry_run": dry_run, "eligible_ranks": ranks,
          "excluded": excluded, "items": [], "cb_open": False}
    halted = False
    for item, draft in elig:
        if dry_run:
            pf = preflight(item, draft)
            records.append({"p0_rank": pf["p0_rank"], "article_id": pf["article_id"],
                            "title": pf["title"], "decision": pf["decision"], "reason": pf["reason"],
                            "put": 0, "state": "DRY_RUN", "verify": "", "backup_path": ""})
            continue
        rec = apply_one(item, draft, ts)
        records.append(rec)
        put_count += rec["put"]
        cp["items"] = records
        _save_checkpoint(cp)
        if rec["state"] == "UNCERTAIN_POST_PUT":
            cp["cb_open"] = True
            _save_checkpoint(cp)
            halted = True
            break  # PAUSE — không apply tiếp

    applied = sum(1 for r in records if r["state"] in ("APPLIED", "LIVE_VERIFIED"))
    reconciled = sum(1 for r in records if r["state"] == "APPLIED_RECONCILED")
    skipped = sum(1 for r in records if r["state"] in ("SKIP", "CONFLICT_SKIP", "DRY_RUN"))
    conflict = sum(1 for r in records if r["state"] == "CONFLICT_SKIP")
    failed = sum(1 for r in records if r["state"] in ("NOT_APPLIED_RETRYABLE", "UNCERTAIN_POST_PUT"))
    verify_pass = sum(1 for r in records if r["verify"] in ("VERIFIED", "VERIFIED_SEMANTIC", "VERIFIED_RAW"))
    cp.update(applied=applied, applied_reconciled=reconciled, skipped=skipped, conflict=conflict,
              failed=failed, put_count=put_count, verify_pass=verify_pass, halted=halted)
    _save_checkpoint(cp)
    return {"ok": True, "phase": "P9.1", "dry_run": dry_run, "ts": ts,
            "eligible": len(elig), "applied": applied, "applied_reconciled": reconciled,
            "skipped": skipped, "conflict": conflict, "failed": failed, "put_count": put_count,
            "verify_pass": verify_pass, "halted": halted, "cb_open": _cb_open(),
            "excluded": excluded, "records": records}


def _save_checkpoint(cp):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(cp, ensure_ascii=False, indent=2), encoding="utf-8")


def load_checkpoint():
    try:
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    except Exception:
        return None


# ═══════════════════════ rollback manual (body-only từ backup) ═══════════════════════
def rollback(article_id, confirm_phrase=""):
    if confirm_phrase.strip() != ROLLBACK_PHRASE:
        return {"ok": False, "error": "Confirm phrase rollback sai. Cần: %s" % ROLLBACK_PHRASE, "put": 0}
    # tìm backup mới nhất cho article_id
    cands = sorted(BACKUP_ROOT.glob("*/%s.json" % article_id), reverse=True)
    if not cands:
        return {"ok": False, "error": "Không có backup cho article %s" % article_id, "put": 0}
    bk = json.loads(cands[0].read_text(encoding="utf-8"))
    blog_id = bk["blog_id"]
    body = bk.get("live_body_html")
    if not body:
        return {"ok": False, "error": "Backup không có body_html", "put": 0}
    try:
        status, _ = ap._put_article(blog_id, int(article_id), {"id": int(article_id), "body_html": body})
    except Exception as e:
        return {"ok": False, "error": "PUT rollback lỗi: %s" % str(e)[:120], "put": 1}
    br.record_event("p0_apply_rollback", detail={"article_id": article_id, "http": status, "backup": str(cands[0])})
    return {"ok": status in (200, 201), "http": status, "put": 1, "restored_from": str(cands[0])}


# ═══════════════════════ status (UI) ═══════════════════════
def status():
    elig, excluded = eligible()
    cp = load_checkpoint() or {}
    by_rank = {it["p0_rank"]: it for it in (cp.get("items") or [])}
    rows = []
    for item, draft in elig:
        r = by_rank.get(item["p0_rank"], {})
        rows.append({
            "p0_rank": item["p0_rank"], "article_id": (br.get_candidate(draft["candidate_id"]) or {}).get("article_id"),
            "title": item["title"], "draft_id": draft["id"], "preview_status": item["status"],
            "apply_state": r.get("state", "pending"), "verify": r.get("verify", ""),
            "backup": bool(r.get("backup_path")), "rollback_available": bool(r.get("backup_path")),
        })
    kpi = {
        "eligible": len(elig),
        "applied": cp.get("applied", 0),
        "applied_reconciled": cp.get("applied_reconciled", 0),
        "skipped": cp.get("skipped", 0),
        "conflict": cp.get("conflict", 0),
        "failed": cp.get("failed", 0),
        "put_count": cp.get("put_count", 0),
        "verify_pass": cp.get("verify_pass", 0),
    }
    return {"kpi": kpi, "rows": rows, "excluded": excluded, "confirm_phrase": CONFIRM_PHRASE,
            "cb_open": _cb_open(), "ts": cp.get("ts")}


# ═══════════════════════ exports ═══════════════════════
def _w(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f); wr.writerow(header); wr.writerows(rows)
    return len(rows)


def export_all():
    cp = load_checkpoint() or {}
    items = cp.get("items") or []
    counts = {}
    applied_rows, skipped_rows, backup_rows = [], [], []
    for r in items:
        base = [r.get("p0_rank"), r.get("article_id"), r.get("title"), r.get("url", "")]
        st = r.get("state", "")
        if st in ("APPLIED", "LIVE_VERIFIED", "APPLIED_RECONCILED"):
            applied_rows.append(base + [r.get("draft_id"), st, r.get("verify"), r.get("http"),
                                        r.get("verify_source"), r.get("put"), r.get("backup_path")])
        else:
            skipped_rows.append(base + [st, r.get("decision"), r.get("reason"), r.get("put")])
        if r.get("backup_path"):
            backup_rows.append([r.get("article_id"), r.get("title"), r.get("backup_path")])

    counts["items"] = _w(O_ITEMS_CSV,
                         ["p0_rank", "article_id", "title", "url", "draft_id", "apply_state",
                          "verify", "http", "verify_source", "put", "backup_path"], applied_rows)
    counts["skipped"] = _w(O_SKIPPED_CSV,
                           ["p0_rank", "article_id", "title", "url", "state", "decision", "reason", "put"], skipped_rows)
    counts["backups"] = _w(O_BACKUPS_CSV, ["article_id", "title", "backup_path"], backup_rows)
    _write_complete_md(cp)
    counts["complete_md"] = 1
    return counts


def _write_complete_md(cp):
    items = cp.get("items") or []
    exc = cp.get("excluded", {})
    L = ["# BLOG PERFORMANCE — P0 QUICKWIN APPLY COMPLETE\n",
         "> P9.1 — apply LIVE body_html cho bài P0 AUTO_SAFE preview-ready. "
         "Body-only · 1 PUT/bài · backup + verify + reconcile · rollback manual.\n",
         "## Coverage",
         f"- eligible **{len(cp.get('eligible_ranks', []))}** · applied **{cp.get('applied', 0)}** "
         f"· applied_reconciled **{cp.get('applied_reconciled', 0)}** · skipped **{cp.get('skipped', 0)}** "
         f"· conflict **{cp.get('conflict', 0)}** · failed **{cp.get('failed', 0)}**",
         f"- PUT count **{cp.get('put_count', 0)}** · verify pass **{cp.get('verify_pass', 0)}** "
         f"· CB {'OPEN ⛔' if cp.get('cb_open') else 'closed'}\n",
         "## Bài đã xử lý"]
    L.append("| P0# | article | apply_state | verify | http | PUT | backup |")
    L.append("|---|---|---|---|---|---|---|")
    for r in items:
        L.append(f"| {r.get('p0_rank')} | {r.get('article_id')} | {r.get('state')} | {r.get('verify')} "
                 f"| {r.get('http')} | {r.get('put')} | {'✓' if r.get('backup_path') else '—'} |")
    L.append("\n## Excluded")
    L.append(f"- blocked image: {exc.get('blocked_image', [])} (vd #7 GTA5 — ảnh đối thủ)")
    L.append(f"- theme-only: {exc.get('theme_only', [])}")
    L.append(f"- manual-review: {exc.get('manual_review', [])}\n")
    L.append("## Lưu ý kỹ thuật (verify live)")
    L.append("- ✅ **Sống trên live:** clean HTML legacy + table responsive (`overflow-x` wrapper) — win CLS chính cho bài nhiều bảng.")
    L.append("- ⚠️ **Haravan STRIP** attr `loading=\"lazy\"` + `fetchpriority` của `<img>` khi PUT (whitelist body) → phần lazy-load/LCP-hint KHÔNG sống ở mức bài. Đây đúng là việc của THEME (BLOG_TEMPLATE_CODE_HANDOFF #4 lazy mặc định, #3 fetchpriority hero, #5 width/height). Đã verify draft local có đủ lazy nhưng live bị gỡ.")
    L.append("- verify VERIFIED do canonical signature so text/ảnh/cấu trúc (bỏ qua attr) → apply đúng nội dung.\n")
    L.append("## Safety")
    L.append("- body_html only · no title/handle/summary/tags/author/featured change")
    L.append("- upload = 0 · rehost = 0 · theme edits = 0 · no commit/push/deploy")
    L.append(f"- CB: {'OPEN' if cp.get('cb_open') else 'closed'}")
    L.append(f"\n## Backups\n- path: `state/backups/p0_quickwin_apply/{cp.get('ts', '')}/`")
    L.append("\n## Exports\n- BLOG_PERFORMANCE_P0_APPLY_COMPLETE.md\n- blog_performance_p0_apply_items.csv"
             "\n- blog_performance_p0_apply_skipped.csv\n- blog_performance_p0_apply_backups.csv")
    O_COMPLETE_MD.write_text("\n".join(L), encoding="utf-8")
