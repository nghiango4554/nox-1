@echo off
REM Wrapper chay audit_schema_all.py (Phase 4C Task 4 SEO Crawl Optimization)
REM Chay weekly Chu Nhat 03:00 qua Task Scheduler.
cd /d "C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub"

echo. >> data\backups\audit_schema.log
echo === %date% %time% === >> data\backups\audit_schema.log
"C:\Users\NGHIANGO\AppData\Local\Programs\Python\Python312\python.exe" "_scripts\audit_schema_all.py" >> data\backups\audit_schema.log 2>&1
