@echo off
REM Wrapper chain: snapshot CWV tuan hien tai -> diff vs tuan truoc
REM Chay moi Chu Nhat 02:00 qua Task Scheduler.
call "%~dp0env.bat"
cd /d "%MH_DIR%"

echo. >> data\backups\weekly_cwv.log
echo === %date% %time% === >> data\backups\weekly_cwv.log
"%PYTHON_BIN%" "_scripts\weekly_cwv_snapshot.py" >> data\backups\weekly_cwv.log 2>&1
"%PYTHON_BIN%" "_scripts\weekly_cwv_diff.py" >> data\backups\weekly_cwv.log 2>&1
