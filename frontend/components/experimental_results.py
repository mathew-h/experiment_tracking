import datetime
import streamlit as st
import os
import json
from sqlalchemy.orm import Session # Import Session for type hinting
from database.database import SessionLocal
from database.models import (
    Experiment,
    ExperimentalResults,
    ResultFiles, # Import ResultFiles
    ModificationsLog
)
# Import utilities and config
from frontend.components.utils import log_modification, save_uploaded_file, delete_file_if_exists
from frontend.config.variable_config import RESULTS_CONFIG

# TODO: Define a base class or interface for different result types (e.g., Scalar, pXRF, NMR)
# class BaseResultHandler:
#     def process(self, data):
#         raise NotImplementedError
#     def save(self, db, experiment_id, processed_data):
#         raise NotImplementedError

# TODO: Implement specific handlers for different result types inheriting from BaseResultHandler

def save_results(experiment_id, time_post_reaction, results_data, uploaded_files_data=None):
    """
    Save or update experiment results for a specific time point, including scalar values and associated files.

    Args:
        experiment_id (int): The unique identifier of the experiment
        time_post_reaction (float): Time in hours post-reaction when results were measured.
        results_data (dict): Dictionary containing scalar result values keyed by field names from RESULTS_CONFIG.
        uploaded_files_data (list[dict], optional): List of dictionaries, each containing:
            {'file': UploadedFile, 'description': str}. Defaults to None.

    This function:
    - Checks if results exist for the experiment at the specified time_post_reaction
    - Updates existing scalar results or creates a new results entry using RESULTS_CONFIG
    - Handles file uploads: saves files and creates/updates ResultFiles entries
    - Creates modification log entries for scalar data changes
    - Handles database transactions and error cases

    Returns:
        bool: True if save was successful, False otherwise
    """
    db = SessionLocal()
    try:
        # Check if results exist for this experiment AND time point
        result = db.query(ExperimentalResults).filter(
            ExperimentalResults.experiment_id == experiment_id,
            ExperimentalResults.time_post_reaction == time_post_reaction
        ).first()

        modification_type = ""
        old_values = {}
        new_values_log = {'time_post_reaction': time_post_reaction} # Initialize with time

        if result:
            modification_type = "update"
            # Prepare old values for logging dynamically using RESULTS_CONFIG
            old_values['time_post_reaction'] = result.time_post_reaction
            for field_name in RESULTS_CONFIG.keys():
                 # Use the actual model attribute name (field_name)
                 if hasattr(result, field_name):
                     old_values[field_name] = getattr(result, field_name)

            # Update existing scalar results dynamically using RESULTS_CONFIG
            for field_name, value in results_data.items():
                if field_name in RESULTS_CONFIG and hasattr(result, field_name):
                    setattr(result, field_name, value)
                    new_values_log[field_name] = value # Add to new values for logging

            result.data_type = 'SCALAR_RESULTS' # Keep this
            # TODO: Make data_type dynamic based on input or handler used

            # Log the scalar update
            log_modification(
                db=db,
                experiment_id=experiment_id,
                modified_table="experimental_results",
                modification_type=modification_type,
                old_values=old_values,
                new_values=new_values_log
            )

        else:
            modification_type = "create"

            # Prepare data for new entry, including defaults from config if not provided
            result_kwargs = {
                'experiment_id': experiment_id,
                'time_post_reaction': time_post_reaction,
                'data_type': 'SCALAR_RESULTS' # TODO: Make dynamic
            }

            for field_name, config in RESULTS_CONFIG.items():
                 # Use field_name for model attribute
                 result_kwargs[field_name] = results_data.get(field_name, config.get('default'))
                 new_values_log[field_name] = result_kwargs[field_name] # Add to new values for logging

            new_values_log['data_type'] = 'SCALAR_RESULTS' # Add data_type to log

            # Create new results entry using unpacked kwargs
            result = ExperimentalResults(**result_kwargs)
            db.add(result)

            # --- Flush and Refresh to get result.id BEFORE saving files ---
            try:
                db.flush()
                db.refresh(result)
            except Exception as flush_err:
                 st.error(f"DB flush/refresh error before saving result entry: {flush_err}")
                 db.rollback()
                 return False
            # --- End Flush and Refresh ---

            # Log the scalar creation
            log_modification(
                db=db,
                experiment_id=experiment_id,
                modified_table="experimental_results",
                modification_type=modification_type,
                new_values=new_values_log
            )

        # --- Handle File Uploads ---
        if uploaded_files_data:
            saved_files_info = []
            for file_data in uploaded_files_data:
                uploaded_file = file_data.get('file')
                description = file_data.get('description', '')

                if uploaded_file:
                    # Construct a unique filename prefix including result ID
                    # TODO: Consider moving file saving logic to a more specific function or class
                    filename_prefix = f"exp_{experiment_id}_res_{result.id}"
                    file_path = save_uploaded_file(
                        file=uploaded_file,
                        storage_folder=f'result_files/exp_{experiment_id}/res_{result.id}', # More structured folder
                        filename_prefix=filename_prefix # May be redundant now
                    )

                    if file_path:
                        file_name = uploaded_file.name
                        file_type = uploaded_file.type

                        # Create ResultFiles entry
                        result_file_entry = ResultFiles(
                            result_id=result.id, # Link to the ExperimentalResults entry
                            file_path=file_path,
                            file_name=file_name,
                            file_type=file_type,
                            description=description
                        )
                        db.add(result_file_entry)
                        saved_files_info.append({'name': file_name, 'path': file_path, 'description': description})
                    else:
                        # Rollback if any file fails to save
                        st.error(f"Failed to save uploaded file: {uploaded_file.name}")
                        db.rollback()
                        return False

            # TODO: Add specific logging for file additions/changes if needed more granularly.
            if saved_files_info:
                 pass

        # --- Commit all changes (scalar + files) ---
        db.commit()
        st.success(f"Results and files for time point {time_post_reaction}h saved successfully!")
        return True

    except Exception as e:
        db.rollback()
        st.error(f"Error saving results/files for time {time_post_reaction}h: {str(e)}")
        # TODO: Enhance file cleanup on rollback in save_uploaded_file or here.
        return False
    finally:
        db.close()

