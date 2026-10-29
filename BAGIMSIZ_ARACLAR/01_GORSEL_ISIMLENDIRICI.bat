@echo off
setlocal
chcp 65001 >nul
title Gorsel Isimlendirici - Bagimsiz
cd /d "%~dp0.."
set "PYEXE=%~dp0..\MERKEZ\.venv\Scripts\python.exe"
if exist "%PYEXE%" goto launch
where py >nul 2>nul
if errorlevel 1 goto missing
py -3.11 -B "SABLON_V2_MIMARI\tools_runner.py" rename
goto result
:launch
"%PYEXE%" -B "SABLON_V2_MIMARI\tools_runner.py" rename
:result
if errorlevel 1 goto failed
exit /b 0
:missing
echo Python 3.11 bulunamadi. Ana merkezin BASLAT_V47_WINDOWS.bat dosyasini bir kez acin.
goto failed
:failed
echo GORSEL ISIMLENDIRICI ACILAMADI. Yukaridaki hata mesaji kapatilmadi.
echo Onayli sablonlar veya orijinal yedekler degistirilmedi.
pause
exit /b 1
