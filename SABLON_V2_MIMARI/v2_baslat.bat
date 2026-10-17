@echo off
chcp 65001 >nul
title JARVIS Mockup - V2 Inceleme Merkezi
REM Same supported launcher, no pip installs, no unexpected migrations.
call "%~dp0..\INCELEME_MERKEZINI_AC.bat"
exit /b %errorlevel%
