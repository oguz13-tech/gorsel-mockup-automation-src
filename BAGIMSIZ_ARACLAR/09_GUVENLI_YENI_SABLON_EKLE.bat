@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
call "%~dp0..\KUR_ORTAM_V491_WINDOWS.bat"
if errorlevel 1 goto failed
rem The setup script validates or creates this exact local Windows interpreter.
set "PYEXE=%~dp0..\MERKEZ\.venv\Scripts\python.exe"
"%PYEXE%" -B "SABLON_V2_MIMARI\tools_runner.py" stage
if errorlevel 1 goto failed
exit /b 0
:failed
echo Arac calistirilamadi: stage. Kod ve canli sablon dosyalari degistirilmedi.
echo Hatayi raporlamak icin bu ekrani kaydedin.
pause
exit /b 1
