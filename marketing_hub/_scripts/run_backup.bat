@echo off
REM Wrapper run backup_db.py
cd /d "C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub"

"C:\Users\NGHIANGO\AppData\Local\Programs\Python\Python312\python.exe" "_scripts\backup_db.py" >> data\backups\backup.log 2>&1
