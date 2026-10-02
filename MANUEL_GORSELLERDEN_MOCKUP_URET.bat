@echo off
chcp 65001 > nul
title Manuel Mockup Uretim Motoru
cls
echo ===============================================================================
echo      MANUEL GORSELLERDEN MOCKUP URETIM MERKEZI
echo ===============================================================================
echo.
echo 'MOCKUP A HAZIR GORSELLER' klasorundeki gorseller taraniyor...
echo.
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\manuel_mockup_motoru.py --mod dongusel
echo.
echo ===============================================================================
echo  ISLEM TAMAMLANDI!
echo  Uretilen Mockuplar: 3_URETILEN_MOCKUPLAR klasorunde
echo ===============================================================================
echo.
pause
