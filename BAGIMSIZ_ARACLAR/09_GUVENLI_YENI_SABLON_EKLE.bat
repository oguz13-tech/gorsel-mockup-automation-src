@echo off
chcp 65001 > nul
title Guvenli Yeni Sablon Ekleme - Yalniz Kopyala
cd /d "%~dp0.."
if not defined MOCKUP_RUNTIME_WORKSPACE (
  set /p "MOCKUP_RUNTIME_WORKSPACE=Runtime klasorunu girin: "
)
if not exist "%MOCKUP_RUNTIME_WORKSPACE%\2_SABLON_HAVUZU_ORIJINAL_YEDEK" (
  echo BLOCKED: Gercek runtime dogrulanamadi.
  pause
  exit /b 2
)
python scripts\safe_intake_manual.py --runtime-root "%MOCKUP_RUNTIME_WORKSPACE%" --execute
if errorlevel 1 (
  echo ISLEM HATA ILE BITTI. Sablon numaralandirma baslatilmadi.
  pause
  exit /b 2
)
echo Yalniz guvenli gelen kutusuna kopyalandi. Watcher baslatilmadi.
pause
