@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INCELEME_MERKEZINI_AC.ps1" -OpenPath "/tools"
