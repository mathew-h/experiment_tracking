import datetime
import streamlit as st
import os
import json
from database.database import SessionLocal
from database.models import (
    Experiment,
    ExperimentStatus,
    ExperimentalResults,
    ExperimentalConditions,
    ModificationsLog,
    ExperimentNotes,
    ExternalAnalysis
)
# Import utilities and config
from frontend.components.utils import log_modification, save_uploaded_file, delete_file_if_exists
from frontend.config.variable_config import EXPERIMENT_TYPES, EXPERIMENT_STATUSES

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
            
            experiment_type = st.selectbox(
                "Experiment Type",
                options=EXPERIMENT_TYPES,
                index=EXPERIMENT_TYPES.index(conditions.get('experiment_type', 'Serum')) if conditions.get('experiment_type') in EXPERIMENT_TYPES else 0
            )
            
            # Fix particle_size input handling
            particle_size = st.number_input(
                "Particle Size (μm)",
                min_value=0.0,
                value=float(conditions.get('particle_size', 0.0)),
                step=0.1,
                format="%.1f",
                help="Enter the particle size in micrometers"
            )
            
            initial_ph = st.number_input(
                "Initial pH",
                min_value=0.0,
                max_value=14.0,
                value=float(conditions.get('initial_ph', 7.0) or 7.0),
                step=0.1,
                format="%.1f"
            )
            
            catalyst = st.text_input(
                "Catalyst",
                value=conditions.get('catalyst', '')
            )
            
            catalyst_mass = st.number_input(
                "Catalyst Mass (g)",
                min_value=0.0,
                value=float(conditions.get('catalyst_mass', 0.0) or 0.0),
                step=0.000001,  # 6 significant figures
                format="%.6f",
                help="Enter the mass of catalyst in grams"
            )
            
            temperature = st.number_input(
                "Temperature (°C)",
                min_value=-273.15,
                value=float(conditions.get('temperature', 25.0) or 25.0),
                step=1.0,
                format="%.1f"
            )
            
            pressure = st.number_input(
                "Pressure (psi)",
                min_value=0.0,
                value=float(conditions.get('pressure', 14.6959) or 14.6959),
                step=0.1,
                format="%.2f",
                help="Enter the pressure in psi"
            )
            
        
        with col4:
            st.markdown("#### Optional Parameters")
            
            catalyst_percentage = st.number_input(
                "Catalyst %",
                min_value=0.0,
                max_value=100.0,
                value=float(conditions.get('catalyst_percentage', 0.0) or 0.0),
                step=0.1,
                format="%.1f"
            )
            
            water_to_rock_ratio = st.number_input(
                "Water to Rock Ratio",
                min_value=0.0,
                value=float(conditions.get('water_to_rock_ratio', 0.0) or 0.0),
                step=0.1,
                format="%.2f",
                help="Enter the water to rock ratio"
            )

            buffer_system = st.text_input(
                "Buffer System",
                value=conditions.get('buffer_system', ''),
                help="Enter the buffer system used"
            )

            buffer_concentration = st.number_input(
                "Buffer Concentration (mM)",
                min_value=0.0,
                value=float(conditions.get('buffer_concentration', 0.0) or 0.0),
                step=0.1,
                format="%.1f"
            )
            
            initial_nitrate_concentration = st.number_input(
                "Initial Nitrate Concentration (mM)",
                min_value=0.0,
                value=float(conditions.get('initial_nitrate_concentration', 0.0) or 0.0),
                step=0.1,
                format="%.1f"
            )
            
            dissolved_oxygen = st.number_input(
                "Dissolved Oxygen (ppm)",
                min_value=0.0,
                value=float(conditions.get('dissolved_oxygen', 0.0) or 0.0),
                step=0.1,
                format="%.1f"
            )
            
            surfactant_type = st.text_input(
                "Surfactant Type",
                value=conditions.get('surfactant_type', '')
            )
            
            surfactant_concentration = st.number_input(
                "Surfactant Concentration",
                min_value=0.0,
                value=float(conditions.get('surfactant_concentration', 0.0) or 0.0),
                step=0.1,
                format="%.2f"
            )

            flow_rate = st.number_input(
                "Flow Rate (mL/min)",
                min_value=0.0,
                value=float(conditions.get('flow_rate', 0.0) or 0.0),
                step=0.1,
                format="%.1f",
                help="Enter the flow rate in mL/min (optional)"
            )

            co2_partial_pressure = st.number_input(
                "CO2 Partial Pressure (psi)",
                min_value=0.0,
                value=float(conditions.get('co2_partial_pressure', 0.0) or 0.0),
                step=0.1,
                format="%.2f"
            )
            
            confining_pressure = st.number_input(
                "Confining Pressure (psi)",
                min_value=0.0,
                value=float(conditions.get('confining_pressure', 0.0) or 0.0),
                step=0.1,
                format="%.2f"
            )
            
            pore_pressure = st.number_input(
                "Pore Pressure (psi)",
                min_value=0.0,
                value=float(conditions.get('pore_pressure', 0.0) or 0.0),
                step=0.1,
                format="%.2f"
            )
        
        # Prepare data for submission
        form_data = {
            'sample_id': sample_id,
            'researcher': researcher,
            'status': status,
            'date': datetime.datetime.combine(exp_date, datetime.datetime.now().time()),
            'conditions': {
                'particle_size': particle_size,
                'water_to_rock_ratio': water_to_rock_ratio if water_to_rock_ratio > 0 else 0.0,
                'initial_ph': initial_ph,
                'catalyst': catalyst,
                'catalyst_mass': catalyst_mass,
                'catalyst_percentage': catalyst_percentage,
                'temperature': temperature,
                'buffer_system': buffer_system.strip() if buffer_system else '',
                'buffer_concentration': buffer_concentration,
                'pressure': pressure,
                'flow_rate': flow_rate if flow_rate > 0 else None,
                'experiment_type': experiment_type,
                'initial_nitrate_concentration': initial_nitrate_concentration,
                'dissolved_oxygen': dissolved_oxygen,
                'surfactant_type': surfactant_type.strip() if surfactant_type else '',
                'surfactant_concentration': surfactant_concentration,
                'co2_partial_pressure': co2_partial_pressure,
                'confining_pressure': confining_pressure,
                'pore_pressure': pore_pressure
            }
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
            # Update existing conditions
            conditions.water_to_rock_ratio = data['conditions']['water_to_rock_ratio']
            conditions.initial_ph = data['conditions']['initial_ph']
            conditions.catalyst = data['conditions']['catalyst']
            conditions.catalyst_percentage = data['conditions']['catalyst_percentage']
            conditions.temperature = data['conditions']['temperature']
            conditions.buffer_system = data['conditions']['buffer_system'].strip() if data['conditions']['buffer_system'] else ''
            conditions.buffer_concentration = data['conditions']['buffer_concentration']
            conditions.pressure = data['conditions']['pressure']
            conditions.flow_rate = data['conditions']['flow_rate']
            conditions.experiment_type = data['conditions']['experiment_type']
            conditions.initial_nitrate_concentration = data['conditions']['initial_nitrate_concentration']
            conditions.dissolved_oxygen = data['conditions']['dissolved_oxygen']
            conditions.surfactant_type = data['conditions']['surfactant_type'].strip() if data['conditions']['surfactant_type'] else ''
            conditions.surfactant_concentration = data['conditions']['surfactant_concentration']
            conditions.co2_partial_pressure = data['conditions']['co2_partial_pressure']
            conditions.confining_pressure = data['conditions']['confining_pressure']
            conditions.pore_pressure = data['conditions']['pore_pressure']
            if hasattr(conditions, 'particle_size'):
                conditions.particle_size = data['conditions']['particle_size']
        else:
            # Create new conditions
            conditions = ExperimentalConditions(
                experiment_id=experiment.id,
                water_to_rock_ratio=data['conditions']['water_to_rock_ratio'],
                initial_ph=data['conditions']['initial_ph'],
                catalyst=data['conditions']['catalyst'],
                catalyst_percentage=data['conditions']['catalyst_percentage'],
                temperature=data['conditions']['temperature'],
                buffer_system=data['conditions']['buffer_system'].strip() if data['conditions']['buffer_system'] else '',
                buffer_concentration=data['conditions']['buffer_concentration'],
                pressure=data['conditions']['pressure'],
                flow_rate=data['conditions']['flow_rate'],
                experiment_type=data['conditions']['experiment_type'],
                initial_nitrate_concentration=data['conditions']['initial_nitrate_concentration'],
                dissolved_oxygen=data['conditions']['dissolved_oxygen'],
                surfactant_type=data['conditions']['surfactant_type'].strip() if data['conditions']['surfactant_type'] else '',
                surfactant_concentration=data['conditions']['surfactant_concentration'],
                co2_partial_pressure=data['conditions']['co2_partial_pressure'],
                confining_pressure=data['conditions']['confining_pressure'],
                pore_pressure=data['conditions']['pore_pressure']
            )
            if hasattr(conditions, 'particle_size'):
                conditions.particle_size = data['conditions']['particle_size']
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
            
def save_results(experiment_id, final_ph, final_nitrate, yield_value):
    """
    Save experiment results to the database.
    
    Args:
        experiment_id (int): The unique identifier of the experiment
        final_ph (float): The final pH value of the experiment
        final_nitrate (float): The final nitrate concentration
        yield_value (float): The yield value of the experiment
        
    This function:
    - Checks if results exist for the experiment
    - Updates existing results or creates new ones
    - Creates a modification log entry
    - Handles database transactions and error cases
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        db = SessionLocal()
        
        # Check if results exist for this experiment
        result = db.query(ExperimentalResults).filter(ExperimentalResults.experiment_id == experiment_id).first()
        
        if result:
            # Prepare old values for logging
            old_values={
                'final_ph': result.final_ph,
                'final_nitrate_concentration': result.final_nitrate_concentration,
                'yield_value': result.yield_value
            }
            # Update existing results
            result.final_ph = final_ph
            result.final_nitrate_concentration = final_nitrate
            result.yield_value = yield_value
            
            # Prepare new values for logging
            new_values={
                'final_ph': final_ph,
                'final_nitrate_concentration': final_nitrate,
                'yield_value': yield_value
            }
            
            # Use utility for logging
            log_modification(
                db=db,
                experiment_id=experiment_id,
                modified_table="results",
                modification_type="update",
                old_values=old_values,
                new_values=new_values
            )
        else:
            # Create new results
            new_result = ExperimentalResults(
                experiment_id=experiment_id,
                final_ph=final_ph,
                final_nitrate_concentration=final_nitrate,
                yield_value=yield_value
            )
            db.add(new_result)
            
            # Prepare new values for logging
            new_values={
                'final_ph': final_ph,
                'final_nitrate_concentration': final_nitrate,
                'yield_value': yield_value
            }
            
            # Use utility for logging
            log_modification(
                db=db,
                experiment_id=experiment_id,
                modified_table="results",
                modification_type="create",
                new_values=new_values
            )
        
        # Commit the changes
        db.commit()
        
        st.success("Results saved successfully!")
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error saving results: {str(e)}")
        return False
    finally:
        db.close()

def delete_experimental_results(data_id):
    """
    Delete experimental data from the database.
    
    Args:
        data_id (int): The unique identifier of the experimental data to delete
        
    This function:
    - Retrieves the data to be deleted
    - Removes associated files from storage
    - Creates a modification log entry
    - Deletes the database record
    - Handles database transactions and error cases
    """
    try:
        db = SessionLocal()
        
        # Get the data
        data = db.query(ExperimentalResults).filter(ExperimentalResults.id == data_id).first()
        
        if data is None:
            st.error("Data not found")
            return
        
        # Store old values before deleting
        old_values={
            'data_type': data.data_type,
            'description': data.description,
            'data_values': data.data_values,
            'file_path': data.file_path,
            'file_name': data.file_name
        }

        # Use utility to delete file
        delete_file_if_exists(data.file_path)
        
        # Use utility for logging
        log_modification(
            db=db,
            experiment_id=data.experiment_id,
            modified_table="experimental_results",
            modification_type="delete",
            old_values=old_values
        )
        
        # Delete the data
        db.delete(data)
        
        # Commit the transaction
        db.commit()
        
        st.success("Experimental data deleted successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error deleting experimental data: {str(e)}")
        raise e
    finally:
        db.close()

def save_experimental_results(experiment_id, data_type, file=None, description=None, data_values=None):
    """
    Save experimental data to the database.
    
    Args:
        experiment_id (int): The unique identifier of the experiment
        data_type (str): Type of experimental data being saved
        file (UploadedFile, optional): File containing experimental data
        description (str, optional): Description of the experimental data
        data_values (dict, optional): Dictionary containing experimental data values
        
    This function:
    - Creates a new experimental data entry
    - Handles file upload if present
    - Creates a modification log entry
    - Handles database transactions and error cases
    """
    try:
        db = SessionLocal()
        
        file_path = None
        file_name = None
        file_type = None

        # Handle file upload using utility
        if file:
            file_path = save_uploaded_file(
                file=file, 
                base_dir_name='experimental_results', 
                filename_prefix=f"{experiment_id}"
            )
            if file_path: # Check if save was successful
                file_name = file.name
                file_type = file.type
            else:
                # Handle file save error (optional: raise exception or return False)
                db.rollback()
                st.error("Failed to save uploaded file.")
                return False # Or raise?
        
        # Create a new experimental data entry
        experimental_results = ExperimentalResults(
            experiment_id=experiment_id,
            data_type=data_type,
            description=description,
            data_values=json.dumps(data_values) if data_values else None,
            file_path=file_path, # Use path from utility
            file_name=file_name, # Use name from file object
            file_type=file_type  # Use type from file object
        )
        
        # No need to get user info here, log_modification handles it
        # user = st.session_state.get('user', {})
        # user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Prepare new values for logging
        new_values={
            'data_type': data_type,
            'description': description,
            'data_values': data_values, # Pass the dict, log_modification will serialize
            'file_path': file_path,
            'file_name': file_name
        }
        
        # Use utility for logging
        log_modification(
            db=db,
            experiment_id=experiment_id,
            modified_table="experimental_results",
            modification_type="add",
            new_values=new_values
        )
        
        # Commit the transaction
        db.commit()
        
        st.success("Experimental data saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving experimental data: {str(e)}")
        raise e
    finally:
        db.close()

def delete_external_analysis(analysis_id):
    """
    Delete external analysis from the database.
    
    Args:
        analysis_id (int): The unique identifier of the analysis to delete
        
    This function:
    - Retrieves the analysis to be deleted
    - Removes associated files from storage
    - Creates a modification log entry
    - Deletes the database record
    - Handles database transactions and error cases
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

        # Use utility to delete file
        delete_file_if_exists(analysis.report_file_path)
        
        # No need to get user info here, log_modification handles it
        # user = st.session_state.get('user', {})
        # user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Use utility for logging
        log_modification(
            db=db,
            experiment_id=None, # Sample-level modification
            modified_table="external_analyses",
            modification_type="delete",
            old_values=old_values
        )
        
        # Delete the analysis
        db.delete(analysis)
        
        # Commit the transaction
        db.commit()
        
        st.success("External analysis deleted successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error deleting external analysis: {str(e)}")
        raise e
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