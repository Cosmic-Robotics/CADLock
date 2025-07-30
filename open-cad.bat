@echo off
REM CAD Lock System - Calls Python script to handle locking (silent mode)

REM Call the Python script with the "open" action (no console window)
pythonw "C:\Users\brams\OneDrive\Desktop\CAD Lock\main.py" open "%~1"