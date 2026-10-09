@echo off
chcp 65001 > nul
title TEHLIKELI LEGACY ISLEM - Toplu Şablon Yenileme
cls
echo ===============================================================================
echo      DIKKAT: BU LEGACY TOPLU YENILEME NORMAL URETIM AKISININ PARCASI DEGIL
echo ===============================================================================
echo.
echo Bu işlem çalışma şablonlarının piksel içeriğini topluca değiştirebilir.
echo Source-hash-bound APPROVED profiller bu durumda STALE olur ve yeniden
echo analiz / insan onayı gerekir.
echo.
echo Normal kullanım için:
echo   1. SISTEMI_BASLAT.bat  - Şablon İnceleme Merkezi
echo   2. OTOMASYONU_CALISTIR.bat - Güvenli üretim
echo.
echo Bu aracı sadece bilinçli bir kurtarma operasyonunda kullanın.
echo Devam etmek için aşağıdaki ifadeyi AYNEN yazın:
echo TUM_ONAYLARI_YENIDEN_INCELEYECEGIM
echo.
set /p "CONFIRM=> "
if not "%CONFIRM%"=="TUM_ONAYLARI_YENIDEN_INCELEYECEGIM" (
    echo İşlem iptal edildi. Hiçbir dosya değiştirilmedi.
    pause
    exit /b 2
)

if not defined MOCKUP_RUNTIME_WORKSPACE (
    set /p "MOCKUP_RUNTIME_WORKSPACE=Runtime klasörü: "
)
if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
    echo HATA: Runtime workspace geçersiz.
    pause
    exit /b 2
)

cd /d "%~dp0"
echo.
echo Son güvenlik kontrolü: Factory Doctor...
python scripts\factory_doctor.py --runtime "%MOCKUP_RUNTIME_WORKSPACE%"
if errorlevel 1 (
    echo Doctor kritik sorun buldu; toplu yenileme başlatılmadı.
    pause
    exit /b 2
)

echo.
echo Legacy kurtarma işlemi başlatılıyor...
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\temizlik_motoru.py
if errorlevel 1 goto :failed
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\sablon_beyazlatma_motoru.py --force
if errorlevel 1 goto :failed

echo.
echo İşlem tamamlandı. ÜRETİMDEN ÖNCE TÜM DEĞİŞEN ŞABLONLARI YENİDEN İNCELEYİN.
pause
exit /b 0

:failed
echo.
echo HATA: Legacy kurtarma işlemi tam tamamlanmadı. Üretim yapmayın;
echo Factory Doctor ve İnceleme Merkezi ile durumu kontrol edin.
pause
exit /b 2
