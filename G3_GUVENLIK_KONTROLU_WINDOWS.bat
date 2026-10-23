@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title G3 Salt Okunur Veri ve SHA Denetimi
if exist "MERKEZ\.venv\Scripts\python.exe" (
  "MERKEZ\.venv\Scripts\python.exe" -B "MERKEZ\G3_GUVENLIK_KONTROLU.py"
) else (
  py -3.11 -B "MERKEZ\G3_GUVENLIK_KONTROLU.py"
)
if errorlevel 1 echo Kontrol basarisiz; ana programdan veri kaydedilmedi.
pause
