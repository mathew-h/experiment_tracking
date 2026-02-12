@echo off
REM =========================================================================
REM  auto_update.bat
REM  
REM  Single-check auto-updater for the Experiment Tracking application.
REM  Checks GitHub for new commits, backs up the database, pulls changes,
REM  runs migrations, and restarts the Streamlit app.
REM
REM  Usage:
REM    auto_update.bat              - Run a single update check
REM    auto_update.bat --poll       - Run in continuous polling mode (5 min)
REM    auto_update.bat --poll --interval 600   - Poll every 10 minutes
REM    auto_update.bat --restart-only           - Just restart Streamlit
REM
REM  For Windows Task Scheduler, use the no-argument form and schedule it
REM  to run every N minutes.
REM =========================================================================

:: Change to the project directory (where this bat file lives)
cd /d "%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    exit /b 1
)

:: Activate virtual environment
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate
) else (
    echo [WARNING] Virtual environment not found at .venv – using system Python
)

:: Run the auto-updater, passing through any command-line arguments
python -m utils.auto_updater %*

:: Capture exit code
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% neq 0 (
    echo [ERROR] Auto-updater exited with code %EXIT_CODE%. Check logs\auto_updater.log for details.
)

exit /b %EXIT_CODE%
