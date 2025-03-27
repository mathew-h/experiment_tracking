import streamlit as st
from database.database import SessionLocal
from database.models import Experiment, SampleInfo

def render_sidebar():
    with st.sidebar:
        st.title("Navigation")
        page = st.radio(
            "Go to",
            ["New Experiment", "View Experiments", 
             "New Rock Sample", "View Sample Inventory", "Settings"]
        )
         # Add some statistics or summary information
        st.markdown("### Quick Statistics")
        col1, col2 = st.columns(2)
        
        with col1:
            try:
                db = SessionLocal()
                total_experiments = db.query(Experiment).count()
                st.metric("Experiments", total_experiments)
            except Exception as e:
                st.error(f"Error retrieving experiment count: {str(e)}")
            finally:
                db.close()
        
        with col2:
            try:
                db = SessionLocal()
                total_samples = db.query(SampleInfo).count()
                st.metric("Samples", total_samples)
            except Exception as e:
                st.error(f"Error retrieving sample count: {str(e)}")
            finally:
                db.close()

        return page