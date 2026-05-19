@echo off
REM Auto-start Marketing Hub Flask + restart-on-crash loop
cd /d "C:\Users\NGHIANGO\.openclaw\workspace\nox-1\marketing_hub"

:loop
echo [%date% %time%] Starting marketing_hub Flask... >> server.log
"C:\Users\NGHIANGO\AppData\Local\Programs\Python\Python312\python.exe" app.py >> server.log 2>> server.err.log
echo [%date% %time%] Flask exited (code %errorlevel%) restart in 5s >> server.err.log
timeout /t 5 /nobreak >nul
goto loop
