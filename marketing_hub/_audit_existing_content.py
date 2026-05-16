"""Audit Haravan content sẵn có cho các collection pending.

Flow:
  1. ALTER TABLE thêm column existing_body_len (idempotent)
  2. Với mỗi job pending có haravan_id, fetch Haravan smart_collection / custom_collection
  3. Đếm text content thuần (strip HTML, không khoảng trắng dư)
  4. Nếu len ≥ THRESHOLD → status='existing' (đã có content, không cần gen)
  5. Update DB

Chạy: python _audit_existing_content.py
"""
import sys, io, sqlite3, urllib3, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
urllib3.disable_warnings()

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import haravan_client
from bs4 import BeautifulSoup
from collection_content_writer import sanitize_pasted_html

DB_PATH = HERE / "data" / "posts.db"
THRESHOLD = 200  # ≥ 200 ký tự text thuần coi như "đã có content"


def ensure_column(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(collection_jobs)")
    cols = [r[1] for r in cur.fetchall()]
    if "existing_body_len" not in cols:
        print("ALTER TABLE: add existing_body_len ...")
        cur.execute("ALTER TABLE collection_jobs ADD COLUMN existing_body_len INTEGER DEFAULT 0")
        conn.commit()
    else:
        print("Column existing_body_len OK")


def count_text(body_html: str) -> int:
    if not body_html:
        return 0
    # Lau wrapper rỗng kiểu Lenovo bug trước khi đếm
    cleaned = sanitize_pasted_html(body_html)
    soup = BeautifulSoup(cleaned or body_html, "lxml")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return len(text)


def fetch_body_len(hid: int) -> int:
    """Fetch body_html từ Haravan, trả về số ký tự text thuần. -1 nếu lỗi."""
    for ct in ("smart_collections", "custom_collections"):
        try:
            d = haravan_client._request("GET", f"/{ct}/{hid}.json")
            c = d.get(ct[:-1], {})
            body = c.get("body_html") or ""
            return count_text(body)
        except Exception:
            continue
    return -1


def process_one(job_row):
    jid, hid, title = job_row["id"], job_row["haravan_id"], job_row["collection_title"]
    n = fetch_body_len(hid)
    return jid, hid, title, n


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    ensure_column(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT id, haravan_id, collection_title FROM collection_jobs "
        "WHERE status='pending' AND haravan_id IS NOT NULL"
    )
    pending = cur.fetchall()
    print(f"Audit {len(pending)} pending jobs ...")

    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(process_one, j): j for j in pending}
        for i, fu in enumerate(as_completed(futures), 1):
            try:
                results.append(fu.result())
            except Exception as e:
                print(f"  err: {e}")
            if i % 10 == 0:
                print(f"  {i}/{len(pending)} done")

    # Update DB
    existing_count = pending_count = err_count = 0
    for jid, hid, title, n in results:
        if n < 0:
            err_count += 1
            continue
        if n >= THRESHOLD:
            existing_count += 1
            conn.execute(
                "UPDATE collection_jobs SET status='existing', existing_body_len=?, "
                "updated_at=datetime('now') WHERE id=?",
                (n, jid),
            )
            print(f"  ✓ #{jid:>3} ({n:>5}c) {title[:50]} → existing")
        else:
            pending_count += 1
            conn.execute(
                "UPDATE collection_jobs SET existing_body_len=?, updated_at=datetime('now') "
                "WHERE id=?",
                (n, jid),
            )
    conn.commit()
    conn.close()

    print()
    print("=" * 60)
    print(f"Done: {existing_count} đã có content (≥{THRESHOLD}c) → status=existing")
    print(f"      {pending_count} còn thiếu → giữ status=pending")
    print(f"      {err_count} fetch lỗi (giữ nguyên)")
    print("=" * 60)


if __name__ == "__main__":
    main()
