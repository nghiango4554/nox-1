@echo off
REM Wrapper chay weekly_empty_desc_scan.py (quet SP thieu mo ta hang tuan)
cd /d "C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub"
"C:\Users\NGHIANGO\AppData\Local\Programs\Python\Python312\python.exe" "_scripts\weekly_empty_desc_scan.py" >> data\backups\empty_desc_scan.log 2>&1
