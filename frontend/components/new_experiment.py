import datetime
import streamlit as st
from database.database import SessionLocal
from database.models import Experiment, ExperimentalConditions, ExperimentNotes, ExperimentStatus
from frontend.components.utils import log_modification, generate_form_fields
from frontend.config.variable_config import FIELD_CONFIG, EXPERIMENT_STATUSES

# Helper function to get default values from FIELD_CONFIG
def get_default_conditions():
    return {name: config['default'] for name, config in FIELD_CONFIG.items()}

def render_new_experiment():
    """
    Render the interface for creating a new experiment.
    
    This function creates a multi-step form interface that allows users to:
    - Enter basic experiment information (ID, sample ID, researcher, status)
    - Set experimental conditions (temperature, pressure, pH, etc.)
    - Configure optional parameters
    - Add initial notes
    
    The function uses Streamlit's session state to manage form data, the 
    `generate_form_fields` utility for creating inputs, and handles the 
    submission process with proper validation and error handling.
    
    The interface is divided into two steps:
    1. Data collection form
    2. Success message and option to create another experiment
    """
    # Initialize session state
    if 'step' not in st.session_state:
        st.session_state.step = 1

    if 'experiment_data' not in st.session_state:
        st.session_state.experiment_data = {
            'experiment_id': '',
            'sample_id': '',
            'researcher': '',
            'status': 'PLANNED', # Default status
            'conditions': get_default_conditions(), # Load defaults from FIELD_CONFIG
            'notes': [], # Keep notes separate, initial note handled in form
            'initial_note': '' # Clear initial note field
        }
    else:
        # Always merge defaults with current conditions
        current = st.session_state.experiment_data.get('conditions', {})
        st.session_state.experiment_data['conditions'] = {**{**get_default_conditions(), **current}, **current}
    
    # STEP 1: Collect experiment data
    if st.session_state.step == 1:
        with st.form(key="experiment_form"):
            st.subheader("Experiment Details")

            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Basic Information")
                experiment_id = st.text_input(
                    "Experiment ID", 
                    value=st.session_state.experiment_data.get('experiment_id', ''),
                    help="Enter a unique identifier for this experiment"
                )
                sample_id = st.text_input(
                    "Rock Sample ID", 
                    value=st.session_state.experiment_data.get('sample_id', ''),
                    help="Enter the sample identifier (e.g., 20UM21)"
                )
                researcher = st.text_input(
                    "Researcher Name", 
                    value=st.session_state.experiment_data.get('researcher', '')
                )
                status = st.selectbox(
                    "Experiment Status",
                    options=EXPERIMENT_STATUSES,
                    index=EXPERIMENT_STATUSES.index(st.session_state.experiment_data.get('status', 'PLANNED'))
                )
                
                st.markdown("#### Required Conditions")
                # Get required field names from FIELD_CONFIG
                required_field_names = [name for name, config in FIELD_CONFIG.items() if config.get('required', False)]
                required_values = generate_form_fields(
                    FIELD_CONFIG, 
                    st.session_state.experiment_data['conditions'], 
                    required_field_names,
                    key_prefix="new_req"
                )
                
            with col2:
                st.markdown("### Optional Parameters")
                # Get optional field names from FIELD_CONFIG
                optional_field_names = [name for name, config in FIELD_CONFIG.items() if not config.get('required', False)]
                optional_values = generate_form_fields(
                    FIELD_CONFIG, 
                    st.session_state.experiment_data['conditions'], 
                    optional_field_names,
                    key_prefix="new_opt"
                )

            # Combine required and optional values into a single dictionary
            all_condition_values = {**required_values, **optional_values}
            
            # --- Initial Notes Section ---
            st.markdown("---") # Separator
            st.markdown("### Initial Notes")
            initial_note = st.text_area(
                 "Lab Note",
                 value=st.session_state.experiment_data.get('initial_note', ''), # Allow pre-filling if needed later
                 height=150,
                 help="Add any initial lab notes for this experiment. You can add more notes later."
             )

            # --- Form Submission ---
            st.markdown("---") # Separator
            submit_button = st.form_submit_button("💾 Save Experiment")

            if submit_button:                
                # --- Data Validation (Basic Example) ---
                if not experiment_id or not sample_id or not researcher:
                     st.error("Experiment ID, Sample ID, and Researcher Name are required.")
                # Add more specific validation based on FIELD_CONFIG if needed 
                # (e.g., check numeric ranges beyond what st.number_input enforces)
                else:
                    # Update session state with collected data
                    st.session_state.experiment_data.update({
                        'experiment_id': experiment_id,
                        'sample_id': sample_id,
                        'researcher': researcher,
                        'status': status,
                        'conditions': all_condition_values,
                        'initial_note': initial_note.strip() # Store the initial note text
                    })
                    
                    # Call save_experiment
                    save_experiment() # No need to pass data, it reads from session state
                    # Go to step 2 if save is successful (save_experiment handles success/error messages)
                    # The save_experiment function will now implicitly move to step 2 on success by setting session state.

    # STEP 2: Show a success message and allow another experiment
    elif st.session_state.step == 2:
        st.success(f"Experiment {st.session_state.get('last_created_experiment_id', '')} (Number: {st.session_state.get('last_created_experiment_number', '')}) created successfully!")
        if st.button("Create Another Experiment"):
            st.session_state.step = 1
            st.session_state.experiment_data = {
                'experiment_id': '',
                'sample_id': '',
                'researcher': '',
                'status': 'PLANNED',
                'conditions': get_default_conditions(), # Reset conditions to defaults
                'notes': [], # Keep notes separate, initial note handled in form
                'initial_note': '' # Clear initial note field
            }
            if 'last_created_experiment_number' in st.session_state:
                del st.session_state['last_created_experiment_number']
            if 'last_created_experiment_id' in st.session_state:
                del st.session_state['last_created_experiment_id']
            st.rerun()

