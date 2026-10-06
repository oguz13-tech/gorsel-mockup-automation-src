@echo off
chcp 65001 > nul
title JARVIS Güvenli Şablon Ingest İzleyicisi
cls
echo ===============================================================================
echo      YENI ŞABLONLAR - GÜVENLI REVIEW INGEST IZLEYICISI
echo ===============================================================================
echo.
echo Bu araç 2_SABLON_HAVUZU'nu doğrudan değiştirmek için kullanılmaz.
echo YENI-BOS MOCKUP SABLON HAVUZU staging klasörüne eklediğiniz görselleri:
echo   - orijinal yedeğini koruyarak,
echo   - çalışma kopyasını oluşturarak,
echo   - REVIEW_REQUIRED durumunda İnceleme Merkezi'ne ekler.
echo İnsan onayı olmadan üretime APPROVED şablon vermez.
echo.

if not defined MOCKUP_RUNTIME_WORKSPACE (
    set /p "MOCKUP_RUNTIME_WORKSPACE=Runtime klasörü: "
)

if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
    echo HATA: Runtime içinde SABLON_V2_MIMARI\ayarlar.db bulunamadı.
    pause
    exit /b 2
)

cd /d "%~dp0"
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\sablon_oto_izleyici.py
pause
