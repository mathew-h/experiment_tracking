import streamlit as st
import pandas as pd
import io
from database.database import SessionLocal
from database.models import (
    Experiment, SampleInfo, ExperimentalConditions, ExperimentNotes,
    ExperimentalResults, NMRResults, ScalarResults, ExternalAnalysis, PXRFReading
)
from sqlalchemy import text

def download_database_as_excel():
    """
    Fetches data from specified tables and returns it as an Excel file
    in a BytesIO buffer.
    """
    db = SessionLocal()
    try:
        # Define tables to fetch and their corresponding models and sheet names
        tables_to_fetch = {
            "Experiments": Experiment,
            "ExperimentalConditions": ExperimentalConditions,
            "ExperimentNotes": ExperimentNotes,
            "ExperimentalResults": ExperimentalResults,
            "NMRResults": NMRResults,
            "ScalarResults": ScalarResults,
            "SampleInfo": SampleInfo,
            "ExternalAnalyses": ExternalAnalysis,
            "PXRFReadings": PXRFReading,
        }

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for sheet_name, model in tables_to_fetch.items():
                query_result = db.query(model).all()
                if query_result:
                    df = pd.DataFrame([row.__dict__ for row in query_result])
                    # Remove SQLAlchemy internal state column if it exists
                    if '_sa_instance_state' in df.columns:
                        df = df.drop(columns=['_sa_instance_state'])
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                else:
                    # Create an empty sheet if the table has no data
                    pd.DataFrame().to_excel(writer, sheet_name=sheet_name, index=False)
        
        output.seek(0)  # Reset buffer position to the beginning
        return output
    except Exception as e:
        st.error(f"Error generating Excel file: {str(e)}")
        return None
    finally:
        db.close()

def render_sidebar():
    with st.sidebar:
        st.title("Navigation")
        page = st.radio(
            "Go to",
            ["New Experiment", "View Experiments", 
             "New Rock Sample", "View Sample Inventory", "Issue Submission"]
        )
         # Add some statistics or summary information
        st.markdown("---") # Separator
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

        st.markdown("---") # Separator
        
        excel_data = download_database_as_excel()
        if excel_data:
            st.download_button(
                label="Download Database as Excel",
                data=excel_data,
                file_name="database_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        return page