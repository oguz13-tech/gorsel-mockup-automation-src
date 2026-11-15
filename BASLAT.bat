@echo off
setlocal
cd /d "%~dp0"
set "GORSEL_CODE_ROOT=%~dp0"
set "GORSEL_RUNTIME_ROOT=%~dp0.."
set "MOCKUP_RUNTIME_WORKSPACE=%GORSEL_RUNTIME_ROOT%"
call "%~dp0MERKEZ\BASLAT.bat"
endlocal
