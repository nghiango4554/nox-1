import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import seo
urls = seo.fetch_sitemap_urls()
print(f"TOTAL: {len(urls)}")
print("FIRST 5:")
for u in urls[:5]:
    print(" -", u)
print("CLASSIFY (first 5):")
for u in urls[:5]:
    print(" -", seo.classify_url(u), "→", u)
