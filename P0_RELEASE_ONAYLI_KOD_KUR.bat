@echo off
chcp 65001 >nul
title P0 Release - Yalniz KOD Kurulumu
cd /d "%~dp0"
echo Bu arac ORIJINAL/YENI-BOS/WORKING/SQLite'a yazmaz.
set /p "SNAPSHOT=Onayli backup SNAPSHOT klasorunu yapistirin: "
if "%SNAPSHOT%"=="" exit /b 2
set /p "ONAY=Kod kurulumu icin KOD_ONAY yazin: "
if /I not "%ONAY%"=="KOD_ONAY" exit /b 2
python scripts\p0_release_transaction.py --mode install --snapshot "%SNAPSHOT%" --approval INSTALL_CODE_ONLY
if errorlevel 1 (
  echo BLOCKED! Raporu ChatGPT'ye gonderin.
  pause
  exit /b 2
)
echo Yalniz kod kurulumu tamam. Canli test baslatilmadi.
pause
