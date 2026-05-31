@echo off
REM Start Telegram bot self-service + restart-on-crash loop
call "%~dp0env.bat"
cd /d "%MH_DIR%"

:loop
echo [%date% %time%] Starting telegram_bot... >> telegram_bot.log
"%PYTHON_BIN%" -u telegram_bot.py >> telegram_bot.log 2>> telegram_bot.err.log
echo [%date% %time%] Bot exited (code %errorlevel%) restart in 10s >> telegram_bot.err.log
timeout /t 10 /nobreak >nul
goto loop
