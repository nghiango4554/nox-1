@echo off
REM Wrapper chay weekly_empty_desc_scan.py (quet SP thieu mo ta hang tuan)
call "%~dp0env.bat"
cd /d "%MH_DIR%"
"%PYTHON_BIN%" "_scripts\weekly_empty_desc_scan.py" >> data\backups\empty_desc_scan.log 2>&1
