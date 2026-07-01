@echo off
title dotx PC Check Tool
setlocal EnableDelayedExpansion

cd /d "%~dp0"

if not exist "main.py" (
    echo.
    echo [ERROR] main.py was not found in this folder.
    echo.
    echo Do NOT run this from inside the zip or WinRAR.
    echo.
    echo 1. Right-click dotx-pc-check.zip -^> Extract All
    echo 2. Open the extracted dotx-pc-check folder
    echo 3. Double-click run_scan.bat in that folder
    echo.
    pause
    exit /b 1
)

if not exist "pccheck\" (
    echo.
    echo [ERROR] The pccheck folder is missing.
    echo Extract the full zip before running run_scan.bat.
    echo.
    pause
    exit /b 1
)

set "PYTHON_EXE="

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

echo.
echo  ==============================
echo   dotx PC Check Tool
echo  ==============================
echo.

set "DOTX_PIN="
if not "%~1"=="" set "DOTX_PIN=%~1"

if not defined DOTX_PIN (
    set /p DOTX_PIN=Enter your 6-digit dotx PIN: 
)

if not defined DOTX_PIN (
    echo No PIN entered.
    pause
    exit /b 1
)

echo Using PIN: !DOTX_PIN!
echo.
echo Scanning... please wait.
echo.

"%PYTHON_EXE%" main.py --pin !DOTX_PIN!
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

echo.
pause
exit /b %EXITCODE%
