@echo off
chcp 65001 > nul
title Format Cevirici PNG JPG
cd /d "%~dp0.."
python ".\SABLON_V2_MIMARI\tools_runner.py" convert
