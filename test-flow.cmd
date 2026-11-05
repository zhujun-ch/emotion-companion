@echo off
cd /d "%~dp0"
set "PYTHONUTF8=1"
"%~dp0.venv\Scripts\python.exe" test_flow.py
pause
