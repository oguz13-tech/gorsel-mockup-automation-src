@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title V4.10.1 - Paket SHA256 Dogrulama
py -3.11 -B scripts\v4101_verify_package.py
if errorlevel 1 goto fail
echo [PASS] V4.10.1 SHA256 paket butunlugu dogrulandi.
echo PETEK Toplu Secim ve Tek Onay icin Test Merkezini ac.
pause
exit /b 0
:fail
echo [HATA] Paket eksik veya SHA256 uyumsuz. Programi calistirmayin.
pause
exit /b 1
