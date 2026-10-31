@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0KUR_ORTAM_V491_WINDOWS.bat"
if errorlevel 1 goto failed
"%PYEXE%" -B MERKEZ\merkez.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Gorsel Uretim Merkezi baslatilamadi. Program verileri degistirilmedi.
echo Bu ekrandaki hata mesajini paylasin.
pause
exit /b 1
