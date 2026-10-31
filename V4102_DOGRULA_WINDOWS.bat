@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Gorsel Uretim V4.10.2 - SHA256 Kontrol
py -3.11 -B scripts\v4102_verify_package.py
if errorlevel 1 goto fail
echo [PASS] V4.10.2 paket butunlugu dogrulandi.
echo PETEK Maske Onay Hizi ve 7 kategori UI Test Merkezinde bekler.
pause
exit /b 0
:fail
echo [HATA] Dosya eksik veya SHA-256 uyumsuz; eski surumu kullanmaya devam edin.
pause
exit /b 1
