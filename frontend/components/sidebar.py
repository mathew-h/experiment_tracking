import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from database.database import SessionLocal
from database.models import (
    Experiment, SampleInfo, ExperimentalConditions, ExperimentNotes,
    ExperimentalResults, ScalarResults, ExternalAnalysis, PXRFReading,
    ModificationsLog
)
from sqlalchemy import text, and_

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

def generate_weekly_log():
    """
    Generates a CSV file containing all database modifications from the last 7 days.
    """
    db = SessionLocal()
    try:
        # Calculate date 7 days ago
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        # Get modifications log entries
        modifications = db.query(ModificationsLog).filter(
            ModificationsLog.created_at >= seven_days_ago
        ).all()
        
        # Get new experiments
        new_experiments = db.query(Experiment).filter(
            Experiment.created_at >= seven_days_ago
        ).all()
        
        # Get new sample entries
        new_samples = db.query(SampleInfo).filter(
            SampleInfo.created_at >= seven_days_ago
        ).all()
        
        # Get new experimental results
        new_results = db.query(ExperimentalResults).filter(
            ExperimentalResults.created_at >= seven_days_ago
        ).all()
        
        # Prepare data for CSV
        log_data = []
        
        # Add modifications log entries
        for mod in modifications:
            log_data.append({
                'ID': mod.experiment_id or 'N/A',
                'Type': f'Modification - {mod.modification_type}',
                'Description': f'Modified {mod.modified_table}',
                'Date': mod.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Add new experiments
        for exp in new_experiments:
            log_data.append({
                'ID': exp.experiment_id,
                'Type': 'New Experiment',
                'Description': f'Status: {exp.status.value}',
                'Date': exp.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Add new samples
        for sample in new_samples:
            log_data.append({
                'ID': sample.sample_id,
                'Type': 'New Sample',
                'Description': f'Rock Classification: {sample.rock_classification}',
                'Date': sample.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Add new results
        for result in new_results:
            log_data.append({
                'ID': result.experiment_id,
                'Description': result.description or 'No description',
                'Date': result.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Sort by date
        log_data.sort(key=lambda x: x['Date'], reverse=True)
        
        # Convert to DataFrame and then to CSV
        df = pd.DataFrame(log_data)
        output = io.StringIO()
        df.to_csv(output, index=False)
        return output.getvalue()
    except Exception as e:
        st.error(f"Error generating weekly log: {str(e)}")
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
        
        # Add weekly log download button
        weekly_log_data = generate_weekly_log()
        if weekly_log_data:
            st.download_button(
                label="Download Weekly Log",
                data=weekly_log_data,
                file_name=f"weekly_log_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        
        excel_data = download_database_as_excel()
        if excel_data:
            st.download_button(
                label="Download Database as Excel",
                data=excel_data,
                file_name="database_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        return page