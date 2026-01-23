@echo off
echo Setting up Experiment Tracker on Lab PC...

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed! Please install Python 3.8 or higher.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment!
        pause
        exit /b 1
    )
)

:: Activate virtual environment
call .venv\Scripts\activate
if errorlevel 1 (
    echo Failed to activate virtual environment!
    pause
    exit /b 1
)

:: Install requirements
echo Installing required packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements!
    pause
    exit /b 1
)

:: Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file...
    copy .env.example .env
    if errorlevel 1 (
        echo Failed to create .env file!
        pause
        exit /b 1
    )
    echo Please edit the .env file with your configuration settings.
)

:: Initialize database only if it doesn't exist
if not exist experiments.db (
    echo Initializing new database...
    python -m alembic upgrade head
    if errorlevel 1 (
        echo Failed to initialize database!
        pause
        exit /b 1
    )
) else (
    echo Database file exists, skipping initialization...
)

echo Setup complete! You can now run start_app.bat to start the application.
pause 