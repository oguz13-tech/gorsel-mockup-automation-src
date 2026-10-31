@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo PETEK ACIL ONIZLEME KAYNAK BUTUNLUGU
py -3.11 -B scripts\v4102_verify_package.py
if errorlevel 1 (
  echo [HATA] PAKET DOSYALARI BOZULMUS, BASLATMAYIN
  pause
  exit /b 1
)
echo [PASS] DOSYA BUTUNLUGU. GERCEK WINDOWS KABULU: WINDOWS_NOT_VERIFIED.
pause
exit /b 0
