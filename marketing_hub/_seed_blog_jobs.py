"""Seed blog_jobs từ seo_pages (đã crawl) + cross-match GSC click data.

Lý do: Haravan API /blogs.json đang trả 502 (lâu rồi). Trang /haravan/blogs cũng
đã workaround dùng seo_pages — seeder này theo cùng pattern.

Flow:
  1. db.seo_list_pages(url_type='blog', limit=500) → 286 blog URL crawled
  2. Parse URL https://sintech.vn/blogs/<blog_handle>/<handle> → tách handle
  3. Cross-match URL với gsc_cache.json để có click/imp/pos
  4. Upsert vào blog_jobs (UNIQUE blog_url) — status='pending', haravan_*=NULL
     (Sync sẽ lookup Haravan article_id lúc cần — defer cho tới khi API fix.)
"""
import sys
import io
import json
import re
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import db


BLOG_URL_RE = re.compile(r"https?://sintech\.vn/blogs/([^/]+)/([^/?#]+)")


def load_gsc_pages():
    cache_path = HERE / "data" / "gsc_cache.json"
    if not cache_path.exists():
        print("WARN khong co gsc_cache.json - skip GSC cross-match.")
        return {}
    with open(cache_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    pages = data.get("performance", {}).get("pages", [])
    return {p["url"].rstrip("/"): p for p in pages}


def main():
    print("=" * 60)
    print("Seed blog_jobs tu seo_pages + GSC cross-match")
    print("=" * 60)

    blogs = db.seo_list_pages(url_type="blog", limit=500, sort="url")
    print(f"\nFound {len(blogs)} blog URL trong seo_pages")

    gsc_pages = load_gsc_pages()
    print(f"GSC cache: {len(gsc_pages)} URL co click data")

    conn = db.get_conn()
    now = datetime.now().isoformat(timespec="seconds")

    total_inserted = total_updated = total_skipped = 0

    for b in blogs:
        url = (b.get("url") or "").strip()
        if not url:
            total_skipped += 1
            continue

        m = BLOG_URL_RE.match(url)
        if not m:
            total_skipped += 1
            continue
        blog_handle, handle = m.group(1), m.group(2)

        title = b.get("title") or handle
        word_count = b.get("word_count") or 0

        url_clean = url.rstrip("/")
        gsc = gsc_pages.get(url_clean) or gsc_pages.get(url) or {}
        click = gsc.get("click", 0)
        imp = gsc.get("imp", 0)
        pos = gsc.get("pos", 0.0)

        existing = conn.execute(
            "SELECT id FROM blog_jobs WHERE blog_url = ?", (url,)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE blog_jobs SET
                  handle = ?, article_title = ?,
                  click = ?, impression = ?, pos = ?,
                  word_count = COALESCE(?, word_count),
                  updated_at = ?
                WHERE id = ?
            """, (handle, title, click, imp, pos, word_count, now, existing["id"]))
            total_updated += 1
        else:
            conn.execute("""
                INSERT INTO blog_jobs (
                  blog_url, handle, article_title, status,
                  click, impression, pos, word_count,
                  created_at, updated_at
                ) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """, (url, handle, title, click, imp, pos, word_count, now, now))
            total_inserted += 1

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print(f"Done: insert {total_inserted}, update {total_updated}, skip {total_skipped}")
    print("=" * 60)


if __name__ == "__main__":
    main()
