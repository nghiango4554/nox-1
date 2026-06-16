# -*- coding: utf-8 -*-
"""QA P7.2 — 500-but-write reconcile + engine hardening. Monkeypatch, KHÔNG network/PUT thật.
Tạo test candidate+draft thật → chạy → assert → cleanup. Snapshot/restore CB+flags+config."""
import sys, io, json, sqlite3
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DIR = Path(__file__).parent.parent
sys.path.insert(0, str(DIR))
import db, blog_rewrite as br, blog_rewrite_apply as ap, blog_rewrite_autopilot as auto

ORIGINAL = ("<p>Bài viết gốc nói về cấu hình máy tính chơi game phổ thông giá rẻ "
            "với các linh kiện cơ bản phù hợp người mới bắt đầu lắp ráp tại nhà alpha alpha alpha. "
            "Đoạn này chứa nội dung đặc trưng riêng của bản gốc không trùng bản mới.</p>"
            "<h2>Mục gốc một</h2><p>Phần thân bài gốc trình bày chi tiết từng bước lựa chọn "
            "bo mạch chủ ổ cứng nguồn điện và tản nhiệt theo ngân sách của bản gốc beta beta beta.</p>")
DRAFT = ("<p>Bài viết được biên tập lại hoàn toàn mới với cách diễn đạt nguyên bản sạch sẽ "
         "tập trung trải nghiệm thực tế khi xây dựng dàn máy chơi game mượt mà gamma gamma gamma. "
         "Câu văn này hoàn toàn khác biệt so với bản gốc ban đầu không hề trùng lặp.</p>"
         "<h2>Phần mới một</h2><p>Nội dung thân bài mới giải thích rõ ràng tiêu chí chọn linh kiện "
         "cân đối hiệu năng và chi phí cho từng nhu cầu sử dụng cụ thể delta delta delta.</p>")
OTHER = ("<p>Một nội dung thứ ba hoàn toàn khác lạ không liên quan gì tới hai bản trên epsilon epsilon "
         "epsilon zeta zeta zeta nói về chủ đề nấu ăn và du lịch biển đảo mùa hè eta eta eta.</p>")

def public_wrap(body):
    return "<html><head><title>t</title></head><body><nav>menu trang chủ</nav><main>" + body + "</main><footer>chân trang liên hệ</footer></body></html>"

# ── snapshot state ──
CB = auto.CB_PATH; FL = ap._FLAGS_PATH; CFG = auto.CONFIG_PATH
snap = {p: (p.read_text(encoding="utf-8") if p.exists() else None) for p in (CB, FL, CFG)}

def restore():
    for p, v in snap.items():
        if v is None:
            if p.exists(): p.unlink()
        else:
            p.write_text(v, encoding="utf-8")

# ── test fixtures (real rows) ──
conn = db.get_conn()
cur = conn.execute("INSERT INTO blog_rewrite_candidates (article_id,blog_id,title,article_url,rewrite_eligible,"
                   "audit_reverse_copy,status) VALUES (?,?,?,?,1,0,'approved_local')",
                   (999000111, 1000960873, "QA P7.2 test article", "https://sintech.vn/blogs/news/qa-p72-test"))
CID = cur.lastrowid
cur = conn.execute("INSERT INTO blog_rewrite_drafts (candidate_id,version,original_body_html,draft_body_html,"
                   "approval_status) VALUES (?,1,?,?,'approved_local')", (CID, ORIGINAL, DRAFT))
DID = cur.lastrowid
conn.commit(); conn.close()
ART = 999000111

# ── monkeypatch ──
state = {"put_calls": 0, "put_done": False, "live_after": ("admin", 200, DRAFT), "public": None, "put_behavior": ("ok", 201)}
def fake_put(blog_id, article_id, fields):
    state["put_calls"] += 1; state["put_done"] = True
    kind, val = state["put_behavior"]
    if kind == "raise":
        raise val
    return val, {}
