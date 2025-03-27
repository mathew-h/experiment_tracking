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

from frontend.config.variable_config import (
    REQUIRED_DEFAULTS,
    OPTIONAL_FIELDS,
    VALUE_LABELS,
    EXPERIMENT_TYPES,
    EXPERIMENT_STATUSES
)


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
            
            # Create a custom table layout with headers
            # First row: Headers
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

def extract_conditions(conditions_obj):
    """
    Extract experimental conditions from an ORM object,
    using REQUIRED_DEFAULTS and OPTIONAL_FIELDS to provide default values.
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
        results = experiment.results  # Changed from experimental_results to results
        
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
            'experimental_results': []  # Keep this key for compatibility with existing code
        }
        
        # Add conditions if they exist with default values for missing fields
        if conditions:
            # Initialize with default values
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
        required_conditions, optional_conditions = split_conditions_for_display(experiment['conditions'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Required Parameters")
            req_df = pd.DataFrame([required_conditions]).T.rename(columns={0: "Value"})
            req_df['Value'] = req_df['Value'].astype(str)  # Ensure all values are strings
            st.table(req_df)
        
        with col2:
            st.markdown("#### Secondary Parameters")
            opt_df = pd.DataFrame([optional_conditions]).T.rename(columns={0: "Value"})
            opt_df['Value'] = opt_df['Value'].astype(str)  # Ensure all values are strings
            st.table(opt_df)
    else:
        st.info("No experimental conditions recorded for this experiment.")
    
    # Results Section
    st.markdown("### Results")
    
    # Try to get results data
    db = SessionLocal()
    result = db.query(ExperimentalResults).filter(ExperimentalResults.experiment_id == experiment['id']).first()
    db.close()
    
    if result:
        results_data = {
            "Final pH": str(result.final_ph) if result.final_ph else "Not recorded",
            "Final Nitrate Concentration (mM)": str(result.final_nitrate_concentration) if result.final_nitrate_concentration else "Not recorded",
            "Yield Value (%)": str(result.yield_value) if result.yield_value else "Not recorded"
        }
        
        results_df = pd.DataFrame([results_data]).T.rename(columns={0: "Value"})
        results_df['Value'] = results_df['Value'].astype(str)  # Ensure all values are strings
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
    if 'experimental_results_state' not in st.session_state:
        st.session_state.experimental_results_state = {}
    
    # Initialize state for this specific experiment if not exists
    if experiment['id'] not in st.session_state.experimental_results_state:
        st.session_state.experimental_results_state[experiment['id']] = {
            'adding_data': False,
            'data_type': None,
            'current_file': None,
            'description': '',
            'data_values': {}
        }
    
    # Display existing experimental data
    if 'experimental_results' in experiment and experiment['experimental_results']:
        for data in experiment['experimental_results']:
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
                    delete_experimental_results(data['id'])
                    st.rerun()
    else:
        st.info("No experimental data recorded for this experiment.")
    
    # Add Experimental Data Button
    if st.button("Add Experimental Data", key=f"add_exp_data_{experiment['id']}"):
        st.session_state.experimental_results_state[experiment['id']]['adding_data'] = True
        st.rerun()  # Force a rerun to show the form
    
    # Experimental Data Form
    if st.session_state.experimental_results_state[experiment['id']]['adding_data']:
        with st.form(f"experimental_results_form_{experiment['id']}", clear_on_submit=True):
            data_type = st.selectbox(
                "Data Type",
                options=['NMR', 'GC', 'AMMONIA_YIELD'],
                key=f"data_type_select_{experiment['id']}"
            )
            
            if data_type in ['NMR', 'GC']:
                uploaded_file = st.file_uploader(
                    f"Upload {data_type} File",
                    type=['txt', 'csv', 'pdf', 'jpg', 'png'],
                    key=f"file_upload_{data_type}_{experiment['id']}"
                )
            elif data_type == 'AMMONIA_YIELD':
                yield_value = st.number_input(
                    "Ammonia Yield Value",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.1,
                    format="%.2f",
                    key=f"yield_value_{experiment['id']}"
                )
                yield_unit = st.selectbox(
                    "Yield Unit",
                    options=['%', 'mg/L', 'mmol/L'],
                    key=f"yield_unit_{experiment['id']}"
                )
            
            description = st.text_area(
                "Description",
                help="Add a description of the experimental data",
                key=f"exp_data_desc_{experiment['id']}"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save Data"):
                    if data_type in ['NMR', 'GC'] and uploaded_file:
                        save_experimental_results(
                            experiment['id'],
                            data_type,
                            uploaded_file,
                            description
                        )
                        st.session_state.experimental_results_state[experiment['id']]['adding_data'] = False
                        st.rerun()
                    elif data_type == 'AMMONIA_YIELD':
                        save_experimental_results(
                            experiment['id'],
                            data_type,
                            None,
                            description,
                            {'value': yield_value, 'unit': yield_unit}
                        )
                        st.session_state.experimental_results_state[experiment['id']]['adding_data'] = False
                        st.rerun()
            
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.experimental_results_state[experiment['id']]['adding_data'] = False
                    st.rerun()
    
    # Sample Information Section
    st.markdown("### Sample Information")
    sample_info = get_sample_info(experiment['sample_id'])
    
    if sample_info:
        # Display existing sample info
        sample_info_df = pd.DataFrame([{
            "Rock Classification": str(sample_info['rock_classification']),
            "Location": f"{str(sample_info['state'])}, {str(sample_info['country'])}",
            "Coordinates": f"{str(sample_info['latitude'])}, {str(sample_info['longitude'])}",
            "Description": str(sample_info['description'])
        }]).T.rename(columns={0: "Value"})
        sample_info_df['Value'] = sample_info_df['Value'].astype(str)  # Ensure all values are strings
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
    """Handle experiment edit form submission."""
    success = update_experiment(experiment_id, data)
    if success:
        st.session_state.edit_mode = False

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
            
def save_results(experiment_id, final_ph, final_nitrate, yield_value):
    """Save experiment results to the database."""
    try:
        db = SessionLocal()
        
        # Check if results exist for this experiment
        result = db.query(ExperimentalResults).filter(ExperimentalResults.experiment_id == experiment_id).first()
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        if result:
            # Update existing results
            result.final_ph = final_ph
            result.final_nitrate_concentration = final_nitrate
            result.yield_value = yield_value
            
            # Create a modification log entry
            modification = ModificationsLog(
                experiment_id=experiment_id,
                modified_by=user_identifier,
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
            new_result = ExperimentalResults(
                experiment_id=experiment_id,
                final_ph=final_ph,
                final_nitrate_concentration=final_nitrate,
                yield_value=yield_value
            )
            db.add(new_result)
            
            # Create a modification log entry
            modification = ModificationsLog(
                experiment_id=experiment_id,
                modified_by=user_identifier,
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

def delete_experimental_results(data_id):
    """Delete experimental data from the database."""
    try:
        db = SessionLocal()
        
        # Get the data
        data = db.query(ExperimentalResults).filter(ExperimentalResults.id == data_id).first()
        
        if data is None:
            st.error("Data not found")
            return
        
        # Delete file if it exists
        if data.file_path and os.path.exists(data.file_path):
            try:
                os.remove(data.file_path)
            except OSError as e:
                st.warning(f"Could not delete file: {e}")
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=data.experiment_id,
            modified_by=user_identifier,
            modification_type="delete",
            modified_table="experimental_results",
            old_values=json.dumps({  # Convert dict to JSON string
                'data_type': data.data_type,
                'description': data.description,
                'data_values': data.data_values
            })
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

def save_experimental_results(experiment_id, data_type, file=None, description=None, data_values=None):
    """Save experimental data to the database."""
    try:
        db = SessionLocal()
        
        # Create a new experimental data entry
        experimental_results = ExperimentalResults(
            experiment_id=experiment_id,
            data_type=data_type,
            description=description,
            data_values=json.dumps(data_values) if data_values else None  # Convert dict to JSON string
        )
        
        # Handle file upload if present
        if file:
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads', 'experimental_results')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Save file and store path
            file_path = os.path.join(upload_dir, f"{experiment_id}_{file.name}")
            with open(file_path, 'wb') as f:
                f.write(file.getvalue())
            
            experimental_results.file_path = file_path
            experimental_results.file_name = file.name
            experimental_results.file_type = file.type
        
        # Add the data to the session
        db.add(experimental_results)
        
        # Get user information for the modification log
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Create a modification log entry
        modification = ModificationsLog(
            experiment_id=experiment_id,
            modified_by=user_identifier,
            modification_type="add",
            modified_table="experimental_results",
            new_values=json.dumps({  # Convert dict to JSON string
                'data_type': data_type,
                'description': description,
                'data_values': data_values
            })
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

def submit_note_edit(note_id, edited_text):
    """Handle note edit submission."""
    if not edited_text.strip():
        st.error("Note text cannot be empty")
        return
    
    update_note(note_id, edited_text)
    st.session_state.note_form_state['editing_note_id'] = None

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