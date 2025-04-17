import streamlit as st
from database.database import SessionLocal
from database.models import ExternalAnalysis, SampleInfo, AnalysisFiles, SamplePhotos
from .utils import log_modification, delete_file_if_exists, save_uploaded_file
import json
import datetime
from sqlalchemy.orm import selectinload
import os
from frontend.config.variable_config import ROCK_SAMPLE_CONFIG

def delete_external_analysis(analysis_id):
    """
    Delete external analysis from the database.
    
    Args:
        analysis_id (int): The unique identifier of the analysis to delete
        
    This function:
    - Retrieves the analysis to be deleted
    - Removes associated files from storage (Handles both direct path and AnalysisFiles relation)
    - Creates a modification log entry
    - Deletes the database record
    - Handles database transactions and error cases
    """
    db = SessionLocal()
    try:
        # Get the analysis and related files
        analysis = db.query(ExternalAnalysis).options(selectinload(ExternalAnalysis.analysis_files)).filter(ExternalAnalysis.id == analysis_id).first()
        
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
            # Include info about files being deleted
            'analysis_files': [{'name': f.file_name, 'path': f.file_path} for f in analysis.analysis_files]
        }

        # --- Delete associated files from storage --- 
        files_deleted_info = []
        for file_record in analysis.analysis_files:
            deleted = delete_file_if_exists(file_record.file_path)
            files_deleted_info.append({
                'name': file_record.file_name,
                'path': file_record.file_path,
                'deleted_from_storage': deleted
            })
            if not deleted:
                 st.warning(f"Could not delete file from storage: {file_record.file_path}")
        # Add actual deletion status to log
        old_values['deleted_files_status'] = files_deleted_info
                 
        # Use utility for logging
        log_modification(
            db=db,
            experiment_id=None, # Sample-level modification
            modified_table="external_analyses",
            modification_type="delete",
            old_values=old_values
        )
        
        # Delete the analysis (cascade should delete AnalysisFiles entries)
        db.delete(analysis)
        
        # Commit the transaction
        db.commit()
        
        st.success("External analysis and associated files deleted successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error deleting external analysis: {str(e)}")
        raise e # Re-raise after logging/rollback
    finally:
        db.close()

# Add other sample editing functions here later, e.g.,
# def update_sample_info(sample_id, data):
#     pass

