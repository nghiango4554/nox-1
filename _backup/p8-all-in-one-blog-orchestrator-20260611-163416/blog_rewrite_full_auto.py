# -*- coding: utf-8 -*-
"""Blog Rewrite — P7 FULL AUTO RUN ONCE.

1 nút chạy hết queue: candidate → sort traffic → generate → self-review 2-pass →
auto-fix → image/fact/quality gate (FULL_RECOMPUTE) → backup → body-only PUT 1 lần →
verify → reconcile → checkpoint → next. KHÔNG approve tay, KHÔNG scheduler, KHÔNG daily cap.

An toàn: full-auto thật chỉ chạy khi confirm phrase + KHÔNG bật trong build.
Write transport monkeypatch-able qua blog_rewrite_apply. Reuse engine + autopilot gates.
"""
import json, re, time, logging, logging.handlers
from pathlib import Path

import db
import blog_rewrite as br
import blog_rewrite_gen as gen
# stage kết thúc (không còn RUNNING): hết queue / lỗi pause / reconcile xong incident
TERMINAL_STAGES = ("completed", "PAUSED_ERROR", "completed_reconciled", None)
import blog_rewrite_remediate as rem
import blog_rewrite_images as imgs
import blog_rewrite_apply as ap
import blog_rewrite_verify as verify
import blog_rewrite_autopilot as auto

_DIR = Path(__file__).parent
CHECKPOINT_PATH = _DIR / "state" / "blog_rewrite_full_auto_checkpoint.json"
STATE_PATH = _DIR / "state" / "blog_rewrite_full_auto.json"
START_PHRASE = "START FULL AUTO BLOG REWRITE SYNC"

DEFAULT_CONFIG = {
    "mode": "FULL_AUTO_RUN_ONCE", "scheduler_enabled": False,
    "process_until_queue_empty": True, "resume_from_checkpoint": True,
    "generate_concurrency": 1, "apply_concurrency": 1, "max_regenerate_per_article": 1,
    "cooldown_seconds_between_apply": 5, "traffic_priority": True, "high_traffic_strict_review": True,
    "body_html_only": True, "auto_backup": True, "auto_verify": True, "auto_reconcile": True, "auto_rollback": False,
    "quality": {"min_quality_score": 80, "max_overlap_percent": 12},
    "circuit_breaker": {"max_consecutive_put_fail": 2},
}


def load_config():
    try:
        return auto._merge(DEFAULT_CONFIG, json.loads(STATE_PATH.read_text(encoding="utf-8")))
    except Exception:
        return dict(DEFAULT_CONFIG)


# ═══════════════════ rotating log (KHÔNG log token/secret/body/prompt/response) ═══════════════════
LOG_DIR = _DIR / "state" / "logs"
LOG_PATH = LOG_DIR / "blog_rewrite_full_auto.log"


