@echo off
REM CAD Lock System - Calls Python script to handle locking
echo Opening CAD file with lock check...

REM Call the Python script with the "open" action
python "C:\Users\brams\OneDrive\Desktop\CAD Lock\main.py" open "%~1"

echo.
echo Press any key to continue...
pause >nul