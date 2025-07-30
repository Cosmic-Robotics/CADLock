@echo off
REM start_tray_monitor.bat
title CAD Lock System Tray Setup

REM Load INSTALL_DIR from .env file
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="INSTALL_DIR" set "INSTALL_DIR=%%B"
)

echo =============================================
echo    CAD Lock System Tray Monitor
echo =============================================
echo.
echo Installing to system tray...
echo.

cd /d "%INSTALL_DIR%"

REM Install required packages
echo Checking/installing required packages...
python -c "import pystray, PIL, psutil" 2>nul || (
    echo Installing required packages...
    pip install pystray pillow psutil
    echo.
)

echo Starting CAD Lock Monitor in system tray...
echo Look for the lock icon in your system tray!
echo.
echo Right-click the icon for options:
echo - Show Logs (opens in Notepad)
echo - Start/Stop Monitor
echo - Unlock All Files
echo - Quit
echo.
echo The icon will show a red number indicating how many files you have locked.
echo.

REM Start the simple tray monitor without console window
echo Starting in background (no console window)...
start /B pythonw simple_tray.py

timeout /t 3 >nul

echo ✅ CAD Lock Monitor is now running in system tray
echo ✅ This console window can now be closed safely
echo.
echo To stop: Right-click tray icon → Quit
echo To see logs: Right-click tray icon → Show Logs
echo.
echo You can close this window now - the tray monitor will keep running.
pause