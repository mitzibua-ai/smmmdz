@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PATH=C:\Program Files\Git\cmd;%LOCALAPPDATA%\Programs\Git\cmd;%PATH%"

if "%~1"=="" (
    echo.
    echo  First-time GitHub push for dotx
    echo  ===============================
    echo.
    echo  1. Open your repo on github.com
    echo  2. Click the green "Code" button
    echo  3. Copy the HTTPS link ^(ends in .git^)
    echo.
    set /p REPO_URL="Paste your GitHub repo URL here: "
) else (
    set "REPO_URL=%~1"
)

if not defined REPO_URL (
    echo [ERROR] No URL entered.
    pause
    exit /b 1
)

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

"%PY%" scripts\setup_github.py "%REPO_URL%"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" echo. & echo Setup failed. See errors above.
pause
exit /b %RC%
