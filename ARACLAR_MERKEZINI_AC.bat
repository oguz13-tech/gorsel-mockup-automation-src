@echo off
chcp 65001 > nul
title Profesyonel Araclar Merkezi
cls

set "DEFAULT_RUNTIME=%USERPROFILE%\OneDrive\Masaüstü\GörselÜretme-ve-Mockup Otomasyonu"
if exist "%DEFAULT_RUNTIME%\SABLON_V2_MIMARI\ayarlar.db" (
    set "MOCKUP_RUNTIME_WORKSPACE=%DEFAULT_RUNTIME%"
)

if not defined MOCKUP_RUNTIME_WORKSPACE (
    set "ALT_RUNTIME=%USERPROFILE%\Desktop\GörselÜretme-ve-Mockup Otomasyonu"
    if exist "%ALT_RUNTIME%\SABLON_V2_MIMARI\ayarlar.db" (
        set "MOCKUP_RUNTIME_WORKSPACE=%ALT_RUNTIME%"
    )
)

cd /d "%~dp0"

powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/tools' -TimeoutSec 1 ^| Out-Null; exit 0 } catch { exit 1 }"
if not errorlevel 1 (
    start "" "http://127.0.0.1:8080/tools"
    exit /b 0
)

start "" "http://127.0.0.1:8080/tools"
python ".\SABLON_V2_MIMARI\app.py"
pause
