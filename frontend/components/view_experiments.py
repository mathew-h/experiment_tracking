import streamlit as st
import pandas as pd
import os
import json
import datetime
from database.database import SessionLocal
from database.models import (
    Experiment, 
    ExperimentStatus, 
    ExperimentalResults, 
    ExperimentNotes, 
    ExperimentalConditions, 
    ModificationsLog,
    SampleInfo,
    ExternalAnalysis
)

from frontend.components.experiment_details import display_experiment_details
from frontend.components.edit_experiment import edit_experiment
from frontend.components.utils import split_conditions_for_display

from frontend.config.variable_config import (
    REQUIRED_DEFAULTS,
    OPTIONAL_FIELDS,
    VALUE_LABELS,
    EXPERIMENT_TYPES,
    EXPERIMENT_STATUSES
)

def render_view_experiments():
    """
    Main function to render the experiments view page.
    
    This function handles:
    1. Setting up the page layout and styling
    2. Managing experiment list view and detail view
    3. Handling experiment filtering and search
    4. Managing experiment editing state
    """
    # Add custom CSS for better layout
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

    # Handle experiment update state
    if st.session_state.get('experiment_updated', False):
        st.session_state.experiment_updated = False
        st.rerun()

    st.header("View Experiments")
    
    # Initialize session state for experiment viewing
    if 'view_experiment_id' not in st.session_state:
        st.session_state.view_experiment_id = None
    
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False
    
    # Quick access section for direct experiment lookup
    st.markdown("### Quick Access")
    exp_id = st.text_input("Enter Experiment ID to view details directly:")
    if st.button("View Experiment") and exp_id:
        st.session_state.view_experiment_id = exp_id
        st.rerun()

    # Main view logic
    if st.session_state.view_experiment_id is None:
        # Show experiment list view
        render_experiment_list()
    else:
        # Show experiment detail view
        render_experiment_detail()

def render_experiment_list():
    """
    Renders the list view of all experiments with filtering options.
    
    This function:
    1. Fetches all experiments from the database
    2. Provides filtering options (search, status, date range, conditions)
    3. Displays experiments in a formatted table
    4. Handles navigation to experiment details
    """
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
        
        # Create a custom table layout with headers
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 2, 1])
        
        with col1:
            st.markdown("**Experiment ID**")
        with col2:
            st.markdown("**Sample ID**")
        with col3:
            st.markdown("**Researcher**")
        with col4:
            st.markdown("**Date**")
        with col5:
            st.markdown("**Status**")
        with col6:
            st.markdown("**Actions**")
        
        # Add a separator line
        st.markdown("<hr style='margin: 2px 0px; background-color: #f0f0f0; height: 1px; border: none;'>", unsafe_allow_html=True)
        
        # Data rows
        for index, row in exp_df.iterrows():
            with st.container():
                col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 2, 1])
                
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
                
                st.markdown("<hr style='margin: 2px 0px; background-color: #f0f0f0; height: 1px; border: none;'>", unsafe_allow_html=True)

def render_experiment_detail():
    """
    Renders the detail view for a specific experiment.
    
    This function:
    1. Fetches the experiment details
    2. Handles navigation back to list view
    3. Manages edit mode state
    4. Displays experiment details or edit form
    """
    experiment = get_experiment_by_id(st.session_state.view_experiment_id)
    
    if experiment is None:
        st.error(f"Experiment with ID {st.session_state.view_experiment_id} not found.")
        if st.button("Back to Experiment List"):
            st.session_state.view_experiment_id = None
            st.session_state.edit_mode = False
    else:
        # Navigation buttons
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
            # View mode - display experiment details
            display_experiment_details(experiment)
        else:
            # Edit mode - show editable form
            edit_experiment(experiment)

def get_all_experiments():
    """
    Retrieves all experiments from the database.
    
    Returns:
        list: List of dictionaries containing basic experiment information
    """
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

def extract_conditions(conditions_obj):
    """
    Extracts experimental conditions from an ORM object.
    
    This function uses REQUIRED_DEFAULTS and OPTIONAL_FIELDS to provide default values
    for any missing conditions.
    
    Args:
        conditions_obj: SQLAlchemy ORM object containing experimental conditions
        
    Returns:
        dict: Dictionary of conditions with default values for missing fields
    """
    # Merge required and optional defaults
    condition_defaults = {**REQUIRED_DEFAULTS, **OPTIONAL_FIELDS}
    extracted = {}
    for field, default in condition_defaults.items():
        # Try to get the attribute from the conditions object;
        # if it's None or missing, use the default
        value = getattr(conditions_obj, field, None)
        extracted[field] = value if value is not None else default
    return extracted

def get_experiment_by_id(experiment_id):
    """
    Retrieves a specific experiment by ID with all related data.
    
    This function fetches an experiment and all its related data (conditions, notes,
    modifications, results) and formats them for display.
    
    Args:
        experiment_id: Either a string (experiment_id) or integer (database id)
        
    Returns:
        dict: Dictionary containing all experiment data and related information
    """
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
        results = experiment.results
        
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
            'experimental_results': []
        }
        
        # Add conditions if they exist with default values for missing fields
        if conditions:
            exp_dict['conditions'] = extract_conditions(conditions)
        
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
        if results:
            exp_dict['experimental_results'] = [
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
                for data in results
            ]
        
        return exp_dict
    except Exception as e:
        st.error(f"Error retrieving experiment: {str(e)}")
        return None
    finally:
        db.close()

def get_condition_display_dict(conditions):
    """
    Build a display dictionary for experimental conditions.
    
    It leverages REQUIRED_DEFAULTS and OPTIONAL_FIELDS to determine:
      - Which fields to display,
      - The expected type of the field (numeric if the default is a float, string otherwise),
      - And a friendly label with units.
    """
    display_dict = {}
    # Combine both required and optional defaults
    combined_defaults = {**REQUIRED_DEFAULTS, **OPTIONAL_FIELDS}
    
    for field, default in combined_defaults.items():
        # Get the friendly label; if not defined, fallback to the field name itself.
        label = VALUE_LABELS.get(field, field)
        value = conditions.get(field)
        
        # If value is None or an empty string, display as "N/A"
        if value is None or (isinstance(value, str) and not value.strip()):
            display_value = "N/A"
        else:
            # If the default is a float and the value is numeric, format as a number
            if isinstance(default, float) and isinstance(value, (int, float)):
                display_value = f"{float(value):.2f}"
            else:
                display_value = str(value)
        
        display_dict[label] = display_value
    return display_dict

def split_conditions_for_display(conditions):
    """
    Splits conditions into required and optional fields for display purposes.
    
    It uses get_condition_display_dict to build the full display dict, and then
    separates the required fields (based on REQUIRED_DEFAULTS keys) from the rest.
    """
    display_dict = get_condition_display_dict(conditions)
    
    # Build a set of display labels for required fields using REQUIRED_DEFAULTS keys.
    required_labels = {VALUE_LABELS.get(field, field) for field in REQUIRED_DEFAULTS.keys()}
    
    required_fields = {label: value for label, value in display_dict.items() if label in required_labels}
    optional_fields = {label: value for label, value in display_dict.items() if label not in required_labels}
    
    return required_fields, optional_fields



