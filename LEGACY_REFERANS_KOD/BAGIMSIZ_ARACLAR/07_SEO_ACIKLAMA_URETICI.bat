@echo off
chcp 65001 > nul
title SEO Aciklama Uretici
cd /d "%~dp0.."
python ".\SABLON_V2_MIMARI\tools_runner.py" seo_descriptions
