@echo off
chcp 65001 >nul
title JARVIS - Guvenli Yeni Sablon Ekle
cd /d "%~dp0.."
python "SABLON_V2_MIMARI\tools_runner.py" stage
if errorlevel 1 (
  echo HATA: Dosyalarin hepsi guvenle alinmamis olabilir. Receipt raporunu kontrol edin.
  pause
  exit /b 2
)
pause
