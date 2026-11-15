@echo off
chcp 65001 > nul
title JARVIS V2 - Guvenli Kontrol Merkezi
cd /d "%~dp0.."
set "GORSEL_CODE_ROOT=%CD%"
if not defined GORSEL_RUNTIME_ROOT set "GORSEL_RUNTIME_ROOT=%CD%\.."
if not defined MOCKUP_RUNTIME_WORKSPACE set "MOCKUP_RUNTIME_WORKSPACE=%GORSEL_RUNTIME_ROOT%"
if not defined MOCKUP_RUNTIME_WORKSPACE (
    echo Guvenlik: Baslatmadan once mevcut gercek calisma klasoru secilmeli.
    set /p "MOCKUP_RUNTIME_WORKSPACE=Runtime klasoru: "
)
if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
    echo HATA: Gecerli runtime veritabani bulunamadi, hicbir sey baslatilmadi.
    pause
    exit /b 2
)
python -c "import flask, cv2, numpy" >nul 2>&1
if errorlevel 1 (
    echo HATA: Python bagimliliklari eksik, otomatik paket yuklemesi yapilmadi.
    pause
    exit /b 2
)
echo Sistem guvenli calisma modunda baslatiliyor.
python SABLON_V2_MIMARI\app.py
pause
