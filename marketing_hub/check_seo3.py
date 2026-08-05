import sys, io, json, re
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

# Load synced URLs from backup dir
backup_dir = Path(__file__).parent.parent / "data" / "title_meta_fix_backup"
synced_urls = set()
if backup_dir.exists():
    for f in backup_dir.glob("*.json"):
        try:
            u = json.loads(f.read_text(encoding='utf-8')).get('url')
            if u: synced_urls.add(u)
        except: pass
print(f"Synced URLs in backup: {len(synced_urls)}")

# TITLE_META_ISSUE_CODES (from seo.py)
CODES = {"no_title","title_long","title_short","no_meta","meta_long","meta_short",
         "duplicate_title","duplicate_meta"}

rows = conn.execute("""
    SELECT id, url, url_type, title, title_len, meta_desc, meta_desc_len,
           score, issues, last_crawled
    FROM seo_pages
    WHERE last_crawled IS NOT NULL AND url_type='product'
""").fetchall()
print(f"Product pages with last_crawled: {len(rows)}\n")

# Collect issue stats for unsynced
by_code = {}
anomalies = []

for r in rows:
    if r['url'] in synced_urls:
        continue  # synced → skip
    try:
        issue_list = json.loads(r['issues']) if r['issues'] else []
    except:
        issue_list = []
    codes = {it.get('code') for it in issue_list if it.get('code') in CODES}

    # title_long re-eval trên ĐỘ DÀI ĐẦY ĐỦ (cái Google đọc), trần 61c.
    # KHÔNG dùng bản đã strip suffix: 4/2637 trang tự chứa "Sintech" nên Haravan
    # không nối " – Sintech", strip rồi so 51 sẽ báo oan. Audit 5/8/2026.
    raw_title = r['title'] or ''
    fl = len(re.sub(r'\s+', ' ', raw_title).strip())
    if 'title_long' in codes and fl <= 61: codes.discard('title_long')
    if fl > 61 and 'no_title' not in codes: codes.add('title_long')

    if not codes:
        continue

    for c in codes:
        by_code[c] = by_code.get(c, 0) + 1

    # Detect anomalies:
    t = raw_title
    m = r['meta_desc'] or ''
    flags = list(codes)
    extra = []

    # meta_long exactly 320c = Haravan default truncation (bất thường)
    if r['meta_desc_len'] == 320:
        extra.append('META_EXACTLY_320c')
    # meta same as title
    if t and m and t.strip()[:50] == m.strip()[:50]:
        extra.append('META=TITLE')
    # title contains price (6+ digits)
    if re.search(r'\d{6,}', t):
        extra.append('PRICE_IN_TITLE')
    # title too generic (just product name no brand)
    if t and 'sintech' not in t.lower() and sl > 0:
        extra.append('NO_BRAND_IN_TITLE')

    if extra or 'no_title' in codes or 'no_meta' in codes:
        anomalies.append({
            'handle': r['url'].split('/products/')[-1].rstrip('/'),
            'title': t[:75],
            'meta': m[:100],
            'tl': sl, 'ml': r['meta_desc_len'] or 0,
            'score': r['score'],
            'codes': flags, 'extra': extra
        })

print(f"=== Issues breakdown (unsynced products): ===")
for code, cnt in sorted(by_code.items(), key=lambda x: -x[1]):
    print(f"  {code}: {cnt}")

print(f"\n=== Anomalies (no_title / no_meta / price / meta=320c): {len(anomalies)} ===")
# Show by category
no_title = [a for a in anomalies if 'no_title' in a['codes']]
no_meta = [a for a in anomalies if 'no_meta' in a['codes']]
price_in_title = [a for a in anomalies if 'PRICE_IN_TITLE' in a['extra']]
meta_320 = [a for a in anomalies if 'META_EXACTLY_320c' in a['extra']]

print(f"\n--- no_title ({len(no_title)}) ---")
for a in no_title[:10]:
    print(f"  score={a['score']} {a['handle'][:60]}")

print(f"\n--- no_meta ({len(no_meta)}) ---")
for a in no_meta[:10]:
    print(f"  score={a['score']} {a['handle'][:60]} | T: {a['title'][:60]}")

print(f"\n--- META = exactly 320c (Haravan default truncation) ({len(meta_320)}) ---")
for a in meta_320[:15]:
    print(f"  score={a['score']} [{a['ml']}c] {a['handle'][:55]}")
    print(f"    M: {a['meta']}")

print(f"\n--- PRICE in title ({len(price_in_title)}) ---")
for a in price_in_title[:10]:
    print(f"  {a['handle']}: {a['title']}")

conn.close()
