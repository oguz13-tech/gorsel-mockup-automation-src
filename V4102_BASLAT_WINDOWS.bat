@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Gorsel Uretim Merkezi V4.10.2 - Windows Aday
call "%~dp0BASLAT_V47_WINDOWS.bat"
set "rc=%errorlevel%"
if not "%rc%"=="0" (
 echo [HATA] Baslatma basarisiz. Lütfen hata penceresindeki neden/çözümü takip edin.
 pause
)
exit /b %rc%
