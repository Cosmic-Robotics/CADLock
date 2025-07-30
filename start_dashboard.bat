@echo off
title CAD Lock Dashboard Server

REM Load configuration
call "%~dp0config.bat"

REM Debug output: show what was loaded
echo DEBUG: INSTALL_DIR is [%INSTALL_DIR%]

REM Check if INSTALL_DIR was set
if not defined INSTALL_DIR (
    echo ERROR: INSTALL_DIR not set in config.bat
    pause
    exit /b 1
)

REM Change to the install directory
cd /d "%INSTALL_DIR%" || (
    echo ERROR: Could not change to directory "%INSTALL_DIR%"
    pause
    exit /b 1
)

echo =============================================
echo    CAD Lock Dashboard Server
echo    Cosmic Engineering
echo =============================================
echo Starting web server at http://localhost:%DASHBOARD_PORT%
echo Press Ctrl+C to stop
echo.

REM Ensure Flask is installed
python -c "import flask" 2>nul || (
    echo Installing Flask...
    pip install flask
)

REM Launch the dashboard
python dashboard.py

echo.
echo Server stopped.
pause