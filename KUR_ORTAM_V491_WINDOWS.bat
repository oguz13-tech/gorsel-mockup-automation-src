@echo off
rem Shared Python setup for main app and every independent professional tool.
rem CALL from a parent BAT; PYEXE remains in the caller's environment.
cd /d "%~dp0"
set "PYEXE=%~dp0MERKEZ\.venv\Scripts\python.exe"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
if exist "%PYEXE%" (
 "%PYEXE%" -c "import sys;sys.exit(0 if sys.version_info[:2] == (3,11) else 1)" >nul 2>&1
 if errorlevel 1 (
  echo Eski/tasinmis Python ortami ayri bir yedek klasore aliniyor.
  ren "%~dp0MERKEZ\.venv" ".venv_ESKI_%RANDOM%_%RANDOM%"
  if errorlevel 1 exit /b 1
 )
)
if not exist "%PYEXE%" (
 py -3.11 -c "import sys;sys.exit(0 if sys.version_info[:2] == (3,11) else 1)" >nul 2>&1
 if errorlevel 1 (
  echo Python 3.11 bulunamadi. Microsoft Windows icin resmi Python 3.11 kurulumu gerekiyor.
  exit /b 1
 )
 echo Python 3.11 sanal ortami hazirlaniyor.
 py -3.11 -m venv "%~dp0MERKEZ\.venv"
 if errorlevel 1 exit /b 1
)
"%PYEXE%" -B scripts\v46_dependency_check.py
if errorlevel 1 (
 echo Temel sabitlenmis bagimliliklar yukleniyor; ilk kurulumda internet gerekebilir.
 "%PYEXE%" -m pip install --disable-pip-version-check -r MERKEZ\requirements-v46-lock.txt
 if errorlevel 1 exit /b 1
)
"%PYEXE%" -B scripts\v46_dependency_check.py
if errorlevel 1 exit /b 1
exit /b 0
