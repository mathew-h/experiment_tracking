import streamlit as st
from database.database import SessionLocal
from database.models import SampleInfo, ModificationsLog
import os
from frontend.components.utils import save_uploaded_file, log_modification, generate_form_fields
from frontend.config.variable_config import ROCK_SAMPLE_CONFIG

def render_new_rock_sample():
    """
    Render the interface for creating a new rock sample.
    
    This function creates a form interface that allows users to:
    - Enter basic sample information (ID, classification, location)
    - Add geographical coordinates
    - Provide a sample description
    - Upload a sample photo
    
    The form includes validation and proper error handling for the submission process.
    """
    st.header("New Rock Sample")
    
    with st.form("new_rock_sample_form", clear_on_submit=True):
        # Generate form fields using the configuration
        form_values = generate_form_fields(
            ROCK_SAMPLE_CONFIG,
            {},  # Empty dict for new sample
            list(ROCK_SAMPLE_CONFIG.keys()),
            'rock_sample'
        )
        
        if st.form_submit_button("Save Rock Sample"):
            # Validate required fields
            required_fields = [field for field, config in ROCK_SAMPLE_CONFIG.items() if config.get('required', False)]
            missing_fields = [field for field in required_fields if not form_values.get(field)]
            
            if missing_fields:
                st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
                return
            
            save_rock_sample(
                sample_id=form_values['sample_id'],
                rock_classification=form_values['rock_classification'],
                state=form_values['state'],
                country=form_values['country'],
                latitude=form_values['latitude'],
                longitude=form_values['longitude'],
                description=form_values.get('description', '')
            )

def save_rock_sample(sample_id, rock_classification, state, country, latitude, longitude, description):
    """
    Save a new rock sample to the database (without initial photo).
    
    Args:
        sample_id (str): Unique identifier for the rock sample
        rock_classification (str): Type/classification of the rock
        state (str): State/Province where the sample was collected
        country (str): Country where the sample was collected
        latitude (float): Latitude coordinate of collection site
        longitude (float): Longitude coordinate of collection site
        description (str): Description of the sample
        
    This function:
    - Validates required fields
    - Checks for duplicate sample IDs
    - Creates a new database record (without photo info).
    
    Raises:
        ValueError: If required fields are missing
        DuplicateError: If sample_id already exists
    """
    if not sample_id or not rock_classification:
        st.error("Sample ID and Rock Classification are required")
        return
    
    try:
        db = SessionLocal()
        
        # Check if sample ID already exists
        existing_sample = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        if existing_sample:
            st.error(f"Sample ID {sample_id} already exists")
            db.close()
            return
        
        sample = SampleInfo(
            sample_id=sample_id,
            rock_classification=rock_classification,
            state=state,
            country=country,
            latitude=latitude,
            longitude=longitude,
            description=description
        )
        
        db.add(sample)
        
        log_modification(
            db=db,
            experiment_id=None,
            modified_table="sample_info",
            modification_type="create",
            new_values={
                'sample_id': sample.sample_id,
                'rock_classification': sample.rock_classification,
                'state': sample.state,
                'country': sample.country,
                'latitude': sample.latitude,
                'longitude': sample.longitude,
                'description': sample.description
            }
        )

        db.commit()
        
        st.success(f"Rock sample {sample_id} saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving rock sample: {str(e)}")
    finally:
        if 'db' in locals() and db.is_active:
            db.close()