@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if not errorlevel 1 (
    python app.py
    if errorlevel 1 pause
    exit /b
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 app.py
    if errorlevel 1 pause
    exit /b
)
echo Python 3.10 or newer is required. Install Python, then run this file again.
pause
