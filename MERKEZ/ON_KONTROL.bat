@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
".venv\Scripts\python.exe" -B ON_KONTROL.py
) else (
py -3 -B ON_KONTROL.py
)
pause
