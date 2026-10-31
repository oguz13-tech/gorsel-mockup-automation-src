@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Gorsel Uretim Merkezi V4.10.0
call "%~dp0BASLAT_V47_WINDOWS.bat"
set "rc=%errorlevel%"
if not "%rc%"=="0" (
  echo [HATA] Program acilisinda hata. Test Merkezindeki raporu sohbete gonderin.
  pause
)
exit /b %rc%
