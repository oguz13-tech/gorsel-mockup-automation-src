@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo MOR PREMIUM VNext - dosya hash kontrolu
py -3.11 -B scripts\v4102_verify_package.py
if errorlevel 1 (
 echo [HATA] MANIFEST UYUMSUZ - KURMAYIN
 pause
 exit /b 1
)
echo [PASS] MOR VNext paket dosyalari dogrulandi. WINDOWS_NOT_VERIFIED.
pause
exit /b 0
