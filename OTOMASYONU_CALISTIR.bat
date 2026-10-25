@echo off
chcp 65001 > nul
title JARVIS E-Ticaret Mockup Fabrikası
cls

echo ===============================================================================
echo      JARVIS MOCKUP FABRİKASI - GÜVENLİ ÜRETİM
echo ===============================================================================
echo.

if not defined MOCKUP_RUNTIME_WORKSPACE (
    echo Görsellerinizin, ayarlar.db ve üretim klasörlerinin bulunduğu
    echo ana runtime klasörünün tam yolunu yapıştırın.
    echo.
    set /p "MOCKUP_RUNTIME_WORKSPACE=Runtime klasörü: "
)

if not defined MOCKUP_RUNTIME_WORKSPACE (
    echo HATA: Runtime workspace belirtilmedi.
    pause
    exit /b 2
)

if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
    echo HATA: Runtime içinde SABLON_V2_MIMARI\ayarlar.db bulunamadı:
    echo %MOCKUP_RUNTIME_WORKSPACE%
    pause
    exit /b 2
)

cd /d "%~dp0"

echo [1/5] Factory Doctor hızlı bütünlük taraması...
python scripts\factory_doctor.py --runtime "%MOCKUP_RUNTIME_WORKSPACE%" --fast
if errorlevel 1 (
    echo.
    echo ===============================================================================
    echo  URETIM BASLATILMADI: Factory Doctor kritik sorun buldu.
    echo ===============================================================================
    pause
    exit /b 2
)

echo.
echo [2/5] Üretim preflight güvenlik kontrolü...
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\pc_master_factory.py --preflight
if errorlevel 1 (
    echo.
    echo ===============================================================================
    echo  URETIM BASLATILMADI.
    echo  Yukarıdaki preflight hatalarını düzeltip tekrar deneyin.
    echo ===============================================================================
    pause
    exit /b 2
)

echo.
echo [3/5] Manifest ve H/V master kaynakları okunuyor...
echo [4/5] Source-valid APPROVED şablonlarla güvenli render yapılıyor...
echo [5/5] Final QA sonrası bulut ve Excel işlemleri tamamlanıyor...
echo.
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\pc_master_factory.py --mod dongusel
set FACTORY_EXIT=%errorlevel%

echo.
if not "%FACTORY_EXIT%"=="0" (
    echo ===============================================================================
    echo  URETIM TAM BASARIYLA BITMEDI. Logları kontrol edin.
    echo  Durum kaydı kaldığı yerden güvenli devam için korunmuştur.
    echo ===============================================================================
    pause
    exit /b %FACTORY_EXIT%
)

echo ===============================================================================
echo  TEBRIKLER! UYGUN TUM ISLEMLER BASARIYLA TAMAMLANDI.
echo  Hazır Mockuplar : %MOCKUP_RUNTIME_WORKSPACE%\3_URETILEN_MOCKUPLAR
echo  Yükleme Listesi : %MOCKUP_RUNTIME_WORKSPACE%\4_EXCEL_YUKLEME_LISTELERI
echo ===============================================================================
echo.
pause