def save_experiment():
    """
    Save the new experiment data to the database.
    
    This function:
    - Generates a new experiment number
    - Creates a new experiment record
    - Sets up experimental conditions
    - Adds any initial notes
    - Handles database transactions and error cases
    
    The function reads the data stored in st.session_state.experiment_data
    and ensures all required fields are present with appropriate defaults.
    
    On success:
    - Updates session state with the new experiment number and ID
    - Shows a success message
    - Moves to step 2 of the form
    
    On failure:
    - Rolls back database changes
    - Displays an error message
    """
    try:
        # Create a database session
        db = SessionLocal()
        
        # Get the next experiment number
        last_experiment = db.query(Experiment).order_by(Experiment.experiment_number.desc()).first()
        next_experiment_number = 1 if last_experiment is None else last_experiment.experiment_number + 1
        
        # Get data from session state
        exp_data = st.session_state.experiment_data
        
        # Create a new experiment
        experiment = Experiment(
            experiment_number=next_experiment_number,
            experiment_id=exp_data['experiment_id'],
            sample_id=exp_data['sample_id'],
            researcher=exp_data['researcher'],
            date=datetime.datetime.now(),
            status=getattr(ExperimentStatus, exp_data['status'])
        )
        
        # Add the experiment to the session
        db.add(experiment)
        db.flush()  # Flush to get the experiment ID
        
        # Create experimental conditions directly from the collected form data
        conditions_data = exp_data['conditions'].copy() # Get condition values
        conditions_data['experiment_id'] = experiment.id # Add the foreign key
        conditions = ExperimentalConditions(**conditions_data)
        
        # Add the conditions to the session
        db.add(conditions)
        
        # Add initial notes if any
        initial_note_text = exp_data.get('initial_note')
        if initial_note_text:
            note = ExperimentNotes(
                experiment_id=experiment.id,
                note_text=initial_note_text
            )
            db.add(note)
        
        # Log the creation of the experiment and its related data
        log_modification(
            db=db,
            experiment_id=experiment.id,
            modified_table="experiments",
            modification_type="create",
            new_values={
                'experiment_number': experiment.experiment_number,
                'experiment_id': experiment.experiment_id,
                'sample_id': experiment.sample_id,
                'researcher': experiment.researcher,
                'date': experiment.date.isoformat(),
                'status': experiment.status.name,
                'conditions': exp_data['conditions'], # Log the full conditions dict used
                'notes': [initial_note_text] # Log the initial note
            }
        )

        # Commit the transaction
        db.commit()
        
        # Show experiment number and ID for reference in step 2
        st.session_state.last_created_experiment_number = next_experiment_number
        st.session_state.last_created_experiment_id = exp_data['experiment_id']
        
        st.session_state.step = 2 # Move to success step
        
        return True # Indicate success
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving experiment: {str(e)}")
        return False # Indicate failure
    finally:
        db.close()