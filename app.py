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

# Initialize session state for current page if not exists
if 'current_page' not in st.session_state:
    st.session_state.current_page = "Dashboard"

# Initialize authentication state
init_auth_state()

# Get the absolute path to the icon file
icon_path = os.path.join(os.path.dirname(__file__), "frontend", "static", "Addis_Avatar_SandColor_NoBackground.png")

# Streamlit app configuration
st.set_page_config(
    page_title=APP_NAME,
    page_icon=icon_path,  # Using custom icon
    layout=APP_LAYOUT,
    initial_sidebar_state="expanded"
)

def main():
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
    
    if page == "Dashboard":
        render_dashboard()
    elif page == "New Experiment":
        render_new_experiment()
    elif page == "View Experiments":
        render_view_experiments()
    elif page == "New Rock Sample":
        render_new_rock_sample()
    elif page == "View Sample Inventory":
        render_sample_inventory()
    elif page == "Settings":
        render_settings()

if __name__ == "__main__":
    main()