def fake_get_live(blog_id, article_id):
    if not state["put_done"]:
        return 200, {"body_html": ORIGINAL}           # fresh-conflict: live==original (SAFE)
    mode, code, body = state["live_after"]
    if mode == "admin":
        return code, ({"body_html": body} if code == 200 else {})
    return 502, {}                                     # admin down → ép public fallback
def fake_public(url, attempts=3):
    return state["public"]
def fake_backup(draft_id):
    return {"ok": True, "backup_status": "qa_noop"}

ap._put_article = fake_put
ap._get_live = fake_get_live
ap._fetch_public_page = fake_public
ap.backup_preview = fake_backup

def arm():
    FL.write_text(json.dumps({"BLOG_REWRITE_LIVE_APPLY_ENABLED": True,
        "BLOG_REWRITE_LIVE_ROLLBACK_ENABLED": False, "BLOG_REWRITE_BULK_APPLY_ENABLED": False}), encoding="utf-8")

def reset_row():
    c = db.get_conn()
    c.execute("UPDATE blog_rewrite_drafts SET applied_at=NULL, applied_draft_hash=NULL, apply_nonce=NULL WHERE id=?", (DID,))
    c.execute("UPDATE blog_rewrite_candidates SET status='approved_local' WHERE id=?", (CID,))
    c.commit(); c.close()
    state["put_calls"] = 0; state["put_done"] = False
    auto._cb_save({"open": False, "reason": None, "consecutive_generate_fail": 0, "consecutive_fact_fail": 0})

def run_apply():
    arm()
    res, code = ap.apply_draft_body_only(DID, confirm_phrase=f"APPLY PILOT ARTICLE {ART}",
                                         confirm_reviewed_draft=True, confirm_reviewed_images=True)
    return res

results = []
def check(name, cond, extra=""):
    results.append((name, cond, extra))
    print(("  PASS " if cond else "  FAIL ") + name + ("  " + extra if extra else ""))

