@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Gorsel Uretim Merkezi V4.9.5
call "%~dp0BASLAT_V47_WINDOWS.bat"
set "exit_code=%errorlevel%"
if not "%exit_code%"=="0" (
 echo [HATA] Program olagan sekilde sonlanmadi. Terminaldeki hata metnini paylasin.
 pause
)
exit /b %exit_code%
