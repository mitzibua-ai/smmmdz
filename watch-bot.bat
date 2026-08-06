@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Discord bot 24/7 — all licenses go to Supabase.
REM Leave this window open (or minimized). Restarts if the bot crashes.

set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python313;%LOCALAPPDATA%\Programs\Python\Python314;%PATH%"

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

echo [dotx] Bot watchdog — Supabase database. Close window to stop.
echo.

:loop
"%PY%" run_dotx.py
echo.
echo [dotx] Bot stopped. Restarting in 5s...
timeout /t 5 /nobreak >nul
goto loop
