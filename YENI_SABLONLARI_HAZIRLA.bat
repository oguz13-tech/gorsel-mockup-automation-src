@echo off
chcp 65001 > nul
title Yeni Şablonları Hazırla
cls
echo ===============================================================================
echo                    YENI SABLONLARI HAZIRLA
echo ===============================================================================
echo.
echo Bu pencere YENI-BOS MOCKUP SABLON HAVUZU klasorunu izler.
echo Yeni bir mockup geldiginde sistem otomatik olarak:
echo   1. Orijinal yedegini korur.
echo   2. Calisma kopyasini olusturur.
echo   3. DORT KOSEYI BIR KEZ otomatik bulmaya calisir.
echo   4. Sablonu Kontrol Bekliyor durumunda Inceleme Merkezi'ne ekler.
echo.
echo NOT: Otomatik bulunan koseler uretime direkt girmez.
echo Siz kontrol edip "Bu Sablonu Onayla" demeden APPROVED olmaz.
echo.

if not defined MOCKUP_RUNTIME_WORKSPACE (
    set /p "MOCKUP_RUNTIME_WORKSPACE=Calisma klasoru: "
)

if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
    echo.
    echo HATA: Secilen klasorde SABLON_V2_MIMARI\ayarlar.db bulunamadi.
    echo Dogru ana calisma klasorunu secin.
    pause
    exit /b 2
)

cd /d "%~dp0"
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\sablon_oto_izleyici.py
pause
