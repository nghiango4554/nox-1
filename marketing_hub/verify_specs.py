import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import db
PAT = re.compile(r'⚙️ THÔNG SỐ NỔI BẬT\n([\s\S]+?)\n\n')
for pid in [3, 8, 14]:
    p = db.get_post(pid)
    m = PAT.search(p.get("caption", ""))
    print(f"=== FB{pid:04d} ===")
    print(m.group(1) if m else "(no spec block)")
    print()
