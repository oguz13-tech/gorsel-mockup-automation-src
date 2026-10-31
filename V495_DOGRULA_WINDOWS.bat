@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title V4.9.5 - Paket Butunluk Dogrulama
py -3.11 -B scripts\v495_verify_package.py
if errorlevel 1 goto fail
set "PYEXE=%~dp0MERKEZ\.venv\Scripts\python.exe"
if exist "%PYEXE%" (
  "%PYEXE%" -B -m pytest -q tests\test_v495_release_safety.py tests\test_v494_safe_exit.py tests\test_v492_petek_finish_filter.py
  if errorlevel 1 goto fail
  echo [PASS] SHA256 + V4.9.5 hedefli testler.
) else (
  echo [BILGI] SHA256 dogrulandi; test icin once V495_BASLAT_WINDOWS.bat ile Python ortamini kurun.
)
echo Windows canli testleri PETEK gercek fotograf, 4K GPU, Magenta ve magaza icin kullanici onayi gerektirir.
pause
exit /b 0
:fail
echo [HATA] Dogrulama basarisiz. Gercek sablonlar uzerinde kullanmayin.
pause
exit /b 1
