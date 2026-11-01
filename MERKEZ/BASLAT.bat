@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title GORSEL MOCKUP - WINDOWS TESLIM ADAYI V3.13
echo Gorsel Uretim Merkezi V3 baslatiliyor.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -B merkez.py
) else if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
  "%LocalAppData%\Programs\Python\Python311\python.exe" -B merkez.py
) else if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  "%LocalAppData%\Programs\Python\Python312\python.exe" -B merkez.py
) else if exist "%ProgramFiles%\Python311\python.exe" (
  "%ProgramFiles%\Python311\python.exe" -B merkez.py
) else if exist "%ProgramFiles%\Python312\python.exe" (
  "%ProgramFiles%\Python312\python.exe" -B merkez.py
) else if exist "%SystemRoot%\py.exe" (
  py -3 -B merkez.py
) else if exist "%SystemRoot%\System32\python.exe" (
  python -B merkez.py
) else (
  echo Python bulunamadi. KURULUM.bat ile Python 3.11 veya 3.12 kurulumunu tamamlayin.
  pause
  exit /b 1
)
if errorlevel 1 (
  echo.
  echo Program acilmadi. Ilk kez kuruyorsaniz once KURULUM.bat dosyasini calistirin.
  pause
)
endlocal
