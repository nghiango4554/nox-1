@echo off
REM Wrapper run backup_db.py
cd /d "C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub"

"C:\Users\Nghia Dep Gai\AppData\Local\Programs\Python\Python312\python.exe" "_scripts\backup_db.py" >> data\backups\backup.log 2>&1
