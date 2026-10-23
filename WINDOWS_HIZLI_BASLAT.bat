@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title GORSEL URETIM MERKEZI - V4.4 GRUP 1+2+3 KABUL ADAYI
echo =======================================================
echo  GORSEL URETIM MERKEZI V4.4 - GRUP 1 + GRUP 2 + GRUP 3
echo =======================================================
echo Eski onayli sablonlar ve kullanici verileri degistirilmez.
echo.
set "PYEXE=%~dp0MERKEZ\.venv\Scripts\python.exe"
if not exist "%PYEXE%" (
  echo Izole Python ortami kuruluyor. Internet baglantisi gerekebilir.
  where py >nul 2>nul
  if not errorlevel 1 (
    rem Fresh installs prefer the doctor-pinned Python 3.11 when installed.
    rem Existing .venv is NEVER replaced. Older fallback retained.
    py -3.11 -c "import sys; assert sys.version_info[:2] == (3, 11)" >nul 2>nul
    if not errorlevel 1 (
      echo Python 3.11 bulundu; yeni izole ortam bununla kuruluyor.
      py -3.11 -m venv "%~dp0MERKEZ\.venv"
    ) else (
      echo Python 3.11 bulunamadi; mevcut Python 3 varsayilani kullaniliyor.
      py -3 -m venv "%~dp0MERKEZ\.venv"
    )
  ) else (
    where python >nul 2>nul
    if errorlevel 1 goto no_python
    python -m venv "%~dp0MERKEZ\.venv"
  )
  if errorlevel 1 goto failed
  rem Dependencies are checked below. A partially created .venv can be repaired.
)
"%PYEXE%" -B -c "import cv2, numpy, PIL, openpyxl, tkinter, requests, flask; print('BAGIMLILIKLAR HAZIR')"
if errorlevel 1 (
  echo Python paketlerinde eksik var. Yalnizca izole program ortaminda onariliyor...
  "%PYEXE%" -m pip install --disable-pip-version-check -r "%~dp0MERKEZ\requirements.txt"
  if errorlevel 1 goto failed
  "%PYEXE%" -B -c "import cv2, numpy, PIL, openpyxl, tkinter, requests, flask; print('BAGIMLILIKLAR ONARILDI')"
  if errorlevel 1 goto failed
)
"%PYEXE%" -B "%~dp0MERKEZ\merkez_saglik.py"
if errorlevel 1 goto failed
"%PYEXE%" -B "%~dp0MERKEZ\merkez.py"
if errorlevel 1 goto failed
exit /b 0
:no_python
echo Python 3.11+ bulunamadi. Python kurup tekrar calistirin.
goto failed
:failed
echo.
echo Program acilamadi. Ustteki hata bilgisini kopyalayin.
pause
exit /b 1
