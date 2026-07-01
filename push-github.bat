@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PATH=C:\Program Files\nodejs;%APPDATA%\npm;%LOCALAPPDATA%\Python\bin;%LOCALAPPDATA%\Programs\Python\Python314;%LOCALAPPDATA%\Programs\Python\Python313;%LOCALAPPDATA%\Programs\Python\Python312;%PATH%"

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [ERROR] Python not found. Install Python from https://python.org
    pause
    exit /b 1
)

"%PY%" scripts\push_github.py
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo GitHub push failed. See errors above.
)

pause
exit /b %RC%
