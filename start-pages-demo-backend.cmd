@echo off
setlocal
cd /d "%~dp0"
set "ENABLE_DEMO_PAGES=1"
if not defined DEMO_REVIEWER_PASSWORD set "DEMO_REVIEWER_PASSWORD=xinyu-demo"
if not defined APP_HOST set "APP_HOST=127.0.0.1"
set "DB_BACKEND=sqlite"
set "SQLITE_PATH=artifacts/pages_chat_demo.sqlite3"
call start-backend.cmd
