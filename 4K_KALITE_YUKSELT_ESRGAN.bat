@echo off
chcp 65001 > nul
title Real-ESRGAN 4K / AI Kalite Araci
cls
echo ===============================================================================
echo                  REAL-ESRGAN 4K / AI KALITE ARACI
echo ===============================================================================
echo.
echo Bu arac factory'den BAGIMSIZ calisir.
echo Orijinal gorsellerin uzerine yazmaz.
echo Acilacak pencereden islenecek klasoru secin.
echo.
cd /d "%~dp0"
python ".\SABLON_V2_MIMARI\tools_runner.py" 4k
pause
