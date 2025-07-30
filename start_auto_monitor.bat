REM === start_auto_monitor.bat ===
@echo off
title CAD Auto-Lock Monitor

echo =============================================
echo    CAD Auto-Lock Monitor (Integrated)
echo    Cosmic Engineering
echo =============================================
echo.
echo Features:
echo - Detects open SolidWorks files via temp files
echo - Auto-creates/removes locks in real-time
echo - Cleans up old locks automatically
echo - Immediate cleanup when SolidWorks closes
echo.
echo Press Ctrl+C to stop monitoring
echo =============================================
echo.

cd /d "C:\Users\brams\OneDrive\Desktop\CAD Lock"

REM Install required packages if not already installed
echo Checking required packages...
python -c "import psutil" 2>nul || (
    echo Installing psutil...
    pip install psutil
    echo.
)

REM Start the integrated auto-monitor
python main.py start-monitor

echo.
echo Monitor stopped.
pause

REM === cleanup_locks.bat ===
@echo off
title CAD Lock Cleanup

echo =============================================
echo    CAD Lock Cleanup Tool
echo =============================================
echo.
echo Choose cleanup option:
echo 1. Remove all MY locks (immediate)
echo 2. Remove stale locks older than 24 hours
echo 3. Remove stale locks older than custom hours
echo 4. Cancel
echo.
set /p choice="Enter choice (1-4): "

cd /d "C:\Users\brams\OneDrive\Desktop\CAD Lock"

if "%choice%"=="1" (
    echo.
    echo Removing all your locks...
    python main.py unlock-all
) else if "%choice%"=="2" (
    echo.
    echo Removing locks older than 24 hours...
    python main.py cleanup 24
) else if "%choice%"=="3" (
    set /p hours="Enter hours: "
    echo.
    echo Removing locks older than !hours! hours...
    python main.py cleanup !hours!
) else (
    echo Cancelled.
)

echo.
pause

REM === start_dashboard_and_monitor.bat ===
@echo off
title CAD Lock System - Dashboard + Monitor

echo =============================================
echo    CAD Lock System Startup
echo    Dashboard + Auto-Monitor
echo =============================================
echo.
echo Starting both:
echo 1. Web Dashboard (http://localhost:5000)
echo 2. Auto-Lock Monitor (background)
echo.
echo Press Ctrl+C to stop everything
echo =============================================
echo.

cd /d "C:\Users\brams\OneDrive\Desktop\CAD Lock"

REM Start auto-monitor in background
echo Starting auto-monitor...
start /B python main.py start-monitor

REM Wait a moment
timeout /t 3 >nul

REM Start dashboard (this will be the main process)
echo Starting dashboard...
python dashboard.py

REM If dashboard stops, cleanup
echo.
echo Stopping auto-monitor...
python main.py stop-monitor

pause