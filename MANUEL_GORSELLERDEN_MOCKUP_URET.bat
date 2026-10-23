@echo off
chcp 65001 > nul
title Manuel Mockup Uretim Motoru - Guvenli
cd /d "%~dp0"
if not defined MOCKUP_RUNTIME_WORKSPACE (
  echo Onayli sablonlarin bulundugu runtime klasorunu secin:
  set /p "MOCKUP_RUNTIME_WORKSPACE=Runtime klasoru: "
)
if not exist "%MOCKUP_RUNTIME_WORKSPACE%\SABLON_V2_MIMARI\ayarlar.db" (
  echo BLOCKED: Gecerli runtime/veritabani bulunamadi.
  pause
  exit /b 2
)
echo YALNIZ kaynak SHA'si degismemis, insan onayli sablonlarla uretim...
python 99_SISTEM_MOTORLARI_VE_KODLAR\SISTEM_MOTORU\manuel_mockup_motoru.py --mod dongusel
if errorlevel 1 (
  echo HATA: Render tamamlanamadi. Basari bildirilmiyor.
  pause
  exit /b 2
)
echo Manuel uretim komutu hatasiz tamamlandi. Ciktilari ayrica inceleyin.
pause
exit /b 0
