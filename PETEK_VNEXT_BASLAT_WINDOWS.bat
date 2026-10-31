@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo PETEK VNext test adayini ayri klasorde baslatiyorsunuz.
call "%~dp0V4102_BASLAT_WINDOWS.bat"
exit /b %errorlevel%
