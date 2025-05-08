import datetime
import streamlit as st
import os
import json
from sqlalchemy.orm import Session # Import Session for type hinting
from database.database import SessionLocal
from database.models import (
    Experiment,
    ExperimentStatus,
    ExperimentalConditions,
    ModificationsLog,
    ExperimentNotes,
    ExternalAnalysis
)
# Import utilities and config
from frontend.components.utils import log_modification, save_uploaded_file, delete_file_if_exists, generate_form_fields
from frontend.config.variable_config import EXPERIMENT_TYPES, EXPERIMENT_STATUSES, FIELD_CONFIG, SCALAR_RESULTS_CONFIG, NMR_RESULTS_CONFIG

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