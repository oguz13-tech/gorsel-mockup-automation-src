@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo STORE P0 ISSUE79 - Windows aday / gercek verileri koruyun
call "%~dp0V4102_BASLAT_WINDOWS.bat"
exit /b %errorlevel%
