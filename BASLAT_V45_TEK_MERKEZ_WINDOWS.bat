@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title GORSEL URETIM MERKEZI V4.5 - TUM GRUPLAR TEK PAKET
if not exist "%~dp0WINDOWS_HIZLI_BASLAT.bat" (
  echo V4.5 Windows baslaticisi bulunamadi.
  pause
  exit /b 1
)
call "%~dp0WINDOWS_HIZLI_BASLAT.bat"
exit /b %ERRORLEVEL%
