@echo off
setlocal
chcp 65001 >nul
title Magenta - Guvenli Toplu Degistirme / Tek Tus
cd /d "%~dp0"
set "PYEXE=%~dp0MERKEZ\.venv\Scripts\python.exe"
if exist "%PYEXE%" goto run
where py >nul 2>nul
if errorlevel 1 goto missing
py -3.11 -B "MERKEZ\chroma_replace_ui_v486.py"
goto end
:run
"%PYEXE%" -B "MERKEZ\chroma_replace_ui_v486.py"
goto end
:missing
echo Python 3.11 veya paket venv bulunamadi. Once ana BASLAT_V47_WINDOWS.bat dosyasini calistirin.
:end
if errorlevel 1 (
  echo Magenta araci hata verdi; dosyalar degistirilmedi varsaymayin, geri donus gunlugunu kontrol edin.
  pause
)
exit /b %errorlevel%
