@echo off
chcp 65001 > nul
title Sablon Havuzu Otomatik Beyazlatici Izleyici
cls
echo ===============================================================================
echo      SABLON HAVUZU OTOMATIK BEYAZLATICI (ARKAPLAN IZLEYICI)
echo ===============================================================================
echo.
echo 2_SABLON_HAVUZU klasorune yeni bir gorsel attiginizda aninda algilanip
echo cerceve ici bembeyaz bos kanvasa donusturulecektir.
echo.
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\sablon_oto_izleyici.py
pause
