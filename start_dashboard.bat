@echo off
title CAD Lock Dashboard Server

REM --- Move to script directory ---
pushd "%~dp0"

REM --- Read INSTALL_DIR from .env ---
set "INSTALL_DIR="
for /f "tokens=2* delims==" %%I in ('findstr /b "INSTALL_DIR=" .env') do set "INSTALL_DIR=%%J"

REM --- Debug output: show what was read ---
echo DEBUG: INSTALL_DIR is [%INSTALL_DIR%]

REM --- Return to original directory ---
popd

REM --- Check if INSTALL_DIR was set ---
if not defined INSTALL_DIR (
    echo ERROR: "INSTALL_DIR=" not found in .env or value is empty.
    pause
    exit /b 1
)

REM --- Change to the install directory ---
cd /d "%INSTALL_DIR%" || (
    echo ERROR: Could not change to directory "%INSTALL_DIR%"
    pause
    exit /b 1
)

echo =============================================
echo    CAD Lock Dashboard Server
echo    Cosmic Engineering
echo =============================================
echo Starting web server at http://localhost:5000
echo Press Ctrl+C to stop
echo.

REM --- Ensure Flask is installed ---
python -c "import flask" 2>nul || (
    echo Installing Flask...
    pip install flask
)

REM --- Launch the dashboard ---
python dashboard.py

echo.
echo Server stopped.
pause