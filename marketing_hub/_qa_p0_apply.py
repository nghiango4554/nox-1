# -*- coding: utf-8 -*-
"""QA monkeypatch cho P9.1 apply — PUT=0 thật, snapshot/restore DB để không bẩn state."""
import json, sys
import db, blog_rewrite as br, blog_rewrite_apply as ap
import blog_rewrite_p0_apply as p91

PASS, FAIL = [], []
def chk(name, cond):
    (PASS if cond else FAIL).append(name)
    print(("  ✓ " if cond else "  ✗ FAIL ") + name)

# ── snapshot 5 drafts + candidates để restore sau QA ──
elig, excluded = p91.eligible()
snap = []
conn = db.get_conn()
for item, d in elig:
    row = conn.execute("SELECT id,applied_at,applied_draft_hash,apply_nonce,apply_result_json FROM blog_rewrite_drafts WHERE id=?", (d["id"],)).fetchone()
    cst = conn.execute("SELECT id,status FROM blog_rewrite_candidates WHERE id=?", (d["candidate_id"],)).fetchone()
    snap.append((dict(row), dict(cst)))
conn.close()

def restore():
    c = db.get_conn()
    for drow, crow in snap:
        c.execute("UPDATE blog_rewrite_drafts SET applied_at=?,applied_draft_hash=?,apply_nonce=?,apply_result_json=? WHERE id=?",
                  (drow["applied_at"], drow["applied_draft_hash"], drow["apply_nonce"], drow["apply_result_json"], drow["id"]))
        c.execute("UPDATE blog_rewrite_candidates SET status=? WHERE id=?", (crow["status"], crow["id"]))
    c.commit(); c.close()
    try: p91.CHECKPOINT.unlink()
    except Exception: pass

# ── PUT counter + captured payloads ──
PUT_CALLS = []   # (article_id, fields)
_PUT_RET = {"status": 201}
def fake_put(blog_id, article_id, fields):
    PUT_CALLS.append((article_id, dict(fields)))
    return _PUT_RET["status"], {}

# stateful GET: trả body theo scenario per article
# scenario: 'apply_ok' = preflight GET trả original, post-put GET trả p0
#           'conflict' = GET trả body lạ
#           '500write' = preflight original, put 500, post-put p0
_SCEN = {}          # article_id -> scenario
_GET_N = {}         # article_id -> số lần GET
_BODIES = {}        # article_id -> (original, p0, foreign)
def _load_bodies():
    for item, d in elig:
        c = br.get_candidate(d["candidate_id"])
        _BODIES[c["article_id"]] = (d.get("original_body_html") or "", d.get("draft_body_html") or "", "<p>BODY LẠ KHÁC HẲN ABC XYZ</p>")
def fake_get(blog_id, article_id):
    n = _GET_N.get(article_id, 0); _GET_N[article_id] = n + 1
    orig, p0, foreign = _BODIES[article_id]
    sc = _SCEN.get(article_id, "apply_ok")
    if sc == "conflict":
        return 200, {"id": article_id, "body_html": foreign, "title": "t", "handle": "h"}
    # apply_ok / 500write: lần đầu (preflight) = original, sau (verify) = p0
    body = orig if n == 0 else p0
    return 200, {"id": article_id, "body_html": body, "title": "t", "handle": "h"}

ap._put_article = fake_put
ap._get_live = fake_get
ap._fetch_public_page = lambda *a, **k: None   # ép dùng admin GET
_load_bodies()

print("=== T1: eligibility ===")
ranks = sorted(i["p0_rank"] for i, _ in elig)
chk("eligible đúng 5 bài [2,3,4,6,10]", ranks == [2, 3, 4, 6, 10])
chk("#7 blocked_image excluded", 7 in excluded["blocked_image"])
chk("theme-only excluded [1,8,9]", sorted(excluded["theme_only"]) == [1, 8, 9])
chk("manual-review excluded [5]", excluded["manual_review"] == [5])

print("=== T2: confirm phrase sai → no PUT ===")
PUT_CALLS.clear()
r = p91.run_apply(confirm_phrase="WRONG")
chk("phrase sai → ok False", r["ok"] is False)
chk("phrase sai → PUT=0", len(PUT_CALLS) == 0)

