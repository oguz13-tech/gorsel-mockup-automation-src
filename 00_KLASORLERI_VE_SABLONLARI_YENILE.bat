@echo off
chcp 65001 > nul
title Sablon Klasorlerini Yenileme Motoru
cls
echo ===============================================================================
echo      TUM FIZIKSEL KLASORLERI VE SABLONLARI YENILEME MOTORU
echo ===============================================================================
echo.
echo Bu islem ayarlar.json icindeki TUM guncel koordinat verilerini okuyarak
echo sistemdeki tum sablonlari fiziksel olarak bastan asagi yeniden beyazlatir.
echo.
echo Klasorlerdeki gorsel hatalarini temizler ve veritabaniyla %100 senkronize eder.
echo Lutfen islem bitene kadar bekleyin (ortalama 15-30 saniye surebilir)...
echo.
echo 1. Asama: Veritabani Temizligi (Hayalet kayitlar siliniyor)...
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\temizlik_motoru.py
echo.
echo 2. Asama: Fiziksel Sablon Beyazlatma ve Yenileme...
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\sablon_beyazlatma_motoru.py --force
echo.
echo ===============================================================================
echo ISLEM TAMAMLANDI! Tum fiziksel klasorler basariyla guncellendi.
echo ===============================================================================
pause
