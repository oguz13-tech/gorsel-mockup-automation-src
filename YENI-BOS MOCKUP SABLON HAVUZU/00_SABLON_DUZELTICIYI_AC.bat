@echo off
chcp 65001 > nul
title Sablon Duzeltme Paneli
cls
echo ===============================================================================
echo      SABLON DUZELTME PANELI (LOCALHOST) BASLATILIYOR...
echo ===============================================================================
echo.
echo Arka planda acik kalmis eski sunucular temizleniyor (Zombi Korumasi)...
FOR /F "tokens=5" %%a IN ('netstat -ano ^| findstr :8999') DO taskkill /F /PID %%a > nul 2>&1
echo.
echo Panel hazirlaniyor... Tarayiciniz aninda otomatik olarak acilacaktir! 
echo.
start http://127.0.0.1:8999
cd ..
python SABLON_DUZELTICI.py
pause
