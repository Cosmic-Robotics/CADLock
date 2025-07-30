REM ========================================
REM CAD Lock System Configuration
REM ========================================
REM Edit the paths below to match your setup

REM Directory where CAD Lock system is installed
set "INSTALL_DIR=C:\Users\brams\OneDrive\Desktop\CADLock"

REM Root directory of your CAD files  
set "CAD_ROOT_DIR=G:\Shared drives\Cosmic\Engineering\50 - CAD Data"

REM Path to SolidWorks executable
set "SOLIDWORKS_PATH=C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe"

REM Lock directory (usually inside CAD_ROOT_DIR)
set "LOCK_DIR=%CAD_ROOT_DIR%\Locks"

REM Advanced Settings (usually don't need to change)
set "CLEANUP_MAX_HOURS=24"
set "MONITOR_INTERVAL=10"
set "DASHBOARD_HOST=0.0.0.0" 
set "DASHBOARD_PORT=5000"

REM ========================================
REM Don't edit below this line
REM ========================================