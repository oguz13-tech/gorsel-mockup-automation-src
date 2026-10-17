@echo off
chcp 65001 >nul
title JARVIS Mockup - Sablon Inceleme Merkezi
cd /d "%~dp0"
call "%~dp0INCELEME_MERKEZINI_AC.bat"
exit /b %errorlevel%
