@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title GORSEL MOCKUP V3 - BAGIMLILIK KURULUMU
where py >nul 2>nul
if errorlevel 1 (
 echo Python bulunamadi. Python 3.11 veya 3.12 kurup yeniden deneyin.
 pause
 exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
 py -3 -m venv ".venv"
 if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -B -c "import cv2,PIL,openpyxl,numpy,tkinter;print('BAGIMLILIKLAR_HAZIR')"
if errorlevel 1 goto failed
echo Kurulum hazir. BASLAT.bat ile merkezi acabilirsiniz.
pause
exit /b 0
:failed
echo Kurulum tamamlanamadi. Ustteki hatayi kaydedip iletin.
pause
exit /b 1
