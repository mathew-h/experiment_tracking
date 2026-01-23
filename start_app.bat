@echo off
echo Starting Experiment Tracker Application...

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed! Please install Python 3.8 or higher.
    pause
    exit /b 1
)

:: Activate virtual environment
call .venv\Scripts\activate
if errorlevel 1 (
    echo Failed to activate virtual environment!
    pause
    exit /b 1
)

:: Set environment variables (if needed)
set STREAMLIT_SERVER_PORT=8501
set STREAMLIT_SERVER_ADDRESS=0.0.0.0

:: Start the Streamlit application
echo Starting Streamlit application...
python -m streamlit run app.py
if errorlevel 1 (
    echo Failed to start Streamlit application!
    pause
    exit /b 1
)

:: Keep the window open if there's an error
pause 