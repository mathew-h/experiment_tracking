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
                             delete_external_analysis(analysis.id) # This needs to handle deleting files too
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
                            delete_sample_photo(photo.id)
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
                                # Call save function WITHOUT specific_file_types
                                success = save_external_analysis(
                                    sample_info_id=sample.id, 
                                    analysis_type=form_values['analysis_type'], 
                                    files=uploaded_files, # Pass list of files
                                    laboratory=form_values['laboratory'],
                                    analyst=form_values['analyst'],
                                    analysis_date=form_values['analysis_date'],
                                    description=form_values.get('description', '')
                                )
                                if success:
                                    st.session_state.adding_analysis = False
                                    st.session_state.experiment_updated = True # Flag update
                                    st.rerun()
                                # Keep form open on failure (error shown in save function)

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

def save_external_analysis(sample_info_id, analysis_type, files: list, laboratory, analyst, analysis_date, description):
    """
    Save a new external analysis entry and its associated file(s).
    Args:
        sample_info_id (int): The database ID of the sample
        analysis_type (str): General category for this analysis entry
        files (list): List of UploadedFile objects from Streamlit.
        laboratory (str): Name of the laboratory performing the analysis
        analyst (str): Name of the analyst
        analysis_date (datetime.date): Date when the analysis was performed
        description (str): Description for the overall analysis entry
    Returns:
        bool: True if successful, False otherwise.
    """
    db = None # Initialize db to None
    try:
        db = SessionLocal()
        
        sample = db.query(SampleInfo).filter(SampleInfo.id == sample_info_id).first()
        if not sample:
             st.error(f"Sample with DB ID {sample_info_id} not found for analysis.")
             return False

        # --- Create the main ExternalAnalysis record --- 
        analysis_datetime = datetime.datetime.combine(analysis_date, datetime.datetime.min.time()) if isinstance(analysis_date, datetime.date) else analysis_date
        if not isinstance(analysis_datetime, datetime.datetime):
             analysis_datetime = datetime.datetime.now()

        main_analysis = ExternalAnalysis(
            sample_id=sample.sample_id,
            analysis_type=analysis_type,
            analysis_date=analysis_datetime,
            laboratory=laboratory,
            analyst=analyst,
            description=description
            # No file paths here anymore
        )
        db.add(main_analysis)
        db.flush() # Get the ID for the main_analysis entry
        db.refresh(main_analysis)
        main_analysis_id = main_analysis.id

        # --- Process and save each uploaded file --- 
        saved_files_info = []
        for i, file in enumerate(files):
            # Save the physical file
            file_path = save_uploaded_file(
                file=file, 
                base_dir_name='external_analyses', # Keep same base dir?
                # Make prefix more unique: sampleID_analysisID_fileIndex
                filename_prefix=f"{sample.sample_id}_{main_analysis_id}_{i}"
            )
            if not file_path:
                st.error(f"Failed to save file: {file.name}. Rolling back.")
                db.rollback()
                # Consider deleting already saved files for this batch
                return False 

            # Create the AnalysisFiles database record
            analysis_file_record = AnalysisFiles(
                external_analysis_id=main_analysis_id,
                file_path=file_path,
                file_name=file.name,
                file_type=file.type
            )
            db.add(analysis_file_record)
            # No need to flush/refresh each file record usually, commit handles it
            saved_files_info.append({
                'file_path': file_path,
                'file_name': file.name
            }) # Store info for logging
            
        # --- Log the creation of the main entry and files --- 
        log_modification(
            db=db,
            experiment_id=None, 
            modified_table="external_analyses",
            modification_type="add",
            new_values={
                'sample_id': sample.sample_id,
                'analysis_id': main_analysis_id,
                'analysis_type': analysis_type,
                'laboratory': laboratory,
                'analyst': analyst,
                'analysis_date': analysis_datetime.isoformat(),
                'description': description,
                'added_files': saved_files_info # Log details of added files
            }
        )
        
        # Commit the transaction (saves main entry and all file records)
        db.commit()
        st.success(f"External analysis entry and {len(saved_files_info)} file(s) saved successfully!")
        return True
        
    except Exception as e:
        if db: db.rollback()
        st.error(f"Error saving external analysis: {str(e)}")
        # Consider deleting any successfully saved files before rollback if possible
        return False
    finally:
        if db and db.is_active:
             db.close()

def delete_external_analysis(analysis_id):
    """
    Delete an external analysis record and ALL its associated files.
    Args:
        analysis_id (int): The unique identifier of the ExternalAnalysis record.
    """
    db = None
    try:
        db = SessionLocal()
        # Load the analysis and its associated files eagerly
        analysis = db.query(ExternalAnalysis).options(
            selectinload(ExternalAnalysis.analysis_files)
        ).filter(ExternalAnalysis.id == analysis_id).first()
        
        if analysis is None:
            st.error("Analysis not found")
            return False
        
        # Store details for logging before deletion
        old_values={
            'sample_id': analysis.sample_id,
            'analysis_id': analysis.id,
            'analysis_type': analysis.analysis_type,
            'laboratory': analysis.laboratory,
            'analyst': analysis.analyst,
            'analysis_date': analysis.analysis_date.isoformat() if analysis.analysis_date else None,
            'description': analysis.description,
            'files': [{'id': f.id, 'path': f.file_path, 'name': f.file_name} for f in analysis.analysis_files]
        }
        # Store file paths separately to delete AFTER DB commit
        file_paths_to_delete = [f.file_path for f in analysis.analysis_files if f.file_path]

        # Log the deletion (log before deleting)
        log_modification(
            db=db,
            experiment_id=None,
            modified_table="external_analyses",
            modification_type="delete",
            old_values=old_values
        )
        
        # Delete the main analysis object (cascade should handle AnalysisFiles DB records)
        db.delete(analysis)
        db.commit()
        
        # --- Delete physical files AFTER successful commit ---
        for file_path in file_paths_to_delete:
            delete_file_if_exists(file_path)
        
        st.success("External analysis entry and associated files deleted successfully!")
        return True

    except Exception as e:
        if db: db.rollback()
        st.error(f"Error deleting external analysis: {str(e)}")
        return False
    finally:
        if db and db.is_active:
             db.close()

