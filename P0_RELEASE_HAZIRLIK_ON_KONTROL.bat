@echo off
chcp 65001 >nul
title P0 Release - SALT OKUNUR Hazirlik
set "CODE=C:\AI_WORK\gorsel-mockup-automation-src"
set "RUNTIME=%USERPROFILE%\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu"
set "VAULT=C:\AI_WORK\P0_RELEASE_KORUMALI_YEDEK"
cd /d "%~dp0"
python scripts\p0_release_transaction.py --mode plan --source "%~dp0" --code "%CODE%" --runtime "%RUNTIME%" --vault "%VAULT%"
if errorlevel 1 (
  echo PLAN BLOCKED. Hicbir canli dosya degistirilmedi.
  pause
  exit /b 2
)
echo.
echo ON KONTROL BASARILI. Bu dosya kurulum veya yedekleme yapmaz.
pause
