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
            # Pass all form values to save_rock_sample
            save_rock_sample(form_values)

def save_rock_sample(form_values):
    """
    Save a new rock sample to the database (without initial photo).
    
    Args:
        form_values (dict): Dictionary containing all form field values from ROCK_SAMPLE_CONFIG
        
    This function:
    - Validates required fields
    - Checks for duplicate sample IDs
    - Creates a new database record (without photo info).
    
    Raises:
        ValueError: If required fields are missing
        DuplicateError: If sample_id already exists
    """
    # Validate required fields using ROCK_SAMPLE_CONFIG
    required_fields = [field for field, config in ROCK_SAMPLE_CONFIG.items() if config.get('required', False)]
    missing_fields = []
    for field in required_fields:
        value = form_values.get(field)
        config = ROCK_SAMPLE_CONFIG[field]
        is_missing = False
        if config['type'] == 'number':
            # For required numbers, only None is missing (assuming 0 is valid)
            if value is None:
                is_missing = True
        else:
            # For other required types (text, select, etc.), None or empty string is missing
            if value is None or value == '':
                is_missing = True

        if is_missing:
            missing_fields.append(config['label']) # Use label for error message

    if missing_fields:
        st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
        return
    
    try:
        db = SessionLocal()
        
        # Check if sample ID already exists
        existing_sample = db.query(SampleInfo).filter(SampleInfo.sample_id == form_values['sample_id']).first()
        if existing_sample:
            st.error(f"Sample ID {form_values['sample_id']} already exists")
            db.close()
            return
        
        # Create sample using all fields from ROCK_SAMPLE_CONFIG
        sample = SampleInfo(**{
            field: form_values.get(field)
            for field in ROCK_SAMPLE_CONFIG.keys()
        })
        
        db.add(sample)
        
        # Log modification using all fields from ROCK_SAMPLE_CONFIG
        log_modification(
            db=db,
            experiment_id=None,
            modified_table="sample_info",
            modification_type="create",
            new_values={
                field: getattr(sample, field)
                for field in ROCK_SAMPLE_CONFIG.keys()
            }
        )

        db.commit()
        
        st.success(f"Rock sample {form_values['sample_id']} saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving rock sample: {str(e)}")
    finally:
        if 'db' in locals() and db.is_active:
            db.close()