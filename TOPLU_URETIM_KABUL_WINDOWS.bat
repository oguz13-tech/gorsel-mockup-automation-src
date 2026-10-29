@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYEXE=%~dp0MERKEZ\.venv\Scripts\python.exe"
if not exist "%PYEXE%" (
    where py >nul 2>nul
    if errorlevel 1 goto no_python
    set "PYEXE=py"
    set "PYARGS=-3.11"
)
"%PYEXE%" %PYARGS% -B "MERKEZ\uretim_toplu_kabul_v479.py"
if errorlevel 1 goto failed
echo.
echo Rapor Not Defteri'nde acildi. Bu tek raporu ChatGPT'ye gonderebilirsiniz.
pause
exit /b 0
:no_python
echo Python 3.11 veya mevcut MERKEZ .venv bulunamadi.
goto failed
:failed
echo Bu SALT-OKUNUR kabul araci tamamlanamadi. Mevcut veriler degistirilmedi.
pause
exit /b 1
