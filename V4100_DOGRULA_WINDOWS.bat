@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title V4.10.0 - Paket SHA256 Dogrulama
py -3.11 -B scripts\v4100_verify_package.py
if errorlevel 1 goto fail
echo [PASS] V4.10.0 dosya butunlugu dogrulandi.
echo Gercek Windows testi icin Test Merkezi ^> Magaza-Kategori-Mockup atama bolumune bak.
pause
exit /b 0
:fail
echo [HATA] Paket eksik veya SHA256 uyumsuz. Programi calistirmayin.
pause
exit /b 1
