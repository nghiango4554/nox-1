# -*- coding: utf-8 -*-
"""Cleanup unused images in _Sintech_Marketing_Hub_Asset_Storage_ SP.

Logic safe:
  1. Get full image list of asset storage SP (haravan_id 1074465986)
  2. Scan content_jobs synced/approved → collect URLs đang dùng trong body
  3. Tìm intersection → ảnh dùng giữ lại; phần còn lại = ảnh không dùng
  4. DELETE qua Haravan API: DELETE /products/{pid}/images/{img_id}.json
  5. Report: deleted count, remaining count
"""
import os, sys, io, json, sqlite3, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import haravan_client

ASSET_SP = 1074465986
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'posts.db')


def collect_used_urls() -> set:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT ai_body_md, edited_body_html FROM content_jobs WHERE status IN ('synced','approved','draft','text_done')")
    used = set()
    for body_md, body_html in cur.fetchall():
        text = (body_md or '') + ' ' + (body_html or '')
        for m in re.finditer(r'https?://[^\s"<>)]+', text):
            url = m.group(0).rstrip('.,;:')
            used.add(url)
    conn.close()
    return used


def main():
    print(f'Loading asset storage product {ASSET_SP}...')
    prod = haravan_client.get_product(ASSET_SP)
    imgs = prod.get('images', [])
    print(f'  Total images: {len(imgs)}')

    print('Collecting URLs used in content_jobs (synced/approved/draft/text_done)...')
    used_urls = collect_used_urls()
    print(f'  Used URLs (toàn bài): {len(used_urls)}')

    to_delete = []
    keep = []
    for img in imgs:
        src = img.get('src', '')
        if src in used_urls:
            keep.append(img)
        else:
            to_delete.append(img)

    print()
    print(f'Keep (đang dùng): {len(keep)}')
    print(f'Delete (không dùng): {len(to_delete)}')
    print()

    if not to_delete:
        print('Không có ảnh nào để xóa.')
        return

    # Confirm via env var or arg
    if '--yes' not in sys.argv:
        print('Add --yes để chạy delete. Hiện tại chỉ dry-run.')
        return

    print('Deleting unused images...')
    deleted = 0
    failed = 0
    for img in to_delete:
        img_id = img.get('id')
        if not img_id:
            continue
        try:
            haravan_client._request('DELETE', f'/products/{ASSET_SP}/images/{img_id}.json')
            deleted += 1
            print(f'  [{deleted}/{len(to_delete)}] deleted img_id={img_id}')
        except Exception as e:
            failed += 1
            print(f'  FAIL img_id={img_id}: {e}')

    print()
    print(f'Done: deleted={deleted}, failed={failed}, kept={len(keep)}')

    # Re-check
    prod_after = haravan_client.get_product(ASSET_SP)
    print(f'Asset storage now has: {len(prod_after.get("images", []))} images (free slots: {90 - len(prod_after.get("images", []))})')


if __name__ == '__main__':
    main()
