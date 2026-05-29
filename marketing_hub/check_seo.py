import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3, re

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

# haravan_products: meta_title, meta_description
# "unsynced" means meta_title was edited but not pushed - but actually
# the page may track this differently. Let's look at all products with meta issues.

rows = conn.execute("""
    SELECT handle, title, meta_title, meta_description,
           LENGTH(COALESCE(meta_title,'')) as tl,
           LENGTH(COALESCE(meta_description,'')) as ml,
           audit_score
    FROM haravan_products
    WHERE status = 'active'
    ORDER BY COALESCE(audit_score, 0) ASC
""").fetchall()

print(f"Active products total: {len(rows)}\n")

critical = []
long_t = []
short_m = []
no_brand = []
suspicious = []

for r in rows:
    handle = r['handle']
    title = r['title'] or ''
    t = r['meta_title'] or ''
    m = r['meta_description'] or ''
    tl = r['tl']
    ml = r['ml']

    flags = []

    if not t: flags.append('NO_META_TITLE')
    if not m: flags.append('NO_META_DESC')
    if tl > 65: flags.append(f'TITLE_LONG({tl}c)')
    if 0 < tl < 20: flags.append(f'TITLE_SHORT({tl}c)')
    if 0 < ml < 80: flags.append(f'META_SHORT({ml}c)')
    if ml > 165: flags.append(f'META_LONG({ml}c)')

    # Placeholder / broken content
    for kw in ['[', '{{', 'TODO', 'lorem', 'undefined', 'null', 'N/A', '...']:
        if kw in t or kw in m:
            flags.append(f'PLACEHOLDER')
            break

    # Title same as product title (no SEO optimization)
    if t and title and t.strip().lower() == title.strip().lower():
        flags.append('META_TITLE=PRODUCT_TITLE')

    # No brand
    if t and 'sintech' not in t.lower():
        flags.append('NO_BRAND')

    # Numbers / prices in meta title (might be stale)
    if re.search(r'\d{6,}', t):  # 6+ digit number = likely price
        flags.append('PRICE_IN_TITLE')

    if flags:
        entry = {
            'handle': handle,
            'product_title': title[:60],
            'meta_title': t[:80],
            'meta_desc': m[:120],
            'tl': tl, 'ml': ml,
            'score': r['audit_score'],
            'flags': flags
        }
        if 'NO_META_TITLE' in flags or 'NO_META_DESC' in flags or 'PLACEHOLDER' in flags:
            critical.append(entry)
        elif any('LONG' in f or 'SHORT' in f for f in flags):
            if 'TITLE_LONG' in ' '.join(flags):
                long_t.append(entry)
            if 'META_SHORT' in ' '.join(flags):
                short_m.append(entry)
        if 'PRICE_IN_TITLE' in flags:
            suspicious.append(entry)

print(f"=== CRITICAL (no title/meta/placeholder): {len(critical)} ===")
for i in critical[:30]:
    print(f"  [{','.join(i['flags'])}] {i['handle']}")
    if i['meta_title']: print(f"    T: {i['meta_title']} ({i['tl']}c)")
    if i['meta_desc']: print(f"    M: {i['meta_desc']} ({i['ml']}c)")

print(f"\n=== TITLE > 65c: {len(long_t)} ===")
for i in long_t[:20]:
    print(f"  [{i['tl']}c] {i['handle']}: {i['meta_title']}")

print(f"\n=== META < 80c: {len(short_m)} ===")
for i in short_m[:20]:
    print(f"  [{i['ml']}c] {i['handle']}: {i['meta_desc']}")

print(f"\n=== PRICE IN TITLE (có thể stale): {len(suspicious)} ===")
for i in suspicious[:20]:
    print(f"  {i['handle']}: {i['meta_title']}")

conn.close()
