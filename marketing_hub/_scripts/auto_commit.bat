@echo off
REM ── Auto-commit snapshot LOCAL (KHONG push) — chong mat viec do quen commit ──
REM Dang ky Task Scheduler "Marketing Hub Auto Commit" chay hang ngay.
cd /d "C:\Users\NGHIANGO\.openclaw\workspace\nox-1"
git add -A
git diff --cached --quiet && (
  echo [%date% %time%] no changes >> marketing_hub\data\backups\autocommit.log
) || (
  git commit -m "auto-snapshot %date% %time%" >> marketing_hub\data\backups\autocommit.log 2>&1
  echo [%date% %time%] committed >> marketing_hub\data\backups\autocommit.log
)
