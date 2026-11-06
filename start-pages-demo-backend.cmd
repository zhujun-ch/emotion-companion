@echo off
setlocal
cd /d "%~dp0"
set "ENABLE_DEMO_PAGES=1"
if /i "%~1"=="lan" set "APP_HOST=0.0.0.0"
if not defined APP_HOST set "APP_HOST=127.0.0.1"
set "DB_BACKEND=sqlite"
call start-backend.cmd
