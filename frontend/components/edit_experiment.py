import datetime
import streamlit as st
import os
import json
from sqlalchemy.orm import Session # Import Session for type hinting
from database.database import SessionLocal
from database.models import (
    Experiment,
    ExperimentStatus,
    ExperimentalResults,
    ResultFiles, # Import ResultFiles
    ExperimentalConditions,
    ModificationsLog,
    ExperimentNotes,
    ExternalAnalysis
)
# Import utilities and config
from frontend.components.utils import log_modification, save_uploaded_file, delete_file_if_exists, generate_form_fields
from frontend.config.variable_config import EXPERIMENT_TYPES, EXPERIMENT_STATUSES, FIELD_CONFIG, RESULTS_CONFIG

def edit_experiment(experiment):
    """
    Render the interface for editing an existing experiment.
    
    Args:
        experiment (dict): Dictionary containing the experiment data to edit
        
    This function creates a form interface that allows users to:
    - Edit basic experiment information (sample ID, researcher, status, date)
    - Modify experimental conditions (temperature, pressure, pH, etc.)
    - Update optional parameters
    - Save changes to the database
    
    The form includes validation and proper error handling for the submission process.
    """
    with st.form(key="edit_experiment_form"):
        st.markdown("### Basic Information")
        col1, col2 = st.columns(2)
        
        with col1:
            sample_id = st.text_input("Rock Sample ID", value=experiment['sample_id'])
            researcher = st.text_input("Researcher Name", value=experiment['researcher'])
        
        with col2:
            status = st.selectbox(
                "Experiment Status",
                options=EXPERIMENT_STATUSES,
                index=EXPERIMENT_STATUSES.index(experiment['status']) if experiment['status'] in EXPERIMENT_STATUSES else 0
            )
            exp_date = st.date_input(
                "Experiment Date", 
                value=experiment['date'] if isinstance(experiment['date'], datetime.datetime) else datetime.datetime.now()
            )
        
        st.markdown("### Experimental Conditions")
        col3, col4 = st.columns(2)
        
        conditions = experiment.get('conditions', {})
        
        with col3:
            st.markdown("#### Required Parameters")
            # Get required field names from FIELD_CONFIG
            required_field_names = [name for name, config in FIELD_CONFIG.items() if config.get('required', False)]
            required_values = generate_form_fields(
                FIELD_CONFIG, 
                conditions, 
                required_field_names,
                key_prefix="edit_req"
            )
            
        with col4:
            st.markdown("#### Optional Parameters")
            # Get optional field names from FIELD_CONFIG
            optional_field_names = [name for name, config in FIELD_CONFIG.items() if not config.get('required', False)]
            optional_values = generate_form_fields(
                FIELD_CONFIG, 
                conditions, 
                optional_field_names,
                key_prefix="edit_opt"
            )
        
        # Combine required and optional values into a single dictionary
        all_condition_values = {**required_values, **optional_values}
        
        # Prepare data for submission
        form_data = {
            'sample_id': sample_id,
            'researcher': researcher,
            'status': status,
            'date': datetime.datetime.combine(exp_date, datetime.datetime.now().time()),
            'conditions': all_condition_values
        }
        
        # Submit button
        submit_button = st.form_submit_button("Save Changes")
        if submit_button:
            submit_experiment_edit(experiment['id'], form_data)

def submit_experiment_edit(experiment_id, data):
    """
    Handle the submission of experiment edit form.
    
    Args:
        experiment_id (int): The unique identifier of the experiment to update
        data (dict): Dictionary containing the updated experiment data
        
    This function:
    - Calls update_experiment to save changes
    - Updates the session state to reflect the changes
    - Handles success/failure states
    """
    success = update_experiment(experiment_id, data)
    if success:
        st.session_state.edit_mode = False