print("=== T3: apply_ok 5 bài → PUT đúng 1/bài, body-only ===")
PUT_CALLS.clear(); _GET_N.clear(); _SCEN.clear(); _PUT_RET["status"] = 201
r = p91.run_apply(confirm_phrase=p91.CONFIRM_PHRASE)
chk("ok True", r["ok"] is True)
chk("PUT count = 5", len(PUT_CALLS) == 5)
chk("applied = 5", r["applied"] == 5)
per_art = {}
for aid, f in PUT_CALLS: per_art[aid] = per_art.get(aid, 0) + 1
chk("PUT ≤ 1 mỗi bài", all(v == 1 for v in per_art.values()))
chk("payload body-only (chỉ id+body_html)", all(set(f.keys()) == {"id", "body_html"} for _, f in PUT_CALLS))
chk("KHÔNG có title/handle/tags/summary/author/featured", all(
    not any(k in f for k in ("title", "handle", "tags", "summary_html", "author", "published", "image")) for _, f in PUT_CALLS))
restore()

print("=== T4: conflict (live đổi) → skip, no PUT ===")
PUT_CALLS.clear(); _GET_N.clear()
_SCEN.clear()
for aid in _BODIES: _SCEN[aid] = "conflict"
r = p91.run_apply(confirm_phrase=p91.CONFIRM_PHRASE)
chk("conflict → PUT=0", len(PUT_CALLS) == 0)
chk("conflict count = 5", r["conflict"] == 5)
restore()

print("=== T5: 500-but-write → reconcile APPLIED_RECONCILED, no re-PUT ===")
PUT_CALLS.clear(); _GET_N.clear(); _SCEN.clear(); _PUT_RET["status"] = 500
r = p91.run_apply(confirm_phrase=p91.CONFIRM_PHRASE)
per_art = {}
for aid, f in PUT_CALLS: per_art[aid] = per_art.get(aid, 0) + 1
chk("500 → vẫn PUT đúng 1/bài (KHÔNG re-PUT)", all(v == 1 for v in per_art.values()) and len(PUT_CALLS) == 5)
chk("500 → applied_reconciled = 5", r["applied_reconciled"] == 5)
_PUT_RET["status"] = 201
restore()

print("=== T6: backup saved + rollback payload valid ===")
PUT_CALLS.clear(); _GET_N.clear(); _SCEN.clear()
r = p91.run_apply(confirm_phrase=p91.CONFIRM_PHRASE)
bk = sorted(p91.BACKUP_ROOT.glob("*/*.json"))
chk("backup file tạo ra", len(bk) >= 5)
# rollback 1 bài
aid0 = elig[0][1]["candidate_id"]
art0 = br.get_candidate(aid0)["article_id"]
PUT_CALLS.clear()
rb = p91.rollback(art0, confirm_phrase="WRONG")
chk("rollback phrase sai → no PUT", rb["ok"] is False and len(PUT_CALLS) == 0)
rb = p91.rollback(art0, confirm_phrase=p91.ROLLBACK_PHRASE)
chk("rollback đúng phrase → PUT 1 lần body-only", len(PUT_CALLS) == 1 and set(PUT_CALLS[0][1].keys()) == {"id", "body_html"})
restore()

print("=== T7: p0_preview KHÔNG dùng được trong apply blog-rewrite thường ===")
PUT_CALLS.clear()
p0_did = elig[0][1]["id"]
res, code = ap.apply_draft_body_only(p0_did, confirm_phrase="x", confirm_reviewed_draft=True, confirm_reviewed_images=True)
print("    → normal apply trả: ok=%s code=%s error=%s" % (res.get("ok"), code, str(res.get("error"))[:60]))
chk("normal apply từ chối p0_preview draft", (not res.get("ok")) and len(PUT_CALLS) == 0)
restore()

print("=== T8: static safety (no upload/rehost/theme/commit trong module) ===")
src = open("blog_rewrite_p0_apply.py", encoding="utf-8").read()
import re
chk("không upload/rehost/theme asset", not re.search(r"upload_|theme_asset|assets\.json|rehost\(", src))

# cleanup mọi backup QA
import shutil
for d in p91.BACKUP_ROOT.glob("*"):
    try: shutil.rmtree(d)
    except Exception: pass
try: p91.CHECKPOINT.unlink()
except Exception: pass

print("\n===== QA RESULT: %d PASS, %d FAIL =====" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", FAIL); sys.exit(1)
print("ALL PASS — PUT thật = 0 (mọi PUT đều monkeypatch). State restored.")
