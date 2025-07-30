@echo off
REM -- Always use the batch file's folder for .env and main.py --
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%"

REM -- Grab INSTALL_DIR from .env in the script's folder --
for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if /i "%%A"=="INSTALL_DIR" set "INSTALL_DIR=%%B"
)

popd

if not defined INSTALL_DIR (
  echo ERROR: .env missing INSTALL_DIR or file not found.
  pause
  exit /b 1
)

REM -- Build full path to main.py --
if "%INSTALL_DIR:~-1%"=="\" (
  set "INSTALL_PATH=%INSTALL_DIR%main.py"
) else (
  set "INSTALL_PATH=%INSTALL_DIR%\main.py"
)

REM -- For debugging: show what will be run
REM echo Running: python "%INSTALL_PATH%" open "%~1"

REM -- If a file is passed, open it using the Python script
if not "%~1"=="" (
  python "%INSTALL_PATH%" open "%~1"
REM  pause
) else (
  echo Usage: open-cad.bat "full\path\to\file.sldprt"
REM pause
)