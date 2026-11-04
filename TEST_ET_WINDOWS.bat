@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist "MERKEZ\.venv\Scripts\python.exe" (
  echo Python ortami yok. Once WINDOWS_HIZLI_BASLAT.bat calistirin.
  pause
  exit /b 1
)
set "PY=MERKEZ\.venv\Scripts\python.exe"
echo PETEK ve 7 kategori merkezini koruyan otomatik testler basliyor...
"%PY%" -B -m pytest -q TESTLER
if errorlevel 1 goto failed
echo TESTLER BASARILI. Gercek Windows gorsel kabulunu ayri yapin.
pause
exit /b 0
:failed
echo TEST HATASI. Ustteki hata mesajini kaydedin.
pause
exit /b 1
