@echo off
REM Auto-commit local snapshot (no push) - prevents losing work from forgotten commits.
REM Registered as Task Scheduler "Marketing Hub Auto Commit" (daily).
call "%~dp0env.bat"
cd /d "%WORKSPACE_ROOT%"
git add -A
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "auto-snapshot %date% %time%" >> marketing_hub\data\backups\autocommit.log 2>&1
  echo [%date% %time%] committed >> marketing_hub\data\backups\autocommit.log
) else (
  echo [%date% %time%] no changes >> marketing_hub\data\backups\autocommit.log
)
