import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3

conn = sqlite3.connect('data/posts.db')
conn.row_factory = sqlite3.Row

# Check haravan_products meta fields
r = conn.execute("SELECT COUNT(*) as c FROM haravan_products WHERE meta_title IS NOT NULL AND meta_title != ''").fetchone()
print(f"haravan_products with meta_title filled: {r['c']}")

# Check seo_pages
r2 = conn.execute("SELECT COUNT(*) as c FROM seo_pages").fetchone()
print(f"seo_pages total: {r2['c']}")
r3 = conn.execute("SELECT COUNT(*) as c FROM seo_pages WHERE url_type='product'").fetchone()
print(f"seo_pages products: {r3['c']}")

# Check content_jobs: edited_title / edited_meta, sync status
r4 = conn.execute("SELECT COUNT(*) as c FROM content_jobs WHERE status='draft'").fetchone()
r5 = conn.execute("SELECT COUNT(*) as c FROM content_jobs WHERE synced_at IS NOT NULL").fetchone()
r6 = conn.execute("SELECT COUNT(*) as c FROM content_jobs WHERE status='draft' AND edited_meta IS NOT NULL AND edited_meta != ''").fetchone()
print(f"content_jobs draft: {r4['c']}, synced: {r5['c']}, draft+has_meta: {r6['c']}")

# Check seo_pages for products - what fields does it have for title/meta
sample = conn.execute("""
    SELECT url, title, title_len, meta_desc, meta_desc_len, score, issues
    FROM seo_pages WHERE url_type='product' ORDER BY score ASC LIMIT 20
""").fetchall()
print(f"\nSeo_pages product sample (lowest score):")
for r in sample:
    issues = r['issues'] or ''
    print(f"  score={r['score']} t={r['title_len']}c m={r['meta_desc_len']}c | {r['url'].split('/')[-1][:50]}")
    if issues:
        import json
        try:
            iss = json.loads(issues)
            for i in iss[:3]:
                print(f"    - {i}")
        except:
            print(f"    issues: {issues[:80]}")

conn.close()
