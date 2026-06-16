# -*- coding: utf-8 -*-
"""Blog Rewrite worker — P2 MOCK (KHÔNG gọi AI/network/Haravan).

Spawn bởi Flask qua sys.executable: python run_blog_rewrite_worker.py --job <id>
Đọc job → từng candidate: generating → mock draft → draft_ready. Heartbeat + cancel check.

P2: provider=mock, model=mock-blog-rewriter-v1. KHÔNG PUT, KHÔNG upload, KHÔNG mạng.
"""
import sys, os, time, argparse, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # marketing_hub on path
import db
import blog_rewrite as br

HEARTBEAT_EVERY = 1  # candidate


def _job_status(conn, jid):
    r = conn.execute("SELECT status FROM blog_rewrite_jobs WHERE id=?", (jid,)).fetchone()
    return r[0] if r else None


def _heartbeat(conn, jid, completed, failed):
    conn.execute("UPDATE blog_rewrite_jobs SET last_heartbeat_at=datetime('now'), "
                 "completed_count=?, failed_count=?, updated_at=datetime('now') WHERE id=?",
                 (completed, failed, jid))
    conn.commit()


def run(jid):
    conn = db.get_conn()
    # claim: queued → running
    row = conn.execute("SELECT status, provider FROM blog_rewrite_jobs WHERE id=?", (jid,)).fetchone()
    st = row["status"] if row else None
    provider = row["provider"] if row else "mock"
    if st not in ("queued",):
        print(f"[worker] job {jid} status={st}, bỏ qua")
        conn.close(); return
    conn.execute("UPDATE blog_rewrite_jobs SET status='running', started_at=datetime('now'), "
                 "last_heartbeat_at=datetime('now'), updated_at=datetime('now') WHERE id=?", (jid,))
    conn.execute("INSERT INTO blog_rewrite_events (job_id, event_type, detail_json) VALUES (?,?,?)",
                 (jid, "generate_started", json.dumps({"pid": os.getpid(), "provider": "mock"})))
    conn.commit()
    conn.close()

    cids = br.job_candidate_ids(jid)
    completed = failed = 0
    for cid in cids:
        conn = db.get_conn()
        if _job_status(conn, jid) == "cancel_requested":
            conn.execute("UPDATE blog_rewrite_jobs SET status='cancelled', finished_at=datetime('now') WHERE id=?", (jid,))
            conn.execute("INSERT INTO blog_rewrite_events (job_id, event_type, detail_json) VALUES (?,?,?)",
                         (jid, "cancelled", "{}"))
            conn.commit(); conn.close()
            print(f"[worker] job {jid} cancelled")
            return
        cand = conn.execute("SELECT * FROM blog_rewrite_candidates WHERE id=?", (cid,)).fetchone()
        conn.close()
        if not cand:
            failed += 1; continue
        cand = dict(cand)
        try:
            br._set_candidate_status(cid, "generating")
            br.record_event("generate_started", candidate_id=cid, job_id=jid, detail={"provider": provider})
            if provider == "mock":
                time.sleep(0.2)  # mô phỏng, KHÔNG network
                draft_id, ver = br.save_mock_draft(cand, jid)
                final_status = "draft_ready"
            else:
                # P3 — AI THẬT (1 pilot). KHÔNG PUT/upload/apply.
                import blog_rewrite_gen as gen
                cfg = json.loads((Path(__file__).parent.parent.parent / "state" / "haravan_token.json").read_text(encoding="utf-8"))
                obj = gen.generate_real_draft(cand, cfg, provider=provider)
                draft_id, ver, final_status = br.save_real_draft(cand, jid, obj)
            br._set_candidate_status(cid, final_status)
            br.record_event("generate_completed", candidate_id=cid, draft_id=draft_id, job_id=jid,
                            detail={"version": ver, "provider": provider, "status": final_status})
            completed += 1
        except Exception as e:
            failed += 1
            br._set_candidate_status(cid, "failed")
            br.record_event("generate_failed", candidate_id=cid, job_id=jid, detail={"error": str(e)[:160]})
        conn = db.get_conn(); _heartbeat(conn, jid, completed, failed); conn.close()

    conn = db.get_conn()
    final = "completed" if failed == 0 else "completed_with_errors"
    conn.execute("UPDATE blog_rewrite_jobs SET status=?, finished_at=datetime('now'), "
                 "completed_count=?, failed_count=?, updated_at=datetime('now') WHERE id=?",
                 (final, completed, failed, jid))
    conn.execute("INSERT INTO blog_rewrite_events (job_id, event_type, detail_json) VALUES (?,?,?)",
                 (jid, "generate_completed", json.dumps({"completed": completed, "failed": failed})))
    conn.commit(); conn.close()
    print(f"[worker] job {jid} done: completed={completed} failed={failed} status={final}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", type=int, required=True)
    a = ap.parse_args()
    try:
        db.init_db()
        run(a.job)
    except Exception as e:
        print(f"[worker] FATAL job {a.job}: {e}")
        sys.exit(1)
