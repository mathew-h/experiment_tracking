import streamlit as st
from config import APP_NAME, APP_LAYOUT
from frontend.components.sidebar import render_sidebar
from frontend.components.header import render_header
from frontend.components.new_experiment import render_new_experiment
from frontend.components.view_experiments import render_view_experiments
from frontend.components.new_rock import render_new_rock_sample
from frontend.components.view_samples import render_sample_inventory
from frontend.components.auth_components import init_auth_state, render_login_page, render_logout_button
from frontend.components.issue_submission import render_issue_submission_form
from utils.scheduler import setup_backup_scheduler, shutdown_scheduler
from utils.database_backup import copy_to_public_location
import os
import logging
import atexit

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize session state for current page if not exists
if 'current_page' not in st.session_state:
    st.session_state.current_page = "New Experiment"

# Initialize authentication state with error handling
try:
    init_auth_state()
    logger.info("Authentication state initialized successfully")
except Exception as e:
    logger.error(f"Error initializing authentication state: {str(e)}")
    st.error("Failed to initialize authentication. Please check your configuration.")
    st.stop()

# Get the absolute path to the icon file
icon_path = os.path.join(os.path.dirname(__file__), ".streamlit", "static", "Addis_Avatar_SandColor_NoBackground.png")

# Streamlit app configuration
st.set_page_config(
    page_title=APP_NAME,
    page_icon=icon_path,
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded"
)

# Create an initial public copy of the database
try:
    public_path = copy_to_public_location()
    if public_path:
        logger.info(f"Created initial public database copy at: {public_path}")
except Exception as e:
    logger.error(f"Error creating initial public database copy: {str(e)}")

# Initialize the backup scheduler
try:
    backup_scheduler = setup_backup_scheduler()
    # Register shutdown handler
    atexit.register(shutdown_scheduler)
    logger.info("Database backup scheduler initialized successfully")
except Exception as e:
    logger.error(f"Error initializing backup scheduler: {str(e)}")

def main():
    try:
        # Show login page if user is not authenticated
        if not st.session_state.get('user'):
            render_login_page()
            return

        # Show main app content if user is authenticated
        page = render_sidebar()
        st.session_state.current_page = page
        
        # Add logout button to sidebar
        render_logout_button()
        
        # Render header after setting the current page
        render_header()
        
        if page == "New Experiment":
            render_new_experiment()
        elif page == "View Experiments":
            render_view_experiments()
        elif page == "New Rock Sample":
            render_new_rock_sample()
        elif page == "View Sample Inventory":
            render_sample_inventory()
        elif page == "Issue Submission":
            render_issue_submission_form()
        # elif page == "Settings":
        #     render_settings()
    except Exception as e:
        logger.error(f"Error in main application: {str(e)}")
        st.error("An error occurred while running the application. Please try again later.")

if __name__ == "__main__":
    main()
