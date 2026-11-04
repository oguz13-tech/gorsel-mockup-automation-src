@echo off
chcp 65001 >nul
title P0 Release - Yalniz Dis Yedek
set "CODE=C:\AI_WORK\gorsel-mockup-automation-src"
set "RUNTIME=%USERPROFILE%\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu"
set "VAULT=C:\AI_WORK\P0_RELEASE_KORUMALI_YEDEK"
cd /d "%~dp0"
echo YALNIZ harici koda ve SQLite'in kopyasina yedek alinacak.
echo CANLI dosyalar degistirilmeyecek.
set /p "OK=Devam icin YEDEK yazin: "
if /I not "%OK%"=="YEDEK" exit /b 2
python scripts\p0_release_transaction.py --mode backup --source "%~dp0" --code "%CODE%" --runtime "%RUNTIME%" --vault "%VAULT%"
if errorlevel 1 (
  echo YEDEK HATASI! Kuruluma gecmeyin.
  pause
  exit /b 2
)
echo YEDEK HAZIR; rapordaki SNAPSHOT klasorunu saklayin.
pause
