@echo off
title FiveM PC Check Scanner
setlocal EnableDelayedExpansion

cd /d "%~dp0"

set "PYTHON_EXE="

REM Prefer real Python install over Windows Store stub
if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Python\bin\python.exe"
)

if not defined PYTHON_EXE (
    where py >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=py"
)

if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    echo.
    echo [ERROR] Python was not found on this PC.
    echo Install Python 3 from https://www.python.org/downloads/
    echo Check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo Using: %PYTHON_EXE%
echo.

"%PYTHON_EXE%" main.py
set "EXITCODE=%ERRORLEVEL%"

if %EXITCODE% EQU 2 (
    echo.
    echo Scan failed - error details opened in Notepad.
    pause
    exit /b 2
)

if %EXITCODE% EQU 1 (
    echo.
    echo Scan complete - detections found. Result opened in Notepad.
) else (
    echo.
    echo Scan complete - no major issues. Result opened in Notepad.
)

timeout /t 3 >nul
exit /b %EXITCODE%
