# -*- coding: utf-8 -*-
"""Backup posts.db daily.

Zips DB into data/backups/, keeps last 30 days.
Schedule via Task Scheduler daily 3:00 AM.
"""
import os, sys, io, zipfile, datetime, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, 'data', 'posts.db')
BACKUP_DIR = os.path.join(ROOT, 'data', 'backups')
KEEP_DAYS = 30


def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)

    if not os.path.exists(DB_PATH):
        print(f'[backup] DB not found: {DB_PATH}')
        return

    today = datetime.date.today().strftime('%Y-%m-%d')
    zip_path = os.path.join(BACKUP_DIR, f'posts_{today}.db.zip')

    if os.path.exists(zip_path):
        print(f'[backup] Already exists today: {zip_path}')
        return

    db_size = os.path.getsize(DB_PATH) / 1024 / 1024
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(DB_PATH, 'posts.db')
    zip_size = os.path.getsize(zip_path) / 1024 / 1024
    print(f'[backup] {today}: posts.db ({db_size:.1f}MB) -> {zip_path} ({zip_size:.1f}MB)')

    cutoff = datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)
    removed = 0
    for f in glob.glob(os.path.join(BACKUP_DIR, 'posts_*.db.zip')):
        name = os.path.basename(f).replace('posts_', '').replace('.db.zip', '')
        try:
            d = datetime.datetime.strptime(name, '%Y-%m-%d').date()
            if d < cutoff:
                os.remove(f)
                removed += 1
        except ValueError:
            pass
    if removed:
        print(f'[backup] Removed {removed} old backups (>{KEEP_DAYS} days)')


if __name__ == '__main__':
    main()
