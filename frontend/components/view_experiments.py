import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, date, time
import re  # Add re module for regex support
from database.database import SessionLocal
from database.models import (
    Experiment, 
    ExperimentStatus, 
    ExperimentalResults, 
    ExperimentNotes, 
    ExperimentalConditions, 
    ModificationsLog,
    SampleInfo,
    ExternalAnalysis,
    ResultType
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
    EXPERIMENT_STATUSES,
    SCALAR_RESULTS_CONFIG,
    NMR_RESULTS_CONFIG
)

from sqlalchemy.orm import selectinload
from sqlalchemy import or_, func

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

    st.markdown("### View Experiments")
    
    # Initialize session state for experiment viewing
    if 'view_experiment_id' not in st.session_state:
        st.session_state.view_experiment_id = None
    
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = False
    
    # Quick access section for direct experiment lookup
    st.markdown("#### Quick Access")
    quick_col1, quick_col2, quick_col3 = st.columns([0.9, 3, 1])
    with quick_col1:
        st.markdown("<div style='margin-top: 7px;'>Search by Experiment ID:</div>", unsafe_allow_html=True)
    with quick_col2:
        exp_id = st.text_input("Experiment ID Search", key="quick_search", label_visibility="collapsed")
    with quick_col3:

        if st.button("View Experiment", key="quick_view", use_container_width=True) and exp_id:
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
    1. Fetches all experiments from the database with pagination
    2. Provides filtering options (search, status, date range)
    3. Displays experiments in a formatted table
    4. Handles navigation to experiment details
    """
    # Initialize pagination state
    if 'experiments_page' not in st.session_state:
        st.session_state.experiments_page = 1
    if 'experiments_per_page' not in st.session_state:
        st.session_state.experiments_per_page = 10

    # Create filter/search options
    st.markdown("#### Search and Filter Experiments")
    
    # Create columns for filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Search filter
        search_term = st.text_input(
            "Search: Sample ID, Experiment ID or Researcher:", 
            "",
            key="search_term",
            on_change=lambda: setattr(st.session_state, 'experiments_page', 1)
        )
        use_regex = st.checkbox("Use regex pattern matching", value=True)
    with col2:
        # Status filter
        status_filter = st.selectbox(
            "Filter by Status:",
            ["All"] + [status.name for status in ExperimentStatus],
            key="status_filter",
            on_change=lambda: setattr(st.session_state, 'experiments_page', 1)
        )
    
    with col3:
        # Date range filter
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input(
                "Start Date Range", 
                value=None,
                key="start_date",
                on_change=lambda: setattr(st.session_state, 'experiments_page', 1)
            )
        with date_col2:
            end_date = st.date_input(
                "End Date Range", 
                value=None,
                key="end_date",
                on_change=lambda: setattr(st.session_state, 'experiments_page', 1)
            )
    
    # Get experiments with search and filters applied at database level
    experiments, total_count = get_all_experiments(
        page=st.session_state.experiments_page,
        per_page=st.session_state.experiments_per_page,
        search_term=search_term if use_regex or not search_term else re.escape(search_term),
        status_filter=status_filter if status_filter != "All" else None,
        start_date=start_date,
        end_date=end_date
    )
    
    # Calculate total pages based on filtered count
    total_pages = (total_count + st.session_state.experiments_per_page - 1) // st.session_state.experiments_per_page
    
    if not experiments:
        st.info("No experiments found matching the selected criteria.")
        # Reset pagination if no results found
        if st.session_state.experiments_page > 1:
            st.session_state.experiments_page = 1
            st.rerun()
    else:
        # Display experiments in a table
        st.markdown("#### Experiments")
        
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
        for index, exp in enumerate(experiments):
            with st.container():
                col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 2, 1])
                
                with col1:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{exp['experiment_id']}</div>", unsafe_allow_html=True)
                with col2:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{exp['sample_id']}</div>", unsafe_allow_html=True)
                with col3:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{exp['researcher']}</div>", unsafe_allow_html=True)
                with col4:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{exp['date'].strftime('%Y-%m-%d %H:%M')}</div>", unsafe_allow_html=True)
                with col5:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{exp['status']}</div>", unsafe_allow_html=True)
                with col6:
                    if st.button("View Details", key=f"view_{index}"):
                        st.session_state.view_experiment_id = exp['experiment_id']
                        st.rerun()
                
                st.markdown("<hr style='margin: 2px 0px; background-color: #f0f0f0; height: 1px; border: none;'>", unsafe_allow_html=True)
        
        # Pagination controls
        st.markdown("---")
        pagination_cols = st.columns([1, 2, 1])
        
        with pagination_cols[0]:
            if st.session_state.experiments_page > 1:
                if st.button("← Previous"):
                    st.session_state.experiments_page -= 1
                    st.rerun()
                    
        with pagination_cols[1]:
            st.markdown(f"<div style='text-align: center'>Page {st.session_state.experiments_page} of {total_pages}</div>", unsafe_allow_html=True)
            
        with pagination_cols[2]:
            if st.session_state.experiments_page < total_pages:
                if st.button("Next →"):
                    st.session_state.experiments_page += 1
                    st.rerun()
                    
        # Items per page selector
        st.selectbox(
            "Items per page",
            options=[10, 25, 50],
            key="experiments_per_page",
            on_change=lambda: setattr(st.session_state, 'experiments_page', 1)
        )

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
        # Back to List button - Place it consistently at the top left
        if st.button("← Back to List"):
            st.session_state.view_experiment_id = None
            st.session_state.edit_mode = False
            st.rerun() # Rerun to go back to the list
        
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
            
            # Place Edit button *after* details in view mode
            if st.button("Edit Experiment"):
                st.session_state.edit_mode = True
                st.rerun() # Rerun to switch to edit mode
        else:
            # Edit mode - show editable form
            edit_experiment(experiment)
            
            # Place Cancel button *after* edit form in edit mode
            if st.button("Cancel Edit"):
                st.session_state.edit_mode = False
                st.rerun() # Rerun to switch back to view mode

def get_total_experiments_count(db=None):
    """
    Get total count of experiments for pagination.
    """
    try:
        if db is None:
            db = SessionLocal()
        return db.query(Experiment).count()
    except Exception as e:
        st.error(f"Error getting experiment count: {str(e)}")
        return 0
    finally:
        if db:
            db.close()

def get_all_experiments(page=1, per_page=10, search_term=None, status_filter=None, start_date=None, end_date=None):
    """
    Retrieves experiments from the database with pagination and filtering.
    
    Args:
        page (int): Current page number (1-based)
        per_page (int): Number of items per page
        search_term (str): Optional search term for filtering
        status_filter (str): Optional status filter
        start_date (date): Optional start date for date range filter
        end_date (date): Optional end date for date range filter
        
    Returns:
        list: List of dictionaries containing basic experiment information
    """
    try:
        db = SessionLocal()
        query = db.query(Experiment)

        # Apply search filter at database level if provided
        if search_term:
            try:
                pattern = re.compile(search_term, re.IGNORECASE)
                # For regex pattern, we need to use custom SQL for regex matching
                # SQLite doesn't support regex directly, so we'll use LIKE with wildcards
                search_pattern = f"%{search_term}%"
                query = query.filter(
                    or_(
                        Experiment.sample_id.like(search_pattern),
                        Experiment.researcher.like(search_pattern),
                        Experiment.experiment_id.like(search_pattern)
                    )
                )
            except re.error:
                # If invalid regex, fall back to simple LIKE search
                search_term_lower = f"%{search_term.lower()}%"
                query = query.filter(
                    or_(
                        func.lower(Experiment.sample_id).like(search_term_lower),
                        func.lower(Experiment.researcher).like(search_term_lower),
                        func.lower(Experiment.experiment_id).like(search_term_lower)
                    )
                )

        # Apply status filter if provided
        if status_filter:
            query = query.filter(Experiment.status == status_filter)

        # Apply date range filter if provided
        if start_date:
            query = query.filter(Experiment.date >= datetime.combine(start_date, time.min))
        if end_date:
            query = query.filter(Experiment.date <= datetime.combine(end_date, time.max))

        # Get total count for pagination after applying filters
        total_count = query.count()
        
        # Apply ordering and pagination
        offset = (page - 1) * per_page
        experiments_query = query.order_by(Experiment.date.desc()).offset(offset).limit(per_page).all()
        
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
        
        return experiments, total_count
    except Exception as e:
        st.error(f"Error retrieving experiments: {str(e)}")
        return [], 0
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
            experiment = db.query(Experiment).options(
                selectinload(Experiment.conditions),
                selectinload(Experiment.notes),
                selectinload(Experiment.modifications),
                selectinload(Experiment.results).selectinload(ExperimentalResults.scalar_data), # Eager load scalar data
                selectinload(Experiment.results).selectinload(ExperimentalResults.nmr_data),    # Eager load NMR data
                selectinload(Experiment.results).selectinload(ExperimentalResults.files)       # Eager load files
            ).filter(Experiment.experiment_id == experiment_id).first()
        else:
            experiment = db.query(Experiment).options(
                selectinload(Experiment.conditions),
                selectinload(Experiment.notes),
                selectinload(Experiment.modifications),
                selectinload(Experiment.results).selectinload(ExperimentalResults.scalar_data), # Eager load scalar data
                selectinload(Experiment.results).selectinload(ExperimentalResults.nmr_data),    # Eager load NMR data
                selectinload(Experiment.results).selectinload(ExperimentalResults.files)       # Eager load files
            ).filter(Experiment.id == experiment_id).first()
        
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
            exp_dict['experimental_results'] = [] # Initialize list
            for data in results: # data is an ExperimentalResults object
                result_item = {
                    'id': data.id,
                    'time_post_reaction': data.time_post_reaction,
                    'result_type': data.result_type.name if data.result_type else None,
                    'description': data.description,
                    'created_at': data.created_at,
                    'updated_at': data.updated_at,
                    'scalar_data': None, # Placeholder for scalar data
                    'nmr_data': None,    # Placeholder for NMR data
                    # Add placeholders for other data types (GC, PXRF, etc.) as needed
                    'files': []          # List to hold associated files
                }

                # Extract scalar data if present (independent of primary result type)
                if data.scalar_data:
                    scalar_dict = {}
                    for field_name in SCALAR_RESULTS_CONFIG.keys():
                        if hasattr(data.scalar_data, field_name):
                            scalar_dict[field_name] = getattr(data.scalar_data, field_name)
                    result_item['scalar_data'] = scalar_dict

                # Extract primary result type data
                if data.result_type == ResultType.NMR and data.nmr_data:
                    nmr_dict = {}
                    for field_name in NMR_RESULTS_CONFIG.keys():
                        if hasattr(data.nmr_data, field_name):
                            nmr_dict[field_name] = getattr(data.nmr_data, field_name)
                    result_item['nmr_data'] = nmr_dict
                # Add elif blocks for other primary result types (GC, PXRF, etc.) as they are implemented

                # Extract files if they exist
                if data.files:
                    for file_obj in data.files:
                        result_item['files'].append({
                            'id': file_obj.id,
                            'file_path': file_obj.file_path,
                            'file_name': file_obj.file_name,
                            'file_type': file_obj.file_type,
                            'description': file_obj.description,
                            'created_at': file_obj.created_at
                        })

                exp_dict['experimental_results'].append(result_item)
        else:
            pass # No results to process
            
        return exp_dict
    except Exception as e:
        st.error(f"Error retrieving experiment: {str(e)}")
        return None
    finally:
        db.close()



