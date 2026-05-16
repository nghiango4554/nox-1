@echo off
REM Start Telegram bot self-service + restart-on-crash loop
cd /d "C:\Users\Nghia Dep Gai\.openclaw\workspace\marketing_hub"

:loop
echo [%date% %time%] Starting telegram_bot... >> telegram_bot.log
"C:\Users\Nghia Dep Gai\AppData\Local\Programs\Python\Python312\python.exe" -u telegram_bot.py >> telegram_bot.log 2>> telegram_bot.err.log
echo [%date% %time%] Bot exited (code %errorlevel%) restart in 10s >> telegram_bot.err.log
timeout /t 10 /nobreak >nul
goto loop
