import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

# T6=2026-05-29, T7=2026-05-30, CN=2026-05-31
dates = ['2026-05-29', '2026-05-30', '2026-05-31']
labels = {'2026-05-29': 'Thứ 6 (29/5)', '2026-05-30': 'Thứ 7 (30/5)', '2026-05-31': 'CN (31/5)'}

for d in dates:
    posts = conn.execute("""
        SELECT id, title, type, status, scheduled_time, caption
        FROM posts WHERE scheduled_date=? ORDER BY scheduled_time
    """, (d,)).fetchall()
    print(f"\n=== {labels[d]} — {len(posts)} bài ===")
    for p in posts:
        cap_preview = (p['caption'] or '')[:80].replace('\n', ' ')
        print(f"  [{p['status']}] {p['type']} | {p['scheduled_time']} | {p['title'] or cap_preview[:60]}")

conn.close()
