import streamlit as st
import pandas as pd
from database.database import SessionLocal
from database.models import SampleInfo, ExternalAnalysis, ModificationsLog, SamplePhotos, AnalysisFiles
import os
import datetime
# Import utilities and config
from frontend.components.utils import (
    log_modification, 
    save_uploaded_file, 
    delete_file_if_exists,
    generate_form_fields
)
from frontend.config.variable_config import (
    ANALYSIS_TYPES,
    EXTERNAL_ANALYSIS_CONFIG
)
# Import for eager loading
from sqlalchemy.orm import selectinload
# Import functions moved to edit_sample.py
from frontend.components.edit_sample import (
    delete_external_analysis, 
    add_external_analysis, 
    add_sample_photo,        # <-- Import added function
    delete_sample_photo,     # <-- Import added function
    delete_analysis_file     # <-- Import added function
)

def render_sample_inventory():
    """
    Render the main sample inventory view with search and filtering capabilities.
    
    This function creates the main interface for viewing rock samples, including:
    - Search functionality by sample ID or classification
    - Location-based filtering
    - A table view of all samples with basic information
    - Navigation to detailed sample views
    
    The function uses Streamlit's session state to manage the view state and
    handles the display of sample details when a sample is selected.
    """
    st.header("Rock Sample Inventory")
    
    # Initialize session state for viewing sample details if not exists
    if 'view_sample_id' not in st.session_state:
        st.session_state.view_sample_id = None
    
    # Add search and filter options
    col1, col2 = st.columns(2)
    with col1:
        search_term = st.text_input("Search by Sample ID or Classification:")
        
    with col2:
        location_filter = st.text_input("Filter by Location (State/Country):")
    
    # Get samples from database
    samples = get_all_samples()
    
    # Apply filters
    if search_term:
        samples = [s for s in samples if (
            search_term.lower() in s['sample_id'].lower() or 
            search_term.lower() in s['rock_classification'].lower()
        )]
    
    if location_filter:
        samples = [s for s in samples if (
            location_filter.lower() in s['state'].lower() or 
            location_filter.lower() in s['country'].lower()
        )]
    
    # Display samples in a table
    if samples:
        st.markdown("### Sample List")
        for sample in samples:
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 3, 1])
                
                with col1:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{sample['sample_id']}</div>", unsafe_allow_html=True)
                with col2:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{sample['rock_classification']}</div>", unsafe_allow_html=True)
                with col3:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{sample['state']}, {sample['country']}</div>", unsafe_allow_html=True)
                with col4:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>({sample['latitude']:.4f}, {sample['longitude']:.4f})</div>", unsafe_allow_html=True)
                with col5:
                    if st.button("Details", key=f"view_sample_{sample['sample_id']}"):
                        st.session_state.view_sample_id = sample['sample_id']
                        st.rerun()
                
                st.markdown("<hr style='margin: 2px 0px; background-color: #f0f0f0; height: 1px; border: none;'>", unsafe_allow_html=True)
    else:
        st.info("No samples found matching the selected criteria.")
    
    # Display sample details if a sample is selected
    if st.session_state.view_sample_id:
        display_sample_details(st.session_state.view_sample_id)

