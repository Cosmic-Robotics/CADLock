@echo off
title CAD Lock Dashboard Server

REM — Read INSTALL_DIR from .env (must be next to this .bat) —
pushd "%~dp0"
for /f "tokens=2* delims==" %%I in ('findstr /b "INSTALL_DIR=" .env') do set "SCRIPT_PATH=%%J"
popd

if not defined SCRIPT_PATH (
  echo ERROR: “INSTALL_DIR=” not found in .env
  pause
  exit /b 1
)

REM — Extract directory and cd into it —
for %%F in ("%SCRIPT_PATH%") do set "SCRIPT_DIR=%%~dpF"
cd /d "%SCRIPT_DIR%"

echo =============================================
echo    CAD Lock Dashboard Server
echo    Cosmic Engineering
echo =============================================
echo Starting web server at http://localhost:5000
echo Press Ctrl+C to stop
echo.

REM — Ensure Flask is installed —
python -c "import flask" 2>nul || (
  echo Installing Flask...
  pip install flask
)

REM — Launch the dashboard —
python "%SCRIPT_PATH%"

echo.
echo Server stopped.
pause
