import streamlit as st
import pandas as pd
from datetime import datetime
from database.database import SessionLocal
from database.models import (
    ExperimentalResults,
    SampleInfo,
    ExternalAnalysis,
    ExperimentNotes,
    Experiment,
    ExperimentStatus,
    ExperimentalConditions
)
from frontend.config.variable_config import (
    REQUIRED_DEFAULTS,
    OPTIONAL_FIELDS,
    VALUE_LABELS,
    EXPERIMENT_TYPES,
    EXPERIMENT_STATUSES
)
from frontend.components.utils import split_conditions_for_display
from frontend.components.load_info import get_sample_info, get_external_analyses
from frontend.components.edit_experiment import (
    save_results,
    delete_experimental_results,
    save_experimental_results,
    delete_external_analysis,
    save_note,
    submit_note_edit
)

def display_experiment_details(experiment):
    """
    Displays the complete details of an experiment.
    
    This function renders all sections of the experiment details page:
    1. Basic Information
    2. Experimental Conditions
    3. Results
    4. Experimental Data
    5. Sample Information
    6. Lab Notes
    
    Args:
        experiment (dict): Dictionary containing all experiment data
    """
    # Basic Info Section
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
    df['Value'] = df['Value'].astype(str)
    st.table(df)
    
    # Conditions Section
    st.markdown("### Experimental Conditions")
    if experiment['conditions']:
        # Split conditions into required and optional fields
        required_conditions, optional_conditions = split_conditions_for_display(experiment['conditions'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Required Parameters")
            req_df = pd.DataFrame([required_conditions]).T.rename(columns={0: "Value"})
            req_df['Value'] = req_df['Value'].astype(str)
            st.table(req_df)
        
        with col2:
            st.markdown("#### Secondary Parameters")
            opt_df = pd.DataFrame([optional_conditions]).T.rename(columns={0: "Value"})
            opt_df['Value'] = opt_df['Value'].astype(str)
            st.table(opt_df)
    else:
        st.info("No experimental conditions recorded for this experiment.")
    
    # Results Section
    st.markdown("### Results")
    
    # Get results data from database
    db = SessionLocal()
    result = db.query(ExperimentalResults).filter(ExperimentalResults.experiment_id == experiment['id']).first()
    db.close()
    
    if result:
        # Display existing results
        results_data = {
            "Final pH": str(result.final_ph) if result.final_ph else "Not recorded",
            "Final Nitrate Concentration (mM)": str(result.final_nitrate_concentration) if result.final_nitrate_concentration else "Not recorded",
            "Yield Value (%)": str(result.yield_value) if result.yield_value else "Not recorded"
        }
        
        results_df = pd.DataFrame([results_data]).T.rename(columns={0: "Value"})
        results_df['Value'] = results_df['Value'].astype(str)
        st.table(results_df)
        
        # Add edit results button
        if st.button("Edit Results"):
            st.session_state.edit_results = True
            st.session_state.current_experiment_id = experiment['id']
    else:
        st.info("No results recorded for this experiment.")
        
        # Add results button
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
                # Default values for new results
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
    
    # Initialize session state for experimental data
    if 'experimental_results_state' not in st.session_state:
        st.session_state.experimental_results_state = {}
    
    # Initialize state for this specific experiment
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
        st.rerun()
    
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
        sample_info_df['Value'] = sample_info_df['Value'].astype(str)
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
    
    # Initialize session state for notes
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