@echo off

setlocal EnableExtensions EnableDelayedExpansion

title dotx - Railway First-Time Setup



cd /d "%~dp0"



echo.

echo  dotx Discord Bot - Railway Setup (first time)

echo  =============================================

echo.

echo  This will:

echo    1. Install Railway CLI (if needed)

echo    2. Log you into Railway (browser opens once)

echo    3. Create a NEW Railway project for this folder

echo    4. Copy your bot settings to Railway

echo    5. Upload and start the bot 24/7

echo.



where railway >nul 2>&1

if errorlevel 1 (

    where npm >nul 2>&1

    if errorlevel 1 (

        echo [ERROR] Node.js/npm not found. Install from https://nodejs.org then run this again.

        pause

        exit /b 1

    )

    echo Installing Railway CLI...

    call npm install -g @railway/cli

    if errorlevel 1 (

        echo [FAILED] Could not install Railway CLI.

        pause

        exit /b 1

    )

)



railway whoami >nul 2>&1

if errorlevel 1 (

    echo Opening browser to log into Railway...

    railway login

    if errorlevel 1 (

        echo [FAILED] Login did not complete.

        pause

        exit /b 1

    )

)



if not exist "discord_bot\config.json" (

    if exist "discord_bot\config.example.json" (

        echo Creating discord_bot\config.json from example...

        copy /Y "discord_bot\config.example.json" "discord_bot\config.json" >nul

        echo.

        echo [IMPORTANT] Edit discord_bot\config.json with your bot token and channel IDs,

        echo             then run this script again.

        echo.

        notepad "discord_bot\config.json"

        pause

        exit /b 0

    ) else (

        echo [ERROR] discord_bot\config.json not found.

        pause

        exit /b 1

    )

)



if exist ".railway\config.json" (

    echo This folder is already linked to a Railway project.

    set /p USE_NEW="Create a NEW project anyway? (y/n): "

    if /i not "!USE_NEW!"=="y" (

        echo Skipping project creation. Syncing variables and deploying...

        goto deploy

    )

)



echo.

echo Creating new Railway project "dotx-discord-bot" and uploading your folder...

echo.



railway up --new --name dotx-discord-bot --detach -y

if errorlevel 1 (

    echo [FAILED] Could not create project or start deploy.

    pause

    exit /b 1

)



:deploy

echo.

echo Pushing bot settings to Railway...

python scripts\railway_sync_env.py

if errorlevel 1 (

    echo [FAILED] Could not set environment variables.

    pause

    exit /b 1

)



echo.

echo Redeploying with your bot token and channel IDs...

railway up --detach

if errorlevel 1 (

    echo [FAILED] Deploy did not start.

    pause

    exit /b 1

)



echo.

echo =============================================

echo  DONE - Your bot is on Railway (24/7)

echo =============================================

echo.

echo  Dashboard:  railway open

echo  Live logs:  railway logs

echo  Redeploy:   double-click push-railway.bat

echo.

echo  In Discord, run /ticket-panel once in your support channel.

echo.

pause

exit /b 0

