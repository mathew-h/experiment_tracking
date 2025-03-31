import datetime
import streamlit as st
from database.database import SessionLocal
from database.models import Experiment, ExperimentalConditions, ExperimentNotes, ExperimentStatus
from frontend.components.utils import build_conditions
from frontend.config.variable_config import (
    REQUIRED_DEFAULTS,
    OPTIONAL_FIELDS,
    VALUE_LABELS,
    EXPERIMENT_TYPES,
    EXPERIMENT_STATUSES
)

def render_new_experiment():

    # Set up session state if not already defined
    if 'step' not in st.session_state:
        st.session_state.step = 1

    if 'experiment_data' not in st.session_state:
        st.session_state.experiment_data = {
            'experiment_id': '',
            'sample_id': '',
            'researcher': '',
            'status': 'PLANNED',
            'conditions': {**REQUIRED_DEFAULTS, **OPTIONAL_FIELDS},
            'notes': []
        }
    else:
        # Always merge defaults with current conditions
        current = st.session_state.experiment_data.get('conditions', {})
        st.session_state.experiment_data['conditions'] = {**{**REQUIRED_DEFAULTS, **OPTIONAL_FIELDS}, **current}
    
    # STEP 1: Collect experiment data
    if st.session_state.step == 1:
        with st.form(key="experiment_form"):
            st.subheader("Experiment Details")

            col1, col2 = st.columns(2)
            with col1:
                experiment_id = st.text_input(
                    "Experiment ID", 
                    value=st.session_state.experiment_data['experiment_id'],
                    help="Enter a unique identifier for this experiment"
                )
                sample_id = st.text_input(
                    "Rock Sample ID", 
                    value=st.session_state.experiment_data['sample_id'],
                    help="Enter the sample identifier (e.g., 20UM21)"
                )
                researcher = st.text_input(
                    "Researcher Name", 
                    value=st.session_state.experiment_data['researcher']
                )
                status = st.selectbox(
                    "Experiment Status",
                    options=['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED'],
                    index=0
                )
                experiment_type = st.selectbox(
                    "Experiment Type",
                    options=['Serum', 'Autoclave', 'HPHT', 'Core Flood'],
                    index=0,
                    help="Select the type of experiment"
                )
                initial_ph = st.number_input(
                    "Initial pH", 
                    min_value=0.0, 
                    max_value=14.0, 
                    value=float(st.session_state.experiment_data['conditions'].get('initial_ph', 7.0)),
                    step=0.1,
                    format="%.1f"
                )
                particle_size = st.number_input(
                    "Particle Size (um)",
                    value=st.session_state.experiment_data['conditions'].get('particle_size', 0.0),
                    help="Enter the particle size specification"
                )
                rock_mass = st.number_input(
                    "Rock Mass (g)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('rock_mass', 0.0)),
                    step=0.000001,  # 6 significant figures
                    format="%.6f",
                    help="Enter the mass of rock in grams"
                )
                water_volume = st.number_input(
                    "Water Volume (mL)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('water_volume', 0.0)),
                    step=0.1,
                    format="%.1f",
                    help="Enter the volume of water in mL"
                )
                catalyst = st.text_input(
                    "Catalyst",
                    value=st.session_state.experiment_data['conditions'].get('catalyst', ''),
                    help="Enter the catalyst used"
                )
                catalyst_mass = st.number_input(
                    "Catalyst Mass (g)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('catalyst_mass', 0.0)),
                    step=0.000001,  # 6 significant figures
                    format="%.6f",
                    help="Enter the mass of catalyst in grams"
                )
                temperature = st.number_input(
                    "Temperature (°C)", 
                    min_value=-273.15, 
                    value=float(st.session_state.experiment_data['conditions'].get('temperature', 25.0)),
                    step=1.0,
                    format="%.1f"
                )
                pressure = st.number_input(
                    "Pressure (psi)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('pressure', 14.6959)),
                    step=0.1,
                    format="%.2f",
                    help="Enter the pressure in psi"
                )

            with col2:
                st.markdown("### Optional Parameters")
                buffer_system = st.text_input(
                    "Buffer System",
                    value=st.session_state.experiment_data['conditions'].get('buffer_system', ''),
                    help="Enter the buffer system used (optional)"
                )
                water_to_rock_ratio = st.number_input(
                    "Water to Rock Ratio", 
                    min_value=0.0, 
                    value=float(st.session_state.experiment_data['conditions'].get('water_to_rock_ratio', 0.0)),
                    step=0.1,
                    format="%.2f",
                    help="Enter the water to rock ratio (optional)"
                )
                flow_rate = st.number_input(
                    "Flow Rate (mL/min)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('flow_rate', 0.0)),
                    step=0.1,
                    format="%.1f",
                    help="Enter the flow rate in mL/min (optional)"
                )
                catalyst_percentage = st.number_input(
                    "Catalyst Percentage (Elemental % of Rock)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(st.session_state.experiment_data['conditions'].get('catalyst_percentage', 0.0)),
                    step=0.1,
                    format="%.1f",
                    help="Enter the percentage of catalyst used"
                )
                buffer_concentration = st.number_input(
                    "Buffer Concentration (mM)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('buffer_concentration', 0.0)),
                    step=0.1,
                    format="%.1f",
                    help="Enter the buffer concentration in mM"
                )
                initial_nitrate_concentration = st.number_input(
                    "Initial Nitrate Concentration (mM)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('initial_nitrate_concentration', 0.0)),
                    step=0.1,
                    format="%.1f",
                    help="Enter the initial nitrate concentration in mM"
                )
                dissolved_oxygen = st.number_input(
                    "Dissolved Oxygen (ppm)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('dissolved_oxygen', 0.0)),
                    step=0.1,
                    format="%.1f",
                    help="Enter the dissolved oxygen in ppm"
                )
                surfactant_type = st.text_input(
                    "Surfactant Type",
                    value=st.session_state.experiment_data['conditions'].get('surfactant_type', ''),
                    help="Enter the surfactant type used (optional)"
                )
                surfactant_concentration = st.number_input(
                    "Surfactant Concentration",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('surfactant_concentration', 0.0)),
                    step=0.1,
                    format="%.2f",
                    help="Enter the surfactant concentration"
                )
                co2_partial_pressure = st.number_input(
                    "CO2 Partial Pressure (psi)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('co2_partial_pressure', 0.0)),
                    step=0.1,
                    format="%.2f",
                    help="Enter the CO2 partial pressure in psi"
                )
                confining_pressure = st.number_input(
                    "Confining Pressure (psi)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('confining_pressure', 0.0)),
                    step=0.1,
                    format="%.2f",
                    help="Enter the confining pressure in psi"
                )
                pore_pressure = st.number_input(
                    "Pore Pressure (psi)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('pore_pressure', 0.0)),
                    step=0.1,
                    format="%.2f",
                    help="Enter the pore pressure in psi"
                )

            st.markdown("### Initial Notes")
            note_text = st.text_area(
                "Lab Note",
                value="",
                height=200,
                help="Add any initial lab notes for this experiment. You can add more notes later."
            )

            # Form submit button
            submit_button = st.form_submit_button("Save Experiment")

            if submit_button:
                # Update session state with form values
                st.session_state.experiment_data.update({
                    'experiment_id': experiment_id,
                    'sample_id': sample_id,
                    'researcher': researcher,
                    'status': status,
                    'conditions': {
                        'particle_size': particle_size,
                        'water_to_rock_ratio': water_to_rock_ratio if water_to_rock_ratio > 0 else 0.0,
                        'initial_ph': initial_ph,
                        'rock_mass': rock_mass,
                        'water_volume': water_volume,
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
                })

                # Handle notes
                if note_text.strip():
                    if 'notes' not in st.session_state.experiment_data:
                        st.session_state.experiment_data['notes'] = []
                    st.session_state.experiment_data['notes'].append({
                        'note_text': note_text.strip(),
                        'created_at': datetime.datetime.now()
                    })

                save_experiment()
                st.success("Experiment saved successfully!")
                st.session_state.step = 2

    # STEP 2: Show a success message and allow another experiment
    elif st.session_state.step == 2:
        st.success("Experiment created successfully!")
        if st.button("Create Another Experiment"):
            st.session_state.step = 1
            st.session_state.experiment_data = {
                'experiment_id': '',
                'sample_id': '',
                'researcher': '',
                'status': 'PLANNED',
                'conditions': build_conditions(REQUIRED_DEFAULTS, OPTIONAL_FIELDS, {}, None),
                'notes': []
            }

def save_experiment():
    """Save the experiment data to the database."""
    try:
        # Create a database session
        db = SessionLocal()
        
        # Get the next experiment number
        last_experiment = db.query(Experiment).order_by(Experiment.experiment_number.desc()).first()
        next_experiment_number = 1 if last_experiment is None else last_experiment.experiment_number + 1
        
        # Ensure all required fields exist and have defaults
        conditions = st.session_state.experiment_data['conditions']
        for field, default in REQUIRED_DEFAULTS.items():
            if field not in conditions or conditions[field] is None:
                conditions[field] = default
        
        # Ensure all optional fields are present and filled
        for field in OPTIONAL_FIELDS:
            if field not in conditions or conditions[field] is None:
                conditions[field] = None
           
        # Create a new experiment
        experiment = Experiment(
            experiment_number=next_experiment_number,
            experiment_id=st.session_state.experiment_data['experiment_id'],
            sample_id=st.session_state.experiment_data['sample_id'],
            researcher=st.session_state.experiment_data['researcher'],
            date=datetime.datetime.now(),
            status=getattr(ExperimentStatus, st.session_state.experiment_data['status'])
        )
        
        # Add the experiment to the session
        db.add(experiment)
        db.flush()  # Flush to get the experiment ID
        
        # Create experimental conditions
        conditions_data = build_conditions(REQUIRED_DEFAULTS, OPTIONAL_FIELDS, st.session_state.experiment_data['conditions'], experiment.id)
        conditions = ExperimentalConditions(**conditions_data)
        
        # Add the conditions to the session
        db.add(conditions)
        
        # Add initial notes if any
        for note_data in st.session_state.experiment_data.get('notes', []):
            note = ExperimentNotes(
                experiment_id=experiment.id,
                note_text=note_data['note_text']
            )
            db.add(note)
        
        # Commit the transaction
        db.commit()
        
        # Show experiment number and ID for reference
        st.session_state.last_created_experiment_number = next_experiment_number
        st.session_state.last_created_experiment_id = st.session_state.experiment_data['experiment_id']
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving experiment: {str(e)}")
        raise e
    finally:
        db.close()