def delete_analysis_file(analysis_file_id):
    """
    Deletes a single analysis file record and its physical file.
    Args:
        analysis_file_id (int): The DB ID of the AnalysisFiles record.
    """
    db = None
    try:
        db = SessionLocal()
        analysis_file = db.query(AnalysisFiles).filter(AnalysisFiles.id == analysis_file_id).first()

        if not analysis_file:
            st.error(f"Analysis file with ID {analysis_file_id} not found.")
            return False

        # Store details for logging and file deletion
        old_values = {
            'external_analysis_id': analysis_file.external_analysis_id,
            'analysis_file_id': analysis_file.id,
            'file_path': analysis_file.file_path,
            'file_name': analysis_file.file_name
        }
        file_path_to_delete = analysis_file.file_path

        # Log modification before delete
        log_modification(
            db=db,
            experiment_id=None,
            modified_table="analysis_files",
            modification_type="delete",
            old_values=old_values
        )

        # Delete the DB record
        db.delete(analysis_file)
        db.commit()

        # Delete the physical file AFTER commit
        delete_file_if_exists(file_path_to_delete)

        st.success(f"Analysis file '{old_values['file_name']}' deleted successfully!")
        return True

    except Exception as e:
        if db: db.rollback()
        st.error(f"Error deleting analysis file: {str(e)}")
        return False
    finally:
        if db and db.is_active:
            db.close()

def add_sample_photo(sample_info_id, photo_file, description=None):
    """
    Adds a new photo record for a given sample.
    Args:
        sample_info_id (int): The database ID of the SampleInfo record.
        photo_file (UploadedFile): The photo file uploaded via Streamlit.
        description (str, optional): Optional description for the photo.
    """
    try:
        db = SessionLocal()
        
        # Fetch parent sample to confirm it exists (optional but good practice)
        sample = db.query(SampleInfo).filter(SampleInfo.id == sample_info_id).first()
        if not sample:
             st.error(f"Sample with DB ID {sample_info_id} not found.")
             return False

        # Save the file using utility
        file_path = save_uploaded_file(
            file=photo_file,
            base_dir_name='sample_photos', 
            filename_prefix=f"sample_{sample.sample_id}" # Use string sample_id for prefix
        )

        if not file_path:
            st.error("Failed to save photo file.")
            db.rollback()
            return False

        # Create new SamplePhotos object
        new_photo = SamplePhotos(
            sample_info_id=sample_info_id,
            file_path=file_path,
            file_name=photo_file.name,
            file_type=photo_file.type,
            description=description
        )
        db.add(new_photo)

        # Flush and Refresh before logging/commit (like experimental results)
        db.flush()
        db.refresh(new_photo)

        # Log modification
        log_modification(
            db=db,
            experiment_id=None, # Sample-level change
            modified_table="sample_photos",
            modification_type="add",
            new_values={
                'sample_info_id': new_photo.sample_info_id,
                'photo_id': new_photo.id,
                'file_path': new_photo.file_path,
                'file_name': new_photo.file_name,
                'description': new_photo.description
            }
        )
        
        db.commit()
        st.success("Photo added successfully!")
        return True

    except Exception as e:
        db.rollback()
        st.error(f"Error adding sample photo: {str(e)}")
        return False
    finally:
        if 'db' in locals() and db.is_active:
            db.close()

def delete_sample_photo(photo_id):
    """
    Deletes a specific photo record and its associated file.
    Args:
        photo_id (int): The database ID of the SamplePhotos record to delete.
    """
    try:
        db = SessionLocal()
        photo = db.query(SamplePhotos).filter(SamplePhotos.id == photo_id).first()

        if not photo:
            st.error(f"Photo with ID {photo_id} not found.")
            return False

        # Store details for logging before deletion
        old_values = {
            'sample_info_id': photo.sample_info_id,
            'photo_id': photo.id,
            'file_path': photo.file_path,
            'file_name': photo.file_name
        }
        file_path_to_delete = photo.file_path # Store path before deleting object

        # Log modification
        log_modification(
            db=db,
            experiment_id=None,
            modified_table="sample_photos",
            modification_type="delete",
            old_values=old_values
        )

        # Delete DB record
        db.delete(photo)
        db.commit()

        # Delete the file AFTER successful commit
        delete_file_if_exists(file_path_to_delete)

        st.success("Photo deleted successfully!")
        return True

    except Exception as e:
        db.rollback()
        st.error(f"Error deleting sample photo: {str(e)}")
        # We might need to manually clean up the file if commit fails but file exists
        return False
    finally:
        if 'db' in locals() and db.is_active:
            db.close()