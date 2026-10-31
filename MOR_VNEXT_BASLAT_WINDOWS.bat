@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo MOR PREMIUM VNext KISMI ADAY - WINDOWS_NOT_VERIFIED
call "%~dp0V4102_BASLAT_WINDOWS.bat"
exit /b %errorlevel%
