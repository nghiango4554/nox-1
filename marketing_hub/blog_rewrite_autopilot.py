# -*- coding: utf-8 -*-
"""Blog Rewrite — P6 AUTOPILOT.

Orchestrate full pipeline reuse engine sẵn có. Mặc định OFF + scheduler OFF.
Tự apply CHỈ bài evergreen đạt chuẩn chặt; tự HOLD bài rủi ro; tự BLOCK ảnh lỗi;
circuit breaker dừng khi lỗi. KHÔNG bỏ qua gate, KHÔNG apply song song.

Write transport (PUT) monkeypatch-able qua blog_rewrite_apply (_put_article/_get_live).
Generate monkeypatch-able qua _generate_draft (QA khỏi gọi AI thật).
"""
import json, re, math
from pathlib import Path

import db
import blog_rewrite as br
import blog_rewrite_gen as gen
import blog_rewrite_remediate as rem
import blog_rewrite_images as imgs
import blog_rewrite_apply as ap
import blog_rewrite_verify as verify

_DIR = Path(__file__).parent
CONFIG_PATH = _DIR / "state" / "blog_rewrite_autopilot.json"
CB_PATH = _DIR / "state" / "blog_rewrite_autopilot_cb.json"

DEFAULT_CONFIG = {
    "enabled": False, "mode": "PREP_ONLY",
    "schedule": {"enabled": False, "hour": 2, "minute": 0, "timezone": "Asia/Ho_Chi_Minh"},
    "limits": {"max_generate_per_run": 5, "max_apply_per_run": 2, "max_apply_per_day": 2,
               "cooldown_minutes_between_apply": 15, "max_regenerate_per_candidate": 1},
    "quality": {"max_overlap_percent": 12, "min_quality_score": 80, "require_gate_allow": True,
                "require_safe_conflict": True, "require_html_safety": True,
                "require_brand_cleanup": True, "require_fact_safety": True},
    "apply": {"body_html_only": True, "auto_backup": True, "semantic_verify": True,
              "auto_reconcile_post_put": True, "auto_rollback": False, "one_shot_flag": True},
    "circuit_breaker": {"enabled": True, "stop_on_verify_mismatch": True, "stop_on_uncertain_post_put": True,
                        "stop_on_backup_fail": True, "max_consecutive_generate_fail": 2,
                        "max_consecutive_fact_fail": 2},
}

ENABLE_APPLY_PHRASE = "ENABLE SAFE BLOG AUTOPILOT"
ENABLE_SCHEDULE_PHRASE = "ENABLE BLOG AUTOPILOT SCHEDULE"

# heuristic keyword sets
_NEWS_KW = ("sắp ra mắt", "sắp ngừng", "ngừng sản xuất", "ra mắt", "rò rỉ", "khai tử", "comeback",
            "vừa công bố", "mới ra", "phiên bản mới nhất", "cập nhật mới")
_TIME_KW = ("driver", "tồn kho", "khan hàng", "giá hiện tại", "deadline", "hết hỗ trợ", "end of support")
_VISUAL_KW = ("như hình", "hình dưới", "ảnh bên dưới", "hình bên dưới", "xem hình", "bước 1", "bước 2",
              "bước 3", "theo hình", "screenshot", "ảnh minh họa bên dưới")


# ═══════════════════ config ═══════════════════
def load_config():
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        cfg = {}
    return _merge(DEFAULT_CONFIG, cfg)


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(base[k], v) if isinstance(base.get(k), dict) and isinstance(v, dict) else v
    return out


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return cfg


def patch_config(patch):
    cfg = _merge(load_config(), patch or {})
    return save_config(cfg)


