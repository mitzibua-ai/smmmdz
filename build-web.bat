@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [dotx] Building obfuscated production website...
python scripts\obfuscate_web.py --site
if errorlevel 1 (
  echo [ERROR] Build failed. Install Node.js from https://nodejs.org/
  pause
  exit /b 1
)

echo.
echo [OK] Obfuscated site is in _site\
echo      Push to GitHub to deploy, or open _site\index.html locally.
pause
