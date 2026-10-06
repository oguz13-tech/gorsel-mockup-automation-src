@echo off
chcp 65001 > nul
title Eski 4K Aracı - Güvenlik Nedeniyle Devre Dışı
cls
echo ===============================================================================
echo      BU ESKI TOPLU 4K ARACI ARTIK KULLANILMIYOR
echo ===============================================================================
echo.
echo NEDEN:
echo  - Üretim dosyasını artifact/recipe kimliği dışında sonradan değiştiriyordu.
echo  - Final QA ve yeniden üretilebilirlik zincirini bypass edebiliyordu.
echo.
echo RealESRGAN gerekiyorsa artık pc_master_factory içindeki ENTEGRE ve
echo FINAL-QA KORUMALI kalite motoru kullanılır. Başarısız AI upscale adayı
echo otomatik reddedilir ve güvenli render korunur.
echo.
echo Hiçbir dosya değiştirilmedi.
echo ===============================================================================
pause
exit /b 2
