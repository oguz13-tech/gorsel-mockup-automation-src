@echo off
chcp 65001 > nul
title Gorsel Isimlendirici
cd /d "%~dp0.."
python ".\SABLON_V2_MIMARI\tools_runner.py" rename
