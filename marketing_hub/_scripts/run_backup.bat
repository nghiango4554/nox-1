@echo off
REM Wrapper run backup_db.py
call "%~dp0env.bat"
cd /d "%MH_DIR%"
"%PYTHON_BIN%" "_scripts\backup_db.py" >> data\backups\backup.log 2>&1
