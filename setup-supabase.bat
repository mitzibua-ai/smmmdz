@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo  dotx Supabase Setup
echo  ===================
echo.
echo  1. Open Supabase SQL Editor and run BOTH files:
echo     - supabase\schema.sql
echo     - supabase\rpc.sql
echo.
echo  2. Copy keys from Supabase - Settings - API:
echo     - anon public key  -^> deploy.config.json supabaseAnonKey
echo     - service_role key -^> deploy.config.json supabaseServiceRoleKey
echo.
echo  3. Run push-supabase.bat
echo.

start https://supabase.com/dashboard/project/bumuisxrzbteeymzeidh/sql/new
start https://supabase.com/dashboard/project/bumuisxrzbteeymzeidh/settings/api

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if defined PY "%PY%" scripts\push_supabase.py

pause