def update_experiment(experiment_id, data):
    """
    Update an experiment in the database.
    
    Args:
        experiment_id (int): The unique identifier of the experiment to update
        data (dict): Dictionary containing the updated experiment data
        
    This function:
    - Retrieves the existing experiment
    - Logs old values before updating
    - Updates basic experiment information
    - Updates or creates experimental conditions
    - Creates a modification log entry
    - Handles database transactions and error cases
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        db = SessionLocal()
        
        # Get the experiment
        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        
        if experiment is None:
            st.error(f"Experiment with ID {experiment_id} not found.")
            return False
        
        # Log old values before updating
        old_values = {
            'sample_id': experiment.sample_id,
            'researcher': experiment.researcher,
            'status': experiment.status.name,
            'date': experiment.date.isoformat() if experiment.date else None
        }
        
        # Update basic experiment information
        experiment.sample_id = data['sample_id']
        experiment.researcher = data['researcher']
        experiment.status = getattr(ExperimentStatus, data['status'])
        experiment.date = data['date']
        
        # Update or create conditions
        conditions = experiment.conditions
        if conditions:
            # Update existing conditions using FIELD_CONFIG to ensure all fields are handled
            for field_name, config in FIELD_CONFIG.items():
                if hasattr(conditions, field_name):
                    value = data['conditions'].get(field_name)
                    # Handle special cases for text fields
                    if config['type'] == 'text' and value is not None:
                        value = value.strip() if value else ''
                    # Handle special cases for numeric fields
                    elif config['type'] == 'number':
                        if value is not None:
                            try:
                                value = float(value)
                            except (ValueError, TypeError):
                                value = float(config['default'])
                    setattr(conditions, field_name, value)
        else:
            # Create new conditions
            conditions_data = {
                'experiment_id': experiment.id,
                **data['conditions']
            }
            conditions = ExperimentalConditions(**conditions_data)
            db.add(conditions)
        
        # Prepare new values for logging
        new_values = {
            'sample_id': data['sample_id'],
            'researcher': data['researcher'],
            'status': data['status'],
            'date': data['date'].isoformat() if data['date'] else None,
            'conditions': data['conditions']
        }
        
        # Use utility for logging
        log_modification(
            db=db,
            experiment_id=experiment.id,
            modified_table="experiments",
            modification_type="update",
            old_values=old_values,
            new_values=new_values
        )
        
        # Commit the changes
        db.commit()
        
        # Set a flag in session state to trigger a rerun
        st.session_state.experiment_updated = True
        
        st.success("Experiment updated successfully!")
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error updating experiment: {str(e)}")
        return False
    finally:
        db.close()
            
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
                'data_type': 'SCALAR_RESULTS'
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
                    filename_prefix = f"exp_{experiment_id}_res_{result.id}"
                    file_path = save_uploaded_file(
                        file=uploaded_file, 
                        base_dir_name='result_files', # Save to a dedicated directory
                        filename_prefix=filename_prefix 
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
            
            # Log file additions separately? Or add to the main log? 
            # For simplicity, we can log them as part of the update/create action.
            if saved_files_info:
                 # We might need another log entry specifically for file changes 
                 # if granular tracking is needed. For now, rely on the main log.
                 pass

        # --- Commit all changes (scalar + files) --- 
        db.commit()
        st.success(f"Results and files for time point {time_post_reaction}h saved successfully!")
        return True
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving results/files for time {time_post_reaction}h: {str(e)}")
        # Clean up any partially saved files if rollback occurs? save_uploaded_file might need enhancement.
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
        raise e # Re-raise after logging/rollback
    finally:
        db.close()

def save_note(experiment_id, note_text):
    """
    Save a new note to the database.
    
    Args:
        experiment_id (int): The unique identifier of the experiment
        note_text (str): The text content of the note
        
    This function:
    - Creates a new note entry
    - Associates it with the specified experiment
    - Handles database transactions and error cases
    """
    try:
        db = SessionLocal()
        
        # Create a new note
        note = ExperimentNotes(
            experiment_id=experiment_id,
            note_text=note_text.strip()
        )
        
        # Add the note to the session
        db.add(note)
        
        # Commit the transaction
        db.commit()
        
        st.success("Note saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving note: {str(e)}")
        raise e
    finally:
        db.close()

def submit_note_edit(note_id, edited_text):
    """
    Handle note edit submission.
    
    Args:
        note_id (int): The unique identifier of the note to edit
        edited_text (str): The new text content for the note
        
    This function:
    - Validates the edited text
    - Calls update_note to save changes
    - Updates the session state
    """
    if not edited_text.strip():
        st.error("Note text cannot be empty")
        return
    
    update_note(note_id, edited_text)
    st.session_state.note_form_state['editing_note_id'] = None

def update_note(note_id, note_text):
    """
    Update an existing note in the database.
    
    Args:
        note_id (int): The unique identifier of the note to update
        note_text (str): The new text content for the note
        
    This function:
    - Retrieves the existing note
    - Updates its content
    - Handles database transactions and error cases
    """
    try:
        db = SessionLocal()
        
        # Get the note
        note = db.query(ExperimentNotes).filter(ExperimentNotes.id == note_id).first()
        
        if note is None:
            st.error("Note not found")
            return
        
        # Update the note
        note.note_text = note_text.strip()
        
        # Commit the transaction
        db.commit()
        
        st.success("Note updated successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error updating note: {str(e)}")
        raise e
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

        # --- Delete the actual file from storage FIRST ---
        file_deleted_from_storage = delete_file_if_exists(file_record.file_path)
        
        if not file_deleted_from_storage:
            # Log a warning if the file couldn't be deleted, but proceed to delete DB record
            st.warning(f"Could not delete file from storage: {file_record.file_path}. Proceeding to remove database record.")
            # We might add this status to the log
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