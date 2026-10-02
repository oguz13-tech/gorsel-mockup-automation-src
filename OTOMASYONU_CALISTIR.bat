@echo off
chcp 65001 > nul
title Trendyol ve E-Ticaret Otomasyonu V5
cls
echo ===============================================================================
echo      E-TICARET OTOMASYON MERKEZI (V5 MASTER FACTORY)
echo ===============================================================================
echo.
echo [1/3] 1_GELEN_KAGGLE_BASKILARI klasoru taraniyor...
echo [2/3] Master eserler 5 urun kategorisine donusturuluyor...
echo [3/3] Mockuplar basiliyor, ImgBB yukleniyor, Excel hazirlaniyor...
echo.
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\pc_master_factory.py --mod dongusel
echo.
echo ===============================================================================
echo  TEBRIKLER! TUM ISLEMLER TAMAMLANDI!
echo  Hazir Mockuplar : 3_URETILEN_MOCKUPLAR klasorunde
echo  Yukleme Listesi : 4_EXCEL_YUKLEME_LISTELERI klasorunde
echo ===============================================================================
echo.
pause