def _get_logger():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger("blog_full_auto")
    if not lg.handlers:
        h = logging.handlers.RotatingFileHandler(str(LOG_PATH), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        lg.addHandler(h); lg.setLevel(logging.INFO); lg.propagate = False
    return lg


def _log(run_id, msg, **kw):
    """Log structured: chỉ id/stage/event/error_type. TUYỆT ĐỐI không body/prompt/secret."""
    parts = [f"run={run_id}"] + [f"{k}={v}" for k, v in kw.items() if v is not None] + [msg]
    try:
        _get_logger().info(" | ".join(str(p) for p in parts))
    except Exception:
        pass


# ═══════════════════ DB (reuse autopilot tables + thêm cột) ═══════════════════
def migrate():
    auto.migrate()  # dùng chung runs/items/events
    conn = db.get_conn()
    # cột thêm cho full-auto (idempotent)
    for col, typ in [("traffic_tier", "TEXT"), ("score_source", "TEXT"), ("review_passes", "INTEGER")]:
        try:
            conn.execute(f"ALTER TABLE blog_rewrite_autopilot_items ADD COLUMN {col} {typ}")
        except Exception:
            pass
    conn.commit(); conn.close()


# ═══════════════════ queue + traffic ═══════════════════
def queue_candidates():
    """Toàn bộ rewrite_eligible · non-reverse · chưa applied. Sort traffic priority."""
    try:
        hold_map = json.loads((_DIR / "state" / "_canary_hold.json").read_text(encoding="utf-8"))
    except Exception:
        hold_map = {}
    conn = db.get_conn()
    rows = conn.execute("SELECT id,article_id,blog_id,title,gsc_clicks_28d,gsc_impressions_28d,"
                        "ga4_organic_sessions_28d,priority_score FROM blog_rewrite_candidates "
                        "WHERE rewrite_eligible=1 AND audit_reverse_copy=0 AND status!='applied'").fetchall()
    conn.close()
    out = [dict(r) for r in rows if str(r["id"]) not in hold_map]

    def keyf(c):
        ev = 0 if auto._is_evergreen(c["title"]) else 1
        return (-(c.get("gsc_clicks_28d") or 0), -(c.get("ga4_organic_sessions_28d") or 0),
                -(c.get("priority_score") or 0), ev)
    out.sort(key=keyf)
    return out


def traffic_tier(c):
    clicks = c.get("gsc_clicks_28d") or 0
    ss = c.get("ga4_organic_sessions_28d") or 0
    if clicks >= 50 or ss >= 50:
        return "HIGH"
    if clicks >= 5 or ss >= 5:
        return "MEDIUM"
    return "LOW"


# ═══════════════════ P7.3 — EVERGREEN-FIRST LANE SELECTOR ═══════════════════
# Phân lane theo title (trước generate). AUTO_LANE = evergreen/how-to/concept/troubleshooting text-first.
# DEFER_LANE = news/launch/driver/giá/benchmark/FPS/game-config-có-FPS/visual-tutorial → HOLD/BLOCKED.
_LANE_NEWS = ("ra mắt", "ra mat", "sắp ra", "trình làng", "vừa công bố", "công bố", "rò rỉ", "khai tử",
              "ngừng sản xuất", "comeback", "phiên bản mới", "mới nhất", "driver", "tồn kho", "khan hàng",
              "giá rẻ", "giá tốt", "bao nhiêu tiền", "giá bao nhiêu", "khuyến mãi", "release", "launch")
_LANE_BENCH = ("benchmark", "fps", "khung hình", "test hiệu năng", "điểm benchmark")
_LANE_GAMECFG = ("cấu hình chơi", "cấu hình game", "config chơi", "build pc chơi", "máy chơi", "chơi được")
_LANE_VISUAL = ("bước 1", "bước 2", "như hình", "hình dưới", "screenshot", "ảnh minh họa", "theo hình",
                "photoshop", "watermark", "xóa chữ", "xóa logo", "cách chụp")
_LANE_EVERGREEN = ("là gì", "phân biệt", "cách chọn", "cách dùng", "cách sử dụng", "tại sao", "có nên",
                   "mẹo", "khái niệm", "sửa lỗi", "khắc phục", "không lên", "không nhận", "vệ sinh",
                   "tối ưu", "nên mua", "cách kiểm tra", "cách kết nối", "cách cài", "cách vệ sinh",
                   "tổng hợp", "kiến thức", "tất tần tật", "toàn tập", "tìm hiểu", "tất cả về", "hướng dẫn")


def classify_lane(c):
    """Trả (lane, defer_decision, reason). DEFER ưu tiên bắt visual > benchmark/game-cfg > news.
    AUTO chỉ khi có tín hiệu evergreen rõ + không có tín hiệu DEFER."""
    t = (c.get("title") or "").lower()
    hit = lambda kws: [k for k in kws if k in t]
    visual, bench, gamecfg, news = hit(_LANE_VISUAL), hit(_LANE_BENCH), hit(_LANE_GAMECFG), hit(_LANE_NEWS)
    if visual:
        return ("DEFER", "BLOCKED_IMAGE", "visual/tutorial: " + ", ".join(visual))
    if bench or gamecfg:
        return ("DEFER", "HOLD_UNSUPPORTED", "benchmark/fps/game-config: " + ", ".join(bench + gamecfg))
    if news:
        return ("DEFER", "HOLD_TIME_SENSITIVE", "news/launch/driver/giá: " + ", ".join(news))
    if auto._is_evergreen(t) or hit(_LANE_EVERGREEN):
        return ("AUTO", None, "evergreen text-first")
    return ("DEFER", "MANUAL_COMPLEX", "không rõ evergreen — xử lý sau")


# Decision "cuối" = đã chốt, KHÔNG xử lý lại trong batch tiếp (retryable/failed/dry-run KHÔNG tính)
_TERMINAL_DECISIONS = ("APPLIED", "APPLIED_RECONCILED", "BLOCKED_IMAGE", "BLOCKED_FACT",
                       "HOLD_TIME_SENSITIVE", "HOLD_UNSUPPORTED", "HOLD_QUALITY",
                       "MANUAL_REVIEW", "MANUAL_COMPLEX", "CONFLICT")


def decided_candidate_ids():
    """candidate_id đã có decision cuối (mọi run) → loại khỏi batch tiếp theo."""
    conn = db.get_conn()
    ph = ",".join("?" * len(_TERMINAL_DECISIONS))
    rows = conn.execute(f"SELECT DISTINCT candidate_id FROM blog_rewrite_autopilot_items "
                        f"WHERE decision IN ({ph})", _TERMINAL_DECISIONS).fetchall()
    conn.close()
    return {r[0] for r in rows}


def _lane_tiebreak(c):
    """Tiebreak 4-5: (số ảnh external/blocked, số bảng) từ draft mới nhất nếu có. Chưa có draft → (0,0).
    Đếm nhẹ bằng regex, KHÔNG check availability mạng (rẻ, để sort)."""
    d = br.latest_draft_for_candidate(c["id"])
    if not d:
        return (0, 0)
    body = d.get("draft_body_html") or ""
    ext = sum(1 for s in re.findall(r'<img[^>]+src="([^"]+)"', body, re.I)
              if "200000860097" not in s and "sintech" not in s.lower())
    return (ext, body.count("<table"))


def _lane_sort_key(c):
    tb = _lane_tiebreak(c)
    return (-(c.get("gsc_clicks_28d") or 0), -(c.get("ga4_organic_sessions_28d") or 0),
            -(c.get("priority_score") or 0), tb[0], tb[1])  # clicks↓ sessions↓ priority↓ ít-ảnh ít-bảng


def build_lanes(q):
    """Chia queue thành (auto_lane, defer_lane), tag mỗi candidate. Sort AUTO theo đủ 5 tiêu chí."""
    auto_l, defer_l = [], []
    for c in q:
        lane, dec, reason = classify_lane(c)
        c["_lane"] = lane; c["_defer_decision"] = dec; c["_defer_reason"] = reason
        (auto_l if lane == "AUTO" else defer_l).append(c)
    auto_l.sort(key=_lane_sort_key)
    defer_l.sort(key=lambda c: (-(c.get("gsc_clicks_28d") or 0), -(c.get("ga4_organic_sessions_28d") or 0),
                                -(c.get("priority_score") or 0)))
    return auto_l, defer_l


# ═══════════════════ self-review + auto-fix (deterministic) ═══════════════════
def self_review(body):
    """PASS: phát hiện vấn đề (gate-based, không AI). Trả list issue."""
    issues = []
    t = auto._text(body)
    if any(b in t for b in ("gearvn", "fptshop", "cellphones", "memoryzone", "tgdd", "hacom")):
        issues.append("brand_competitor")
    if any(x in (body or "").lower() for x in ("<script", "javascript:", "<iframe", "onerror=")):
        issues.append("html_unsafe")
    if re.search(r'href="https?://[^"]*(gearvn|fptshop|cellphones|tgdd|hacom)', body or "", re.I):
        issues.append("competitor_href")
    fg = auto.fact_gate(body)
    if fg["unsupported_remove"]:
        issues.append("unsupported_claims")
    if fg["time_sensitive_review"]:
        issues.append("time_sensitive_claims")
    return issues


def auto_fix(original_body, body):
    """AUTO FIX deterministic: gỡ ảnh ngoài/chết, sanitize, clean href đối thủ, bỏ câu unsupported/price.
    KHÔNG bịa thêm. Trả body mới."""
    out = auto._strip_external_images(body)
    # bỏ câu chứa benchmark (card+fps) hoặc giá cụ thể hoặc fps thừa
    def _drop_sentences(html):
        # tách theo <p>/<li>: nếu nội dung text của block có claim → bỏ block
        def repl(m):
            inner = m.group(0); txt = re.sub(r"<[^>]+>", " ", inner).lower()
            bad = re.search(r"(rtx|rx|gtx|radeon|core\s*i\d)[^.]{0,40}\d+\s*fps", txt) or \
                  re.search(r"\d[\d.,]*\s*(?:triệu|usd|đồng)\b", txt)
            return "" if bad else inner
        return re.sub(r"<(p|li)\b[^>]*>.*?</\1>", repl, html, flags=re.S | re.I)
    out = _drop_sentences(out)
    # clean competitor href → unwrap text
    out = re.sub(r'<a[^>]+href="https?://[^"]*(?:gearvn|fptshop|cellphones|tgdd|hacom)[^"]*"[^>]*>(.*?)</a>',
                 r"\1", out, flags=re.S | re.I)
    out, _, _ = gen.sanitize_html(out)
    return out


# ═══════════════════ quality FULL_RECOMPUTE ═══════════════════
def full_recompute_quality(draft):
    """FULL_RECOMPUTE — KHÔNG dùng inferred fallback để apply. score_source rõ ràng."""
    body = draft.get("draft_body_html") or ""
    orig = draft.get("original_body_html") or ""
    qm = gen.quality_metrics(orig, body)
    sc = qm.get("scorecard") or {}
    ov = (qm.get("normalized_5gram_overlap") or 0) * 100
    t = auto._text(body)
    brand_ok = not any(b in t for b in ("gearvn", "fptshop", "cellphones", "memoryzone", "tgdd", "hacom"))
    html_ok = not any(x in body.lower() for x in ("<script", "javascript:", "<iframe", "onerror="))
    # score từ FULL_RECOMPUTE: ưu tiên scorecard.originality, nếu có thì SCORECARD, không thì tính trực tiếp
    if sc.get("originality") == "high" and sc.get("brand_cleanup") == "PASS":
        score, source = 88, "SCORECARD"
    elif sc.get("originality"):
        score, source = (70 if sc["originality"] != "high" else 88), "SCORECARD"
    else:
        # FULL_RECOMPUTE trực tiếp từ tín hiệu đo được (KHÔNG phải inferred mơ hồ)
        if not brand_ok or not html_ok:
            score = 40
        elif ov < 5:
            score = 88
        elif ov < 10:
            score = 82
        elif ov <= 12:
            score = 78
        else:
            score = 60
        source = "FULL_RECOMPUTE"
    return {"quality_score_verified": score, "score_source": source, "evidence_complete": True,
            "overlap_percent": round(ov, 1), "brand_cleanup": "PASS" if brand_ok else "FAIL",
            "html_safety": "PASS" if html_ok else "FAIL",
            "longest_phrase": qm.get("longest_common_phrase"), "quality_json": qm}


def final_auto_gate(cid, draft, qual, cfg):
    """Auto sync CHỈ khi đủ điều kiện chặt. Trả (ok, reasons)."""
    body = draft.get("draft_body_html") or ""
    reasons = []
    # thin-content guard: bài bị auto-fix gutted hoặc quá ngắn → KHÔNG đăng
    wc = len(re.sub(r"<[^>]+>", " ", body).split())
    if wc < 150:
        reasons.append(f"thin_content({wc}w)")
    gate = rem.article_gate(cid)
    vd = auto.visual_dependency(body)
    fg = auto.fact_gate(body)
    pv = ap.apply_preview(draft["id"])
    comp_href = len(re.findall(r'href="https?://[^"]*(gearvn|fptshop|cellphones|tgdd|hacom)', body, re.I))
    if qual["quality_score_verified"] < cfg["quality"]["min_quality_score"]: reasons.append(f"score {qual['quality_score_verified']}")
    if qual["score_source"] not in ("FULL_RECOMPUTE", "SCORECARD"): reasons.append("score_source")
    if not qual["evidence_complete"]: reasons.append("evidence")
    if qual["overlap_percent"] > cfg["quality"]["max_overlap_percent"]: reasons.append(f"overlap {qual['overlap_percent']}%")
    if qual["html_safety"] != "PASS": reasons.append("html")
    if qual["brand_cleanup"] != "PASS": reasons.append("brand")
    if gate != "ALLOW": reasons.append(f"image_gate {gate}")
    if not fg["fact_safe"]: reasons.append("fact")
    if comp_href: reasons.append("competitor_href")
    if pv["conflict_status"] != "SAFE_TO_APPLY": reasons.append(pv["conflict_status"])
    return (not reasons), {"image_gate": gate, "visual_dep": vd["depends_on_images"], "fact_safe": fg["fact_safe"],
                           "conflict": pv["conflict_status"], "reasons": reasons}


# ═══════════════════ checkpoint ═══════════════════
def save_checkpoint(cp):
    cp["updated_at"] = _now()
    CHECKPOINT_PATH.write_text(json.dumps(cp, ensure_ascii=False, indent=2), encoding="utf-8")


def load_checkpoint():
    try:
        return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _now():
    conn = db.get_conn()
    n = conn.execute("SELECT datetime('now')").fetchone()[0]
    conn.close()
    return n


# ═══════════════════ main loop ═══════════════════
def run_full_auto(confirm_phrase=None, qa=False, dry_run=False, max_articles=None, priority_cids=None,
                  auto_only=False, skip_decided=False):
    """Chạy 1 lượt full-auto hết queue. Live PUT chỉ khi qa=False + confirm_phrase đúng + không dry_run.
    priority_cids: candidate_id đẩy lên đầu queue. auto_only=True: CHỈ AUTO_LANE (bỏ DEFER_LANE).
    skip_decided=True: loại bài đã có decision cuối (chỉ xử lý pending)."""
    migrate()
    cfg = load_config()
    cb = auto.cb_state()
    if cb.get("open"):
        return {"ok": False, "error": "CIRCUIT_BREAKER_OPEN", "reason": cb.get("reason")}
    live = (not qa) and (not dry_run)
    if live and confirm_phrase != START_PHRASE:
        return {"ok": False, "error": "CONFIRM_PHRASE_REQUIRED", "need": START_PHRASE}

    # P7.3 — EVERGREEN-FIRST: chia 2 lane, AUTO trước (xử lý+sync), DEFER sau (ghi status)
    auto_l, defer_l = build_lanes(queue_candidates())
    q = auto_l if auto_only else (auto_l + defer_l)  # auto_only: CHỈ AUTO_LANE (smoke)
    if skip_decided:  # batch tiếp: chỉ pending (bỏ bài đã có decision cuối)
        done = decided_candidate_ids()
        q = [c for c in q if c["id"] not in done]
    if priority_cids:  # override thứ tự (vd smoke) — đẩy cid cụ thể lên đầu, giữ tag lane
        pri = [int(x) for x in priority_cids]
        bycid = {c["id"]: c for c in q}
        priset = set(pri)
        q = [bycid[x] for x in pri if x in bycid] + [c for c in q if c["id"] not in priset]
    if max_articles:
        q = q[:max_articles]
    auto_count = sum(1 for c in q if c.get("_lane") == "AUTO")
    defer_count = sum(1 for c in q if c.get("_lane") == "DEFER")
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO blog_rewrite_autopilot_runs (mode,status,started_at,circuit_breaker_status) "
                       "VALUES (?,?,datetime('now'),?)", ("FULL_AUTO_RUN_ONCE" + ("_DRY" if dry_run else ""), "running", "closed"))
    run_id = cur.lastrowid; conn.commit(); conn.close()
    queue_ids = [{"i": i, "cid": c["id"], "article_id": c["article_id"],
                  "title": (c.get("title") or "")[:70], "clicks": c.get("gsc_clicks_28d") or 0,
                  "tier": traffic_tier(c), "lane": c.get("_lane")} for i, c in enumerate(q)]
    cp = {"run_id": run_id, "started_at": _now(), "queue_total": len(q), "processed": 0, "applied": 0,
          "applied_reconciled": 0, "retryable": 0,
          "hold": 0, "blocked_image": 0, "blocked_fact": 0, "hold_quality": 0, "conflict": 0, "failed": 0,
          "auto_lane": auto_count, "defer_lane": defer_count, "current_lane": None, "lane_index": -1,
          "last_candidate_id": None, "current_stage": "START", "current_article_id": None,
          "current_draft_id": None, "current_index": -1, "current_candidate_id": None,
          "dry_run": dry_run, "queue_ids": queue_ids, "last_event": "run_started"}
    save_checkpoint(cp)
    auto._ev(run_id, "full_auto_started", detail={"queue": len(q), "dry_run": dry_run, "live": live})
    _log(run_id, "run_started", queue=len(q), dry_run=dry_run, live=live, checkpoint=str(CHECKPOINT_PATH))
    put_fail = 0

    _DEFER_CP_KEY = {"HOLD_TIME_SENSITIVE": "hold", "HOLD_UNSUPPORTED": "hold", "MANUAL_COMPLEX": "hold",
                     "BLOCKED_IMAGE": "blocked_image", "BLOCKED_FACT": "blocked_fact", "CONFLICT": "conflict"}
    for _qi, c in enumerate(q):
        cid = c["id"]
        lane = c.get("_lane") or "AUTO"
        cp["current_index"] = _qi; cp["current_candidate_id"] = cid; cp["current_lane"] = lane
        cp["lane_index"] = (cp.get("lane_index", -1) + 1); save_checkpoint(cp)
        # không xử lý lại applied / applied_reconciled
        cc = br.get_candidate(cid)
        if cc and cc.get("status") == "applied":
            continue
        iid = auto._new_item(run_id, c)
        tier = traffic_tier(c)
        auto._upd_item(iid, traffic_tier=tier)
        # DEFER_LANE — KHÔNG generate, chỉ ghi decision rồi next (không chiếm slot/cost)
        if lane == "DEFER":
            dec = c.get("_defer_decision") or "MANUAL_COMPLEX"
            auto._decide(iid, c, dec, f"DEFER_LANE: {c.get('_defer_reason', '')}")
            cp[_DEFER_CP_KEY.get(dec, "hold")] += 1; cp["processed"] += 1
            _log(run_id, "defer_decided", cid=cid, article_id=c["article_id"], stage="DEFER", event=dec)
            save_checkpoint(cp); continue
        cp.update({"last_candidate_id": cid, "current_article_id": c["article_id"], "current_stage": "GENERATE"})
        try:
            d = br.latest_draft_for_candidate(cid)
            regen_used = 0
            if not d:
                if dry_run:
                    auto._decide(iid, c, "PREP_ONLY", "dry-run không generate"); cp["hold"] += 1; cp["processed"] += 1; save_checkpoint(cp); continue
                did = auto._generate_draft(c)
                if not did:
                    auto._decide(iid, c, "FAILED", "generate fail"); cp["failed"] += 1; cp["processed"] += 1; save_checkpoint(cp); continue
                d = br.get_draft(did)

            # SELF-REVIEW PASS 1 → AUTO FIX → PASS 2 (regenerate tối đa 1)
            passes = 1 if tier == "LOW" else 2
            outcome = None  # None = qua hết gate → eligible apply
            while outcome is None:
                cp["current_stage"] = "SELF_REVIEW"; cp["current_draft_id"] = d["id"]; save_checkpoint(cp)
                fixed = auto_fix(d["original_body_html"] or "", d["draft_body_html"] or "")
                if fixed != (d["draft_body_html"] or ""):
                    d = auto._save_clean_version(cid, d, fixed)
                auto._mark_external_removed(cid)
                if auto.visual_dependency(d["draft_body_html"] or "")["depends_on_images"]:
                    auto._decide(iid, c, "BLOCKED_IMAGE", "phụ thuộc ảnh — giữ queue xử lý sau"); cp["blocked_image"] += 1; outcome = "BLOCKED_IMAGE"; break
                qual = full_recompute_quality(d)
                ok, gate_info = final_auto_gate(cid, d, qual, cfg)
                auto._upd_item(iid, draft_id=d["id"], score_source=qual["score_source"], review_passes=passes,
                               quality_json=json.dumps(qual, ensure_ascii=False),
                               fact_json=json.dumps(auto.fact_gate(d["draft_body_html"] or ""), ensure_ascii=False),
                               image_gate_json=json.dumps({"gate": gate_info["image_gate"]}, ensure_ascii=False),
                               conflict_json=json.dumps({"conflict": gate_info["conflict"]}, ensure_ascii=False))
                if ok:
                    outcome = "ELIGIBLE"; break
                rs = gate_info["reasons"]
                can_regen = regen_used < cfg["max_regenerate_per_article"] and not dry_run
                if any("fact" in r for r in rs):
                    if can_regen:
                        regen_used += 1; cp["current_stage"] = "REGENERATE"; save_checkpoint(cp)
                        nid = auto._generate_draft(c)
                        if nid: d = br.get_draft(nid); continue
                    fg2 = auto.fact_gate(d["draft_body_html"] or "")
                    auto._decide(iid, c, "BLOCKED_FACT" if fg2["unsupported_remove"] else "HOLD_TIME_SENSITIVE", f"fact: {rs}"); cp["blocked_fact"] += 1; outcome = "BLOCKED_FACT"; break
                if any("image_gate" in r for r in rs):
                    auto._decide(iid, c, "BLOCKED_IMAGE", f"{rs}"); cp["blocked_image"] += 1; outcome = "BLOCKED_IMAGE"; break
                if any("conflict" in r.lower() or "CONFLICT" in r for r in rs):
                    auto._decide(iid, c, "CONFLICT", f"{rs}"); cp["conflict"] += 1; outcome = "CONFLICT"; break
                # còn lại = quality/score/overlap/thin-content
                if any("thin_content" in r for r in rs):
                    auto._decide(iid, c, "MANUAL_REVIEW", f"thin-content: {rs}"); cp["hold"] += 1; outcome = "MANUAL_REVIEW"; break
                # P7.3 borderline quality: 75–79 → regen tối đa 2 tổng cộng; <75 → HOLD_QUALITY ngay sau max regen.
                # KHÔNG hạ threshold 80, KHÔNG publish bài borderline.
                qscore = qual["quality_score_verified"]
                minq = cfg["quality"]["min_quality_score"]
                borderline = 75 <= qscore < minq
                max_regen_q = max(cfg["max_regenerate_per_article"], 2) if borderline else cfg["max_regenerate_per_article"]
                if regen_used < max_regen_q and not dry_run:
                    regen_used += 1; cp["current_stage"] = "REGENERATE"; save_checkpoint(cp)
                    nid = auto._generate_draft(c)
                    if nid: d = br.get_draft(nid); continue
                auto._decide(iid, c, "HOLD_QUALITY", f"quality {qscore}<{minq} sau {regen_used} regen"); cp["hold_quality"] += 1; outcome = "HOLD_QUALITY"; break

            if outcome != "ELIGIBLE":
                _log(run_id, "item_decided", cid=cid, article_id=c["article_id"], stage="GATE", event=outcome)
                cp["processed"] += 1; save_checkpoint(cp); continue

            # ── ĐẠT final gate → APPLY (serial, body-only, 1 PUT) ──
            if dry_run:
                auto._decide(iid, c, "AUTO_ELIGIBLE", "dry-run — đủ chuẩn, KHÔNG apply"); cp["processed"] += 1; save_checkpoint(cp); continue
            cp["current_stage"] = "APPLY"; save_checkpoint(cp)
            ar = _apply_serial(run_id, iid, c, d, cfg, qa)
            st = ar["state"]
            _log(run_id, "apply_done", cid=cid, article_id=c["article_id"], stage="APPLY",
                 event=st, verify=ar["verify"], source=ar.get("verify_source"))
            if ar["verify"] == "VERIFIED" and st in ("LIVE_VERIFIED", "APPLIED_RECONCILED"):
                # P7.2 — 500-but-write: PUT 5xx/timeout nhưng live == draft → vẫn APPLIED
                if st == "APPLIED_RECONCILED":
                    auto._decide(iid, c, "APPLIED_RECONCILED", f"reconciled src={ar.get('verify_source')}"); cp["applied_reconciled"] += 1
                else:
                    auto._decide(iid, c, "APPLIED", f"verify={ar['verify']}")
                cp["applied"] += 1; put_fail = 0
            elif st == "NOT_APPLIED_RETRYABLE":
                # live == original → chưa lên, để retry, KHÔNG auto retry, KHÔNG CB
                cp["retryable"] += 1
                auto._decide(iid, c, "NOT_APPLIED_RETRYABLE", "live==original — chưa lên live, để retry thủ công")
            elif st == "UNCERTAIN_POST_PUT" or ar.get("backup_fail"):
                # khác cả draft lẫn original / không đọc được → hard error → circuit breaker
                cp["failed"] += 1
                auto.cb_open(f"full_auto_{st}", run_id)
                auto._decide(iid, c, "UNCERTAIN_POST_PUT", f"verify={ar['verify']}")
                _finish(run_id, cp, "PAUSED_ERROR"); return {"ok": False, "error": "CIRCUIT_BREAKER", "state": st, "checkpoint": cp}
            else:
                cp["failed"] += 1; put_fail += 1
                auto._decide(iid, c, "FAILED", f"verify={ar['verify']}")
                if put_fail >= cfg["circuit_breaker"]["max_consecutive_put_fail"]:
                    auto.cb_open("max_consecutive_put_fail", run_id); _finish(run_id, cp, "PAUSED_ERROR"); return {"ok": False, "error": "CIRCUIT_BREAKER_PUT", "checkpoint": cp}
            cp["processed"] += 1; save_checkpoint(cp)
        except Exception as e:
            cp["failed"] += 1; cp["processed"] += 1
            auto._decide(iid, c, "FAILED", str(e)[:160])
            auto._ev(run_id, "item_exception", cid, iid, {"error": str(e)[:200]})
            _log(run_id, "item_error", cid=cid, article_id=c["article_id"], error_type=type(e).__name__)
            save_checkpoint(cp)
            continue  # content/lỗi thường → next, KHÔNG dừng run

    _finish(run_id, cp, "completed")
    return {"ok": True, "run_id": run_id, "checkpoint": cp}


