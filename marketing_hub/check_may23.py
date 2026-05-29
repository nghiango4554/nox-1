import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

print("=== Activity log 23/5 ===")
rows = conn.execute("""
    SELECT ts, kind, icon, title, description FROM activity_log
    WHERE ts LIKE '2026-05-23%' ORDER BY ts
""").fetchall()
for r in rows:
    print(f"  [{r['ts'][:16]}] {r['icon']} {r['title']}")
    if r['description']: print(f"    {r['description'][:100]}")

print("\n=== Posts scheduled 23/5 ===")
posts = conn.execute("SELECT id, title, type, status FROM posts WHERE scheduled_date='2026-05-23'").fetchall()
for p in posts:
    print(f"  [{p['status']}] {p['type']} | {p['title'] or '(no title)'}")

conn.close()
