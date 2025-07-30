@echo off
REM Run as Administrator to fix file association issue
REM This tells Windows to trust batch files for file associations

echo Fixing Windows file association for batch files...

REM Get current directory
set "CURRENT_DIR=%~dp0"

REM Register the batch file properly in registry
reg add "HKEY_CLASSES_ROOT\Applications\open-cad.bat" /f
reg add "HKEY_CLASSES_ROOT\Applications\open-cad.bat\shell" /f
reg add "HKEY_CLASSES_ROOT\Applications\open-cad.bat\shell\open" /f
reg add "HKEY_CLASSES_ROOT\Applications\open-cad.bat\shell\open\command" /t REG_SZ /d "\"%CURRENT_DIR%open-cad.bat\" \"%%1\"" /f

echo.
echo ✅ Registry updated!
echo Now try right-clicking a SolidWorks file and choosing "Open with"
echo Your batch file should appear in the list and work properly.
echo.
pause