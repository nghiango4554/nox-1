@echo off
REM Wrapper run backup_secrets.py (.secrets/ + marketing_hub/.env/ daily zip)
call "%~dp0env.bat"
cd /d "%MH_DIR%"
"%PYTHON_BIN%" "_scripts\backup_secrets.py" >> data\backups\backup.log 2>&1
