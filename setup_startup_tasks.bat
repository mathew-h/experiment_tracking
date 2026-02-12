@echo off
REM =========================================================================
REM  setup_startup_tasks.bat
REM
REM  Registers Windows Task Scheduler tasks so that the Streamlit app and
REM  the auto-updater start automatically when the PC is turned on.
REM
REM  MUST be run as Administrator (right-click -> Run as administrator).
REM
REM  Tasks created:
REM    1. ExperimentTracker_App       - Starts Streamlit on user logon
REM    2. ExperimentTracker_Updater   - Polls for GitHub updates every 5 min
REM
REM  To remove these tasks later:
REM    schtasks /Delete /TN "ExperimentTracker_App" /F
REM    schtasks /Delete /TN "ExperimentTracker_Updater" /F
REM =========================================================================

:: Check for administrator privileges
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] This script must be run as Administrator.
    echo         Right-click this file and select "Run as administrator".
    pause
    exit /b 1
)

:: Resolve the project directory (where this bat file lives)
set "PROJECT_DIR=%~dp0"
:: Remove trailing backslash for cleaner paths
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo =========================================================================
echo  Setting up startup tasks for Experiment Tracker
echo  Project directory: %PROJECT_DIR%
echo =========================================================================
echo.

:: --- Task 1: Start the Streamlit app on logon ---
echo [1/2] Creating task: ExperimentTracker_App (runs on logon)...

schtasks /Create /TN "ExperimentTracker_App" ^
    /TR "\"%PROJECT_DIR%\start_app.bat\"" ^
    /SC ONLOGON ^
    /RL HIGHEST ^
    /DELAY 0000:30 ^
    /F

if errorlevel 1 (
    echo [ERROR] Failed to create ExperimentTracker_App task.
    pause
    exit /b 1
)
echo [OK] ExperimentTracker_App task created.
echo.

:: --- Task 2: Auto-updater polling every 5 minutes ---
echo [2/2] Creating task: ExperimentTracker_Updater (runs on logon, polls)...

schtasks /Create /TN "ExperimentTracker_Updater" ^
    /TR "\"%PROJECT_DIR%\auto_update.bat\" --poll" ^
    /SC ONLOGON ^
    /RL HIGHEST ^
    /DELAY 0001:00 ^
    /F

if errorlevel 1 (
    echo [ERROR] Failed to create ExperimentTracker_Updater task.
    pause
    exit /b 1
)
echo [OK] ExperimentTracker_Updater task created.
echo.

echo =========================================================================
echo  Setup complete! Both tasks will run automatically on next logon.
echo.
echo  To verify:
echo    schtasks /Query /TN "ExperimentTracker_App"
echo    schtasks /Query /TN "ExperimentTracker_Updater"
echo.
echo  To remove:
echo    schtasks /Delete /TN "ExperimentTracker_App" /F
echo    schtasks /Delete /TN "ExperimentTracker_Updater" /F
echo =========================================================================
pause