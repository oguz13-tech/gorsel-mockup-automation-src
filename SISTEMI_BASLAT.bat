@echo off
title Ana Kontrol Merkezi (V2)
color 0A

echo ===================================================
echo 🚀 GORSEL URETIM FABRIKASI - ANA KONTROL MERKEZI
echo ===================================================
echo.
echo Gerekli sistem kontrol ediliyor...

:: Check if flask is installed
python -c "import flask" >nul 2>&1
if %errorlevel% neq 0 (
    echo Flask bulunamadi, otomatik kuruluyor... lutfen bekleyin.
    pip install flask
)

echo.
echo Ana Kontrol Merkezi calistiriliyor... Lutfen bu siyah ekrani KAPATMAYIN!
echo Tarayiciniz otomatik olarak acilacaktir...
echo.

:: Sunucuyu baslat
start "Motor" cmd /k "python V2_KONTROL_MERKEZI\app.py"

:: 3 Saniye bekle ve tarayiciyi ac
timeout /t 3 /nobreak >nul
start http://127.0.0.1:5000

exit
