@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title V4.9.9 - Paket SHA256 Dogrulama
py -3.11 -B scripts\v499_verify_package.py
if errorlevel 1 goto fail
echo [PASS] V4.9.9 butunluk manifesti.
echo Gercek Windows PETEK toplu onay ve arayuz kabulunu Test Merkezi uzerinden yapin.
pause
exit /b 0
:fail
echo [HATA] SHA256 ya da dosya butunlugu dogrulanamadi. Programi calistirmayin.
pause
exit /b 1
