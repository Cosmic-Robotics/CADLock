@echo off
title CAD Lock Dashboard Server

echo =============================================
echo    CAD Lock Dashboard Server
echo    Cosmic Engineering
echo =============================================
echo.
echo Starting web server...
echo Dashboard will be available at: http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo =============================================
echo.

cd /d "C:\Users\brams\OneDrive\Desktop\CAD Lock"

REM Install Flask if not already installed
python -c "import flask" 2>nul || (
    echo Installing Flask...
    pip install flask
    echo.
)

REM Start the dashboard server
python dashboard.py

echo.
echo Server stopped.
pause