def display_sample_details(sample_id):
    """
    Display detailed information about a specific rock sample.
    
    Args:
        sample_id (str): The unique identifier of the sample to display
        
    This function shows:
    - Basic sample information (ID, classification, location, etc.)
    - External analyses associated with the sample
    - Sample photo with upload/update capabilities
    - Options to add new external analyses
    
    The function handles error cases and provides navigation back to the main inventory view.
    """
    try:
        # Fetch sample using the new function with eager loading
        sample = get_sample_by_id(sample_id)
        
        if sample is None:
            st.error(f"Sample with ID {sample_id} not found.")
            if st.button("Back to Sample List"):
                st.session_state.view_sample_id = None
                st.rerun()
            return
        
        # Add back button
        if st.button("← Back to Sample List"):
            st.session_state.view_sample_id = None
            st.rerun()
        
        # Display sample information header
        st.subheader(f"Sample Details: {sample.sample_id}")
        
        # Create columns for layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Basic Information
            st.markdown("### Basic Information")
            info_data = {
                "Sample ID": sample.sample_id,
                "Rock Classification": sample.rock_classification,
                "Location": f"{sample.state}, {sample.country}",
                "Coordinates": f"({sample.latitude:.6f}, {sample.longitude:.6f})",
                "Description": sample.description or "No description provided",
                "Created": sample.created_at.strftime("%Y-%m-%d %H:%M") if sample.created_at else "N/A",
                "Last Updated": sample.updated_at.strftime("%Y-%m-%d %H:%M") if sample.updated_at else "N/A"
            }
            st.table(pd.DataFrame([info_data]).T.rename(columns={0: "Value"}))
            
            # External Analyses
            st.markdown("### External Analyses")
            analyses = sample.external_analyses
            if analyses:
                for analysis in analyses:
                    with st.expander(f"{analysis.analysis_type} ({analysis.laboratory} - {analysis.analysis_date.strftime('%Y-%m-%d')})"):
                        st.write(f"**Laboratory:** {analysis.laboratory}")
                        st.write(f"**Analyst:** {analysis.analyst}")
                        if analysis.description:
                            st.write("**Description:**")
                            st.markdown(f"> {analysis.description}") # Use markdown for blockquote feel
                        if analysis.analysis_metadata:
                            st.write("**Additional Metadata:**")
                            st.json(analysis.analysis_metadata)
                        
                        st.markdown("--- ")
                        st.markdown("**Analysis Files:**")
                        if analysis.analysis_files:
                            for analysis_file in analysis.analysis_files:
                                file_key = f"analysis_file_{analysis_file.id}"
                                file_col1, file_col2 = st.columns([4, 1])
                                with file_col1:
                                    if analysis_file.file_path and os.path.exists(analysis_file.file_path):
                                        try:
                                            with open(analysis_file.file_path, 'rb') as fp:
                                                st.download_button(
                                                    f"Download {analysis_file.file_name}",
                                                    fp.read(),
                                                    file_name=analysis_file.file_name,
                                                    mime=analysis_file.file_type,
                                                    key=f"download_{file_key}"
                                                )
                                        except Exception as e:
                                            st.warning(f"Could not read file {analysis_file.file_name}: {e}")
                                    elif analysis_file.file_path:
                                        st.warning(f"File not found: {analysis_file.file_name}")
                                    else:
                                        st.info("No file path recorded.")
                                with file_col2:
                                    if st.button("Del", key=f"delete_{file_key}", help="Delete this specific file"):
                                        delete_analysis_file(analysis_file.id)
                                        st.rerun()
                                st.markdown("<hr style='margin: 1px 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)
                        else:
                            st.info("No specific files uploaded for this analysis entry.")

                        st.markdown("--- ")
                        # Delete button for the entire analysis entry (including all files)
                        if st.button("Delete Entire Analysis Entry", key=f"delete_analysis_{analysis.id}"):
                             delete_external_analysis(analysis.id) # Use imported function
                             st.rerun() # Rerun to refresh view after delete
            else:
                st.info("No external analyses recorded for this sample.")
        
        with col2:
            # Sample Photos Section (Modified)
            st.markdown("### Sample Photos")
            photos = sample.photos
            if photos:
                for photo in photos:
                    photo_key = f"photo_{photo.id}"
                    with st.expander(f"Photo {photo.id} ({photo.file_name or 'details'}) - Added: {photo.created_at.strftime('%Y-%m-%d')}"):
                        if photo.file_path and os.path.exists(photo.file_path):
                            try:
                                st.image(photo.file_path, caption=f"ID: {photo.id} - {photo.file_name}")
                            except Exception as e:
                                st.warning(f"Could not load image {photo.file_name}: {e}")
                        else:
                            st.warning(f"Photo file not found: {photo.file_name}")
                        if photo.description:
                            st.write("Description:")
                            st.write(photo.description)
                        
                        # Delete button for each photo
                        if st.button("Delete Photo", key=f"delete_{photo_key}"):
                            delete_sample_photo(photo.id) # Use imported function
                            st.rerun() # Rerun to refresh view after delete
            else:
                st.info("No photos available for this sample.")
            
            # Add Photo Button
            if st.button("Add Photo", key=f"add_photo_{sample_id}"):
                # Initialize session state flags for the form
                st.session_state.adding_photo = True
                st.session_state.adding_analysis = False # Ensure analysis form is closed
                st.session_state.current_sample_id = sample_id 
                st.session_state.current_sample_db_id = sample.id
                st.rerun() # Rerun to show the form immediately

            # Photo Upload Form 
            if st.session_state.get('adding_photo') and st.session_state.get('current_sample_id') == sample_id:
                 with st.form(f"photo_upload_form_{sample_id}", clear_on_submit=True):
                    st.markdown("#### Upload New Photo")
                    photo_file = st.file_uploader(
                        "Select Photo",
                        type=['jpg', 'jpeg', 'png'],
                        help="Select a photo file to upload.",
                        key=f"photo_upload_{sample_id}"
                    )
                    photo_desc = st.text_area("Photo Description (Optional)", key=f"photo_desc_{sample_id}")
                    
                    submitted = st.form_submit_button("Save Photo")
                    if submitted:
                        if photo_file:
                            # Calls the imported add_sample_photo function
                            add_sample_photo(st.session_state.current_sample_db_id, photo_file, photo_desc)
                            st.session_state.adding_photo = False
                            st.session_state.experiment_updated = True # Flag update for potential refresh
                            st.rerun()
                        else:
                             st.warning("Please select a photo file.")
                    
                    # Add a cancel button
                    if st.form_submit_button("Cancel"):
                         st.session_state.adding_photo = False
                         st.rerun()

            # Add External Analysis Button
            if st.button("Add External Analysis Entry", key=f"add_ext_analysis_{sample_id}"):
                st.session_state.adding_analysis = True
                st.session_state.adding_photo = False # Ensure photo form is closed
                st.session_state.current_sample_id = sample_id
                st.session_state.current_sample_db_id = sample.id 
                st.rerun() # Rerun to show the form immediately
            
            # External Analysis Form
            if st.session_state.get('adding_analysis', False) and st.session_state.get('current_sample_id') == sample_id:
                with st.form(f"external_analysis_form_{sample_id}", clear_on_submit=True):
                    st.markdown("#### Add New Analysis Entry")
                    # Keep fields for the overall analysis entry (using generate_form_fields)
                    form_values = generate_form_fields(
                        EXTERNAL_ANALYSIS_CONFIG,
                        {},  # Empty dict for new analysis
                        list(EXTERNAL_ANALYSIS_CONFIG.keys()),
                        f'analysis_{sample_id}'
                    )
                    
                    # Keep multi-file uploader
                    uploaded_files = st.file_uploader(
                        "Upload Analysis File(s)",
                        accept_multiple_files=True,
                        key=f"report_files_{sample_id}"
                    )
                    
                    submitted = st.form_submit_button("Save Analysis Entry")
                    if submitted:
                            required_fields = [field for field, config in EXTERNAL_ANALYSIS_CONFIG.items() if config.get('required', False)]
                            missing_fields = [field for field in required_fields if not form_values.get(field)]
                            
                            if missing_fields:
                                st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
                            elif not uploaded_files:
                                st.error("Please upload at least one analysis file.")
                            else:
                                # Prepare the analysis_data dict from form_values
                                analysis_data_to_save = {
                                    'analysis_type': form_values['analysis_type'],
                                    'laboratory': form_values['laboratory'],
                                    'analyst': form_values['analyst'],
                                    'analysis_date': form_values['analysis_date'], # Already a date object
                                    'description': form_values.get('description', ''),
                                    'analysis_metadata': None # Add logic here if metadata is captured in form
                                }
                                
                                # Calls the imported add_external_analysis function
                                success = add_external_analysis(
                                    user_sample_id=sample.sample_id, # Pass the string sample ID
                                    analysis_data=analysis_data_to_save, # Pass the prepared data dict
                                    uploaded_files=uploaded_files # Pass the list of files
                                )
                                if success:
                                    st.session_state.adding_analysis = False
                                    st.session_state.experiment_updated = True # Flag update
                                    st.rerun()

                    # Add a cancel button
                    if st.form_submit_button("Cancel"):
                         st.session_state.adding_analysis = False
                         st.rerun()

    except Exception as e:
        st.error(f"Error displaying sample details: {str(e)}")

def get_sample_by_id(sample_id_str):
    """
    Retrieves a specific sample by its string ID with related photos and analyses.
    Args:
        sample_id_str (str): The string ID of the sample.
    Returns:
        SampleInfo: SQLAlchemy ORM object or None if not found.
    """
    try:
        db = SessionLocal()
        sample = db.query(SampleInfo).options(
            selectinload(SampleInfo.photos),
            # Load external analyses AND their associated files
            selectinload(SampleInfo.external_analyses).selectinload(ExternalAnalysis.analysis_files)
        ).filter(SampleInfo.sample_id == sample_id_str).first()
        return sample
    except Exception as e:
        st.error(f"Error retrieving sample {sample_id_str}: {str(e)}")
        return None
    finally:
        if 'db' in locals() and db.is_active:
            db.close()

def get_all_samples():
    """
    Retrieve all rock samples from the database.
    
    Returns:
        list: A list of dictionaries containing sample information, including:
            - sample_id
            - rock_classification
            - state
            - country
            - latitude
            - longitude
            - description
            - created_at
            - updated_at
            
    The function handles database errors and ensures proper connection cleanup.
    """
    try:
        db = SessionLocal()
        samples = db.query(SampleInfo).all()
        
        return [{
            'sample_id': sample.sample_id,
            'rock_classification': sample.rock_classification,
            'state': sample.state,
            'country': sample.country,
            'latitude': sample.latitude,
            'longitude': sample.longitude,
            'description': sample.description,
            'created_at': sample.created_at,
            'updated_at': sample.updated_at
        } for sample in samples]
    except Exception as e:
        st.error(f"Error retrieving samples: {str(e)}")
        return []
    finally:
        db.close()