import streamlit as st
import pandas as pd
from database.database import SessionLocal
from database.models import SampleInfo, ExternalAnalysis, ModificationsLog
import os
import datetime
# Import utilities and config
from frontend.components.utils import log_modification, save_uploaded_file, delete_file_if_exists
from frontend.config.variable_config import ANALYSIS_TYPES

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
        db = SessionLocal()
        sample = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        
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
        
        # Display sample information
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
                    with st.expander(f"{analysis.analysis_type} Analysis - {analysis.analysis_date.strftime('%Y-%m-%d')}"):
                        st.write(f"Laboratory: {analysis.laboratory}")
                        st.write(f"Analyst: {analysis.analyst}")
                        if analysis.description:
                            st.write("Description:")
                            st.write(analysis.description)
                        
                        if analysis.report_file_path:
                            st.download_button(
                                f"Download {analysis.report_file_name}",
                                open(analysis.report_file_path, 'rb').read(),
                                file_name=analysis.report_file_name,
                                mime=analysis.report_file_type
                            )
                        
                        if analysis.analysis_metadata:
                            st.write("Additional Data:")
                            st.json(analysis.analysis_metadata)
            else:
                st.info("No external analyses recorded for this sample.")
        
        with col2:
            # Sample Photo
            st.markdown("### Sample Photo")
            if sample.photo_path and os.path.exists(sample.photo_path):
                st.image(sample.photo_path, caption=f"Photo of {sample.sample_id}")
            else:
                st.info("No photo available for this sample.")
            
            # Add Photo Button
            if st.button("Add/Update Photo", key=f"add_photo_{sample_id}"):
                st.session_state.adding_photo = True
                st.session_state.current_sample_id = sample_id
            
            # Photo Upload Form
            if st.session_state.get('adding_photo', False) and st.session_state.get('current_sample_id') == sample_id:
                with st.form(f"photo_upload_form_{sample_id}"):
                    photo = st.file_uploader(
                        "Upload Sample Photo",
                        type=['jpg', 'jpeg', 'png'],
                        help="Upload a photo of the rock sample",
                        key=f"photo_upload_{sample_id}"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Save Photo", key=f"save_photo_{sample_id}"):
                            if photo:
                                update_sample_photo(sample_id, photo)
                                st.session_state.adding_photo = False
                                st.rerun()
                    
                    with col2:
                        if st.form_submit_button("Cancel", key=f"cancel_photo_{sample_id}"):
                            st.session_state.adding_photo = False
            
            # Add External Analysis Button
            if st.button("Add External Analysis", key=f"add_ext_analysis_{sample_id}"):
                st.session_state.adding_analysis = True
                st.session_state.current_sample_id = sample_id
            
            # External Analysis Form
            if st.session_state.get('adding_analysis', False) and st.session_state.get('current_sample_id') == sample_id:
                with st.form(f"external_analysis_form_{sample_id}"):
                    # Use config list for analysis types
                    analysis_type = st.selectbox(
                        "Analysis Type",
                        options=ANALYSIS_TYPES, # Use config list
                        key=f"analysis_type_{sample_id}"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        laboratory = st.text_input("Laboratory", key=f"lab_{sample_id}")
                        analyst = st.text_input("Analyst", key=f"analyst_{sample_id}")
                        analysis_date = st.date_input("Analysis Date", key=f"analysis_date_{sample_id}")
                    
                    with col2:
                        report_file = st.file_uploader(
                            "Upload Report",
                            type=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'jpg', 'png'],
                            key=f"report_file_{sample_id}"
                        )
                    
                    description = st.text_area(
                        "Description",
                        help="Add a description of the analysis",
                        key=f"analysis_desc_{sample_id}"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Save Analysis", key=f"save_analysis_{sample_id}"):
                            if report_file:
                                save_external_analysis(
                                    sample_id,
                                    analysis_type,
                                    report_file,
                                    laboratory,
                                    analyst,
                                    analysis_date,
                                    description
                                )
                                st.session_state.adding_analysis = False
                                st.rerun()
                    
                    with col2:
                        if st.form_submit_button("Cancel", key=f"cancel_analysis_{sample_id}"):
                            st.session_state.adding_analysis = False
        
    except Exception as e:
        st.error(f"Error displaying sample details: {str(e)}")
    finally:
        db.close()

def update_sample_photo(sample_id, photo):
    """
    Update the photo associated with a rock sample.
    
    Args:
        sample_id (str): The unique identifier of the sample
        photo (UploadedFile): The new photo file to save
        
    This function:
    - Creates/ensures the upload directory exists
    - Removes the old photo if it exists
    - Saves the new photo
    - Updates the database record
    - Creates a modification log entry
    """
    try:
        db = SessionLocal()
        sample = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        
        if sample is None:
            st.error(f"Sample with ID {sample_id} not found.")
            return
        
        old_photo_path = sample.photo_path # Store old path for logging/deletion
        
        # Use utility to delete old photo
        delete_file_if_exists(old_photo_path)
        
        # Save new photo using utility
        photo_path = save_uploaded_file(
            file=photo, 
            base_dir_name='sample_photos', 
            filename_prefix=sample_id
        )

        if not photo_path:
            # Handle save error
            db.rollback() # Rollback if file save failed
            st.error("Failed to save new photo.")
            return
        
        # Update sample with new photo path
        sample.photo_path = photo_path
        
        # Log modification using utility
        log_modification(
            db=db,
            experiment_id=None,  # Sample-level modification
            modified_table="sample_info",
            modification_type="update",
            old_values={'photo_path': old_photo_path}, # Log old path
            new_values={
                'sample_id': sample_id,
                'photo_path': photo_path,
                'photo_name': photo.name # Log new name
            }
        )
        
        # Commit the changes
        db.commit()
        
        st.success("Sample photo updated successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error updating sample photo: {str(e)}")
    finally:
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

def save_external_analysis(sample_id, analysis_type, file, laboratory, analyst, analysis_date, description):
    """
    Save a new external analysis record for a rock sample.
    
    Args:
        sample_id (str): The unique identifier of the sample
        analysis_type (str): Type of analysis performed (e.g., 'XRD', 'SEM')
        file (UploadedFile): The analysis report file
        laboratory (str): Name of the laboratory performing the analysis
        analyst (str): Name of the analyst
        analysis_date (datetime.date): Date when the analysis was performed
        description (str): Description of the analysis
        
    This function:
    - Creates/ensures the upload directory exists
    - Saves the analysis report file
    - Creates a database record for the analysis
    - Creates a modification log entry
    """
    try:
        db = SessionLocal()
        
        file_path = None
        file_name = None
        file_type = None

        # Save file using utility
        if file:
            file_path = save_uploaded_file(
                file=file, 
                base_dir_name='external_analyses',
                filename_prefix=f"{sample_id}_{analysis_type}" # More specific prefix
            )
            if file_path:
                file_name = file.name
                file_type = file.type
            else:
                db.rollback()
                st.error("Failed to save analysis report file.")
                return False # Indicate failure
        
        # Combine date and time carefully
        analysis_datetime = datetime.datetime.combine(analysis_date, datetime.datetime.min.time()) if isinstance(analysis_date, datetime.date) else analysis_date
        if not isinstance(analysis_datetime, datetime.datetime):
             # Handle case where analysis_date wasn't a date object (e.g., None)
             analysis_datetime = datetime.datetime.now() # Or set to None, depending on requirements

        # Create new external analysis entry
        analysis = ExternalAnalysis(
            sample_id=sample_id,
            analysis_type=analysis_type,
            report_file_path=file_path, # Use path from utility
            report_file_name=file_name, # Use name from file object
            report_file_type=file_type, # Use type from file object
            analysis_date=analysis_datetime, # Use combined datetime
            laboratory=laboratory,
            analyst=analyst,
            description=description
        )
        
        # Add the analysis to the session
        db.add(analysis)
        
        # Log modification using utility
        new_values={
            'sample_id': sample_id,
            'analysis_type': analysis_type,
            'report_file_name': file_name,
            'report_file_path': file_path,
            'laboratory': laboratory,
            'analyst': analyst,
            'analysis_date': analysis_datetime.isoformat(), # Log as ISO string
            'description': description
        }
        log_modification(
            db=db,
            experiment_id=None,  # Sample-level modification
            modified_table="external_analyses",
            modification_type="add",
            new_values=new_values
        )
        
        # Commit the transaction
        db.commit()
        st.success("External analysis saved successfully!")
        return True # Indicate success
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving external analysis: {str(e)}")
        return False # Indicate failure
    finally:
        # Ensure db is closed if it was opened
        if 'db' in locals() and db.is_active:
             db.close()

def delete_external_analysis(analysis_id):
    """
    Delete an external analysis record and its associated file.
    
    Args:
        analysis_id (int): The unique identifier of the analysis to delete
        
    This function:
    - Removes the analysis report file from storage
    - Deletes the database record
    - Creates a modification log entry for the deletion
    """
    try:
        db = SessionLocal()
        
        # Get the analysis
        analysis = db.query(ExternalAnalysis).filter(ExternalAnalysis.id == analysis_id).first()
        
        if analysis is None:
            st.error("Analysis not found")
            return
        
        # Store old values before deleting
        old_values={
            'sample_id': analysis.sample_id,
            'analysis_type': analysis.analysis_type,
            'laboratory': analysis.laboratory,
            'analyst': analysis.analyst,
            'analysis_date': analysis.analysis_date.isoformat() if analysis.analysis_date else None,
            'description': analysis.description,
            'report_file_path': analysis.report_file_path
        }

        # Delete file using utility
        delete_file_if_exists(analysis.report_file_path)
        
        # Log modification using utility
        log_modification(
            db=db,
            experiment_id=None,  # Sample-level modification
            modified_table="external_analyses",
            modification_type="delete",
            old_values=old_values
        )
        
        # Delete the analysis object
        db.delete(analysis)
        
        # Commit the transaction
        db.commit()
        
        st.success("External analysis deleted successfully!")

    except Exception as e:
        db.rollback()
        st.error(f"Error deleting external analysis: {str(e)}")
        raise e
    finally:
        # Ensure db is closed if it was opened
        if 'db' in locals() and db.is_active:
             db.close()