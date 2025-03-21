import streamlit as st
import datetime
import json
import sys
import os

# Add parent directory to path for database imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database.models import Experiment, ExperimentalConditions, ExperimentStatus, ExperimentNotes, ModificationsLog, ExperimentalData, SampleInfo, ExternalAnalysis, Results
from database.database import SessionLocal
import pandas as pd

def render_sidebar():
    with st.sidebar:
        st.title("Navigation")
        page = st.radio(
            "Go to",
            ["New Experiment", "View Experiments", 
             "New Rock Sample", "View Sample Inventory", "Settings"]
        )
        return page

def render_header():
    """Render the header with the current page title and Addis Energy Research icon."""
    col1, col2 = st.columns([1, 4])
    
    with col1:
        # Display the Addis Energy Research icon
        st.image(
            os.path.join(os.path.dirname(__file__), "..", ".streamlit", "static", "Addis_Avatar_SandColor_NoBackground.png"),
            width=100
        )
    
    with col2:
        st.title("Addis Energy Research")
    
    # Add custom CSS for the banner
    st.markdown("""
        <style>
            .banner-container {
                display: flex;
                align-items: center;
                gap: 20px;
                padding: 20px;
                background-color: #f8f9fa;
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .banner-logo {
                width: 120px;
                height: 120px;
                object-fit: contain;
            }
            .banner-title {
                color: #2c3e50;
                font-size: 2.5em;
                margin: 0;
                font-weight: 600;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Use absolute path for the logo
    logo_path = r"C:\Users\MathewHearl\OneDrive - Addis Energy\Documents\0x_Software\experiment_tracking\frontend\static\Addis_Avatar_SandColor_NoBackground.png"
    
    # Only show header on dashboard
    if st.session_state.get('current_page') == "Dashboard":
        try:
            col1, col2 = st.columns([1, 4])
            with col1:
                st.image(logo_path, width=120)
            with col2:
                st.markdown("<h1 class='banner-title'>Addis Energy Research</h1>", unsafe_allow_html=True)
            st.markdown("---")
        except Exception as e:
            st.error(f"Error loading logo: {str(e)}")

def get_image_base64(image_path):
    """Convert image to base64 string."""
    import base64
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

def nav_page(page_name, timeout_secs=3):
    """Navigate to another page using JavaScript."""
    from streamlit.components.v1 import html
    nav_script = """
        <script type="text/javascript">
            function attempt_nav_page(page_name, start_time, timeout_secs) {
                var links = window.parent.document.getElementsByTagName("a");
                for (var i = 0; i < links.length; i++) {
                    if (links[i].href.toLowerCase().endsWith("/" + page_name.toLowerCase())) {
                        links[i].click();
                        return;
                    }
                }
                var elasped = new Date() - start_time;
                if (elasped < timeout_secs * 1000) {
                    setTimeout(attempt_nav_page, 100, page_name, start_time, timeout_secs);
                } else {
                    alert("Unable to navigate to page '" + page_name + "' after " + timeout_secs + " second(s).");
                }
            }
            window.addEventListener("load", function() {
                attempt_nav_page("%s", new Date(), %d);
            });
        </script>
    """ % (page_name, timeout_secs)
    html(nav_script)

def render_dashboard():
    st.header("Dashboard")
    
    # Create a descriptive menu for each section
    st.markdown("### Navigation Menu")
    
    # Define sections with descriptions
    sections = [
        {
            "title": "New Experiment",
            "description": "Create a new experiment with detailed parameters, conditions, and initial notes.",
            "icon": "🧪",
            "page": "new_experiment"
        },
        {
            "title": "View Experiments",
            "description": "Browse, search, and filter all experiments. View detailed information, add notes, and track modifications.",
            "icon": "📊",
            "page": "view_experiments"
        },
        {
            "title": "New Rock Sample",
            "description": "Add a new rock sample to the inventory with classification, location, and photo documentation.",
            "icon": "🪨",
            "page": "new_rock_sample"
        },
        {
            "title": "View Sample Inventory",
            "description": "Access the complete rock sample inventory, search by classification, and view sample details.",
            "icon": "📚",
            "page": "view_sample_inventory"
        },
        {
            "title": "Settings",
            "description": "Configure application settings and preferences.",
            "icon": "⚙️",
            "page": "settings"
        }
    ]
    
    # Create a grid layout for the menu items
    for section in sections:
        with st.container():
            col1, col2 = st.columns([1, 4])
            
            with col1:
                st.markdown(f"### {section['icon']}")
            
            with col2:
                st.markdown(f"#### {section['title']}")
                st.markdown(section['description'])
                if st.button(f"Go to {section['title']}", key=f"nav_{section['title']}"):
                    nav_page(section['page'])
            
            st.markdown("---")
    
    # Add some statistics or summary information
    st.markdown("### Quick Statistics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        try:
            db = SessionLocal()
            total_experiments = db.query(Experiment).count()
            st.metric("Total Experiments", total_experiments)
        except Exception as e:
            st.error(f"Error retrieving experiment count: {str(e)}")
        finally:
            db.close()
    
    with col2:
        try:
            db = SessionLocal()
            total_samples = db.query(SampleInfo).count()
            st.metric("Total Rock Samples", total_samples)
        except Exception as e:
            st.error(f"Error retrieving sample count: {str(e)}")
        finally:
            db.close()
    
    with col3:
        try:
            db = SessionLocal()
            active_experiments = db.query(Experiment).filter(Experiment.status == ExperimentStatus.IN_PROGRESS).count()
            st.metric("Active Experiments", active_experiments)
        except Exception as e:
            st.error(f"Error retrieving active experiment count: {str(e)}")
        finally:
            db.close()

def render_new_experiment():
    st.header("New Experiment")
    
    # Initialize session state
    if 'step' not in st.session_state:
        st.session_state.step = 1
    
    if 'experiment_data' not in st.session_state:
        # Create a complete default structure with all fields initialized
        st.session_state.experiment_data = {
            'experiment_id': '',
            'sample_id': '',
            'researcher': '',
            'status': 'PLANNED',
            'conditions': {
                'particle_size': '',
                'water_to_rock_ratio': None,  # Made optional
                'initial_ph': 7.0,
                'catalyst': '',
                'catalyst_mass': 0.0,  # Added as required field
                'catalyst_percentage': 0.0,
                'temperature': 25.0,
                'buffer_system': None,  # Made optional
                'buffer_concentration': 0.0,
                'pressure': 14.6959,
                'flow_rate': None,  # Made optional
                'experiment_type': 'Serum',
                'initial_nitrate_concentration': 0.0,
                'dissolved_oxygen': 0.0,
                'surfactant_type': '',
                'surfactant_concentration': 0.0,
                'co2_partial_pressure': 0.0,
                'confining_pressure': 0.0,
                'pore_pressure': 0.0
            },
            'notes': []
        }
    # Make sure all fields exist in the conditions
    else:
        # Ensure all fields exist in conditions with default values
        conditions = st.session_state.experiment_data['conditions']
        default_values = {
            'particle_size': '',
            'water_to_rock_ratio': None,  # Made optional
            'initial_ph': 7.0,
            'catalyst': '',
            'catalyst_mass': 0.0,  # Added as required field
            'catalyst_percentage': 0.0,
            'temperature': 25.0,
            'buffer_system': None,  # Made optional
            'buffer_concentration': 0.0,
            'pressure': 14.6959,
            'flow_rate': None,  # Made optional
            'experiment_type': 'Serum',
            'initial_nitrate_concentration': 0.0,
            'dissolved_oxygen': 0.0,
            'surfactant_type': '',
            'surfactant_concentration': 0.0,
            'co2_partial_pressure': 0.0,
            'confining_pressure': 0.0,
            'pore_pressure': 0.0
        }
        
        for field, default_value in default_values.items():
            if field not in conditions or conditions[field] is None:
                conditions[field] = default_value
    
    # Step 1: Collect experiment data
    if st.session_state.step == 1:
        st.subheader("Experiment Details")
        
        # Create a form for experiment data
        with st.form(key="experiment_form"):
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
                
                particle_size = st.text_input(
                    "Particle Size (um)",
                    value=st.session_state.experiment_data['conditions'].get('particle_size', ''),
                    help="Enter the particle size specification"
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
                    value=float(st.session_state.experiment_data['conditions']['initial_ph'] or 7.0),
                    step=0.1,
                    format="%.1f"
                )
                
                temperature = st.number_input(
                    "Temperature (°C)", 
                    min_value=-273.15, 
                    value=float(st.session_state.experiment_data['conditions']['temperature'] or 25.0),
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
                    "Buffer System (Optional)",
                    value=st.session_state.experiment_data['conditions'].get('buffer_system', ''),
                    help="Enter the buffer system used (optional)"
                )
                
                water_to_rock_ratio = st.number_input(
                    "Water to Rock Ratio (Optional)", 
                    min_value=0.0, 
                    value=float(st.session_state.experiment_data['conditions'].get('water_to_rock_ratio', 0.0) or 0.0),
                    step=0.1,
                    format="%.2f",
                    help="Enter the water to rock ratio (optional)"
                )
                
                flow_rate = st.number_input(
                    "Flow Rate (mL/min) (Optional)",
                    min_value=0.0,
                    value=float(st.session_state.experiment_data['conditions'].get('flow_rate', 0.0) or 0.0),
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
            
            # Add Notes Section
            st.markdown("### Initial Notes")
            note_text = st.text_area(
                "Lab Note",
                value="",
                height=200,
                help="Add any initial lab notes for this experiment. You can add more notes later."
            )
            
            # Update form data on submit
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
                        'water_to_rock_ratio': water_to_rock_ratio if water_to_rock_ratio > 0 else None,
                        'initial_ph': initial_ph,
                        'catalyst': catalyst,
                        'catalyst_mass': catalyst_mass,
                        'catalyst_percentage': catalyst_percentage,
                        'temperature': temperature,
                        'buffer_system': buffer_system if buffer_system.strip() else None,
                        'buffer_concentration': buffer_concentration,
                        'pressure': pressure,
                        'flow_rate': flow_rate if flow_rate > 0 else None,
                        'experiment_type': experiment_type,
                        'initial_nitrate_concentration': initial_nitrate_concentration,
                        'dissolved_oxygen': dissolved_oxygen,
                        'surfactant_type': surfactant_type,
                        'surfactant_concentration': surfactant_concentration,
                        'co2_partial_pressure': co2_partial_pressure,
                        'confining_pressure': confining_pressure,
                        'pore_pressure': pore_pressure
                    }
                })
                
                # Handle notes in form submission
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
    
    # Step 2: Success message
    elif st.session_state.step == 2:
        st.success("Experiment created successfully!")
        if st.button("Create Another Experiment"):
            st.session_state.step = 1
            st.session_state.experiment_data = {
                'experiment_id': '',
                'sample_id': '',
                'researcher': '',
                'status': 'PLANNED',
                'conditions': {
                    'particle_size': '',
                    'water_to_rock_ratio': None,  # Made optional
                    'initial_ph': 7.0,
                    'catalyst': '',
                    'catalyst_mass': 0.0,  # Added as required field
                    'catalyst_percentage': 0.0,
                    'temperature': 25.0,
                    'buffer_system': None,  # Made optional
                    'buffer_concentration': 0.0,
                    'pressure': 14.6959,
                    'flow_rate': None,  # Made optional
                    'experiment_type': 'Serum',
                    'initial_nitrate_concentration': 0.0,
                    'dissolved_oxygen': 0.0,
                    'surfactant_type': '',
                    'surfactant_concentration': 0.0,
                    'co2_partial_pressure': 0.0,
                    'confining_pressure': 0.0,
                    'pore_pressure': 0.0
                },
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
        for field in ['particle_size', 'water_to_rock_ratio', 'initial_ph', 'catalyst', 
                     'catalyst_mass', 'catalyst_percentage', 'temperature', 'buffer_system', 'pressure', 
                     'flow_rate', 'experiment_type', 'initial_nitrate_concentration', 
                     'dissolved_oxygen', 'surfactant_type', 'surfactant_concentration', 
                     'buffer_concentration', 'co2_partial_pressure', 'confining_pressure', 'pore_pressure']:
            if field not in conditions or conditions[field] is None:
                if field in ['water_to_rock_ratio', 'catalyst_percentage', 'initial_nitrate_concentration', 
                           'dissolved_oxygen', 'surfactant_concentration', 'buffer_concentration', 
                           'co2_partial_pressure', 'confining_pressure', 'pore_pressure', 'flow_rate']:
                    conditions[field] = None  # These are optional fields
                elif field == 'initial_ph':
                    conditions[field] = 7.0
                elif field == 'catalyst_mass':
                    conditions[field] = 0.0
                elif field == 'temperature':
                    conditions[field] = 25.0
                elif field == 'pressure':
                    conditions[field] = 14.6959
                elif field == 'experiment_type':
                    conditions[field] = 'Serum'
                elif field == 'buffer_system':
                    conditions[field] = None  # Optional field
                else:
                    conditions[field] = ''
        
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
        conditions = ExperimentalConditions(
            experiment_id=experiment.id,
            particle_size=st.session_state.experiment_data['conditions']['particle_size'],
            water_to_rock_ratio=st.session_state.experiment_data['conditions']['water_to_rock_ratio'],
            initial_ph=st.session_state.experiment_data['conditions']['initial_ph'],
            catalyst=st.session_state.experiment_data['conditions']['catalyst'],
            catalyst_mass=st.session_state.experiment_data['conditions']['catalyst_mass'],
            catalyst_percentage=st.session_state.experiment_data['conditions']['catalyst_percentage'],
            temperature=st.session_state.experiment_data['conditions']['temperature'],
            buffer_system=st.session_state.experiment_data['conditions']['buffer_system'],
            buffer_concentration=st.session_state.experiment_data['conditions']['buffer_concentration'],
            pressure=st.session_state.experiment_data['conditions']['pressure'],
            flow_rate=st.session_state.experiment_data['conditions']['flow_rate'],
            experiment_type=st.session_state.experiment_data['conditions']['experiment_type'],
            initial_nitrate_concentration=st.session_state.experiment_data['conditions']['initial_nitrate_concentration'],
            dissolved_oxygen=st.session_state.experiment_data['conditions']['dissolved_oxygen'],
            surfactant_type=st.session_state.experiment_data['conditions']['surfactant_type'],
            surfactant_concentration=st.session_state.experiment_data['conditions']['surfactant_concentration'],
            co2_partial_pressure=st.session_state.experiment_data['conditions']['co2_partial_pressure'],
            confining_pressure=st.session_state.experiment_data['conditions']['confining_pressure'],
            pore_pressure=st.session_state.experiment_data['conditions']['pore_pressure']
        )
        
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

def render_view_experiments():
    # Add custom CSS at the top of your render_view_experiments function
    st.markdown("""
        <style>
            div[data-testid="column"] {
                padding: 0px;
                margin: 0px;
            }
            div[data-testid="stHorizontalBlock"] {
                padding: 0px;
                margin: 0px;
            }
            div[data-testid="stMarkdownContainer"] > hr {
                margin: 5px 0px;
            }
        </style>
    """, unsafe_allow_html=True)

    # Check if experiment was updated and trigger rerun
    if st.session_state.get('experiment_updated', False):
        st.session_state.experiment_updated = False
        st.rerun()

    st.header("View Experiments")
    
    # Initialize session state if not exists
    if 'view_experiment_id' not in st.session_state:
        st.session_state.view_experiment_id = None
    
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False
    
    # Keep the Experiment ID search for direct access
    st.markdown("### Quick Access")
    exp_id = st.text_input("Enter Experiment ID to view details directly:")
    if st.button("View Experiment") and exp_id:
        st.session_state.view_experiment_id = exp_id
        st.rerun()
    # If we're not viewing a specific experiment, show the list
    if st.session_state.view_experiment_id is None:
        # Get all experiments from database
        experiments = get_all_experiments()
        
        # Create filter/search options
        st.markdown("### Search and Filter Experiments")
        
        # Create columns for filters
        col1, col2 = st.columns(2)
        
        with col1:
            # Basic filters
            search_term = st.text_input("Search by Sample ID or Researcher:", "")
            status_filter = st.selectbox(
                "Filter by Status:",
                ["All"] + [status.name for status in ExperimentStatus]
            )
            
            # Date range filter
            st.markdown("#### Date Range")
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                start_date = st.date_input("Start Date", value=None)
            with date_col2:
                end_date = st.date_input("End Date", value=None)
        
        with col2:
            # Experimental conditions filters
            st.markdown("#### Experimental Conditions")
            catalyst_filter = st.text_input("Filter by Catalyst Type:", "")
            
            # Temperature range
            temp_col1, temp_col2 = st.columns(2)
            with temp_col1:
                min_temp = st.number_input("Min Temperature (°C)", value=None, min_value=-273.15)
            with temp_col2:
                max_temp = st.number_input("Max Temperature (°C)", value=None, min_value=-273.15)
            
            # pH range
            ph_col1, ph_col2 = st.columns(2)
            with ph_col1:
                min_ph = st.number_input("Min pH", value=None, min_value=0.0, max_value=14.0)
            with ph_col2:
                max_ph = st.number_input("Max pH", value=None, min_value=0.0, max_value=14.0)
        
        # Apply filters
        filtered_experiments = experiments
        
        if search_term:
            filtered_experiments = [exp for exp in filtered_experiments if 
                          search_term.lower() in exp['sample_id'].lower() or 
                          search_term.lower() in exp['researcher'].lower() or
                          (exp['experiment_id'] and search_term.lower() in exp['experiment_id'].lower())]
        
        if status_filter != "All":
            filtered_experiments = [exp for exp in filtered_experiments if exp['status'] == status_filter]
        
        if start_date:
            filtered_experiments = [exp for exp in filtered_experiments if exp['date'].date() >= start_date]
        
        if end_date:
            filtered_experiments = [exp for exp in filtered_experiments if exp['date'].date() <= end_date]
        
        if not filtered_experiments:
            st.info("No experiments found matching the selected criteria.")
        else:
            # Get detailed experiment data for filtering by conditions
            detailed_experiments = []
            for exp in filtered_experiments:
                detailed_exp = get_experiment_by_id(exp['id'])
                if detailed_exp:
                    detailed_experiments.append(detailed_exp)
            
            # Apply experimental conditions filters
            if catalyst_filter:
                detailed_experiments = [exp for exp in detailed_experiments if 
                                      exp['conditions'].get('catalyst', '').lower() == catalyst_filter.lower()]
            
            if min_temp is not None:
                detailed_experiments = [exp for exp in detailed_experiments if 
                                      exp['conditions'].get('temperature', 0) >= min_temp]
            
            if max_temp is not None:
                detailed_experiments = [exp for exp in detailed_experiments if 
                                      exp['conditions'].get('temperature', 0) <= max_temp]
            
            if min_ph is not None:
                detailed_experiments = [exp for exp in detailed_experiments if 
                                      exp['conditions'].get('initial_ph', 0) >= min_ph]
            
            if max_ph is not None:
                detailed_experiments = [exp for exp in detailed_experiments if 
                                      exp['conditions'].get('initial_ph', 0) <= max_ph]
            
            # Display experiments in a table
            exp_df = pd.DataFrame(detailed_experiments)
            exp_df = exp_df[['experiment_id', 'sample_id', 'researcher', 'date', 'status']]
            exp_df.columns = ['Experiment ID', 'Sample ID', 'Researcher', 'Date', 'Status']
            
            # Format date for display
            exp_df['Date'] = pd.to_datetime(exp_df['Date']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Make the table interactive with clickable rows
            st.markdown("### Experiments")
            st.markdown("Click 'View Details' to see experiment information")
            
            # Create a custom table layout
            for index, row in exp_df.iterrows():
                with st.container():
                    # Create columns for the row
                    col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 2, 1])
                    
                    # Display data in each column
                    with col1:
                        st.write(f"<div style='margin: 0px; padding: 2px;'>{row['Experiment ID']}</div>", unsafe_allow_html=True)
                    with col2:
                        st.write(f"<div style='margin: 0px; padding: 2px;'>{row['Sample ID']}</div>", unsafe_allow_html=True)
                    with col3:
                        st.write(f"<div style='margin: 0px; padding: 2px;'>{row['Researcher']}</div>", unsafe_allow_html=True)
                    with col4:
                        st.write(f"<div style='margin: 0px; padding: 2px;'>{row['Date']}</div>", unsafe_allow_html=True)
                    with col5:
                        st.write(f"<div style='margin: 0px; padding: 2px;'>{row['Status']}</div>", unsafe_allow_html=True)
                    with col6:
                        if st.button("View Details", key=f"view_{index}"):
                            st.session_state.view_experiment_id = row['Experiment ID']
                            st.rerun()
                    
                    # Use a thinner separator
                    st.markdown("<hr style='margin: 2px 0px; background-color: #f0f0f0; height: 1px; border: none;'>", unsafe_allow_html=True)
            
    else:
        # We're viewing a specific experiment
        experiment = get_experiment_by_id(st.session_state.view_experiment_id)
        
        if experiment is None:
            st.error(f"Experiment with ID {st.session_state.view_experiment_id} not found.")
            if st.button("Back to Experiment List"):
                st.session_state.view_experiment_id = None
                st.session_state.edit_mode = False
        else:
            # Show experiment details
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.button("← Back to List"):
                    st.session_state.view_experiment_id = None
                    st.session_state.edit_mode = False
            
            with col3:
                if not st.session_state.edit_mode:
                    if st.button("Edit Experiment"):
                        st.session_state.edit_mode = True
                else:
                    if st.button("Cancel Edit"):
                        st.session_state.edit_mode = False
            
            # Display experiment info
            st.subheader(f"Experiment: {experiment['experiment_id']}")
            
            if not st.session_state.edit_mode:
                # View mode - just display info
                display_experiment_details(experiment)
            else:
                # Edit mode - show editable form
                edit_experiment(experiment)

def get_all_experiments():
    """Get all experiments from the database."""
    try:
        db = SessionLocal()
        experiments_query = db.query(Experiment).order_by(Experiment.date.desc()).all()
        
        # Convert to list of dictionaries for easy display
        experiments = []
        for exp in experiments_query:
            experiments.append({
                'id': exp.id,
                'experiment_id': exp.experiment_id,
                'sample_id': exp.sample_id,
                'date': exp.date,
                'researcher': exp.researcher,
                'status': exp.status.name
            })
        
        return experiments
    except Exception as e:
        st.error(f"Error retrieving experiments: {str(e)}")
        return []
    finally:
        db.close()

def get_experiment_by_id(experiment_id):
    """Get a specific experiment by ID with all related data."""
    try:
        db = SessionLocal()
        # Check if input is a string (experiment_id) or integer (database id)
        if isinstance(experiment_id, str):
            experiment = db.query(Experiment).filter(Experiment.experiment_id == experiment_id).first()
        else:
            experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        
        if experiment is None:
            return None
        
        # Get related conditions, notes, and experimental data
        conditions = experiment.conditions
        notes = experiment.notes
        modifications = experiment.modifications
        experimental_data = experiment.experimental_data  # Get experimental data
        
        # Convert to dictionary for display
        exp_dict = {
            'id': experiment.id,
            'experiment_number': experiment.experiment_number,
            'experiment_id': experiment.experiment_id,
            'sample_id': experiment.sample_id,
            'date': experiment.date,
            'researcher': experiment.researcher,
            'status': experiment.status.name,
            'created_at': experiment.created_at,
            'updated_at': experiment.updated_at,
            'conditions': {},
            'notes': [],
            'modifications': [],
            'experimental_data': []  # Add experimental data list
        }
        
        # Add conditions if they exist with default values for missing fields
        if conditions:
            # Initialize with default values
            condition_dict = {
                'particle_size': '',
                'water_to_rock_ratio': 0.0,
                'initial_ph': 7.0,
                'catalyst': '',
                'catalyst_percentage': 0.0,
                'temperature': 25.0,
                'buffer_system': '',
                'buffer_concentration': 0.0,
                'pressure': 14.6959,
                'flow_rate': 0.0,
                'experiment_type': 'Serum',
                'initial_nitrate_concentration': 0.0,
                'dissolved_oxygen': 0.0,
                'surfactant_type': '',
                'surfactant_concentration': 0.0,
                'co2_partial_pressure': 0.0,
                'confining_pressure': 0.0,
                'pore_pressure': 0.0
            }
            
            # Update with actual values where they exist
            if hasattr(conditions, 'particle_size') and conditions.particle_size is not None:
                condition_dict['particle_size'] = conditions.particle_size
            
            if hasattr(conditions, 'water_to_rock_ratio') and conditions.water_to_rock_ratio is not None:
                condition_dict['water_to_rock_ratio'] = conditions.water_to_rock_ratio
                
            if hasattr(conditions, 'initial_ph') and conditions.initial_ph is not None:
                condition_dict['initial_ph'] = conditions.initial_ph
                
            if hasattr(conditions, 'catalyst') and conditions.catalyst is not None:
                condition_dict['catalyst'] = conditions.catalyst
                
            if hasattr(conditions, 'catalyst_percentage') and conditions.catalyst_percentage is not None:
                condition_dict['catalyst_percentage'] = conditions.catalyst_percentage
                
            if hasattr(conditions, 'temperature') and conditions.temperature is not None:
                condition_dict['temperature'] = conditions.temperature
                
            if hasattr(conditions, 'buffer_system') and conditions.buffer_system is not None:
                condition_dict['buffer_system'] = conditions.buffer_system
                
            if hasattr(conditions, 'buffer_concentration') and conditions.buffer_concentration is not None:
                condition_dict['buffer_concentration'] = conditions.buffer_concentration
                
            if hasattr(conditions, 'pressure') and conditions.pressure is not None:
                condition_dict['pressure'] = conditions.pressure
                
            if hasattr(conditions, 'flow_rate') and conditions.flow_rate is not None:
                condition_dict['flow_rate'] = conditions.flow_rate
                
            if hasattr(conditions, 'experiment_type') and conditions.experiment_type is not None:
                condition_dict['experiment_type'] = conditions.experiment_type
                
            if hasattr(conditions, 'initial_nitrate_concentration') and conditions.initial_nitrate_concentration is not None:
                condition_dict['initial_nitrate_concentration'] = conditions.initial_nitrate_concentration
                
            if hasattr(conditions, 'dissolved_oxygen') and conditions.dissolved_oxygen is not None:
                condition_dict['dissolved_oxygen'] = conditions.dissolved_oxygen
                
            if hasattr(conditions, 'surfactant_type') and conditions.surfactant_type is not None:
                condition_dict['surfactant_type'] = conditions.surfactant_type
                
            if hasattr(conditions, 'surfactant_concentration') and conditions.surfactant_concentration is not None:
                condition_dict['surfactant_concentration'] = conditions.surfactant_concentration
                
            if hasattr(conditions, 'co2_partial_pressure') and conditions.co2_partial_pressure is not None:
                condition_dict['co2_partial_pressure'] = conditions.co2_partial_pressure
                
            if hasattr(conditions, 'confining_pressure') and conditions.confining_pressure is not None:
                condition_dict['confining_pressure'] = conditions.confining_pressure
                
            if hasattr(conditions, 'pore_pressure') and conditions.pore_pressure is not None:
                condition_dict['pore_pressure'] = conditions.pore_pressure
            
            exp_dict['conditions'] = condition_dict
        
        # Add notes if they exist
        if notes:
            exp_dict['notes'] = [
                {
                    'id': note.id,
                    'note_text': note.note_text,
                    'created_at': note.created_at,
                    'updated_at': note.updated_at
                }
                for note in notes
            ]
        
        # Add modifications if they exist
        if modifications:
            exp_dict['modifications'] = [
                {
                    'id': mod.id,
                    'modified_by': mod.modified_by,
                    'modification_type': mod.modification_type,
                    'modified_table': mod.modified_table,
                    'old_values': mod.old_values,
                    'new_values': mod.new_values,
                    'created_at': mod.created_at
                }
                for mod in modifications
            ]
        
        # Add experimental data if they exist
        if experimental_data:
            exp_dict['experimental_data'] = [
                {
                    'id': data.id,
                    'data_type': data.data_type,
                    'file_path': data.file_path,
                    'file_name': data.file_name,
                    'file_type': data.file_type,
                    'data_values': data.data_values,
                    'description': data.description,
                    'created_at': data.created_at,
                    'updated_at': data.updated_at
                }
                for data in experimental_data
            ]
        
        return exp_dict
    except Exception as e:
        st.error(f"Error retrieving experiment: {str(e)}")
        return None
    finally:
        db.close()

def display_experiment_details(experiment):
    """Display the details of an experiment."""
    # Basic Info
    st.markdown("### Basic Information")
    basic_info = {
        "Experiment Number": str(experiment['experiment_number']),
        "Experiment ID": str(experiment['experiment_id']),
        "Sample ID": str(experiment['sample_id']),
        "Researcher": str(experiment['researcher']),
        "Status": str(experiment['status']),
        "Date Created": experiment['date'].strftime("%Y-%m-%d %H:%M") if isinstance(experiment['date'], datetime.datetime) else str(experiment['date']),
        "Date Updated": experiment['updated_at'].strftime("%Y-%m-%d %H:%M") if experiment['updated_at'] else "N/A"
    }
    
    # Convert to DataFrame and ensure all values are strings
    df = pd.DataFrame([basic_info]).T.rename(columns={0: "Value"})
    df['Value'] = df['Value'].astype(str)  # Convert all values to strings
    st.table(df)
    
    # Conditions
    st.markdown("### Experimental Conditions")
    if experiment['conditions']:
        # Split conditions into two columns: required and optional
        required_conditions = {
            "Experiment Type": experiment['conditions'].get('experiment_type', 'N/A'),
            "Particle Size": experiment['conditions'].get('particle_size', 'N/A'),
            "Water to Rock Ratio": experiment['conditions'].get('water_to_rock_ratio', 'N/A'),
            "Initial pH": experiment['conditions'].get('initial_ph', 'N/A'),
            "Temperature (°C)": experiment['conditions'].get('temperature', 'N/A'),
            "Pressure (psi)": experiment['conditions'].get('pressure', 'N/A'),
            "Flow Rate (mL/min)": experiment['conditions'].get('flow_rate', 'N/A'),
            "Catalyst": experiment['conditions'].get('catalyst', 'N/A'),
            "Buffer System": experiment['conditions'].get('buffer_system', 'N/A')
        }
        
        optional_conditions = {
            "Catalyst Percentage (%)": experiment['conditions'].get('catalyst_percentage', 'N/A'),
            "Buffer Concentration (mM)": experiment['conditions'].get('buffer_concentration', 'N/A'),
            "Initial Nitrate Concentration (mM)": experiment['conditions'].get('initial_nitrate_concentration', 'N/A'),
            "Dissolved Oxygen (ppm)": experiment['conditions'].get('dissolved_oxygen', 'N/A'),
            "Surfactant Type": experiment['conditions'].get('surfactant_type', 'N/A'),
            "Surfactant Concentration": experiment['conditions'].get('surfactant_concentration', 'N/A'),
            "CO2 Partial Pressure (psi)": experiment['conditions'].get('co2_partial_pressure', 'N/A'),
            "Confining Pressure (psi)": experiment['conditions'].get('confining_pressure', 'N/A'),
            "Pore Pressure (psi)": experiment['conditions'].get('pore_pressure', 'N/A')
        }
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Required Parameters")
            req_df = pd.DataFrame([required_conditions]).T.rename(columns={0: "Value"})
            st.table(req_df)
        
        with col2:
            st.markdown("#### Optional Parameters")
            opt_df = pd.DataFrame([optional_conditions]).T.rename(columns={0: "Value"})
            st.table(opt_df)
    else:
        st.info("No experimental conditions recorded for this experiment.")
    
    # Results Section
    st.markdown("### Results")
    
    # Try to get results data
    db = SessionLocal()
    result = db.query(Results).filter(Results.experiment_id == experiment['id']).first()
    db.close()
    
    if result:
        results_data = {
            "Final pH": result.final_ph if result.final_ph else "Not recorded",
            "Final Nitrate Concentration (mM)": result.final_nitrate_concentration if result.final_nitrate_concentration else "Not recorded",
            "Yield Value (%)": result.yield_value if result.yield_value else "Not recorded"
        }
        
        results_df = pd.DataFrame([results_data]).T.rename(columns={0: "Value"})
        st.table(results_df)
        
        # Add an option to edit results
        if st.button("Edit Results"):
            st.session_state.edit_results = True
            st.session_state.current_experiment_id = experiment['id']
    else:
        st.info("No results recorded for this experiment.")
        
        # Add an option to add results
        if st.button("Add Results"):
            st.session_state.edit_results = True
            st.session_state.current_experiment_id = experiment['id']
    
    # Results Edit Form
    if st.session_state.get('edit_results', False) and st.session_state.get('current_experiment_id') == experiment['id']:
        with st.form("results_form"):
            st.markdown("#### Edit Results")
            
            # Pre-populate with existing data if available
            if result:
                final_ph = st.number_input(
                    "Final pH",
                    min_value=0.0,
                    max_value=14.0,
                    value=float(result.final_ph) if result.final_ph else 7.0,
                    step=0.1,
                    format="%.1f"
                )
                
                final_nitrate = st.number_input(
                    "Final Nitrate Concentration (mM)",
                    min_value=0.0,
                    value=float(result.final_nitrate_concentration) if result.final_nitrate_concentration else 0.0,
                    step=0.1,
                    format="%.1f"
                )
                
                yield_value = st.number_input(
                    "Yield Value (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(result.yield_value) if result.yield_value else 0.0,
                    step=0.1,
                    format="%.1f"
                )
            else:
                final_ph = st.number_input(
                    "Final pH",
                    min_value=0.0,
                    max_value=14.0,
                    value=7.0,
                    step=0.1,
                    format="%.1f"
                )
                
                final_nitrate = st.number_input(
                    "Final Nitrate Concentration (mM)",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    format="%.1f"
                )
                
                yield_value = st.number_input(
                    "Yield Value (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.1,
                    format="%.1f"
                )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save Results"):
                    save_results(experiment['id'], final_ph, final_nitrate, yield_value)
                    st.session_state.edit_results = False
                    st.session_state.experiment_updated = True
            
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.edit_results = False
    
    # Experimental Data Section
    st.markdown("### Experimental Data")
    
    # Initialize session state for experimental data if not exists
    if 'experimental_data_state' not in st.session_state:
        st.session_state.experimental_data_state = {
            'adding_data': False,
            'data_type': None,
            'current_file': None,
            'description': '',
            'data_values': {}
        }
    
    # Display existing experimental data
    if 'experimental_data' in experiment and experiment['experimental_data']:
        for data in experiment['experimental_data']:
            with st.expander(f"{data['data_type']} Data - {data['created_at'].strftime('%Y-%m-%d %H:%M')}"):
                if data['data_type'] in ['NMR', 'GC']:
                    if data['file_path']:
                        st.download_button(
                            f"Download {data['file_name']}",
                            open(data['file_path'], 'rb').read(),
                            file_name=data['file_name'],
                            mime=data['file_type']
                        )
                elif data['data_type'] == 'AMMONIA_YIELD':
                    if data['data_values']:
                        st.write("Yield Values:")
                        st.json(data['data_values'])
                
                if data['description']:
                    st.write("Description:")
                    st.write(data['description'])
                
                # Delete button
                if st.button("Delete Data", key=f"delete_data_{data['id']}"):
                    delete_experimental_data(data['id'])
    else:
        st.info("No experimental data recorded for this experiment.")
    
    # Add Experimental Data Button
    if st.button("Add Experimental Data"):
        st.session_state.experimental_data_state['adding_data'] = True
    
    # Experimental Data Form
    if st.session_state.experimental_data_state['adding_data']:
        with st.form("experimental_data_form"):
            data_type = st.selectbox(
                "Data Type",
                options=['NMR', 'GC', 'AMMONIA_YIELD'],
                key="data_type_select"
            )
            
            if data_type in ['NMR', 'GC']:
                uploaded_file = st.file_uploader(
                    f"Upload {data_type} File",
                    type=['txt', 'csv', 'pdf', 'jpg', 'png'],
                    key=f"file_upload_{data_type}"
                )
            elif data_type == 'AMMONIA_YIELD':
                yield_value = st.number_input(
                    "Ammonia Yield Value",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.1,
                    format="%.2f"
                )
                yield_unit = st.selectbox(
                    "Yield Unit",
                    options=['%', 'mg/L', 'mmol/L']
                )
            
            description = st.text_area(
                "Description",
                help="Add a description of the experimental data"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save Data"):
                    if data_type in ['NMR', 'GC'] and uploaded_file:
                        save_experimental_data(
                            experiment['id'],
                            data_type,
                            uploaded_file,
                            description
                        )
                    elif data_type == 'AMMONIA_YIELD':
                        save_experimental_data(
                            experiment['id'],
                            data_type,
                            None,
                            description,
                            {'value': yield_value, 'unit': yield_unit}
                        )
                    st.session_state.experimental_data_state['adding_data'] = False
            
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.experimental_data_state['adding_data'] = False
    
    # Sample Information Section
    st.markdown("### Sample Information")
    sample_info = get_sample_info(experiment['sample_id'])
    
    if sample_info:
        # Display existing sample info
        sample_info_df = pd.DataFrame([{
            "Rock Classification": sample_info['rock_classification'],
            "Location": f"{sample_info['state']}, {sample_info['country']}",
            "Coordinates": f"{sample_info['latitude']}, {sample_info['longitude']}",
            "Description": sample_info['description']
        }]).T.rename(columns={0: "Value"})
        st.table(sample_info_df)
        
        # External Analyses
        st.markdown("#### External Analyses")
        external_analyses = get_external_analyses(experiment['sample_id'])
        
        if external_analyses:
            for analysis in external_analyses:
                with st.expander(f"{analysis['analysis_type']} Analysis - {analysis['analysis_date'].strftime('%Y-%m-%d')}"):
                    st.write(f"Laboratory: {analysis['laboratory']}")
                    st.write(f"Analyst: {analysis['analyst']}")
                    if analysis['description']:
                        st.write("Description:")
                        st.write(analysis['description'])
                    
                    if analysis['report_file_path']:
                        st.download_button(
                            f"Download {analysis['report_file_name']}",
                            open(analysis['report_file_path'], 'rb').read(),
                            file_name=analysis['report_file_name'],
                            mime=analysis['report_file_type']
                        )
                    
                    if analysis['analysis_metadata']:
                        st.write("Additional Data:")
                        st.json(analysis['analysis_metadata'])
                    
                    # Delete button
                    if st.button("Delete Analysis", key=f"delete_analysis_{analysis['id']}"):
                        delete_external_analysis(analysis['id'])
        else:
            st.info("No external analyses recorded for this sample.")
    else:
        st.info("No sample information recorded.")
    
    # Add External Analysis Button
    if st.button("Add External Analysis"):
        st.session_state.adding_external_analysis = True
        st.session_state.current_sample_id = experiment['sample_id']
    
    # External Analysis Form
    if st.session_state.get('adding_external_analysis', False) and st.session_state.get('current_sample_id') == experiment['sample_id']:
        with st.form("external_analysis_form"):
            analysis_type = st.selectbox(
                "Analysis Type",
                options=['XRD', 'SEM', 'Elemental', 'Other']
            )
            
            col1, col2 = st.columns(2)
            with col1:
                laboratory = st.text_input("Laboratory")
                analyst = st.text_input("Analyst")
                analysis_date = st.date_input("Analysis Date")
            
            with col2:
                report_file = st.file_uploader(
                    "Upload Report",
                    type=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'jpg', 'png']
                )
            
            description = st.text_area(
                "Description",
                help="Add a description of the analysis"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save Analysis"):
                    if report_file:
                        save_external_analysis(
                            experiment['sample_id'],
                            analysis_type,
                            report_file,
                            laboratory,
                            analyst,
                            analysis_date,
                            description
                        )
                        st.session_state.adding_external_analysis = False
            
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.adding_external_analysis = False
    
    # Notes Section
    st.markdown("### Lab Notes")
    
    # Initialize session state for notes if not exists
    if 'note_form_state' not in st.session_state:
        st.session_state.note_form_state = {
            'adding_note': False,
            'editing_note_id': None,
            'note_to_delete': None
        }
    
    # Add Note Button
    if st.button("Add Note"):
        st.session_state.note_form_state['adding_note'] = True
    
    # Note Form
    if st.session_state.note_form_state['adding_note']:
        with st.form("note_form"):
            note_text = st.text_area(
                "Note Text",
                height=200,
                help="Enter your lab note here."
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save Note"):
                    if note_text:
                        save_note(experiment['id'], note_text)
                        st.session_state.note_form_state['adding_note'] = False
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.note_form_state['adding_note'] = False
    
    # Display existing notes
    if 'notes' in experiment and experiment['notes']:
        for note in experiment['notes']:
            with st.expander(f"Note from {note['created_at'].strftime('%Y-%m-%d %H:%M')}"):
                if st.session_state.note_form_state['editing_note_id'] == note['id']:
                    # Edit mode
                    with st.form(f"edit_note_{note['id']}"):
                        edited_text = st.text_area(
                            "Edit Note",
                            value=note['note_text'],
                            height=200,
                            help="Edit your lab note here."
                        )
                        col1, col2 = st.columns(2)
                        with col1:
                            st.form_submit_button(
                                "Save Changes",
                                on_click=submit_note_edit,
                                args=(note['id'], edited_text)
                            )
                        with col2:
                            if st.form_submit_button("Cancel"):
                                st.session_state.note_form_state['editing_note_id'] = None
                else:
                    # View mode
                    st.markdown(note['note_text'])
                    if note.get('updated_at') and note['updated_at'] != note['created_at']:
                        st.caption(f"Last updated: {note['updated_at'].strftime('%Y-%m-%d %H:%M')}")
                    
                    # Edit and Delete buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Edit", key=f"edit_{note['id']}"):
                            st.session_state.note_form_state['editing_note_id'] = note['id']
                    with col2:
                        if st.button("Delete", key=f"delete_{note['id']}"):
                            st.session_state.note_form_state['note_to_delete'] = note['id']
    else:
        st.info("No lab notes recorded for this experiment.")

def get_sample_info(sample_id):
    """Get sample information from the database."""
    try:
        db = SessionLocal()
        sample_info = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        
        if sample_info:
            return {
                'id': sample_info.id,
                'sample_id': sample_info.sample_id,
                'rock_classification': sample_info.rock_classification,
                'state': sample_info.state,
                'country': sample_info.country,
                'latitude': sample_info.latitude,
                'longitude': sample_info.longitude,
                'description': sample_info.description,
                'created_at': sample_info.created_at,
                'updated_at': sample_info.updated_at
            }
        return None
    except Exception as e:
        st.error(f"Error retrieving sample information: {str(e)}")
        return None
    finally:
        db.close()

def get_external_analyses(sample_id):
    """Get external analyses for a sample from the database."""
    try:
        db = SessionLocal()
        analyses = db.query(ExternalAnalysis).filter(ExternalAnalysis.sample_id == sample_id).all()
        
        return [{
            'id': analysis.id,
            'analysis_type': analysis.analysis_type,
            'report_file_path': analysis.report_file_path,
            'report_file_name': analysis.report_file_name,
            'report_file_type': analysis.report_file_type,
            'analysis_date': analysis.analysis_date,
            'laboratory': analysis.laboratory,
            'analyst': analysis.analyst,
            'description': analysis.description,
            'analysis_metadata': analysis.analysis_metadata,
            'created_at': analysis.created_at,
            'updated_at': analysis.updated_at
        } for analysis in analyses]
    except Exception as e:
        st.error(f"Error retrieving external analyses: {str(e)}")
        return []
    finally:
        db.close()

def save_sample_info(sample_id, rock_classification, state, country, latitude, longitude, description):
    """Save or update sample information in the database."""
    try:
        db = SessionLocal()
        
        # Check if sample info exists
        sample_info = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        
        if sample_info:
            # Update existing sample info
            sample_info.rock_classification = rock_classification
            sample_info.state = state
            sample_info.country = country
            sample_info.latitude = latitude
            sample_info.longitude = longitude
            sample_info.description = description
        else:
            # Create new sample info
            sample_info = SampleInfo(
                sample_id=sample_id,
                rock_classification=rock_classification,
                state=state,
                country=country,
                latitude=latitude,
                longitude=longitude,
                description=description
            )
            db.add(sample_info)
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=None,  # This is sample-level modification
            modified_by=st.session_state.get('user', 'Unknown User'),
            modification_type="update" if sample_info.id else "create",
            modified_table="sample_info",
            new_values={
                'sample_id': sample_id,
                'rock_classification': rock_classification,
                'state': state,
                'country': country,
                'latitude': latitude,
                'longitude': longitude,
                'description': description
            }
        )
        db.add(modification)
        
        # Commit the transaction
        db.commit()
        
        st.success("Sample information saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving sample information: {str(e)}")
        raise e
    finally:
        db.close()

def save_external_analysis(sample_id, analysis_type, file, laboratory, analyst, analysis_date, description):
    """Save external analysis data to the database."""
    try:
        db = SessionLocal()
        
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'external_analyses')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file and store path
        file_path = os.path.join(upload_dir, file.name)
        with open(file_path, 'wb') as f:
            f.write(file.getvalue())
        
        # Create new external analysis entry
        analysis = ExternalAnalysis(
            sample_id=sample_id,
            analysis_type=analysis_type,
            report_file_path=file_path,
            report_file_name=file.name,
            report_file_type=file.type,
            analysis_date=datetime.datetime.combine(analysis_date, datetime.datetime.now().time()),
            laboratory=laboratory,
            analyst=analyst,
            description=description
        )
        
        # Add the analysis to the session
        db.add(analysis)
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=None,  # This is sample-level modification
            modified_by=user_identifier,  # Use email as identifier
            modification_type="add",
            modified_table="external_analyses",
            new_values={
                'sample_id': sample_id,
                'analysis_type': analysis_type,
                'laboratory': laboratory,
                'analyst': analyst,
                'analysis_date': analysis_date.isoformat(),
                'description': description
            }
        )
        db.add(modification)
        
        # Commit the transaction
        db.commit()
        
        st.success("External analysis saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving external analysis: {str(e)}")
        raise e
    finally:
        db.close()

def delete_external_analysis(analysis_id):
    """Delete external analysis from the database."""
    try:
        db = SessionLocal()
        
        # Get the analysis
        analysis = db.query(ExternalAnalysis).filter(ExternalAnalysis.id == analysis_id).first()
        
        if analysis is None:
            st.error("Analysis not found")
            return
        
        # Delete file if it exists
        if analysis.report_file_path and os.path.exists(analysis.report_file_path):
            os.remove(analysis.report_file_path)
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=None,  # This is sample-level modification
            modified_by=user_identifier,  # Use email as identifier
            modification_type="delete",
            modified_table="external_analyses",
            old_values={
                'sample_id': analysis.sample_id,
                'analysis_type': analysis.analysis_type,
                'laboratory': analysis.laboratory,
                'analyst': analysis.analyst,
                'analysis_date': analysis.analysis_date.isoformat() if analysis.analysis_date else None,
                'description': analysis.description
            }
        )
        db.add(modification)
        
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

def save_experimental_data(experiment_id, data_type, file=None, description=None, data_values=None):
    """Save experimental data to the database."""
    try:
        db = SessionLocal()
        
        # Create a new experimental data entry
        experimental_data = ExperimentalData(
            experiment_id=experiment_id,
            data_type=data_type,
            description=description,
            data_values=data_values
        )
        
        # Handle file upload if present
        if file:
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file and store path
            file_path = os.path.join(upload_dir, file.name)
            with open(file_path, 'wb') as f:
                f.write(file.getvalue())
            
            experimental_data.file_path = file_path
            experimental_data.file_name = file.name
            experimental_data.file_type = file.type
        
        # Add the data to the session
        db.add(experimental_data)
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=experiment_id,
            modified_by=user_identifier,  # Use email as identifier
            modification_type="add",
            modified_table="experimental_data",
            new_values={
                'data_type': data_type,
                'description': description,
                'data_values': data_values
            }
        )
        db.add(modification)
        
        # Commit the transaction
        db.commit()
        
        st.success("Experimental data saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving experimental data: {str(e)}")
        raise e
    finally:
        db.close()

def delete_experimental_data(data_id):
    """Delete experimental data from the database."""
    try:
        db = SessionLocal()
        
        # Get the data
        data = db.query(ExperimentalData).filter(ExperimentalData.id == data_id).first()
        
        if data is None:
            st.error("Data not found")
            return
        
        # Delete file if it exists
        if data.file_path and os.path.exists(data.file_path):
            os.remove(data.file_path)
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=data.experiment_id,
            modified_by=st.session_state.get('user', 'Unknown User'),
            modification_type="delete",
            modified_table="experimental_data",
            old_values={
                'data_type': data.data_type,
                'description': data.description,
                'data_values': data.data_values
            }
        )
        db.add(modification)
        
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

def submit_note(experiment_id, note_text):
    """Handle note submission."""
    if not note_text.strip():
        st.error("Note text cannot be empty")
        return
    
    save_note(experiment_id, note_text)
    st.session_state.note_form_state['adding_note'] = False
    st.session_state.note_form_state['current_note'] = ""

def submit_note_edit(note_id, edited_text):
    """Handle note edit submission."""
    if not edited_text.strip():
        st.error("Note text cannot be empty")
        return
    
    update_note(note_id, edited_text)
    st.session_state.note_form_state['editing_note_id'] = None

def submit_experiment():
    """Handle experiment form submission."""
    # Validate inputs
    if not st.session_state.experiment_data['experiment_id']:
        st.error("Experiment ID is required")
        return
    elif not st.session_state.experiment_data['sample_id']:
        st.error("Sample ID is required")
        return
    elif not st.session_state.experiment_data['researcher']:
        st.error("Researcher name is required")
        return
    
    # Ensure notes array exists
    if 'notes' not in st.session_state.experiment_data:
        st.session_state.experiment_data['notes'] = []
    
    st.session_state.step = 2

def submit_experiment_edit(experiment_id, data):
    """Handle experiment edit form submission."""
    success = update_experiment(experiment_id, data)
    if success:
        st.session_state.edit_mode = False

def edit_experiment(experiment):
    """Edit an existing experiment."""
    with st.form(key="edit_experiment_form"):
        st.markdown("### Basic Information")
        col1, col2 = st.columns(2)
        
        with col1:
            sample_id = st.text_input("Rock Sample ID", value=experiment['sample_id'])
            researcher = st.text_input("Researcher Name", value=experiment['researcher'])
        
        with col2:
            status = st.selectbox(
                "Experiment Status",
                options=['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED'],
                index=['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED'].index(experiment['status'])
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
                options=['Serum', 'Autoclave', 'HPHT', 'Core Flood'],
                index=['Serum', 'Autoclave', 'HPHT', 'Core Flood'].index(conditions.get('experiment_type', 'Serum')) if conditions.get('experiment_type') in ['Serum', 'Autoclave', 'HPHT', 'Core Flood'] else 0
            )
            
            particle_size = st.text_input(
                "Particle Size (μm)",
                value=conditions.get('particle_size', '')
            )
            
            water_to_rock_ratio = st.number_input(
                "Water to Rock Ratio (Optional)",
                min_value=0.0,
                value=float(conditions.get('water_to_rock_ratio', 0.0) or 0.0),
                step=0.1,
                format="%.2f",
                help="Enter the water to rock ratio (optional)"
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
            
            flow_rate = st.number_input(
                "Flow Rate (mL/min) (Optional)",
                min_value=0.0,
                value=float(conditions.get('flow_rate', 0.0) or 0.0),
                step=0.1,
                format="%.1f",
                help="Enter the flow rate in mL/min (optional)"
            )
            
            buffer_system = st.text_input(
                "Buffer System (Optional)",
                value=conditions.get('buffer_system', ''),
                help="Enter the buffer system used (optional)"
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
                'water_to_rock_ratio': water_to_rock_ratio if water_to_rock_ratio > 0 else None,
                'initial_ph': initial_ph,
                'catalyst': catalyst,
                'catalyst_mass': catalyst_mass,
                'catalyst_percentage': catalyst_percentage,
                'temperature': temperature,
                'buffer_system': buffer_system if buffer_system.strip() else None,
                'buffer_concentration': buffer_concentration,
                'pressure': pressure,
                'flow_rate': flow_rate if flow_rate > 0 else None,
                'experiment_type': experiment_type,
                'initial_nitrate_concentration': initial_nitrate_concentration,
                'dissolved_oxygen': dissolved_oxygen,
                'surfactant_type': surfactant_type,
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

def update_experiment(experiment_id, data):
    """Update an experiment in the database."""
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
            conditions.buffer_system = data['conditions']['buffer_system']
            conditions.buffer_concentration = data['conditions']['buffer_concentration']
            conditions.pressure = data['conditions']['pressure']
            conditions.flow_rate = data['conditions']['flow_rate']
            conditions.experiment_type = data['conditions']['experiment_type']
            conditions.initial_nitrate_concentration = data['conditions']['initial_nitrate_concentration']
            conditions.dissolved_oxygen = data['conditions']['dissolved_oxygen']
            conditions.surfactant_type = data['conditions']['surfactant_type']
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
                buffer_system=data['conditions']['buffer_system'] if data['conditions']['buffer_system'].strip() else None,
                buffer_concentration=data['conditions']['buffer_concentration'],
                pressure=data['conditions']['pressure'],
                flow_rate=data['conditions']['flow_rate'],
                experiment_type=data['conditions']['experiment_type'],
                initial_nitrate_concentration=data['conditions']['initial_nitrate_concentration'],
                dissolved_oxygen=data['conditions']['dissolved_oxygen'],
                surfactant_type=data['conditions']['surfactant_type'],
                surfactant_concentration=data['conditions']['surfactant_concentration'],
                co2_partial_pressure=data['conditions']['co2_partial_pressure'],
                confining_pressure=data['conditions']['confining_pressure'],
                pore_pressure=data['conditions']['pore_pressure']
            )
            if hasattr(conditions, 'particle_size'):
                conditions.particle_size = data['conditions']['particle_size']
            db.add(conditions)
        
        # Create a modification log entry
        new_values = {
            'sample_id': data['sample_id'],
            'researcher': data['researcher'],
            'status': data['status'],
            'date': data['date'].isoformat() if data['date'] else None,
            'conditions': data['conditions']
        }
        
        modification = ModificationsLog(
            experiment_id=experiment.id,
            modified_by=data['researcher'],  # Using the researcher as the modifier
            modification_type="update",
            modified_table="experiments",
            old_values=old_values,
            new_values=new_values
        )
        db.add(modification)
        
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
    """Save a new note to the database."""
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

def update_note(note_id, note_text):
    """Update an existing note in the database."""
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

def delete_note(note_id):
    """Delete a note from the database."""
    try:
        db = SessionLocal()
        
        # Get the note
        note = db.query(ExperimentNotes).filter(ExperimentNotes.id == note_id).first()
        
        if note is None:
            st.error("Note not found")
            return
        
        # Delete the note
        db.delete(note)
        
        # Commit the transaction
        db.commit()
        
        st.success("Note deleted successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error deleting note: {str(e)}")
        raise e
    finally:
        db.close()

def render_settings():
    st.header("Settings")
    # Add settings components here 

# Add new function for the rock sample form
def render_new_rock_sample():
    st.header("New Rock Sample")
    
    with st.form("new_rock_sample_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            sample_id = st.text_input(
                "Sample ID",
                help="Enter a unique identifier for this rock sample (e.g., 20UM21)"
            )
            rock_classification = st.text_input(
                "Rock Classification",
                help="Enter the rock type/classification"
            )
            state = st.text_input("State/Province")
            country = st.text_input("Country")
        
        with col2:
            latitude = st.number_input(
                "Latitude",
                min_value=-90.0,
                max_value=90.0,
                step=0.000001,
                format="%.6f"
            )
            longitude = st.number_input(
                "Longitude",
                min_value=-180.0,
                max_value=180.0,
                step=0.000001,
                format="%.6f"
            )
        
        description = st.text_area(
            "Sample Description",
            height=100,
            help="Add any relevant details about the rock sample"
        )
        
        # Add photo upload section
        st.markdown("### Sample Photo")
        photo = st.file_uploader(
            "Upload Sample Photo",
            type=['jpg', 'jpeg', 'png'],
            help="Upload a photo of the rock sample"
        )
        
        if st.form_submit_button("Save Rock Sample"):
            save_rock_sample(
                sample_id=sample_id,
                rock_classification=rock_classification,
                state=state,
                country=country,
                latitude=latitude,
                longitude=longitude,
                description=description,
                photo=photo
            )

def save_rock_sample(sample_id, rock_classification, state, country, latitude, longitude, description, photo=None):
    """Save a new rock sample to the database."""
    if not sample_id or not rock_classification:
        st.error("Sample ID and Rock Classification are required")
        return
    
    try:
        db = SessionLocal()
        
        # Check if sample ID already exists
        existing_sample = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        if existing_sample:
            st.error(f"Sample ID {sample_id} already exists")
            return
        
        # Handle photo upload if provided
        photo_path = None
        if photo:
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'sample_photos')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save photo and store path
            photo_path = os.path.join(upload_dir, f"{sample_id}_{photo.name}")
            with open(photo_path, 'wb') as f:
                f.write(photo.getvalue())
        
        # Create new sample
        sample = SampleInfo(
            sample_id=sample_id,
            rock_classification=rock_classification,
            state=state,
            country=country,
            latitude=latitude,
            longitude=longitude,
            description=description,
            photo_path=photo_path  # This will be None if no photo was uploaded
        )
        
        db.add(sample)
        db.commit()
        
        st.success(f"Rock sample {sample_id} saved successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error saving rock sample: {str(e)}")
    finally:
        db.close()

def render_sample_inventory():
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
    """Display detailed information about a specific sample."""
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
            if st.button("Add/Update Photo"):
                st.session_state.adding_photo = True
                st.session_state.current_sample_id = sample_id
            
            # Photo Upload Form
            if st.session_state.get('adding_photo', False) and st.session_state.get('current_sample_id') == sample_id:
                with st.form("photo_upload_form"):
                    photo = st.file_uploader(
                        "Upload Sample Photo",
                        type=['jpg', 'jpeg', 'png'],
                        help="Upload a photo of the rock sample"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Save Photo"):
                            if photo:
                                update_sample_photo(sample_id, photo)
                                st.session_state.adding_photo = False
                                st.rerun()
                    
                    with col2:
                        if st.form_submit_button("Cancel"):
                            st.session_state.adding_photo = False
            
            # Add External Analysis Button
            if st.button("Add External Analysis"):
                st.session_state.adding_analysis = True
                st.session_state.current_sample_id = sample_id
            
            # External Analysis Form
            if st.session_state.get('adding_analysis', False) and st.session_state.get('current_sample_id') == sample_id:
                with st.form("external_analysis_form"):
                    analysis_type = st.selectbox(
                        "Analysis Type",
                        options=['XRD', 'SEM', 'Elemental', 'Other']
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        laboratory = st.text_input("Laboratory")
                        analyst = st.text_input("Analyst")
                        analysis_date = st.date_input("Analysis Date")
                    
                    with col2:
                        report_file = st.file_uploader(
                            "Upload Report",
                            type=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'jpg', 'png']
                        )
                    
                    description = st.text_area(
                        "Description",
                        help="Add a description of the analysis"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Save Analysis"):
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
                        if st.form_submit_button("Cancel"):
                            st.session_state.adding_analysis = False
        
    except Exception as e:
        st.error(f"Error displaying sample details: {str(e)}")
    finally:
        db.close()

def update_sample_photo(sample_id, photo):
    """Update the photo for a sample."""
    try:
        db = SessionLocal()
        sample = db.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()
        
        if sample is None:
            st.error(f"Sample with ID {sample_id} not found.")
            return
        
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'sample_photos')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Delete old photo if it exists
        if sample.photo_path and os.path.exists(sample.photo_path):
            os.remove(sample.photo_path)
        
        # Save new photo
        photo_path = os.path.join(upload_dir, f"{sample_id}_{photo.name}")
        with open(photo_path, 'wb') as f:
            f.write(photo.getvalue())
        
        # Update sample with new photo path
        sample.photo_path = photo_path
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=None,  # This is sample-level modification
            modified_by=st.session_state.get('user', 'Unknown User'),
            modification_type="update",
            modified_table="sample_info",
            new_values={
                'sample_id': sample_id,
                'photo_path': photo_path
            }
        )
        db.add(modification)
        
        # Commit the changes
        db.commit()
        
        st.success("Sample photo updated successfully!")
        
    except Exception as e:
        db.rollback()
        st.error(f"Error updating sample photo: {str(e)}")
    finally:
        db.close()

def get_all_samples():
    """Get all rock samples from the database."""
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

def save_results(experiment_id, final_ph, final_nitrate, yield_value):
    """Save experiment results to the database."""
    try:
        db = SessionLocal()
        
        # Check if results exist for this experiment
        result = db.query(Results).filter(Results.experiment_id == experiment_id).first()
        
        if result:
            # Update existing results
            result.final_ph = final_ph
            result.final_nitrate_concentration = final_nitrate
            result.yield_value = yield_value
            
            # Create a modification log entry
            modification = ModificationsLog(
                experiment_id=experiment_id,
                modified_by=st.session_state.get('user', 'Unknown User'),
                modification_type="update",
                modified_table="results",
                old_values={
                    'final_ph': result.final_ph,
                    'final_nitrate_concentration': result.final_nitrate_concentration,
                    'yield_value': result.yield_value
                },
                new_values={
                    'final_ph': final_ph,
                    'final_nitrate_concentration': final_nitrate,
                    'yield_value': yield_value
                }
            )
            db.add(modification)
        else:
            # Create new results
            new_result = Results(
                experiment_id=experiment_id,
                final_ph=final_ph,
                final_nitrate_concentration=final_nitrate,
                yield_value=yield_value
            )
            db.add(new_result)
            
            # Create a modification log entry
            modification = ModificationsLog(
                experiment_id=experiment_id,
                modified_by=st.session_state.get('user', 'Unknown User'),
                modification_type="create",
                modified_table="results",
                new_values={
                    'final_ph': final_ph,
                    'final_nitrate_concentration': final_nitrate,
                    'yield_value': yield_value
                }
            )
            db.add(modification)
        
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