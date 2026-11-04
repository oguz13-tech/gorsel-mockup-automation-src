@echo off
chcp 65001 > nul
title JARVIS Mockup - Şablon İnceleme Merkezi
color 0A

echo ================================================================
echo   JARVIS MOCKUP - AKTIF ŞABLON İNCELEME MERKEZİ
echo ================================================================
echo.

if not defined MOCKUP_RUNTIME_WORKSPACE (
    echo Runtime workspace bu terminalde tanımlı değil.
    echo Görsellerinizin ve SABLON_V2_MIMARI\ayarlar.db dosyasının
    echo bulunduğu ana klasörün tam yolunu yapıştırın.
    echo.
    set /p "MOCKUP_RUNTIME_WORKSPACE=Runtime klasörü: "
)

if not defined MOCKUP_RUNTIME_WORKSPACE (
    echo HATA: Runtime workspace belirtilmedi.
    pause
    exit /b 2
)

if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
    echo HATA: Seçilen runtime içinde SABLON_V2_MIMARI\ayarlar.db yok:
    echo %MOCKUP_RUNTIME_WORKSPACE%
    pause
    exit /b 2
)

python -c "import flask, cv2, numpy" >nul 2>&1
if errorlevel 1 (
    echo HATA: Gerekli Python paketleri eksik. Otomatik ve kontrolsüz kurulum
    echo yapılmadı. Proje ortamını/venv'i açıp tekrar deneyin.
    pause
    exit /b 2
)

echo Runtime: %MOCKUP_RUNTIME_WORKSPACE%
echo Aktif uygulama: SABLON_V2_MIMARI\app.py
echo Adres: http://127.0.0.1:8080
echo.
echo Bu pencere açık kalmalıdır.

start "JARVIS Review Server" cmd /k "set MOCKUP_RUNTIME_WORKSPACE=%MOCKUP_RUNTIME_WORKSPACE%&& cd /d "%~dp0"&& python SABLON_V2_MIMARI\app.py"
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8080
exit /b 0
