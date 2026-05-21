"""DRY-RUN: phân loại draft collection theo blueprint MỚI vs cũ. KHÔNG ghi gì."""
import re, db

conn = db.get_conn()
rows = conn.execute(
    "SELECT id, collection_title, status, ai_generated_at, edited_title, edited_meta, edited_body_html "
    "FROM collection_jobs WHERE status='draft' AND edited_body_html IS NOT NULL AND edited_body_html != '' "
    "ORDER BY ai_generated_at ASC, id ASC"
).fetchall()
conn.close()

keep, reset = [], []
print(f"Tổng draft có nội dung: {len(rows)}\n")
for r in rows:
    j = dict(r)
    body = j["edited_body_html"] or ""
    h2s = re.findall(r"(?i)<h2[^>]*>(.*?)</h2>", body)
    chunks = re.split(r"(?i)<h2[^>]*>", body)
    # H3 trong 2 H2 đầu (taxonomy = dấu hiệu blueprint mới)
    h3_first2 = 0
    for i in (1, 2):
        if i < len(chunks):
            h3_first2 += chunks[i].lower().count("<h3")
    first_tbl = next((i for i in range(1, len(chunks)) if "<table" in chunks[i].lower()), None)
    avg_h2 = (sum(len(re.sub(r"<[^>]+>","",h).split()) for h in h2s) / len(h2s)) if h2s else 0
    meta_len = len(j.get("edited_meta") or "")

    # KEEP nếu: có H3 taxonomy trong 2 H2 đầu + bảng từ H2#3 + H2 ngắn
    is_new = (h3_first2 >= 2) and (first_tbl is None or first_tbl >= 3) and (avg_h2 <= 11)
    verdict = "KEEP ✅" if is_new else "RESET ↩"
    (keep if is_new else reset).append(j["id"])
    h1 = re.sub(r"<[^>]+>","",h2s[0]).strip()[:42] if h2s else "(no h2)"
    print(f"#{j['id']:<3} {verdict} | gen={j['ai_generated_at']} | H2={len(h2s)} avgLen={avg_h2:.1f} "
          f"H3_top2={h3_first2} tbl@H2#{first_tbl} meta={meta_len}c | {j['collection_title'][:24]} | H2#1='{h1}'")

print(f"\n=== KEEP ({len(keep)}): {keep}")
print(f"=== RESET ({len(reset)}): {reset}")
