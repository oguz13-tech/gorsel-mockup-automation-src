@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0BASLAT_V47_WINDOWS.bat"
if errorlevel 1 (
 echo [HATA] Baslatma tamamlanamadi. V493_DOGRULA_WINDOWS.bat calistirin.
 pause
 exit /b 1
)
exit /b 0
