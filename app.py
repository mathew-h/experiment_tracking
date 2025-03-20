import streamlit as st
from config import APP_NAME, APP_ICON, APP_LAYOUT
from frontend.components import (
    render_sidebar,
    render_header,
    render_dashboard,
    render_new_experiment,
    render_view_experiments,
    render_settings,
    render_new_rock_sample,
    render_sample_inventory
)
from frontend.auth_components import init_auth_state, render_login_page, render_logout_button
import os
import logging

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
    page_icon=icon_path,  # Using custom icon
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded"
)

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
        elif page == "Settings":
            render_settings()
    except Exception as e:
        logger.error(f"Error in main application: {str(e)}")
        st.error("An error occurred while running the application. Please try again later.")

if __name__ == "__main__":
    main()
