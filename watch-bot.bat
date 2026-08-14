@echo off
setlocal EnableExtensions
cd /d "%~dp0"

REM Discord bot 24/7 — all licenses go to Supabase.
REM Leave this window open (or minimized). Restarts if the bot crashes.

set "PYEXE="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined PYEXE where py >nul 2>&1 && (
  for /f "delims=" %%I in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
)
if not defined PYEXE (
  echo [ERROR] Python 3.12 required. Install from https://www.python.org/downloads/
  pause
  exit /b 1
)

echo [dotx] Bot watchdog — Supabase database. Close window to stop.
echo.

:loop
"%PYEXE%" run_dotx.py
echo.
echo [dotx] Bot stopped. Restarting in 5s...
timeout /t 5 /nobreak >nul
goto loop
