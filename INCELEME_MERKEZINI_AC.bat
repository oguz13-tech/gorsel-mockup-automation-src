@echo off
chcp 65001 > nul
title Şablon İnceleme Merkezi
cls
echo ===============================================================================
echo                         SABLON INCELEME MERKEZI
echo ===============================================================================
echo.
echo Bu pencere sablonlari kontrol etmek, 4 koseyi duzeltmek,
echo onaylamak ve cop kutusunu yonetmek icindir.
echo.

if not defined MOCKUP_RUNTIME_WORKSPACE (
    set "DEFAULT_RUNTIME=%USERPROFILE%\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu"
    if exist "%DEFAULT_RUNTIME%\SABLON_V2_MIMARI\ayarlar.db" (
        set "MOCKUP_RUNTIME_WORKSPACE=%DEFAULT_RUNTIME%"
    )
)

if not defined MOCKUP_RUNTIME_WORKSPACE (
    set /p "MOCKUP_RUNTIME_WORKSPACE=Ana calisma klasoru: "
)

if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
    echo.
    echo HATA: Secilen klasorde SABLON_V2_MIMARI\ayarlar.db bulunamadi.
    echo Girilen yol:
    echo %MOCKUP_RUNTIME_WORKSPACE%
    echo.
    pause
    exit /b 2
)

cd /d "%~dp0"

echo Calisma klasoru:
echo %MOCKUP_RUNTIME_WORKSPACE%
echo.
echo Inceleme Merkezi aciliyor: http://127.0.0.1:8080
echo Bu pencere acik kaldigi surece Inceleme Merkezi calisir.
echo.

python ".\SABLON_V2_MIMARI\app.py"
pause
