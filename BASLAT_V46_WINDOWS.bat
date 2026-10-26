@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYEXE=%~dp0MERKEZ\.venv\Scripts\python.exe"
if not exist "%PYEXE%" (
  py -3.11 -m venv "%~dp0MERKEZ\.venv"
  if errorlevel 1 goto failed
)
"%PYEXE%" scripts\v46_dependency_check.py
if errorlevel 1 (
  "%PYEXE%" -m pip install --disable-pip-version-check -r MERKEZ\requirements-v46-lock.txt
  if errorlevel 1 goto failed
)
"%PYEXE%" scripts\v46_dependency_check.py
if errorlevel 1 goto failed
"%PYEXE%" -B MERKEZ\merkez.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo BASLATILAMADI. Python 3.11 ve internet/izin durumunu kontrol edin.
echo Eski program ve calisma verileri degistirilmedi. Bu ekrani paylasin.
pause
exit /b 1
