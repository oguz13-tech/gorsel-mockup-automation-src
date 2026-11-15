@echo off
setlocal
rem V4 isolated launcher: uses the active CODEX_ACTIVE package only.
set "CODEX_ROOT=%~dp0.."
set "PYTHON=%CODEX_ROOT%\MERKEZ\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"
set "PYTHONPATH=%CODEX_ROOT%"
"%PYTHON%" -m SABLON_V2_MIMARI.tools_runner orientation_sort
exit /b %errorlevel%
