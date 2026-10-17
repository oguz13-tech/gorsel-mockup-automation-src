@echo off
chcp 65001 >nul
setlocal
title JARVIS - Manuel Mockup Uretimi
cd /d "%~dp0"
echo.
echo ========= MANUEL MOCKUP - KONTROLLU BASLATMA =========
if not defined MOCKUP_RUNTIME_WORKSPACE (
    set /p "MOCKUP_RUNTIME_WORKSPACE=Ana calisma klasorunun tam yolu: "
)
if not defined MOCKUP_RUNTIME_WORKSPACE (
    echo HATA: Calisma klasoru belirtilmedi. Hicbir uretim baslatilmadi.
    pause
    exit /b 2
)
if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
    echo HATA: SABLON_V2_MIMARI\ayarlar.db bulunamadi. Islem iptal edildi.
    pause
    exit /b 2
)
if not exist "%~dp099_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\manuel_mockup_motoru.py" (
    echo HATA: Manuel mockup motoru bulunamadi.
    pause
    exit /b 2
)
python scripts\factory_doctor.py --runtime "%MOCKUP_RUNTIME_WORKSPACE%" --fast
if errorlevel 1 (
    echo HATA: Factory Doctor kritik sorun buldu. Uretim baslatilmadi.
    pause
    exit /b 2
)
echo Kategori / koseler onayi olmayan sablonlar manuel bile olsa kullanilmamalidir.
echo.
set /p "P0_MANUAL_CONFIRM=Baslatmak icin BASLAT yazin: "
if /I not "%P0_MANUAL_CONFIRM%"=="BASLAT" (
    echo Iptal edildi, hicbir gorev baslatilmadi.
    pause
    exit /b 2
)
python "99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\manuel_mockup_motoru.py" --mod dongusel
set "TASK_CODE=%errorlevel%"
if not "%TASK_CODE%"=="0" (
    echo HATA: Manuel mockup gorevi basarisiz oldu. Hata kodu: %TASK_CODE%
    pause
    exit /b %TASK_CODE%
)
echo Tamamlandi. Cikti: %MOCKUP_RUNTIME_WORKSPACE%\3_URETILEN_MOCKUPLAR
pause
exit /b 0
