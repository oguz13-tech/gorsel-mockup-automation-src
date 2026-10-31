@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo PETEK VNext - 13-16 gercek izgara + kavis + firca + secim koruma SHA256 kontrolu
py -3.11 -B scripts\v4102_verify_package.py
if errorlevel 1 (
 echo [HATA] PAKET BUTUNLUGU DOGRULANAMADI
 pause
 exit /b 1
)
echo [PASS] PETEK VNext paket butunlugu dogrulandi. WINDOWS_NOT_VERIFIED.
pause
exit /b 0
