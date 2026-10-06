@echo off
chcp 65001 > nul
title Real-ESRGAN 4K / AI Kalite Power Tool
cls
echo ===============================================================================
echo      REAL-ESRGAN 4K / AI KALITE POWER TOOL
echo ===============================================================================
echo.
echo Bu arac BAGIMSIZ kullanilir.
echo - Ana factory artifact zincirini degistirmez.
echo - Orijinal dosyalari ASLA overwrite etmez.
echo - Ciktilari ayri 4K_POWER_TOOL_OUTPUT klasorune yazar.
echo - Isterseniz --input ve --output parametreleri ile baska klasorlerde de kullanabilirsiniz.
echo.

if not defined MOCKUP_RUNTIME_WORKSPACE (
    echo Varsayilan kaynak olarak 3_URETILEN_MOCKUPLAR kullanilacak.
    echo Runtime ana klasorunu yapistirin:
    set /p "MOCKUP_RUNTIME_WORKSPACE=Runtime klasoru: "
)

if not defined MOCKUP_RUNTIME_WORKSPACE (
    echo HATA: Runtime workspace belirtilmedi.
    pause
    exit /b 2
)

cd /d "%~dp0"

echo.
echo Power tool baslatiliyor...
python "99_SISTEM_MOTORLARI_VE_KODLARSISTEM_MOTORUkalite_artirici_otomasyon.py" %*
set TOOL_EXIT=%errorlevel%

echo.
if not "%TOOL_EXIT%"=="0" (
    echo Islem hata/uyari ile tamamlandi. Yukaridaki logu kontrol edin.
) else (
    echo Islem basariyla tamamlandi.
)
echo.
pause
exit /b %TOOL_EXIT%
