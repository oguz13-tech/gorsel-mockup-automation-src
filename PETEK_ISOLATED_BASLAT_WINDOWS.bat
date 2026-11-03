@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not defined MOCKUP_RUNTIME_WORKSPACE (
  set /p "MOCKUP_RUNTIME_WORKSPACE=Salt-okunur test runtime klasoru: "
)
if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
  echo HATA: Runtime SQLite bulunamadi. Canli veriler tasinmadi veya degistirilmedi.
  exit /b 2
)
set "PYTHONPATH=%CD%;%CD%\MERKEZ"
python SABLON_V2_MIMARI\app.py
endlocal
