@echo off
REM -- Move into script folder (so .env is found) --
pushd "%~dp0"

REM -- Grab everything after “INSTALL_DIR=” in .env --
for /f "tokens=2* delims==" %%I in ('findstr /b "INSTALL_DIR=" .env') do set "INSTALL_DIR=%%J"

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

REM -- Call your Python script --
python "%INSTALL_PATH%"

open "%~1"
