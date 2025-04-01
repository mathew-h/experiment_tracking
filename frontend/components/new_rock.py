import streamlit as st
from database.database import SessionLocal
from database.models import SampleInfo, ModificationsLog
import os
from frontend.components.utils import save_uploaded_file, log_modification

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
    
    with st.form("new_rock_sample_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            sample_id = st.text_input(
                "Sample ID",
                help="Enter a unique identifier for this rock sample (e.g., 20UM21)"
            )
            rock_classification = st.text_input(
                "Rock Classification",
                help="Enter the rock type/classification"
            )
            state = st.text_input("State/Province")
            country = st.text_input("Country")
        
        with col2:
            latitude = st.number_input(
                "Latitude",
                min_value=-90.0,
                max_value=90.0,
                step=0.000001,
                format="%.6f"
            )
            longitude = st.number_input(
                "Longitude",
                min_value=-180.0,
                max_value=180.0,
                step=0.000001,
                format="%.6f"
            )
        
        description = st.text_area(
            "Sample Description",
            height=100,
            help="Add any relevant details about the rock sample"
        )
        
        # Add photo upload section
        st.markdown("### Sample Photo")
        photo = st.file_uploader(
            "Upload Sample Photo",
            type=['jpg', 'jpeg', 'png'],
            help="Upload a photo of the rock sample"
        )
        
        if st.form_submit_button("Save Rock Sample"):
            save_rock_sample(
                sample_id=sample_id,
                rock_classification=rock_classification,
                state=state,
                country=country,
                latitude=latitude,
                longitude=longitude,
                description=description,
                photo=photo
            )

def save_rock_sample(sample_id, rock_classification, state, country, latitude, longitude, description, photo=None):
    """
    Save a new rock sample to the database.
    
    Args:
        sample_id (str): Unique identifier for the rock sample
        rock_classification (str): Type/classification of the rock
        state (str): State/Province where the sample was collected
        country (str): Country where the sample was collected
        latitude (float): Latitude coordinate of collection site
        longitude (float): Longitude coordinate of collection site
        description (str): Description of the sample
        photo (UploadedFile, optional): Photo of the rock sample
        
    This function:
    - Validates required fields
    - Checks for duplicate sample IDs
    - Handles photo upload if provided
    - Creates a new database record
    - Ensures proper error handling and database cleanup
    
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
        
        photo_path = None
        photo_name = None
        if photo:
            photo_path = save_uploaded_file(
                file=photo, 
                base_dir_name='sample_photos', 
                filename_prefix=sample_id
            )
            if photo_path:
                photo_name = photo.name
            else:
                db.rollback()
                db.close()
                st.error("Failed to save sample photo.")
                return
        
        sample = SampleInfo(
            sample_id=sample_id,
            rock_classification=rock_classification,
            state=state,
            country=country,
            latitude=latitude,
            longitude=longitude,
            description=description,
            photo_path=photo_path
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
                'description': sample.description,
                'photo_path': sample.photo_path,
                'photo_name': photo_name
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