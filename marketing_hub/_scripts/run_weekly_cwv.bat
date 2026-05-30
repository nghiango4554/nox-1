@echo off
REM Wrapper chain: snapshot CWV tuan hien tai -> diff vs tuan truoc
REM Chay moi Chu Nhat 02:00 qua Task Scheduler.
cd /d "C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub"

echo. >> data\backups\weekly_cwv.log
echo === %date% %time% === >> data\backups\weekly_cwv.log
"C:\Users\NGHIANGO\AppData\Local\Programs\Python\Python312\python.exe" "_scripts\weekly_cwv_snapshot.py" >> data\backups\weekly_cwv.log 2>&1
"C:\Users\NGHIANGO\AppData\Local\Programs\Python\Python312\python.exe" "_scripts\weekly_cwv_diff.py" >> data\backups\weekly_cwv.log 2>&1
