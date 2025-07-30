@echo off
REM CAD Lock System - Calls Python script to handle locking

REM Call the Python script with the "open" action (show messages but hide console)
python "C:\Users\brams\OneDrive\Desktop\CAD Lock\main.py" open "%~1"