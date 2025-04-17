import streamlit as st
from database.database import SessionLocal
from database.models import Experiment, SampleInfo
from sqlalchemy import text

def render_sidebar():
    with st.sidebar:
        st.title("Navigation")
        page = st.radio(
            "Go to",
            ["New Experiment", "View Experiments", 
             "New Rock Sample", "View Sample Inventory", "Issue Submission"]
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
                # Use raw SQL to count samples without relying on the model
                result = db.execute(text("SELECT COUNT(*) FROM sample_info"))
                total_samples = result.scalar()
                st.metric("Samples", total_samples)
            except Exception as e:
                st.error(f"Error retrieving sample count: {str(e)}")
            finally:
                db.close()

        return page