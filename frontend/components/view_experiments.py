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
from frontend.components.utils import (
    generate_form_fields,
    extract_conditions,
    split_conditions_for_display
)

from frontend.config.variable_config import (
    FIELD_CONFIG,
    EXPERIMENT_TYPES,
    EXPERIMENT_STATUSES
)

from sqlalchemy.orm import selectinload

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
        
        # Get numeric fields from FIELD_CONFIG for filtering
        numeric_fields = [
            (field_name, config) 
            for field_name, config in FIELD_CONFIG.items() 
            if config['type'] == 'number'
        ]
        
        # Get text fields from FIELD_CONFIG for filtering
        text_fields = [
            (field_name, config) 
            for field_name, config in FIELD_CONFIG.items() 
            if config['type'] == 'text'
        ]
        
        # Create filters for text fields
        for field_name, config in text_fields:
            if field_name == 'catalyst':  # Special case for catalyst filter
                catalyst_filter = st.text_input(f"Filter by {config['label']}:", "")
            elif field_name == 'buffer_system':  # Special case for buffer system filter
                buffer_filter = st.text_input(f"Filter by {config['label']}:", "")
        
        # Create filters for numeric fields with ranges
        for field_name, config in numeric_fields:
            if field_name == 'temperature':  # Special case for temperature filter
                temp_col1, temp_col2 = st.columns(2)
                with temp_col1:
                    min_temp = st.number_input(
                        f"Min {config['label']}", 
                        value=None, 
                        min_value=config.get('min_value', -273.15)
                    )
                with temp_col2:
                    max_temp = st.number_input(
                        f"Max {config['label']}", 
                        value=None, 
                        min_value=config.get('min_value', -273.15)
                    )
            elif field_name == 'initial_ph':  # Special case for pH filter
                ph_col1, ph_col2 = st.columns(2)
                with ph_col1:
                    min_ph = st.number_input(
                        f"Min {config['label']}", 
                        value=None, 
                        min_value=config.get('min_value', 0.0),
                        max_value=config.get('max_value', 14.0)
                    )
                with ph_col2:
                    max_ph = st.number_input(
                        f"Max {config['label']}", 
                        value=None, 
                        min_value=config.get('min_value', 0.0),
                        max_value=config.get('max_value', 14.0)
                    )
    
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
        
        if buffer_filter:
            detailed_experiments = [exp for exp in detailed_experiments if 
                                  exp['conditions'].get('buffer_system', '').lower() == buffer_filter.lower()]
        
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
    # Initial fetch to check if experiment exists and handle navigation/edit buttons first
    initial_experiment_check = get_experiment_by_id(st.session_state.view_experiment_id)

    if initial_experiment_check is None:
        st.error(f"Experiment with ID {st.session_state.view_experiment_id} not found.")
        if st.button("Back to Experiment List"):
            st.session_state.view_experiment_id = None
            st.session_state.edit_mode = False
            st.rerun() # Rerun to go back to the list
    else:
        # Navigation buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← Back to List"):
                st.session_state.view_experiment_id = None
                st.session_state.edit_mode = False
                st.rerun() # Rerun to go back to the list

        with col3:
            if not st.session_state.edit_mode:
                if st.button("Edit Experiment"):
                    st.session_state.edit_mode = True
                    st.rerun() # Rerun to switch to edit mode
            else:
                if st.button("Cancel Edit"):
                    st.session_state.edit_mode = False
                    st.rerun() # Rerun to switch back to view mode

        # --- Refetch the experiment data HERE ---
        # This ensures we have the latest data before displaying/editing,
        # especially after a rerun triggered by saving sub-components like notes or data.
        experiment = get_experiment_by_id(st.session_state.view_experiment_id)

        # Check again in case something went wrong between the initial check and now
        if experiment is None:
             st.error(f"Could not reload experiment with ID {st.session_state.view_experiment_id}.")
             # Optionally add a back button here too
             return # Stop rendering if reload failed

        # Display experiment info header
        st.subheader(f"Experiment: {experiment['experiment_id']}")

        # Now display either the details or the edit form with the freshly fetched data
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
            experiment = db.query(Experiment).options(selectinload(Experiment.results), selectinload(Experiment.notes), selectinload(Experiment.modifications), selectinload(Experiment.conditions)).filter(Experiment.experiment_id == experiment_id).first()
        else:
            experiment = db.query(Experiment).options(selectinload(Experiment.results), selectinload(Experiment.notes), selectinload(Experiment.modifications), selectinload(Experiment.conditions)).filter(Experiment.id == experiment_id).first()
        
        if experiment is None:
            return None
        
        # Access related data (already loaded due to selectinload)
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
            exp_dict['experimental_results'] = [] # Ensure it starts empty
            for data in results:
                exp_dict['experimental_results'].append(
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
                )
        else:
            pass # Add pass to fix empty block linting error
            
        return exp_dict
    except Exception as e:
        st.error(f"Error retrieving experiment: {str(e)}")
        return None
    finally:
        db.close()



