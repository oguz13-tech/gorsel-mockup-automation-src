@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title GORSEL MOCKUP V4.0 - KOD GERI ALMA (ROLLBACK)
echo ============================================================================
echo  GORSEL MOCKUP V4.0 - ONAYLI KOD GERI ALMA (CANLI VERITABANINA DOKUNMAZ)
echo ============================================================================
if exist "P0_RELEASE_ONAYLI_KOD_GERI_AL.bat" (
  call "%~dp0P0_RELEASE_ONAYLI_KOD_GERI_AL.bat"
  exit /b %ERRORLEVEL%
)
echo Geri alma betigi bulunamadi.
pause
exit /b 1
