@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYEXE=%~dp0MERKEZ\.venv\Scripts\python.exe"
if not exist "%PYEXE%" (
  echo Gereken Python ortami bulunamadi. Once BASLAT_V47_WINDOWS.bat ile kurulum yapin.
  pause
  exit /b 1
)
"%PYEXE%" -B MERKEZ\bakim_merkezi_v472.py
if errorlevel 1 (
 echo On-inceleme acilamadi. Bu ekranin goruntusunu paylasin.
 pause
)
exit /b %errorlevel%
