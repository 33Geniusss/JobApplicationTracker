@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if not errorlevel 1 (
    python app.py --stop
    exit /b
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 app.py --stop
    exit /b
)
echo Python was not found.
pause
