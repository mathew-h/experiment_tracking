@echo off
echo Starting Experiment Tracker Application...

:: Activate virtual environment
call .venv\Scripts\activate

:: Set environment variables (if needed)
set STREAMLIT_SERVER_PORT=8501
set STREAMLIT_SERVER_ADDRESS=localhost

:: Start the Streamlit application
streamlit run app.py

:: Keep the window open if there's an error
pause 