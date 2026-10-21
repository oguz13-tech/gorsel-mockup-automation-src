@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title GORSEL MOCKUP - WINDOWS MERKEZ V3
echo Gorsel Uretim Merkezi V3 baslatiliyor.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -B merkez.py
) else (
  py -3 -B merkez.py
)
if errorlevel 1 (
  echo.
  echo Program acilmadi. Ilk kez kuruyorsaniz once KURULUM.bat dosyasini calistirin.
  pause
)
endlocal
