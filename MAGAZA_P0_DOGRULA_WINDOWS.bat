@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo STORE P0 ISSUE79 - SHA256 manifest kontrolu
py -3.11 -B scripts\v4102_verify_package.py
if errorlevel 1 (
 echo [HATA] SHA256 dosya kontrolu basarisiz. PROGRAMI CALISTIRMAYIN.
 pause
 exit /b 1
)
echo [PASS] Kaynak dosyalar bozulmamis. Windows sistem testi AYRI GEREKIR.
pause
exit /b 0
