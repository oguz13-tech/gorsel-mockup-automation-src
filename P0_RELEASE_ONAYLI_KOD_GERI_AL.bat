@echo off
chcp 65001 >nul
title P0 Release - SHA Dogrulamali Kod Geri Alma
cd /d "%~dp0"
set /p "SNAPSHOT=Onceki kurulum SNAPSHOT klasorunu yapistirin: "
if "%SNAPSHOT%"=="" exit /b 2
set /p "ONAY=Geri alma icin GERI_AL_ONAY yazin: "
if /I not "%ONAY%"=="GERI_AL_ONAY" exit /b 2
python scripts\p0_release_transaction.py --mode rollback --snapshot "%SNAPSHOT%" --approval ROLLBACK_CODE_ONLY
if errorlevel 1 (
  echo BLOCKED/RECOVERY_REQUIRED! Kaynak/yedekleri silmeyin.
  pause
  exit /b 2
)
echo Yalniz kurulan kod eski hale dondu. Kullanici verisi degistirilmedi.
pause
