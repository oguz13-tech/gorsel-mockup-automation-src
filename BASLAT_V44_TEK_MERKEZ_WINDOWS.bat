@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title GORSEL URETIM MERKEZI V4.4 - 3 GRUP TEK MERKEZ
if not exist "%~dp0WINDOWS_HIZLI_BASLAT.bat" (
  echo Windows baslaticisi bulunamadi: WINDOWS_HIZLI_BASLAT.bat
  pause
  exit /b 1
)
call "%~dp0WINDOWS_HIZLI_BASLAT.bat"
exit /b %ERRORLEVEL%
