
from database.database import SessionLocal
from database.models import SampleInfo, ExternalAnalysis
import streamlit as st

def get_sample_info(sample_id):
    """Get sample information from the database."""
    try:
        db = SessionLocal()
        sample_info = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        
        if sample_info:
            return {
                'id': sample_info.id,
                'sample_id': sample_info.sample_id,
                'rock_classification': sample_info.rock_classification,
                'state': sample_info.state,
                'country': sample_info.country,
                'latitude': sample_info.latitude,
                'longitude': sample_info.longitude,
                'description': sample_info.description,
                'created_at': sample_info.created_at,
                'updated_at': sample_info.updated_at
            }
        return None
    except Exception as e:
        st.error(f"Error retrieving sample information: {str(e)}")
        return None
    finally:
        db.close()

def get_external_analyses(sample_id):
    """Get external analyses for a sample from the database."""
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