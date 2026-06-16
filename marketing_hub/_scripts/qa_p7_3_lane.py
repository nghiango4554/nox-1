# -*- coding: utf-8 -*-
"""QA P7.3 — EVERGREEN-FIRST LANE SELECTOR. Monkeypatch, KHÔNG network/PUT thật.
Cases 1-8,16-19 (lane/quality/UI/static). Apply 500-but-write 9-15 = qa_p7_2_reconcile.py."""
import sys, io, json, sqlite3
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DIR = Path(__file__).parent.parent
sys.path.insert(0, str(DIR))
import db, blog_rewrite as br, blog_rewrite_apply as ap, blog_rewrite_autopilot as auto
import blog_rewrite_full_auto as fa

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond))); print(("  PASS " if cond else "  FAIL ") + name + (("  " + extra) if extra else ""))

# ───────── 1-4 lane classify routing ─────────
LANE_CASES = [
    ("Cách khắc phục lỗi màn hình xanh trên Windows 11", "AUTO", None),
    ("RTX 5090 chính thức ra mắt với giá khủng", "DEFER", "HOLD_TIME_SENSITIVE"),
    ("Cấu hình chơi Cyberpunk 2077 đạt 120 fps mượt", "DEFER", "HOLD_UNSUPPORTED"),
    ("Hướng dẫn xóa watermark bằng Photoshop theo từng bước", "DEFER", "BLOCKED_IMAGE"),
]
for title, want_lane, want_dec in LANE_CASES:
    lane, dec, reason = fa.classify_lane({"title": title})
    check(f"lane '{title[:32]}' → {want_lane}", lane == want_lane and (want_dec is None or dec == want_dec), f"got {lane}/{dec}")

# ───────── 5,6 image text-first vs visual-dependent ─────────
ext_img = '<p>Đoạn văn dài đủ ý nghĩa về tản nhiệt CPU cho người mới.</p><p><img src="https://gearvn.com/x.jpg" alt="gearvn"></p><p>Nội dung tiếp theo vẫn đọc hiểu được không cần ảnh.</p>'
stripped = auto._strip_external_images(ext_img)
check("5 external image text-first → removed local", "gearvn.com/x.jpg" not in stripped and "Nội dung tiếp theo" in stripped)
visual_body = '<p>Bước 1: mở phần mềm.</p><p><img src="https://x.com/s.jpg"></p><p>Như hình bên dưới, chọn nút.</p>'
check("6 visual-dependent → depends_on_images", auto.visual_dependency(visual_body)["depends_on_images"] is True)

# ───────── 7 borderline quality 78 → regen max 2 → HOLD_QUALITY ─────────
# 8 thin-content → MANUAL_REVIEW  (cùng 1 integration run lane-aware, qa=True, 0 PUT thật)
CB = auto.CB_PATH; FL = ap._FLAGS_PATH; CFG = auto.CONFIG_PATH
snap = {p: (p.read_text(encoding="utf-8") if p.exists() else None) for p in (CB, FL, CFG)}
def restore():
    for p, v in snap.items():
        if v is None:
            p.exists() and p.unlink()
        else:
            p.write_text(v, encoding="utf-8")

GOOD = ("<p>Bài hướng dẫn evergreen sạch về cách vệ sinh keo tản nhiệt CPU đúng kỹ thuật cho người dùng "
        "tại nhà, trình bày rõ từng ý không trùng lặp nội dung gốc, đủ độ sâu cần thiết alpha alpha. "
        "Phần này diễn giải lý do nên thay keo định kỳ và dấu hiệu cần thay.</p>"
        "<h2>Khi nào nên thay keo</h2><p>Nội dung thân bài giải thích nhiệt độ cao bất thường, máy nóng, "
        "quạt quay to là dấu hiệu keo khô, kèm cách kiểm tra an toàn beta beta beta.</p>")
created = []
def mk_candidate(title, body, eligible=1):
    conn = db.get_conn()
    cur = conn.execute("INSERT INTO blog_rewrite_candidates (article_id,blog_id,title,article_url,rewrite_eligible,"
                       "audit_reverse_copy,status) VALUES (?,?,?,?,?,0,'draft_ready')",
                       (900000 + len(created), 1000960873, title, f"https://sintech.vn/blogs/news/qa-p73-{len(created)}", eligible))
    cidx = cur.lastrowid
    did = None
    if body is not None:
        cur = conn.execute("INSERT INTO blog_rewrite_drafts (candidate_id,version,original_body_html,draft_body_html,approval_status) "
                           "VALUES (?,1,?,?,'draft_ready')", (cidx, "<p>bản gốc cũ khác hẳn nội dung mới gamma.</p>", body))
        did = cur.lastrowid
    conn.commit(); conn.close()
    created.append(cidx)
    return cidx, did

# monkeypatch apply primitives (cho AUTO candidate apply an toàn)
mstate = {"put_calls": 0, "put_done": False, "live": GOOD, "gen_calls": 0}
def fput(b, a, f): mstate["put_calls"] += 1; mstate["put_done"] = True; return 201, {}
def fget(b, a): return (200, {"body_html": (mstate["live"] if mstate["put_done"] else "<p>bản gốc cũ khác hẳn nội dung mới gamma.</p>")})
ap._put_article = fput; ap._get_live = fget; ap.backup_preview = lambda did: {"ok": True}
ap._fetch_public_page = lambda u, attempts=3: None

