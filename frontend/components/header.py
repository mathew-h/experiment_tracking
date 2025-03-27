"""
Components for rendering the application header.
"""
import os
import streamlit as st


def render_header():
    """Render the header with the current page title and Addis Energy Research icon."""
    col1, col2 = st.columns([1, 4])
    
    with col1:
        # Display the Addis Energy Research icon
        st.image(
            os.path.join(os.path.dirname(__file__), "..", "..", ".streamlit", "static", "Addis_Avatar_SandColor_NoBackground.png"),
            width=100
        )
    
    with col2:
        st.title("Addis Energy Research")
    
    # Add custom CSS for the banner
    st.markdown("""
        <style>
            .banner-container {
                display: flex;
                align-items: center;
                gap: 20px;
                padding: 20px;
                background-color: #f8f9fa;
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .banner-logo {
                width: 120px;
                height: 120px;
                object-fit: contain;
            }
            .banner-title {
                color: #2c3e50;
                font-size: 2.5em;
                margin: 0;
                font-weight: 600;
            }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("---")