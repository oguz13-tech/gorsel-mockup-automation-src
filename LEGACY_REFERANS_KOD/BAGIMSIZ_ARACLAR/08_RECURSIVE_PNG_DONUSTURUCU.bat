@echo off
chcp 65001 > nul
title Recursive PNG Donusturucu v2
cd /d "%~dp0.."
python ".\SABLON_V2_MIMARI\tools_runner.py" png_recursive
