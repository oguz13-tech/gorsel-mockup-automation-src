@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Real-ESRGAN 4K - V4.6.1 Guvenli Windows Kurulum ve GPU Testi
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0KUR_REAL_ESRGAN_4K_WINDOWS.ps1"
set CODE=%ERRORLEVEL%
echo.
if "%CODE%"=="0" (
  echo [OK] Real-ESRGAN model kurulumu ve GPU testi tamamlandi.
) else (
  echo [HATA] Ayrintilar: REAL_ESRGAN_KURULUM_SONUC.txt
)
pause
exit /b %CODE%
