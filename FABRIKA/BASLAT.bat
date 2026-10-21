@echo off
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "FABRIKA\BASLAT.ps1"
pause
