@echo off
setlocal
title GORSEL MOCKUP GUNLUK KULLANIM V2
echo Program ve paneller kapali kalsin. Yonetici olarak calistirmayin.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0BASLAT.ps1"
echo Pencere kapaninca bu ekran da kapatilabilir. Hata varsa mesaji sohbete gonderin.
pause
endlocal
