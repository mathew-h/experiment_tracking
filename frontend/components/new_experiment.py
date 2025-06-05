import datetime
import streamlit as st
from database.database import SessionLocal
from database.models import Experiment, ExperimentalConditions, ExperimentNotes, ExperimentStatus
from frontend.components.utils import log_modification, generate_form_fields, get_sample_options
from frontend.config.variable_config import FIELD_CONFIG, EXPERIMENT_STATUSES
# Import the new service
from backend.services.experimental_conditions_service import ExperimentalConditionsService
import pytz

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
            'status': EXPERIMENT_STATUSES[0], # Default status
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
                
                # Sample selection - allow blank for control runs or experiments without rock samples
                # Get sample options from database using utils function
                sample_options, sample_dict = get_sample_options()
                
                # Find current selection if any
                current_sample_id = st.session_state.experiment_data.get('sample_id', '')
                current_index = 0
                if current_sample_id:
                    for i, option in enumerate(sample_options):
                        if sample_dict.get(option) == current_sample_id:
                            current_index = i
                            break
                
                selected_sample_display = st.selectbox(
                    "Rock Sample",
                    options=sample_options,
                    index=current_index,
                    help="Select a rock sample from the database, or leave blank for control runs/experiments without rock samples. You can type to search.",
                    format_func=lambda x: "None (Control Run)" if x == "" else x
                )
                
                # Get the actual sample_id from the selection
                sample_id = sample_dict.get(selected_sample_display, "")
                
                # Additional safety: if mapping fails, extract sample_id from display text
                if not sample_id and selected_sample_display and selected_sample_display != "":
                    # Extract just the sample_id part (everything before the first " - ")
                    sample_id = selected_sample_display.split(" - ")[0].strip()
                    # Verify this is a valid sample_id by checking if it exists in our sample_dict values
                    if sample_id not in sample_dict.values():
                        sample_id = ""  # Reset to empty if not valid
                
                researcher = st.text_input(
                    "Researcher Name", 
                    value=st.session_state.experiment_data.get('researcher', '')
                )
                status = st.selectbox(
                    "Experiment Status",
                    options=EXPERIMENT_STATUSES,
                    index=EXPERIMENT_STATUSES.index(st.session_state.experiment_data.get('status', EXPERIMENT_STATUSES[0]))
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
                
                # --- Moved Initial Notes Section Here ---
                st.markdown("#### Experiment Description") # Changed header to reflect new purpose
                initial_note = st.text_area(
                    "Experiment Description",
                    value=st.session_state.experiment_data.get('initial_note', ''),
                    height=150,
                    max_chars=100,
                    help="Provide a brief description of the experiment (required, max 100 characters)."
                )
                
            with col2:
                st.markdown("#### Optional Parameters")
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
            
            # --- Form Submission ---
            st.markdown("---") # Separator
            submit_button = st.form_submit_button("💾 Save Experiment")

            if submit_button:                
                # --- Data Validation (Basic Example) ---
                if not experiment_id or not researcher or not initial_note:
                     st.error("Experiment ID, Researcher Name, and Experiment Description are required.")
                # Note: sample_id is now optional - blank is allowed for control runs
                # Add more specific validation based on FIELD_CONFIG if needed 
                # (e.g., check numeric ranges beyond what st.number_input enforces)
                else:
                    # Update session state with collected data
                    st.session_state.experiment_data.update({
                        'experiment_id': experiment_id,
                        'sample_id': sample_id,  # Can be empty string for control runs
                        'researcher': researcher,
                        'status': status,
                        'conditions': all_condition_values,
                        'initial_note': initial_note.strip() # Store the initial note text
                    })
                    
                    # Call save_experiment
                    success = save_experiment() # No need to pass data, it reads from session state
                    # Success/error messages are handled within save_experiment
                    # If successful, save_experiment sets step to 2 and reruns
                    if success:
                        st.rerun()

    # STEP 2: Show a success message and allow another experiment
    elif st.session_state.step == 2:
        st.success(f"Experiment {st.session_state.get('last_created_experiment_id', '')} (Number: {st.session_state.get('last_created_experiment_number', '')}) created successfully!")
        if st.button("Create Another Experiment"):
            st.session_state.step = 1
            
            if 'previous_experiment_data' in st.session_state:
                # Pre-fill with previous data
                previous_data = st.session_state.previous_experiment_data
                st.session_state.experiment_data = {
                    'experiment_id': '',  # Clear for new experiment
                    'sample_id': previous_data.get('sample_id', ''),
                    'researcher': previous_data.get('researcher', ''),
                    'status': EXPERIMENT_STATUSES[0],  # Default for new experiments
                    'conditions': previous_data.get('conditions', get_default_conditions()),
                    'notes': [], # Notes are experiment-specific
                    'initial_note': ''  # Description is experiment-specific
                }
                del st.session_state['previous_experiment_data'] # Clear after use
            else:
                # Default reset if no previous data
                st.session_state.experiment_data = {
                    'experiment_id': '',
                    'sample_id': '',
                    'researcher': '',
                    'status': EXPERIMENT_STATUSES[0],
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
    Save the new experiment data to the database using services.
    """
    db = None # Initialize db to None
    try:
        # Create a database session
        db = SessionLocal()
        
        # Get the next experiment number
        last_experiment = db.query(Experiment).order_by(Experiment.experiment_number.desc()).first()
        next_experiment_number = 1 if last_experiment is None else last_experiment.experiment_number + 1
        
        # Get data from session state
        exp_data = st.session_state.experiment_data
        
        # For experiments without rock samples, set sample_id to None
        sample_id = exp_data['sample_id'] if exp_data['sample_id'] else None
        
        # Create a new experiment
        experiment = Experiment(
            experiment_number=next_experiment_number,
            experiment_id=exp_data['experiment_id'],
            sample_id=sample_id,
            researcher=exp_data['researcher'],
            date=datetime.datetime.now(),
            status=getattr(ExperimentStatus, exp_data['status'])
        )
        
        # Add the experiment to the session
        db.add(experiment)
        db.flush() # Flush to ensure experiment exists in the transaction before service query
        
        # --- Use the Service to Create Experimental Conditions ---
        conditions_data = exp_data['conditions'].copy() # Get condition values

        # Convert empty strings to None for numeric fields
        for key, value in conditions_data.items():
            if key in FIELD_CONFIG and FIELD_CONFIG[key]['type'] == 'number' and value == '':
                conditions_data[key] = None
        
        # The service expects the string experiment_id
        conditions = ExperimentalConditionsService.create_experimental_conditions(
            db=db, 
            experiment_id=experiment.experiment_id, # Pass the string ID
            conditions_data=conditions_data
        )

        if conditions is None:
            # Handle error if conditions couldn't be created (e.g., experiment not found by service)
            # This case might be redundant if experiment is created right above, but good practice
            raise Exception(f"Failed to create experimental conditions for {experiment.experiment_id}")
        # Note: The service adds 'conditions' to the session and calls calculate_derived_conditions
        # --- End Service Usage ---
        
        # Add initial notes if any
        initial_note_text = exp_data.get('initial_note')
        if initial_note_text:
            # Ensure experiment has an ID before associating note if FK is on Experiment.id
            # If FK is on experiment_id (string), this flush isn't strictly needed here
            # db.flush() # Uncomment if ExperimentNotes.experiment_id links to Experiment.id (PK) -> Already flushed earlier
            note = ExperimentNotes(
                experiment_fk=experiment.id, # Assign the integer PK of the experiment
                experiment_id=experiment.experiment_id, # Assuming FK is on the string ID -> Keep string ID too
                note_text=initial_note_text
            )
            db.add(note)
        
        # Log the creation of the experiment and its related data
        # Ensure experiment has an ID before logging if FK is on Experiment.id
        # db.flush() # Uncomment if ModificationsLog.experiment_id links to Experiment.id (PK)
        log_modification(
            db=db,
            experiment_id=experiment.experiment_id, # Assuming FK is on the string ID
            modified_table="experiments",
            modification_type="create",
            new_values={
                'experiment_number': experiment.experiment_number,
                'experiment_id': experiment.experiment_id,
                'sample_id': experiment.sample_id,
                'researcher': experiment.researcher,
                'date': experiment.date.isoformat(),
                'status': experiment.status.name,
                # Log the conditions *after* potential calculation by the service
                # Need to refresh 'conditions' to get calculated values if service doesn't refresh
                # The service currently does refresh, so this should be fine
                'conditions': {k: v.isoformat() if isinstance(v, datetime.datetime) else v 
                               for k, v in conditions.__dict__.items() 
                               if not k.startswith('_') and k not in ['id', 'experiment_id', 'experiment_fk']},
                'initial_note': initial_note_text if initial_note_text else None
            }
        )

        # Commit the transaction
        db.commit()
        
        # Store data for pre-filling the next form
        st.session_state.previous_experiment_data = exp_data.copy()
        
        # Show experiment number and ID for reference in step 2
        st.session_state.last_created_experiment_number = next_experiment_number
        st.session_state.last_created_experiment_id = exp_data['experiment_id']
        
        st.session_state.step = 2 # Move to success step
        
        return True # Indicate success
        
    except Exception as e:
        if db: # Check if db was initialized before trying to rollback
            db.rollback()
        # Check if this is a unique constraint violation on experiment_id
        if "UNIQUE constraint failed: experiments.experiment_id" in str(e):
            st.error(f"An experiment with ID '{st.session_state.experiment_data['experiment_id']}' already exists. Please choose a different experiment ID.")
        else:
            st.error(f"Error saving experiment: {str(e)}")
        return False # Indicate failure
    finally:
        if db: # Check if db was initialized before trying to close
            db.close()

def create_new_experiment():
    """
    Create a new experiment entry.
    """
    with st.form(key="new_experiment_form"):
        st.markdown("### Basic Information")
        col1, col2 = st.columns(2)
        
        with col1:
            sample_id = st.text_input("Rock Sample ID")
            researcher = st.text_input("Researcher Name")
        
        with col2:
            status = st.selectbox(
                "Experiment Status",
                options=EXPERIMENT_STATUSES,
                index=0
            )
            # Use EST timezone for the date input
            est = pytz.timezone('US/Eastern')
            current_time = datetime.datetime.now(est)
            exp_date = st.date_input(
                "Experiment Date", 
                value=current_time
            )
        
        st.markdown("### Experimental Conditions")
        col3, col4 = st.columns(2)
        
        with col3:
            st.markdown("#### Required Parameters")
            required_field_names = [name for name, config in FIELD_CONFIG.items() if config.get('required', False)]
            required_values = generate_form_fields(
                FIELD_CONFIG, 
                {}, 
                required_field_names,
                key_prefix="new_req"
            )
            
        with col4:
            st.markdown("#### Optional Parameters")
            optional_field_names = [name for name, config in FIELD_CONFIG.items() if not config.get('required', False)]
            optional_values = generate_form_fields(
                FIELD_CONFIG, 
                {}, 
                optional_field_names,
                key_prefix="new_opt"
            )
        
        all_condition_values = {**required_values, **optional_values}
        
        # Convert EST date to UTC for storage
        utc_time = current_time.astimezone(pytz.UTC)
        
        form_data = {
            'sample_id': sample_id,
            'researcher': researcher,
            'status': status,
            'date': datetime.datetime.combine(exp_date, utc_time.time()).replace(tzinfo=pytz.UTC),
            'conditions': all_condition_values
        }
        
        submit_button = st.form_submit_button("Create Experiment")
        if submit_button:
            submit_new_experiment(form_data)