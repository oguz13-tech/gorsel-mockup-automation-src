@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONPATH=%CD%;%CD%\MERKEZ"
if not exist "%CD%\MERKEZ\.venv\Scripts\python.exe" (
  echo UYARI: Paket icinde venv yok; sistem Python kullaniliyor.
  set "PYTHON=python"
) else (
  set "PYTHON=%CD%\MERKEZ\.venv\Scripts\python.exe"
)
"%PYTHON%" -m pytest -q tests\test_final_petek_contract_20261101.py tests\test_v4112_http_fallback_guard.py tests\test_vnext_petek_dynamic_photo_count.py tests\test_vnext_petek_preview_parity_and_recovery_20261101.py
if errorlevel 1 exit /b %errorlevel%
node --check SABLON_V2_MIMARI\static\js\petek_editor_v477.js
if errorlevel 1 exit /b %errorlevel%
echo PETEK izolasyon testleri PASS; canli runtime verisi kullanilmadi.
endlocal
