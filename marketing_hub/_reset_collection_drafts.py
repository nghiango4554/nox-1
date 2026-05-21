"""One-off: reset draft collection về 'pending' (AI chưa gen), trừ #19 → set 'synced'.
Theo yêu cầu vợ 2026-05-21. Có backup + verify. KHÔNG push Haravan."""
import os, shutil, sqlite3
from datetime import datetime

DB = "data/posts.db"
KEEP_SYNCED = 19  # bài giữ lại + set synced
now = datetime.now().isoformat(timespec="seconds")

# 1) Backup tươi
os.makedirs("data/backups", exist_ok=True)
stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
bak = f"data/backups/posts_pre-reset-collection-drafts_{stamp}.db"
shutil.copy2(DB, bak)
print(f"[backup] {bak}")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# 2) Lấy danh sách draft hiện tại
draft_ids = [r["id"] for r in cur.execute("SELECT id FROM collection_jobs WHERE status='draft' ORDER BY id")]
reset_ids = [i for i in draft_ids if i != KEEP_SYNCED]
print(f"[plan] draft hiện tại: {draft_ids}")
print(f"[plan] RESET -> pending ({len(reset_ids)}): {reset_ids}")
print(f"[plan] SYNCED         : [{KEEP_SYNCED}]")
assert KEEP_SYNCED in draft_ids, "#19 không ở trạng thái draft!"

# 3) Transaction
cur.execute("BEGIN")
# Reset 15 bài -> pending baseline (clear AI-gen artifacts; giữ flag manual_filled/excluded)
ph = ",".join("?" * len(reset_ids))
cur.execute(f"""
    UPDATE collection_jobs SET
        status='pending',
        edited_title=NULL, edited_meta=NULL, edited_body_html=NULL,
        ai_generated_at=NULL, synced_at=NULL,
        quality_score=NULL, readability_score=NULL, quality_breakdown=NULL,
        error=NULL,
        updated_at=?
    WHERE id IN ({ph})
""", [now, *reset_ids])
n_reset = cur.rowcount
# #19 -> synced (giữ nội dung)
cur.execute("""
    UPDATE collection_jobs SET status='synced', synced_at=?, error=NULL, updated_at=?
    WHERE id=?
""", [now, now, KEEP_SYNCED])
n_sync = cur.rowcount
con.commit()
print(f"[done] reset rows={n_reset}, sync rows={n_sync}")

# 4) Verify
print("\n=== STATUS COUNTS sau khi chạy ===")
for r in cur.execute("SELECT status, COUNT(*) c FROM collection_jobs GROUP BY status ORDER BY status"):
    print(f"  {r['status']:<10} {r['c']}")
print("\n=== Verify từng bài ===")
checkids = sorted(reset_ids + [KEEP_SYNCED])
phc = ",".join("?" * len(checkids))
for r in cur.execute(f"SELECT id,status,ai_generated_at,synced_at,edited_title,quality_score,length(COALESCE(edited_body_html,'')) blen FROM collection_jobs WHERE id IN ({phc}) ORDER BY id", checkids):
    print(f"  #{r['id']:<4} {r['status']:<8} gen={str(r['ai_generated_at'])[:16]:<16} sync={str(r['synced_at'])[:16]:<16} body={r['blen']:<6} q={r['quality_score']} title={'set' if r['edited_title'] else 'NULL'}")
con.close()
