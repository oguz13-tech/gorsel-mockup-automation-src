@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Gorsel Uretim Merkezi V4.9.8
call "%~dp0BASLAT_V47_WINDOWS.bat"
set "rc=%errorlevel%"
if not "%rc%"=="0" (
  echo [HATA] Program acilisinda hata. Mesaji Test Merkezine veya sohbete aktar.
  pause
)
exit /b %rc%
