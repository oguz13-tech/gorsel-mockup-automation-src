@echo off
chcp 65001 > nul
title P0 SAFE RELEASE CHECK - READ ONLY
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 scripts\p0_prepare_release.py
) else (
  python scripts\p0_prepare_release.py
)
echo.
echo This is only a read-only acceptance preflight. No installation took place.
echo Send the printed report to ChatGPT before any installation.
pause
