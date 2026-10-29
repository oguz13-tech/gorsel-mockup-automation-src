@echo off
rem V4.7.1 canonical entry point; legacy launcher kept for tested compatibility.
cd /d "%~dp0"
call "%~dp0BASLAT_V46_WINDOWS.bat"
exit /b %errorlevel%
