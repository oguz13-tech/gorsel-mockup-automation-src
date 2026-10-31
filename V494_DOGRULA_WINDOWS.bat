@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title V4.9.4 - Paket guvenlik kontrolu
py -3.11 -B scripts\v494_verify_package.py
if errorlevel 1 goto fail
set "PYEXE=%~dp0MERKEZ\.venv\Scripts\python.exe"
if exist "%PYEXE%" (
  "%PYEXE%" -B -m pytest -q tests\test_v494_safe_exit.py tests\test_v493_persistent_acceptance_and_fifteen.py tests\test_v492_petek_finish_filter.py tests\test_orientation_sort_v489.py tests\test_v491_safety_fixes.py tests\test_v491_independent_tool_launch.py
  if errorlevel 1 goto fail
  echo [PASS] SHA256 + V4.9.4 hedefli regresyonlar.
) else (
  echo [BILGI] SHA256 basarili. Canli test icin ana baslaticiyla Python ortam kurulumunu tamamlayin.
)
echo Bu paket kullanicinin gercek Windows/4K/GPU verisiyle HENUZ dogrulanmadi.
pause
exit /b 0
:fail
echo [HATA] Paket veya test dogrulanamadi. CANLI VERILER UZERINDE KULLANMAYIN.
pause
exit /b 1
