@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
rem Portable data root: CODEX_ACTIVE lives directly under C:\GorselUretimMerkezi.
rem Do not fall back to a historical OneDrive dataset when this root is valid.
set "GORSEL_CODE_ROOT=%~dp0.."
set "GORSEL_RUNTIME_ROOT=%~dp0..\.."
set "MOCKUP_RUNTIME_WORKSPACE=%GORSEL_RUNTIME_ROOT%"
rem Üretim worker profili kesinleştirildi: güvenli ve ölçülmüş ayar 2 worker.
rem Motor ortam değişkeni veya eski benchmark profiliyle değiştirilemez.
set "V4_RENDER_WORKERS=2"
title Gorsel Uretim Merkezi V5 - Graphite Workbench
echo Gorsel Uretim Merkezi V5 Graphite Workbench baslatiliyor.
echo Kod: %GORSEL_CODE_ROOT%
echo Runtime: %GORSEL_RUNTIME_ROOT%
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
  echo Program acilamadi. Ilk kez kuruyorsaniz once KURULUM.bat dosyasini calistirin.
  echo Kod kokunu ve Python kurulumunu kontrol edin: %GORSEL_CODE_ROOT%
  pause
)
endlocal