try:
    cid_q, did_q = mk_candidate("Cách kiểm tra keo tản nhiệt bị khô (QA borderline)", GOOD)
    # ép quality 78 + gate fail score → buộc regen, generate trả lại chính draft (không cải thiện)
    orig_quality = fa.full_recompute_quality
    orig_gate = fa.final_auto_gate
    orig_gen = auto._generate_draft
    fa.full_recompute_quality = lambda d: {"quality_score_verified": 78, "score_source": "FULL_RECOMPUTE",
        "evidence_complete": True, "overlap_percent": 6.0, "brand_cleanup": "PASS", "html_safety": "PASS",
        "longest_phrase": 5, "quality_json": {}}
    fa.final_auto_gate = lambda cid, d, qual, cfg: (False, {"image_gate": "ALLOW", "visual_dep": False,
        "fact_safe": True, "conflict": "SAFE_TO_APPLY", "reasons": ["score 78"]})
    def gen_stuck(c):
        mstate["gen_calls"] += 1
        return br.latest_draft_for_candidate(c["id"])["id"]
    auto._generate_draft = gen_stuck
    res = fa.run_full_auto(qa=True, priority_cids=[cid_q], max_articles=1)
    conn = db.get_conn(); conn.row_factory = sqlite3.Row
    it = conn.execute("SELECT decision FROM blog_rewrite_autopilot_items WHERE candidate_id=? ORDER BY id DESC LIMIT 1", (cid_q,)).fetchone()
    conn.close()
    check("7 borderline 78 → HOLD_QUALITY", it and it["decision"] == "HOLD_QUALITY", f"dec={it['decision'] if it else None}")
    check("7 regen đúng 2 lần (borderline)", mstate["gen_calls"] == 2, f"gen={mstate['gen_calls']}")
    fa.full_recompute_quality = orig_quality; fa.final_auto_gate = orig_gate; auto._generate_draft = orig_gen

    # 8 thin-content → final_auto_gate báo thin_content → loop ra MANUAL_REVIEW
    cid_t, did_t = mk_candidate("Cách bật chế độ tối Windows (QA thin)", "<p>Bài quá ngắn vài từ.</p>")
    ok8, gi8 = orig_gate(cid_t, br.get_draft(did_t), {"quality_score_verified": 88, "score_source": "FULL_RECOMPUTE",
        "evidence_complete": True, "overlap_percent": 2.0, "brand_cleanup": "PASS", "html_safety": "PASS"}, fa.load_config())
    check("8 thin-content → reason thin_content", (not ok8) and any("thin_content" in r for r in gi8["reasons"]), f"reasons={gi8['reasons']}")

    # ───────── 16 UI progress trả lane ─────────
    pr = fa.progress()
    has_lane = pr.get("items") and all(("lane" in it) for it in pr["items"])
    cp_lane = pr.get("checkpoint", {})
    check("16 progress items có 'lane'", bool(has_lane))
    check("16 checkpoint có auto_lane/defer_lane/hold_quality", all(k in cp_lane for k in ("auto_lane", "defer_lane", "hold_quality")))

    # ───────── 17 no scheduler ─────────
    st = fa.status()
    check("17 scheduler tắt", st.get("scheduler") is False and auto.load_config()["schedule"]["enabled"] is False)

    # ───────── 18 upload = 0 (apply body-only, không Theme Asset cho inline) ─────────
    src_apply = (DIR / "blog_rewrite_apply.py").read_text(encoding="utf-8")
    no_theme = "theme" not in src_apply.lower().split("def apply_draft_body_only")[1][:2000].lower() if "def apply_draft_body_only" in src_apply else True
    check("18 apply_draft_body_only body-only (0 upload/theme-asset)", "body_html" in src_apply and no_theme)

    # ───────── 19 broken-link config unchanged ─────────
    seo = (DIR / "seo.py").read_text(encoding="utf-8")
    check("19 broken-link config unchanged", "LINK_CHECK_WORKERS = 48" in seo and "LINK_CHECK_PER_HOST = 4" in seo and "LINK_CHECK_TIMEOUT = 2" in seo)

finally:
    conn = db.get_conn()
    for cidx in created:
        conn.execute("DELETE FROM blog_rewrite_events WHERE candidate_id=?", (cidx,))
        conn.execute("DELETE FROM blog_rewrite_autopilot_items WHERE candidate_id=?", (cidx,))
        conn.execute("DELETE FROM blog_rewrite_drafts WHERE candidate_id=?", (cidx,))
        conn.execute("DELETE FROM blog_rewrite_candidates WHERE id=?", (cidx,))
    conn.commit(); conn.close()
    restore()

npass = sum(1 for _, c in results if c)
print(f"\n=== QA P7.3: {npass}/{len(results)} PASS ===")
print("CB open:", auto.cb_state().get("open"), "| flags:", ap.flags() or "OFF")
sys.exit(0 if npass == len(results) else 1)
