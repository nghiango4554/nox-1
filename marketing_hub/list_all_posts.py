import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import db
rows = db.list_posts(limit=999)
for r in rows:
    print(f"=== id={r['id']} code={r.get('code')} type={r.get('type')} status={r.get('status')} date={r.get('scheduled_date')} time={r.get('scheduled_time')} ===")
    print("LINK:", r.get('link') or '')
    print("CAPTION:")
    print(r.get('caption') or '')
    imgs = r.get('images')
    if imgs:
        try:
            arr = json.loads(imgs) if isinstance(imgs, str) else imgs
            print("IMAGES:", arr)
        except Exception:
            print("IMAGES_RAW:", imgs)
    print()
