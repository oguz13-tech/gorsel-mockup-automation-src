@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo PETEK - 13/14/15/16 GERCEK IZGARA ONIZLEME DUZELTMESI
call "%~dp0PETEK_VNEXT_BASLAT_WINDOWS.bat"
exit /b %errorlevel%
