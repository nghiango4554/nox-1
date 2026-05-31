@echo off
REM Wrapper chay audit_schema_all.py (Phase 4C Task 4 SEO Crawl Optimization)
REM Chay weekly Chu Nhat 03:00 qua Task Scheduler.
call "%~dp0env.bat"
cd /d "%MH_DIR%"

echo. >> data\backups\audit_schema.log
echo === %date% %time% === >> data\backups\audit_schema.log
"%PYTHON_BIN%" "_scripts\audit_schema_all.py" >> data\backups\audit_schema.log 2>&1
