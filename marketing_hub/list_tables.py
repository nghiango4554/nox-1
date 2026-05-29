import sqlite3
conn = sqlite3.connect('data/posts.db')
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print(tables)
for t in tables:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
    print(f"  {t}: {cols}")
conn.close()
