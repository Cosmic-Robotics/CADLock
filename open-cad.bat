@echo off
REM -- Move into script folder (so .env is found) --
pushd "%~dp0"

REM -- Grab INSTALL_DIR from .env --
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

REM -- If a file is passed, open it using the Python script
if not "%~1"=="" (
  python "%INSTALL_PATH%" open "%~1"
) else (
  echo Usage: open-cad.bat "full\path\to\file.sldprt"
  pause
)