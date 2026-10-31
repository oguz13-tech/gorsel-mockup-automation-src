@echo off
rem V4.9.1 arayuz kodunu kaldirmadan V4.8.8 gorunumune donus.
rem Bu ana calisma klasorunu veya veritabanlarini degistirmez.
setlocal
set "GORSEL_UI_LEGACY=1"
call "%~dp0BASLAT_V47_WINDOWS.bat"
exit /b %errorlevel%
