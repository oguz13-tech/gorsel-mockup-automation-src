@echo off
setlocal
chcp 65001 >nul
title Gorsel Uretim Merkezi - Cift Kaynak Inceleme
echo [GUM] Iki kaynak klasoru icin inceleme ZIP'i hazirlaniyor...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0CIFT_KAYNAK_INCELEME_HAZIRLA.ps1"
if errorlevel 1 (
  echo.
  echo [HATA] ZIP hazirlanamadi. Yukaridaki hatayi kontrol edin.
  pause
  exit /b 1
)
echo.
echo [BASARILI] ZIP, Windows Dosya Gezgini'nde secili olarak gosterildi.
exit /b 0
