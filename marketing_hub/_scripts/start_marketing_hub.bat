@echo off
REM Auto-start Marketing Hub Flask + restart-on-crash loop
call "%~dp0env.bat"
cd /d "%MH_DIR%"

:loop
echo [%date% %time%] Starting marketing_hub Flask... >> server.log
"%PYTHON_BIN%" app.py >> server.log 2>> server.err.log
echo [%date% %time%] Flask exited (code %errorlevel%) restart in 5s >> server.err.log
timeout /t 5 /nobreak >nul
goto loop