try:
    # 1) PUT 201 + live draft → APPLIED (LIVE_VERIFIED), PUT=1
    reset_row(); state["put_behavior"] = ("ok", 201); state["live_after"] = ("admin", 200, DRAFT)
    r = run_apply()
    check("1 PUT201+draft → LIVE_VERIFIED/VERIFIED", r["state"] == "LIVE_VERIFIED" and r["verify_status"] == "VERIFIED", f"state={r['state']}")
    check("1 PUT count = 1", state["put_calls"] == 1, f"calls={state['put_calls']}")

    # 2) PUT 500 but live draft → APPLIED_RECONCILED, PUT=1, no retry
    reset_row(); state["put_behavior"] = ("ok", 500); state["live_after"] = ("admin", 200, DRAFT)
    r = run_apply()
    check("2 PUT500+draft → APPLIED_RECONCILED", r["state"] == "APPLIED_RECONCILED" and r["verify_status"] == "VERIFIED", f"state={r['state']}")
    check("2 PUT count = 1 (no retry)", state["put_calls"] == 1, f"calls={state['put_calls']}")

    # 3) PUT 502 but live draft → APPLIED_RECONCILED
    reset_row(); state["put_behavior"] = ("ok", 502); state["live_after"] = ("admin", 200, DRAFT)
    r = run_apply()
    check("3 PUT502+draft → APPLIED_RECONCILED", r["state"] == "APPLIED_RECONCILED", f"state={r['state']}")
    check("3 PUT count = 1", state["put_calls"] == 1, f"calls={state['put_calls']}")

    # 4) PUT timeout but live draft → APPLIED_RECONCILED
    import requests
    reset_row(); state["put_behavior"] = ("raise", requests.exceptions.Timeout("timeout")); state["live_after"] = ("admin", 200, DRAFT)
    r = run_apply()
    check("4 PUTtimeout+draft → APPLIED_RECONCILED", r["state"] == "APPLIED_RECONCILED", f"state={r['state']}")
    check("4 PUT count = 1", state["put_calls"] == 1, f"calls={state['put_calls']}")

    # 5) PUT 500 and live original → NOT_APPLIED_RETRYABLE, PUT=1
    reset_row(); state["put_behavior"] = ("ok", 500); state["live_after"] = ("admin", 200, ORIGINAL)
    r = run_apply()
    check("5 PUT500+original → NOT_APPLIED_RETRYABLE", r["state"] == "NOT_APPLIED_RETRYABLE", f"state={r['state']}")
    check("5 PUT count = 1 (no auto retry)", state["put_calls"] == 1, f"calls={state['put_calls']}")

    # 6) PUT 500 and live other → UNCERTAIN_POST_PUT, CB OPEN, PUT=1
    reset_row(); state["put_behavior"] = ("ok", 500); state["live_after"] = ("admin", 200, OTHER)
    r = run_apply()
    check("6 PUT500+other → UNCERTAIN_POST_PUT", r["state"] == "UNCERTAIN_POST_PUT", f"state={r['state']}")
    check("6 circuit breaker OPEN", auto.cb_state().get("open") is True)
    check("6 PUT count = 1", state["put_calls"] == 1, f"calls={state['put_calls']}")

    # 7) admin GET 502, public page draft → APPLIED_RECONCILED via PUBLIC_PAGE_FALLBACK
    reset_row(); state["put_behavior"] = ("ok", 201); state["live_after"] = ("admindown", 502, None); state["public"] = public_wrap(DRAFT)
    r = run_apply()
    check("7 adminGET502+publicDraft → APPLIED_RECONCILED", r["state"] == "APPLIED_RECONCILED", f"state={r['state']}")
    check("7 verify_source = PUBLIC_PAGE_FALLBACK", r.get("verify_source") == "PUBLIC_PAGE_FALLBACK", f"src={r.get('verify_source')}")
    state["public"] = None; state["live_after"] = ("admin", 200, DRAFT)

    # 8) Crash sau PUT → reconcile, KHÔNG re-PUT
    reset_row(); state["put_behavior"] = ("ok", 201)
    orig_reconcile = ap.reconcile_post_put
    def boom(*a, **k):
        raise RuntimeError("simulated crash after PUT")
    ap.reconcile_post_put = boom
    r = run_apply()
    ap.reconcile_post_put = orig_reconcile
    check("8 crash-sau-PUT → UNCERTAIN_POST_PUT", r["state"] == "UNCERTAIN_POST_PUT", f"state={r['state']}")
    check("8 PUT count = 1 (không re-PUT)", state["put_calls"] == 1, f"calls={state['put_calls']}")

    # 9) Double submit → PUT vẫn = 1
    reset_row(); state["put_behavior"] = ("ok", 201); state["live_after"] = ("admin", 200, DRAFT)
    r1 = run_apply()
    r2 = run_apply()  # lần 2: idempotency
    check("9 double-submit lần 2 already_applied", r2.get("already_applied") is True or r2.get("verify_status") == "VERIFIED", f"r2={r2.get('already_applied')}")
    check("9 tổng PUT = 1", state["put_calls"] == 1, f"calls={state['put_calls']}")

    # 10) Resume checkpoint: bài đã applied KHÔNG chạy lại (queue_candidates loại trừ status=applied)
    import blog_rewrite_full_auto as fa
    # đảm bảo trạng thái applied từ case 9
    st = br.get_candidate(CID).get("status")
    q_ids = [c["id"] for c in fa.queue_candidates()]
    check("10 candidate applied sau reconcile", st == "applied", f"status={st}")
    check("10 queue_candidates loại bài applied", CID not in q_ids)

finally:
    # cleanup test rows + events + restore state
    conn = db.get_conn()
    conn.execute("DELETE FROM blog_rewrite_events WHERE candidate_id=?", (CID,))
    conn.execute("DELETE FROM blog_rewrite_drafts WHERE candidate_id=?", (CID,))
    conn.execute("DELETE FROM blog_rewrite_candidates WHERE id=?", (CID,))
    conn.commit(); conn.close()
    restore()

npass = sum(1 for _, c, _ in results if c)
print(f"\n=== QA P7.2: {npass}/{len(results)} PASS ===")
print("CB sau cleanup open:", auto.cb_state().get("open"))
print("flags sau cleanup:", ap.flags() or "OFF")
sys.exit(0 if npass == len(results) else 1)
