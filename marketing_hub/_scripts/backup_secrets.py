# -*- coding: utf-8 -*-
"""Backup chùm chìa khóa (.secrets/ + marketing_hub/.env/) hàng ngày.

Zip 2 folder credentials ra data/backups/secrets_YYYY-MM-DD.zip.
Giữ 30 file gần nhất, auto xóa cũ.

Schedule: Task Scheduler daily 3:05 AM (lệch 5 phút với backup_db để
không tranh CPU). Hoặc chạy manual:
  python marketing_hub/_scripts/backup_secrets.py

⚠️ SECURITY: file zip này CHỨA TOKEN GỐC (Google OAuth, Telegram,
OpenAI). KHÔNG sync lên cloud public. Để sync Google Drive private,
nén lại với 7-Zip + password trước. Hoặc giữ trên ổ cứng ngoài.
"""
import os, sys, io, zipfile, datetime, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCES = [
    os.path.join(ROOT, '.secrets'),
    os.path.join(ROOT, 'marketing_hub', '.env'),
]
BACKUP_DIR = os.path.join(ROOT, 'marketing_hub', 'data', 'backups')
KEEP_DAYS = 30


def _zip_folder(zf: zipfile.ZipFile, folder: str, arc_root: str):
    """Add tất cả file trong folder vào zip, giữ relative path."""
    if not os.path.exists(folder):
        print(f'[secrets] Skip missing: {folder}')
        return 0
    count = 0
    for dirpath, _, filenames in os.walk(folder):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, ROOT)
            zf.write(full, rel)
            count += 1
    print(f'[secrets] +{count} files from {arc_root}/')
    return count


def main():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    today = datetime.date.today().strftime('%Y-%m-%d')
    zip_path = os.path.join(BACKUP_DIR, f'secrets_{today}.zip')

    if os.path.exists(zip_path):
        print(f'[secrets] Already exists today: {zip_path}')
        return

    total = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for src in SOURCES:
            total += _zip_folder(zf, src, os.path.basename(src))

    if total == 0:
        os.remove(zip_path)
        print(f'[secrets] No source files found. Aborted.')
        return

    zip_kb = os.path.getsize(zip_path) / 1024
    print(f'[secrets] {today}: {total} files -> {zip_path} ({zip_kb:.1f}KB)')

    cutoff = datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)
    removed = 0
    for f in glob.glob(os.path.join(BACKUP_DIR, 'secrets_*.zip')):
        name = os.path.basename(f).replace('secrets_', '').replace('.zip', '')
        try:
            d = datetime.datetime.strptime(name, '%Y-%m-%d').date()
            if d < cutoff:
                os.remove(f)
                removed += 1
        except ValueError:
            pass
    if removed:
        print(f'[secrets] Removed {removed} old backups (>{KEEP_DAYS} days)')


if __name__ == '__main__':
    main()