def add_external_analysis(user_sample_id, analysis_data, uploaded_files: list = None):
    """
    Adds a new external analysis record for a given sample and associates uploaded files.

    Args:
        user_sample_id (str): The user-defined string ID of the sample.
        analysis_data (dict): Dictionary containing the analysis details 
                                (analysis_type, date, lab, analyst, description, metadata).
        uploaded_files (list[UploadedFile], optional): List of report files to associate.

    Returns:
        bool: True if successful, False otherwise.
    """
    db = SessionLocal()
    saved_file_paths = [] # Keep track of files saved in this run for cleanup
    try:
        # --- Step 1 & 2: Find SampleInfo record and get its integer ID --- 
        sample_info_record = db.query(SampleInfo).filter(SampleInfo.sample_id == user_sample_id).first()

        if not sample_info_record:
            st.error(f"Sample with ID '{user_sample_id}' not found. Cannot add analysis.")
            return False

        # --- Step 3: Get the SampleInfo primary key (integer) --- 
        sample_info_primary_key_id = sample_info_record.id

        # --- Step 4: Create the ExternalAnalysis object --- 
        new_analysis = ExternalAnalysis(
            sample_id=user_sample_id,               # User-defined string ID
            sample_info_id=sample_info_primary_key_id, # Integer foreign key *<- Now included*
            analysis_type=analysis_data.get('analysis_type'),
            analysis_date=analysis_data.get('analysis_date'), # Ensure this is a datetime object or None
            laboratory=analysis_data.get('laboratory'),
            analyst=analysis_data.get('analyst'),
            pxrf_reading_no=analysis_data.get('pxrf_reading_no'), # Include new field
            description=analysis_data.get('description'),
            analysis_metadata=json.dumps(analysis_data.get('analysis_metadata')) if analysis_data.get('analysis_metadata') else None
        )
        db.add(new_analysis)

        # --- Flush to get new_analysis.id --- 
        try:
            db.flush()
            db.refresh(new_analysis)
        except Exception as flush_err:
             st.error(f"DB flush/refresh error after adding analysis details: {flush_err}")
             db.rollback()
             return False # Don't proceed if main record fails
        
        # --- Handle File Uploads (Loop through list) --- 
        analysis_file_entries_info = []
        if uploaded_files:
            for idx, uploaded_file in enumerate(uploaded_files):
                if uploaded_file:
                    filename_prefix = f"sample_{sample_info_primary_key_id}_analysis_{new_analysis.id}_{idx}" # Make prefix unique per file
                    file_path = save_uploaded_file(
                        file=uploaded_file, 
                        base_dir_name='analysis_reports',
                        filename_prefix=filename_prefix 
                    )
                    
                    if not file_path:
                        st.error(f"Failed to save uploaded analysis file: {uploaded_file.name}. Aborting analysis entry.")
                        db.rollback() # Rollback the main analysis entry too
                        # Clean up any files already saved in *this* batch before returning
                        for saved_path in saved_file_paths:
                            delete_file_if_exists(saved_path)
                        return False
                    else:
                        saved_file_paths.append(file_path) # Track successfully saved paths
                        file_name = uploaded_file.name
                        file_type = uploaded_file.type
                        
                        # Create AnalysisFiles entry for this file
                        analysis_file_entry = AnalysisFiles(
                            external_analysis_id=new_analysis.id,
                            file_path=file_path,
                            file_name=file_name,
                            file_type=file_type
                        )
                        db.add(analysis_file_entry)
                        analysis_file_entries_info.append({'name': file_name, 'path': file_path}) # For logging
                else:
                     st.warning("Encountered an empty item in the uploaded files list.")

        # --- Log Modification --- 
        log_values = analysis_data.copy()
        log_values['sample_id'] = user_sample_id # User string id
        log_values['sample_info_id'] = sample_info_primary_key_id # Integer id
        # pxrf_reading_no should already be in analysis_data if provided
        if analysis_file_entries_info:
             log_values['analysis_files'] = analysis_file_entries_info
        
        log_modification(
            db=db,
            experiment_id=None, # Sample-level modification
            modified_table="external_analyses",
            modification_type="create",
            new_values=log_values
        )

        # --- Commit Transaction --- 
        db.commit()
        st.success(f"External analysis '{analysis_data.get('analysis_type')}' added for sample '{user_sample_id}'.")
        return True

    except Exception as e:
        db.rollback()
        st.error(f"Error adding external analysis: {str(e)}")
        # Clean up any saved files if rollback occurs
        for saved_path in saved_file_paths:
            delete_file_if_exists(saved_path)
        return False
    finally:
        db.close() 

def add_sample_photo(sample_info_id, photo_file, description=None):
    """
    Adds a new photo record for a given sample.
    Args:
        sample_info_id (int): The database ID of the SampleInfo record.
        photo_file (UploadedFile): The photo file uploaded via Streamlit.
        description (str, optional): Optional description for the photo.
    """
    db = None # Initialize db to None
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
            # No need to rollback if nothing was added yet
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
        if db: db.rollback() # Rollback if exception occurs after adding
        st.error(f"Error adding sample photo: {str(e)}")
        # Attempt to delete the file if it was saved before the error
        if 'file_path' in locals() and file_path and os.path.exists(file_path):
            delete_file_if_exists(file_path)
        return False
    finally:
        if db and db.is_active:
            db.close()

def delete_sample_photo(photo_id):
    """
    Deletes a specific photo record and its associated file.
    Args:
        photo_id (int): The database ID of the SamplePhotos record to delete.
    """
    db = None # Initialize db to None
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
        if db: db.rollback()
        st.error(f"Error deleting sample photo: {str(e)}")
        # We might need to manually clean up the file if commit fails but file exists
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

def update_sample_info(sample_id, form_values):
    """
    Update basic information for a rock sample.
    
    Args:
        sample_id (str): The unique identifier of the sample to update
        form_values (dict): Dictionary containing updated field values
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    db = None
    try:
        db = SessionLocal()
        
        # Get the sample to update
        sample = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        if not sample:
            st.error(f"Sample with ID {sample_id} not found.")
            return False
            
        # Store old values for logging
        old_values = {
            field: getattr(sample, field)
            for field in ROCK_SAMPLE_CONFIG.keys()
        }
        
        # Update fields
        for field, value in form_values.items():
            if field in ROCK_SAMPLE_CONFIG:
                setattr(sample, field, value)
        
        # Log the modification
        log_modification(
            db=db,
            experiment_id=None,  # Sample-level modification
            modified_table="sample_info",
            modification_type="update",
            old_values=old_values,
            new_values=form_values
        )
        
        db.commit()
        st.success("Sample information updated successfully!")
        return True
        
    except Exception as e:
        if db:
            db.rollback()
        st.error(f"Error updating sample information: {str(e)}")
        return False
    finally:
        if db and db.is_active:
            db.close() 