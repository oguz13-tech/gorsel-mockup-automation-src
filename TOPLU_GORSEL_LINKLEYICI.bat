@echo off
chcp 65001 > nul
title Toplu Gorsel Link Donusturucu
cls
echo ===============================================================================
echo                    GORSEL LINK DONUSTURUCU - EXCEL
echo ===============================================================================
echo.
echo Acilacak pencereden linke donusturulecek gorselleri secin.
echo Sistem mevcut ImgBB ayarlarini kullanir.
echo.
cd /d "%~dp0"
python ".\SABLON_V2_MIMARI\tools_runner.py" links
pause
