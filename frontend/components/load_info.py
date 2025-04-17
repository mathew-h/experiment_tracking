from database.database import SessionLocal
from database.models import SampleInfo, ExternalAnalysis
import streamlit as st
from frontend.config.variable_config import ROCK_SAMPLE_CONFIG

def get_sample_info(sample_id):
    """
    Retrieve detailed information about a specific rock sample.
    
    Args:
        sample_id (str): The unique identifier of the sample to retrieve
        
    Returns:
        dict: Dictionary containing sample information with fields defined in ROCK_SAMPLE_CONFIG
    """
    try:
        db = SessionLocal()
        sample_info = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        
        if sample_info:
            # Create dictionary using field names from ROCK_SAMPLE_CONFIG
            return {
                field: getattr(sample_info, field)
                for field in ROCK_SAMPLE_CONFIG.keys()
            }
        return None
    except Exception as e:
        st.error(f"Error retrieving sample information: {str(e)}")
        return None
    finally:
        db.close()

def get_external_analyses(sample_id):
    """
    Retrieve all external analyses associated with a rock sample.
    
    Args:
        sample_id (str): The unique identifier of the sample
        
    Returns:
        list: List of dictionaries containing analysis information including:
            - id: Database record ID
            - analysis_type: Type of analysis performed
            - report_file_path: Path to the analysis report file
            - report_file_name: Name of the report file
            - report_file_type: MIME type of the report file
            - analysis_date: Date when analysis was performed
            - laboratory: Name of the laboratory
            - analyst: Name of the analyst
            - description: Analysis description
            - analysis_metadata: Additional analysis data
            - created_at: Creation timestamp
            - updated_at: Last update timestamp
            
    The function handles database errors and ensures proper connection cleanup.
    Returns an empty list if no analyses are found or if an error occurs.
    """
    try:
        db = SessionLocal()
        analyses = db.query(ExternalAnalysis).filter(ExternalAnalysis.sample_id == sample_id).all()
        
        return [{
            'id': analysis.id,
            'analysis_type': analysis.analysis_type,
            'report_file_path': analysis.report_file_path,
            'report_file_name': analysis.report_file_name,
            'report_file_type': analysis.report_file_type,
            'analysis_date': analysis.analysis_date,
            'laboratory': analysis.laboratory,
            'analyst': analysis.analyst,
            'description': analysis.description,
            'analysis_metadata': analysis.analysis_metadata,
            'created_at': analysis.created_at,
            'updated_at': analysis.updated_at
        } for analysis in analyses]
    except Exception as e:
        st.error(f"Error retrieving external analyses: {str(e)}")
        return []
    finally:
        db.close()