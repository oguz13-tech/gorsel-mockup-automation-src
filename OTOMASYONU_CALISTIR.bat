@echo off
chcp 65001 > nul
title Trendyol ve E-Ticaret Otomasyonu V5
cls
echo ===============================================================================
echo      E-TICARET OTOMASYON MERKEZI (V5 MASTER FACTORY)
echo ===============================================================================
echo.
echo [1/4] Uretim oncesi guvenlik ve hazirlik kontrolu yapiliyor...
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\pc_master_factory.py --preflight
if errorlevel 1 (
    echo.
    echo ===============================================================================
    echo  URETIM BASLATILMADI.
    echo  Yukaridaki on kontrol hatalarini duzeltip tekrar deneyin.
    echo  Hicbir render veya yukleme islemi baslatilmadi.
    echo ===============================================================================
    echo.
    pause
    exit /b 2
)

echo.
echo [2/4] 1_GELEN_KAGGLE_BASKILARI manifest ve H/V masterlari okunuyor...
echo [3/4] Master eserler 6 urun kategorisine guvenli sekilde donusturuluyor...
echo [4/4] Mockuplar basiliyor, buluta yukleniyor ve Excel hazirlaniyor...
echo.
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\pc_master_factory.py --mod dongusel
set FACTORY_EXIT=%errorlevel%
echo.
if not "%FACTORY_EXIT%"=="0" (
    echo ===============================================================================
    echo  URETIM TAM BASARIYLA BITMEDI. Loglari kontrol edin.
    echo  Sistem kaldigi yerden devam edecek sekilde durum kaydi tuttu.
    echo ===============================================================================
    echo.
    pause
    exit /b %FACTORY_EXIT%
)

echo ===============================================================================
echo  TEBRIKLER! TUM UYGUN ISLEMLER BASARIYLA TAMAMLANDI!
echo  Hazir Mockuplar : 3_URETILEN_MOCKUPLAR klasorunde
echo  Yukleme Listesi : 4_EXCEL_YUKLEME_LISTELERI klasorunde
echo ===============================================================================
echo.
pause