# ═══════════════════ DB (additive, idempotent) ═══════════════════
def migrate():
    conn = db.get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS blog_rewrite_autopilot_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT, status TEXT,
      started_at TEXT, finished_at TEXT, selected_count INTEGER DEFAULT 0,
      generated_count INTEGER DEFAULT 0, applied_count INTEGER DEFAULT 0,
      hold_count INTEGER DEFAULT 0, blocked_count INTEGER DEFAULT 0, failed_count INTEGER DEFAULT 0,
      circuit_breaker_status TEXT, summary_json TEXT,
      created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')));
    CREATE TABLE IF NOT EXISTS blog_rewrite_autopilot_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, candidate_id INTEGER, article_id INTEGER,
      draft_id INTEGER, stage TEXT, status TEXT, decision TEXT, decision_reason TEXT,
      quality_json TEXT, fact_json TEXT, image_gate_json TEXT, conflict_json TEXT,
      apply_json TEXT, verify_json TEXT,
      created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')));
    CREATE TABLE IF NOT EXISTS blog_rewrite_autopilot_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, item_id INTEGER, candidate_id INTEGER,
      event_type TEXT, detail_json TEXT, created_at TEXT DEFAULT (datetime('now')));
    CREATE INDEX IF NOT EXISTS idx_ap_items_run ON blog_rewrite_autopilot_items(run_id);
    CREATE INDEX IF NOT EXISTS idx_ap_items_cand ON blog_rewrite_autopilot_items(candidate_id);
    CREATE INDEX IF NOT EXISTS idx_ap_events_run ON blog_rewrite_autopilot_events(run_id);
    """)
    conn.commit(); conn.close()


def _ev(run_id, etype, candidate_id=None, item_id=None, detail=None):
    conn = db.get_conn()
    conn.execute("INSERT INTO blog_rewrite_autopilot_events (run_id,item_id,candidate_id,event_type,detail_json) VALUES (?,?,?,?,?)",
                 (run_id, item_id, candidate_id, etype, json.dumps(detail or {}, ensure_ascii=False)))
    conn.commit(); conn.close()


# ═══════════════════ circuit breaker ═══════════════════
def cb_state():
    try:
        return json.loads(CB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"open": False, "reason": None, "consecutive_generate_fail": 0, "consecutive_fact_fail": 0}


def _cb_save(s):
    CB_PATH.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def cb_open(reason, run_id=None):
    s = cb_state(); s["open"] = True; s["reason"] = reason; _cb_save(s)
    # tự tắt enabled + đảm bảo live flag OFF
    patch_config({"enabled": False})
    ap._FLAGS_PATH.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": False,
        "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")
    if run_id:
        _ev(run_id, "circuit_breaker_opened", detail={"reason": reason})
    try:
        br.record_event("autopilot_circuit_breaker_opened", detail={"reason": reason})
    except Exception:
        pass
    return s


def cb_reset():
    _cb_save({"open": False, "reason": None, "consecutive_generate_fail": 0, "consecutive_fact_fail": 0})


# ═══════════════════ gates ═══════════════════
def _text(body):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body or "")).lower()


def fact_gate(body):
    """Heuristic fact taxonomy. Auto chỉ khi 0 time-sensitive + 0 unsupported + 0 manual."""
    t = _text(body)
    fps = re.findall(r"\d+\s*fps", t)
    # FPS chỉ là khái niệm (vd "144 fps" gần "hz") thì không tính unsupported — đếm số FPS gắn với tên card/game
    bench = re.findall(r"(rtx|rx|gtx|radeon|core\s*i\d)[^.]{0,40}\d+\s*fps", t)
    price = re.findall(r"\d[\d.,]*\s*(?:triệu|usd|đồng)\b", t)
    news = [k for k in _NEWS_KW if k in t]
    timev = [k for k in _TIME_KW if k in t]
    unsupported = len(bench) + (len(fps) if len(fps) > 3 else 0)
    time_sensitive = len(price) + len(news) + len(timev)
    return {"fps_total": len(fps), "benchmark_claims": len(bench), "price_claims": len(price),
            "news_keywords": news, "time_keywords": timev,
            "unsupported_remove": unsupported, "time_sensitive_review": time_sensitive,
            "manual_review": 0, "fact_safe": unsupported == 0 and time_sensitive == 0}


def visual_dependency(body):
    t = _text(body)
    hits = [k for k in _VISUAL_KW if k in t]
    return {"depends_on_images": bool(hits), "hits": hits}


def quality_gate(draft, cfg):
    body = draft.get("draft_body_html") or ""
    try:
        q = json.loads(draft.get("quality_json") or "{}")
    except Exception:
        q = {}
    ov = (q.get("normalized_5gram_overlap") or 0) * 100
    sc = q.get("scorecard") or {}
    t = _text(body)
    brand_ok = not any(b in t for b in ("gearvn", "fptshop", "cellphones", "memoryzone", "tgdd", "hacom"))
    html_ok = not any(x in (body or "").lower() for x in ("<script", "javascript:", "<iframe", "onerror="))
    comp_href = len(re.findall(r'href="https?://[^"]*(gearvn|fptshop|cellphones|tgdd|hacom)', body or "", re.I))
    score = q.get("quality_score")
    if score is None:  # suy score từ scorecard, fallback overlap+brand+html
        orig = sc.get("originality")
        if orig == "high":
            score = 88
        elif orig in ("medium", "low"):
            score = 70
        elif not brand_ok or not html_ok:
            score = 40
        elif ov < 5:
            score = 88
        elif ov < 10:
            score = 82
        elif ov <= 12:
            score = 78
        else:
            score = 60
    qc = cfg["quality"]
    reasons = []
    if qc["require_brand_cleanup"] and not brand_ok: reasons.append("brand")
    if qc["require_html_safety"] and not html_ok: reasons.append("html")
    if comp_href: reasons.append("competitor_href")
    if ov > qc["max_overlap_percent"]: reasons.append(f"overlap {ov:.1f}%")
    if score < qc["min_quality_score"]: reasons.append(f"score {score}")
    return {"ok": not reasons, "overlap_percent": round(ov, 1), "quality_score": score,
            "brand_cleanup": "PASS" if brand_ok else "FAIL", "html_safety": "PASS" if html_ok else "FAIL",
            "competitor_href": comp_href, "reasons": reasons}


# ═══════════════════ selection ═══════════════════
def _is_evergreen(title):
    t = (title or "").lower()
    news = ("nvidia", "microsoft", "windows 11", "rtx 50", "ra mắt", "ngừng sản xuất", "rò rỉ",
            "so sánh 3 vga", "cấu hình chơi", "giá rẻ")
    ever = ("là gì", "cách phân biệt", "phân biệt", "cách chọn", "hướng dẫn", "cách ", "tại sao",
            "có nên", "mẹo", "khái niệm")
    return any(k in t for k in ever) and not any(k in t for k in news)


def select_candidates(cfg, limit=None):
    """evergreen how-to · eligible · non-reverse · chưa apply · không HOLD."""
    try:
        hold_map = json.loads((_DIR / "state" / "_canary_hold.json").read_text(encoding="utf-8"))
    except Exception:
        hold_map = {}
    conn = db.get_conn()
    rows = conn.execute("SELECT id,article_id,blog_id,title,gsc_clicks_28d,ga4_organic_sessions_28d,status "
                        "FROM blog_rewrite_candidates WHERE rewrite_eligible=1 AND audit_reverse_copy=0 "
                        "AND status!='applied'").fetchall()
    conn.close()
    out = []
    for r in rows:
        if str(r["id"]) in hold_map:
            continue
        if not _is_evergreen(r["title"]):
            continue
        out.append(dict(r))
    out.sort(key=lambda x: -(x.get("gsc_clicks_28d") or 0))
    return out[:(limit or cfg["limits"]["max_generate_per_run"])]


# ═══════════════════ generate (monkeypatch-able) ═══════════════════
def gen_provider():
    """Provider generate (đổi được khi Claude chạm limit). Mặc định claude; set codex qua state file."""
    try:
        return json.loads((_DIR / "state" / "blog_rewrite_gen_provider.json").read_text(encoding="utf-8")).get("provider", "claude")
    except Exception:
        return "claude"


def _generate_draft(candidate):
    """Gọi worker AI thật cho 1 candidate (QA monkeypatch hàm này). Trả draft_id hoặc None."""
    res = br.create_job([candidate["id"]], mode="autopilot", provider=gen_provider())
    if not res.get("ok"):
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("apwrk", str(_DIR / "_scripts" / "run_blog_rewrite_worker.py"))
    w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
    w.run(res["job_id"])
    d = br.latest_draft_for_candidate(candidate["id"])
    return d["id"] if d else None


def _strip_external_images(body):
    out = body or ""
    for tag in re.findall(r"<img[^>]+>", out, re.I):
        m = re.search(r'src="([^"]+)"', tag, re.I)
        if m and imgs.classify_image_source(m.group(1)) != "SINTECH_OWNED":
            out = re.sub(r"<p>\s*" + re.escape(tag) + r"\s*</p>", "", out)
            out = out.replace(tag, "")
    return out


# ═══════════════════ pipeline ═══════════════════
def _today_applied_count():
    conn = db.get_conn()
    n = conn.execute("SELECT COUNT(DISTINCT candidate_id) FROM blog_rewrite_drafts WHERE applied_at IS NOT NULL "
                     "AND date(applied_at)=date('now')").fetchone()[0]
    conn.close()
    return n


def _new_item(run_id, c):
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO blog_rewrite_autopilot_items (run_id,candidate_id,article_id,stage,status) "
                       "VALUES (?,?,?,?,?)", (run_id, c["id"], c["article_id"], "DISCOVER", "running"))
    iid = cur.lastrowid; conn.commit(); conn.close()
    return iid


def _upd_item(iid, **kw):
    if not kw:
        return
    cols = ", ".join(f"{k}=?" for k in kw) + ", updated_at=datetime('now')"
    conn = db.get_conn()
    conn.execute(f"UPDATE blog_rewrite_autopilot_items SET {cols} WHERE id=?", (*kw.values(), iid))
    conn.commit(); conn.close()


def run(mode=None, dry_run=False, confirm_apply_phrase=None, qa=False):
    """Chạy 1 lượt autopilot. mode None → theo config. qa=True bỏ qua enabled-check (dùng test).
    SAFE_AUTO_APPLY cần confirm_apply_phrase đúng + enabled."""
    migrate()
    cfg = load_config()
    mode = mode or cfg.get("mode", "PREP_ONLY")
    cb = cb_state()
    if cb.get("open"):
        return {"ok": False, "error": "CIRCUIT_BREAKER_OPEN", "reason": cb.get("reason")}
    if not qa and not dry_run and mode == "SAFE_AUTO_APPLY":
        if not cfg.get("enabled"):
            return {"ok": False, "error": "AUTOPILOT_DISABLED"}
        if confirm_apply_phrase != ENABLE_APPLY_PHRASE:
            return {"ok": False, "error": "CONFIRM_PHRASE_REQUIRED"}

    conn = db.get_conn()
    cur = conn.execute("INSERT INTO blog_rewrite_autopilot_runs (mode,status,started_at,circuit_breaker_status) "
                       "VALUES (?,?,datetime('now'),?)", (mode + ("_DRY" if dry_run else ""), "running", "closed"))
    run_id = cur.lastrowid; conn.commit(); conn.close()
    _ev(run_id, "run_started", detail={"mode": mode, "dry_run": dry_run})

    cands = select_candidates(cfg)
    stats = {"selected": len(cands), "generated": 0, "applied": 0, "hold": 0, "blocked": 0, "failed": 0}
    groups = {}
    gen_fail = 0; fact_fail = 0
    applied_this_run = 0
    cb_status = "closed"

    for c in cands:
        iid = _new_item(run_id, c)
        try:
            d = br.latest_draft_for_candidate(c["id"])
            # GENERATE nếu chưa có draft
            if not d:
                _upd_item(iid, stage="GENERATE")
                if dry_run:  # dry-run KHÔNG gọi AI — chỉ báo cần generate
                    _decide(iid, c, "PREP_ONLY", "chưa có draft — cần generate (dry-run không gọi AI)")
                    groups.setdefault("PREP_ONLY", []).append(c["id"]); continue
                if stats["generated"] >= cfg["limits"]["max_generate_per_run"]:
                    _decide(iid, c, "PREP_ONLY", "đạt cap generate/run"); groups.setdefault("PREP_ONLY", []).append(c["id"]); stats["hold"] += 1; continue
                did = _generate_draft(c)
                if not did:
                    gen_fail += 1; stats["failed"] += 1
                    _decide(iid, c, "FAILED", "generate fail")
                    _ev(run_id, "generate_failed", c["id"], iid)
                    if cfg["circuit_breaker"]["enabled"] and gen_fail >= cfg["circuit_breaker"]["max_consecutive_generate_fail"]:
                        cb_open("max_consecutive_generate_fail", run_id); cb_status = "open"; break
                    continue
                gen_fail = 0; stats["generated"] += 1
                d = br.get_draft(did)
            else:
                gen_fail = 0

            # SANITIZE + IMAGE_REMEDIATE (local, gỡ ảnh ngoài/chết)
            _upd_item(iid, stage="IMAGE_REMEDIATE", draft_id=d["id"])
            body = d["draft_body_html"] or ""
            cleaned = _strip_external_images(body)
            cleaned, _, _ = gen.sanitize_html(cleaned)
            if cleaned != body:  # tạo version sạch mới (không overwrite)
                d = _save_clean_version(c["id"], d, cleaned)
            # mark image_items external → removed, re-gate
            _mark_external_removed(c["id"])
            ig = imgs.audit_body_images(d["draft_body_html"] or "", check_availability=False)
            gate_summary = ig[1] if isinstance(ig, tuple) else ig
            gate_status = rem.article_gate(c["id"])
            _upd_item(iid, image_gate_json=json.dumps({"gate": gate_status}, ensure_ascii=False))
            if gate_status != "ALLOW":
                _decide(iid, c, "BLOCKED_IMAGE", f"gate {gate_status}"); groups.setdefault("BLOCKED_IMAGE", []).append(c["id"]); stats["blocked"] += 1; continue

            # visual dependency → HOLD MANUAL_REVIEW
            vd = visual_dependency(d["draft_body_html"] or "")
            if vd["depends_on_images"]:
                _decide(iid, c, "MANUAL_REVIEW", f"phụ thuộc ảnh: {vd['hits'][:3]}"); groups.setdefault("MANUAL_REVIEW", []).append(c["id"]); stats["hold"] += 1; continue

            # FACT_CHECK
            _upd_item(iid, stage="FACT_CHECK")
            fg = fact_gate(d["draft_body_html"] or "")
            _upd_item(iid, fact_json=json.dumps(fg, ensure_ascii=False))
            if not fg["fact_safe"]:
                fact_fail += 1; stats["hold"] += 1
                grp = "HOLD_UNSUPPORTED" if fg["unsupported_remove"] else "HOLD_TIME_SENSITIVE"
                _decide(iid, c, grp, f"unsupported={fg['unsupported_remove']} time={fg['time_sensitive_review']}")
                groups.setdefault(grp, []).append(c["id"])
                if cfg["circuit_breaker"]["enabled"] and fact_fail >= cfg["circuit_breaker"]["max_consecutive_fact_fail"]:
                    cb_open("max_consecutive_fact_fail", run_id); cb_status = "open"; break
                continue
            fact_fail = 0

            # QUALITY_CHECK
            _upd_item(iid, stage="QUALITY_CHECK")
            qg = quality_gate(d, cfg)
            _upd_item(iid, quality_json=json.dumps(qg, ensure_ascii=False))
            if not qg["ok"]:
                _decide(iid, c, "MANUAL_REVIEW", f"quality: {qg['reasons']}"); groups.setdefault("MANUAL_REVIEW", []).append(c["id"]); stats["hold"] += 1; continue

            # PREFLIGHT (conflict)
            _upd_item(iid, stage="PREFLIGHT")
            pv = ap.apply_preview(d["id"])
            _upd_item(iid, conflict_json=json.dumps({"conflict": pv["conflict_status"]}, ensure_ascii=False))
            if cfg["quality"]["require_safe_conflict"] and pv["conflict_status"] != "SAFE_TO_APPLY":
                _decide(iid, c, "CONFLICT", pv["conflict_status"]); groups.setdefault("CONFLICT", []).append(c["id"]); stats["hold"] += 1; continue

            # → AUTO_ELIGIBLE
            if mode != "SAFE_AUTO_APPLY" or dry_run:
                _decide(iid, c, "AUTO_ELIGIBLE", "đạt chuẩn — chờ apply (PREP_ONLY)")
                groups.setdefault("AUTO_ELIGIBLE", []).append(c["id"]); continue

            # ── SAFE_AUTO_APPLY ──
            if applied_this_run >= cfg["limits"]["max_apply_per_run"]:
                _decide(iid, c, "AUTO_ELIGIBLE", "đạt cap apply/run — để run sau"); groups.setdefault("AUTO_ELIGIBLE", []).append(c["id"]); continue
            if _today_applied_count() >= cfg["limits"]["max_apply_per_day"]:
                _decide(iid, c, "AUTO_ELIGIBLE", "đạt cap apply/ngày"); groups.setdefault("AUTO_ELIGIBLE", []).append(c["id"]); continue

            ar = _apply_one(run_id, iid, c, d, cfg)
            if ar["state"] in ("LIVE_VERIFIED", "DB_RECONCILED") and ar["verify"] == "VERIFIED":
                applied_this_run += 1; stats["applied"] += 1
                groups.setdefault("APPLIED", []).append(c["id"])
            else:
                stats["failed"] += 1
                groups.setdefault("FAILED", []).append(c["id"])
                if cfg["circuit_breaker"]["enabled"]:
                    cb_open(f"apply_{ar['state']}", run_id); cb_status = "open"; break
        except Exception as e:
            stats["failed"] += 1
            _decide(iid, c, "FAILED", str(e)[:160])
            _ev(run_id, "item_exception", c["id"], iid, {"error": str(e)[:200]})
            if cfg["circuit_breaker"]["enabled"]:
                cb_open("item_exception", run_id); cb_status = "open"; break

    summary = {"stats": stats, "groups": {k: len(v) for k, v in groups.items()}, "group_ids": groups, "mode": mode, "dry_run": dry_run}
    conn = db.get_conn()
    conn.execute("UPDATE blog_rewrite_autopilot_runs SET status=?, finished_at=datetime('now'), "
                 "selected_count=?, generated_count=?, applied_count=?, hold_count=?, blocked_count=?, "
                 "failed_count=?, circuit_breaker_status=?, summary_json=?, updated_at=datetime('now') WHERE id=?",
                 ("circuit_open" if cb_status == "open" else "completed", stats["selected"], stats["generated"],
                  stats["applied"], stats["hold"], stats["blocked"], stats["failed"], cb_status,
                  json.dumps(summary, ensure_ascii=False), run_id))
    conn.commit(); conn.close()
    _ev(run_id, "run_finished", detail=summary)
    return {"ok": True, "run_id": run_id, "summary": summary, "circuit_breaker": cb_status}


def _save_clean_version(cid, d, clean):
    qm = gen.quality_metrics(d["original_body_html"] or "", clean)
    conn = db.get_conn()
    ver = (conn.execute("SELECT MAX(version) FROM blog_rewrite_drafts WHERE candidate_id=?", (cid,)).fetchone()[0] or 0) + 1
    cur = conn.execute("""INSERT INTO blog_rewrite_drafts (candidate_id,job_id,version,original_title,original_body_html,
      original_handle,original_content_hash,draft_title,draft_body_html,draft_summary_html,draft_tags,
      seo_title_suggestions_json,meta_description_suggestions_json,outline_json,quality_json,approval_status)
      SELECT candidate_id,job_id,?,original_title,original_body_html,original_handle,original_content_hash,
      draft_title,?,draft_summary_html,draft_tags,seo_title_suggestions_json,meta_description_suggestions_json,
      outline_json,?,'draft_ready' FROM blog_rewrite_drafts WHERE id=?""",
      (ver, clean, json.dumps(qm, ensure_ascii=False), d["id"]))
    nid = cur.lastrowid; conn.commit(); conn.close()
    return br.get_draft(nid)


def _mark_external_removed(cid):
    conn = db.get_conn()
    conn.execute("UPDATE blog_rewrite_image_items SET selected_action='REMOVE_FROM_DRAFT', review_status='reviewed' "
                 "WHERE candidate_id=? AND source_class!='SINTECH_OWNED' "
                 "AND selected_action NOT IN ('REMOVE_DEAD_IMAGE','REMOVE_FROM_DRAFT')", (cid,))
    conn.commit(); conn.close()


def _apply_one(run_id, iid, c, d, cfg):
    """1 bài: backup → one-shot flag → PUT body-only → verify → reconcile → auto-disarm."""
    _upd_item(iid, stage="APPLY_ONE_SHOT")
    if cfg["apply"]["one_shot_flag"]:
        br.approve_local(d["id"])
        ap._FLAGS_PATH.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": True,
            "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")
    _ev(run_id, "apply_armed", c["id"], iid, {"draft_id": d["id"]})
    res, state = None, "UNCERTAIN_POST_PUT"; verify_status = "UNKNOWN"
    try:
        res, code = ap.apply_draft_body_only(d["id"], confirm_phrase=f"APPLY PILOT ARTICLE {c['article_id']}",
                                             confirm_reviewed_draft=True, confirm_reviewed_images=True)
        verify_status = res.get("verify_status", "UNKNOWN"); state = res.get("state", "UNKNOWN")
    except Exception as e:
        _ev(run_id, "apply_exception", c["id"], iid, {"error": str(e)[:160]})
    finally:
        ap._FLAGS_PATH.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": False,
            "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")
        _ev(run_id, "apply_auto_disarmed", c["id"], iid)
    _upd_item(iid, stage="VERIFY", apply_json=json.dumps({"http": (res or {}).get("http")}, ensure_ascii=False),
              verify_json=json.dumps({"verify": verify_status, "state": state}, ensure_ascii=False))
    decision = "APPLIED" if (verify_status == "VERIFIED") else ("FAILED" if state == "UNCERTAIN_POST_PUT" else "FAILED")
    _decide(iid, c, decision, f"verify={verify_status} state={state}")
    return {"verify": verify_status, "state": state}


def _decide(iid, c, decision, reason):
    _upd_item(iid, stage="REPORT", status="done", decision=decision, decision_reason=reason)


# ═══════════════════ status / queries ═══════════════════
def status():
    cfg = load_config(); cb = cb_state()
    conn = db.get_conn()
    last = conn.execute("SELECT * FROM blog_rewrite_autopilot_runs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    badge = "OFF"
    if cb.get("open"): badge = "CIRCUIT BREAKER OPEN"
    elif not cfg.get("enabled"): badge = "OFF" if cfg.get("mode") != "PREP_ONLY" else "PREP ONLY"
    elif cfg.get("mode") == "SAFE_AUTO_APPLY": badge = "SAFE AUTO APPLY"
    else: badge = "PREP ONLY"
    return {"enabled": cfg.get("enabled"), "mode": cfg.get("mode"), "badge": badge,
            "scheduler_enabled": cfg["schedule"]["enabled"], "schedule": cfg["schedule"],
            "limits": cfg["limits"], "quality": cfg["quality"], "circuit_breaker": cb,
            "today_applied": _today_applied_count(), "last_run": dict(last) if last else None,
            "live_flags": ap.flags() if hasattr(ap, "flags") else None}


def list_runs(limit=20):
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM blog_rewrite_autopilot_runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_run(run_id):
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM blog_rewrite_autopilot_runs WHERE id=?", (run_id,)).fetchone()
    items = conn.execute("SELECT * FROM blog_rewrite_autopilot_items WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    conn.close()
    return {"run": dict(r) if r else None, "items": [dict(x) for x in items]}


def list_events(run_id=None, limit=50):
    conn = db.get_conn()
    if run_id:
        rows = conn.execute("SELECT * FROM blog_rewrite_autopilot_events WHERE run_id=? ORDER BY id DESC LIMIT ?", (run_id, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM blog_rewrite_autopilot_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def pause():
    patch_config({"enabled": False}); return {"ok": True, "enabled": False}


def resume():
    if cb_state().get("open"):
        return {"ok": False, "error": "CIRCUIT_BREAKER_OPEN — cần reset thủ công"}
    return {"ok": True, "note": "resume KHÔNG tự bật apply; cần enable SAFE_AUTO_APPLY riêng"}


def emergency_stop():
    patch_config({"enabled": False, "mode": "PREP_ONLY", "schedule": {"enabled": False}})
    ap._FLAGS_PATH.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": False,
        "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")
    cb_open("emergency_stop")
    return {"ok": True, "stopped": True}