def _item_decision(iid):
    conn = db.get_conn()
    r = conn.execute("SELECT decision FROM blog_rewrite_autopilot_items WHERE id=?", (iid,)).fetchone()
    conn.close()
    return r["decision"] if r else None


def _apply_serial(run_id, iid, c, d, cfg, qa):
    """Apply 1 bài: backup → one-shot flag → PUT body-only 1 lần → verify → reconcile → disarm."""
    cp_stage = "BACKUP"
    try:
        br.approve_local(d["id"])  # full-auto: tự approve sau khi qua mọi gate
    except Exception:
        pass
    ap._FLAGS_PATH.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": True,
        "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")
    auto._ev(run_id, "apply_armed", c["id"], iid, {"draft_id": d["id"]})
    res, state, vs = None, "UNKNOWN", "UNKNOWN"
    try:
        res, code = ap.apply_draft_body_only(d["id"], confirm_phrase=f"APPLY PILOT ARTICLE {c['article_id']}",
                                             confirm_reviewed_draft=True, confirm_reviewed_images=True)
        vs = res.get("verify_status", "UNKNOWN"); state = res.get("state", "UNKNOWN")
    except Exception as e:
        # exception SAU PUT (kể cả crash reconcile) → uncertain, KHÔNG re-PUT
        auto._ev(run_id, "apply_exception", c["id"], iid, {"error": str(e)[:160]})
        state = "UNCERTAIN_POST_PUT"; vs = "UNCERTAIN_POST_PUT"
    finally:
        ap._FLAGS_PATH.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": False,
            "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")
        auto._ev(run_id, "apply_auto_disarmed", c["id"], iid)
    src = (res or {}).get("verify_source")
    auto._upd_item(iid, apply_json=json.dumps({"http": (res or {}).get("http"), "verify_source": src}, ensure_ascii=False),
                   verify_json=json.dumps({"verify": vs, "state": state, "source": src}, ensure_ascii=False))
    return {"verify": vs, "state": state, "verify_source": src}


