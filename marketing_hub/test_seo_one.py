import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import seo
url = "https://sintech.vn/products/laptop-acer-predator-triton-14-ai-pt14-52t-99tu-nh-u0gsv-001"
r = seo.crawl_one(url)
print(json.dumps({k: v for k, v in r.items() if k != 'issues'}, ensure_ascii=False, indent=2))
print("\nIssues:")
for i in json.loads(r["issues"]):
    print(f" [{i['level']}] {i['code']}: {i['msg']}")
