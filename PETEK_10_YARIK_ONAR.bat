@echo off
setlocal
cd /d "%~dp0"
if exist "MERKEZ\.venv\Scripts\python.exe" (
  "MERKEZ\.venv\Scripts\python.exe" -B "tools\repair_ten_slot_draft.py"
) else (
  echo Once KURULUM.bat dosyasini calistirin.
  pause
  exit /b 1
)
if errorlevel 1 pause
endlocal