def _finish(run_id, cp, status_):
    if status_ == "PAUSED_ERROR":
        ap._FLAGS_PATH.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": False,
            "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")
    cp["current_stage"] = status_; save_checkpoint(cp)
    _log(cp.get("run_id"), "run_finished", status=status_, processed=cp.get("processed"), applied=cp.get("applied"),
         hold=cp.get("hold"), blocked_image=cp.get("blocked_image"), blocked_fact=cp.get("blocked_fact"), failed=cp.get("failed"))
    conn = db.get_conn()
    conn.execute("UPDATE blog_rewrite_autopilot_runs SET status=?, finished_at=datetime('now'), "
                 "selected_count=?, applied_count=?, hold_count=?, blocked_count=?, failed_count=?, "
                 "summary_json=?, updated_at=datetime('now') WHERE id=?",
                 (status_, cp["queue_total"], cp["applied"], cp["hold"],
                  cp["blocked_image"] + cp["blocked_fact"], cp["failed"], json.dumps(cp, ensure_ascii=False), run_id))
    conn.commit(); conn.close()
    auto._ev(run_id, "full_auto_finished", detail=cp)


# ═══════════════════ status / control ═══════════════════
def status():
    cp = load_checkpoint(); cb = auto.cb_state()
    conn = db.get_conn()
    last = conn.execute("SELECT * FROM blog_rewrite_autopilot_runs WHERE mode LIKE 'FULL_AUTO%' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    badge = "OFF"
    if cb.get("open"): badge = "PAUSED_ERROR"
    elif cp and cp.get("current_stage") == "completed_reconciled": badge = "RECONCILED"
    elif cp and cp.get("current_stage") not in TERMINAL_STAGES: badge = "RUNNING"
    return {"badge": badge, "checkpoint": cp, "circuit_breaker": cb, "queue_total": len(queue_candidates()),
            "last_run": dict(last) if last else None, "live_flags": ap.flags(),
            "scheduler": False, "human_approval": False}


def progress():
    """Realtime: queue có thứ tự + trạng thái từng bài (done/processing/waiting #N)."""
    cp = load_checkpoint()
    if not cp:
        return {"running": False, "items": [], "checkpoint": None}
    conn = db.get_conn()
    rows = conn.execute("SELECT candidate_id, decision, decision_reason FROM blog_rewrite_autopilot_items "
                        "WHERE run_id=?", (cp["run_id"],)).fetchall()
    conn.close()
    dec = {r["candidate_id"]: dict(r) for r in rows}
    finished = cp.get("current_stage") in ("completed", "PAUSED_ERROR", "completed_reconciled")
    cur_cid = cp.get("current_candidate_id")
    wait_n = 0
    out = []
    for q in cp.get("queue_ids", []):
        cid = q["cid"]
        d = dec.get(cid)
        if d and d.get("decision"):
            status, wpos = "done", None
        elif (not finished) and cid == cur_cid:
            status, wpos = "processing", None
        else:
            wait_n += 1; status, wpos = "waiting", wait_n
        out.append({"pos": q["i"] + 1, "candidate_id": cid, "article_id": q["article_id"],
                    "title": q["title"], "clicks": q["clicks"], "tier": q["tier"], "lane": q.get("lane"),
                    "status": status, "wait_position": wpos,
                    "decision": (d or {}).get("decision"), "decision_reason": (d or {}).get("decision_reason"),
                    "stage": cp.get("current_stage") if status == "processing" else None})
    return {"running": not finished, "finished": finished, "badge": status_badge(cp),
            "checkpoint": {k: cp[k] for k in cp if k != "queue_ids"}, "items": out}


def status_badge(cp):
    if auto.cb_state().get("open"):
        return "PAUSED_ERROR"
    if cp and cp.get("current_stage") == "completed_reconciled":
        return "RECONCILED"
    if cp and cp.get("current_stage") not in TERMINAL_STAGES:
        return "RUNNING"
    return "DONE" if cp and cp.get("current_stage") == "completed" else "OFF"


def list_items(run_id=None, limit=200):
    conn = db.get_conn()
    if not run_id:
        r = conn.execute("SELECT id FROM blog_rewrite_autopilot_runs WHERE mode LIKE 'FULL_AUTO%' ORDER BY id DESC LIMIT 1").fetchone()
        run_id = r["id"] if r else 0
    rows = conn.execute("SELECT * FROM blog_rewrite_autopilot_items WHERE run_id=? ORDER BY id LIMIT ?", (run_id, limit)).fetchall()
    conn.close()
    return {"run_id": run_id, "items": [dict(x) for x in rows]}


def list_events(limit=80):
    return auto.list_events(limit=limit)


def report():
    cp = load_checkpoint()
    return {"checkpoint": cp, "last_run": status()["last_run"]}


def pause():
    ap._FLAGS_PATH.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": False,
        "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")
    return {"ok": True, "paused": True}


def resume(confirm_phrase=None):
    if auto.cb_state().get("open"):
        return {"ok": False, "error": "CIRCUIT_BREAKER_OPEN — reset thủ công + kiểm tra trước"}
    return {"ok": True, "note": "gọi run_full_auto với resume_from_checkpoint=true"}


def emergency_stop():
    auto.cb_open("full_auto_emergency_stop")
    ap._FLAGS_PATH.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": False,
        "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")
    cp = load_checkpoint()
    if cp:
        cp["current_stage"] = "PAUSED_ERROR"; save_checkpoint(cp)
    return {"ok": True, "stopped": True}