def delete_experimental_results(data_id):
    """
    Delete an experimental result time point entry and its associated files.

    Args:
        data_id (int): The unique identifier of the ExperimentalResults entry to delete

    This function:
    - Retrieves the ExperimentalResults entry (time point)
    - Retrieves all associated ResultFiles entries
    - Deletes the actual files from storage for each associated ResultFiles entry
    - Creates a modification log entry for the deletion of the time point
    - Deletes the ExperimentalResults database record (cascade deletes ResultFiles records)
    - Handles database transactions and error cases
    """
    db = SessionLocal()
    try:
        # Get the main result entry (time point)
        result_entry = db.query(ExperimentalResults).filter(ExperimentalResults.id == data_id).first()

        if result_entry is None:
            st.error("Result entry not found")
            db.close()
            return

        # Store old values for logging (only scalar data for the main log entry)
        old_values={
            'time_post_reaction': result_entry.time_post_reaction,
            'data_type': result_entry.data_type
            # Add other scalar fields if necessary - dynamically using RESULTS_CONFIG
        }
        for field_name in RESULTS_CONFIG.keys():
            if hasattr(result_entry, field_name):
                old_values[field_name] = getattr(result_entry, field_name)

        # --- Delete associated files first ---
        associated_files = db.query(ResultFiles).filter(ResultFiles.result_id == data_id).all()
        deleted_file_info = []
        for file_record in associated_files:
            deleted = delete_file_if_exists(file_record.file_path)
            deleted_file_info.append({
                'name': file_record.file_name,
                'path': file_record.file_path,
                'deleted': deleted
            })
            if not deleted:
                 # Log a warning but proceed with deleting DB record? Or halt?
                 st.warning(f"Could not delete file from storage: {file_record.file_path}")

        # Add info about deleted files to the log? Optional.
        old_values['deleted_files'] = deleted_file_info

        # Use utility for logging the deletion of the main result entry
        log_modification(
            db=db,
            experiment_id=result_entry.experiment_id,
            modified_table="experimental_results", # Log deletion of the time point
            modification_type="delete",
            old_values=old_values # Includes scalar data and info about attempted file deletions
        )

        # --- Delete the ExperimentalResults record ---
        # The cascade delete will handle removing the ResultFiles records from DB.
        db.delete(result_entry)

        # Commit the transaction
        db.commit()

        st.success(f"Result entry for time {old_values.get('time_post_reaction', '?')}h and associated files deleted successfully!")

    except Exception as e:
        db.rollback()
        st.error(f"Error deleting result entry (ID: {data_id}): {str(e)}")
        # Re-raise or handle as appropriate for the calling UI
        raise e # Re-raise after logging/rollback
    finally:
        db.close()

def delete_result_file(file_id):
    """
    Delete an individual result file record and its corresponding file from storage.

    Args:
        file_id (int): The unique identifier of the ResultFiles entry to delete.

    Returns:
        bool: True if deletion was successful, False otherwise.
    """
    db = SessionLocal()
    try:
        # Find the file record
        file_record = db.query(ResultFiles).filter(ResultFiles.id == file_id).first()

        if file_record is None:
            st.error(f"File record with ID {file_id} not found.")
            return False

        # Store info for logging
        old_values = {
            'result_id': file_record.result_id,
            'file_path': file_record.file_path,
            'file_name': file_record.file_name,
            'description': file_record.description
        }

        # Get the associated experiment ID for logging context
        # We need to query the parent ExperimentalResults to get the experiment_id
        parent_result = db.query(ExperimentalResults).filter(ExperimentalResults.id == file_record.result_id).first()
        experiment_id_for_log = parent_result.experiment_id if parent_result else None
        if not experiment_id_for_log and parent_result:
            st.warning(f"Could not determine experiment ID for logging file deletion (Result ID: {file_record.result_id})")


        # --- Delete the actual file from storage FIRST ---
        file_deleted_from_storage = delete_file_if_exists(file_record.file_path)

        if not file_deleted_from_storage:
            # Log a warning if the file couldn't be deleted, but proceed to delete DB record
            st.warning(f"Could not delete file from storage: {file_record.file_path}. Proceeding to remove database record.")
            old_values['storage_deletion_failed'] = True

        # --- Delete the database record ---
        db.delete(file_record)

        # --- Log the deletion ---
        log_modification(
            db=db,
            experiment_id=experiment_id_for_log, # Log against the parent experiment
            modified_table="result_files", # Indicate which table
            modification_type="delete",
            old_values=old_values # Log the details of the deleted file record
        )

        # --- Commit the transaction ---
        db.commit()
        st.success(f"File '{old_values.get('file_name', 'Unknown')}' deleted successfully.")
        return True

    except Exception as e:
        db.rollback()
        st.error(f"Error deleting file record (ID: {file_id}): {str(e)}")
        return False
    finally:
        db.close()

# TODO: Add function `process_uploaded_results_file(file)`
# This function would handle parsing CSV/Excel, validating data,
# and returning structured data ready for `save_results`.
# It could potentially use the ResultHandler classes mentioned above.

# TODO: Add function `calculate_derived_results(experiment_id)`
# This function could be triggered after saving primary results
# to calculate things like yield based on other data points. 