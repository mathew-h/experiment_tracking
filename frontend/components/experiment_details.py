import streamlit as st
import pandas as pd
import datetime
import os
import json
from sqlalchemy import orm
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
    FIELD_CONFIG,
    EXPERIMENT_TYPES,
    EXPERIMENT_STATUSES,
    RESULTS_CONFIG
)
from frontend.components.utils import (
    split_conditions_for_display,
    get_condition_display_dict,
    generate_form_fields
)
from frontend.components.load_info import get_sample_info, get_external_analyses
from frontend.components.edit_experiment import (
    save_results,
    delete_experimental_results,
    delete_result_file,
    save_note,
    submit_note_edit
)
from frontend.components.edit_sample import delete_external_analysis

# --- Helper function for formatting display values --- 
# Moved here to be defined before use
def format_value(value, config):
    if value is None:
        return "N/A"
    if config['type'] == 'number' and config.get('format') and isinstance(value, (int, float)):
        try:
           return config['format'] % float(value)
        except (ValueError, TypeError):
           return str(value)
    else:
        return str(value)

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
        "Date Updated": experiment['updated_at'].strftime("%Y-%m-%d %H:%M") if isinstance(experiment['updated_at'], datetime.datetime) else "N/A"
    }
    
    # Convert to DataFrame and ensure all values are strings
    df = pd.DataFrame([basic_info]).T.rename(columns={0: "Value"})
    df['Value'] = df['Value'].astype(str)
    st.table(df)
    
    # Conditions Section
    st.markdown("### Experimental Conditions")
    if experiment['conditions']:
        # Split conditions into required and optional fields using FIELD_CONFIG
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
    
    # --- Consolidated Results Section ---
    st.markdown("### Results")

    db = SessionLocal()
    try:
        # Fetch all scalar results, preloading associated files
        results_records = db.query(ExperimentalResults).options(
            orm.selectinload(ExperimentalResults.files) # Eager load files
        ).filter(
            ExperimentalResults.experiment_id == experiment['id'],
            ExperimentalResults.data_type == 'SCALAR_RESULTS'
        ).order_by(ExperimentalResults.time_post_reaction).all()
    finally:
        db.close()

    # Initialize session state for the results form
    if 'show_results_form' not in st.session_state:
        st.session_state.show_results_form = False
    if 'editing_result_id' not in st.session_state:
        st.session_state.editing_result_id = None # Store the ID of the result being edited
    if 'current_experiment_id_results' not in st.session_state:
         st.session_state.current_experiment_id_results = None


    # Determine if we are showing the form for THIS experiment
    showing_form_for_this_experiment = (
        st.session_state.show_results_form and
        st.session_state.current_experiment_id_results == experiment['id']
    )

    # --- Display Existing Results ---
    if results_records:
        st.write("Recorded Results:")
        for result in results_records:
            expander_title = f"Results at {result.time_post_reaction:.1f} hours"
            with st.expander(expander_title):
                # Display Scalar Data Table
                results_data = {}
                for field_name, config in RESULTS_CONFIG.items():
                    if field_name == 'time_post_reaction': continue
                    value = getattr(result, field_name, None)
                    label = config['label']
                    results_data[label] = format_value(value, config)
                results_df = pd.DataFrame([results_data]).T.rename(columns={0: "Value"})
                results_df['Value'] = results_df['Value'].astype(str)
                st.table(results_df)
                
                # Display Associated Files
                if result.files:
                    st.markdown("**Associated Files:**")
                    for file_record in result.files:
                        file_col1, file_col2, file_col3 = st.columns([3, 4, 1])
                        with file_col1:
                            st.write(f"- {file_record.file_name}")
                            if file_record.description:
                                st.caption(f"  Description: {file_record.description}")
                        with file_col2:
                            # Check if file exists before creating download button
                            if os.path.exists(file_record.file_path):
                                try:
                                    with open(file_record.file_path, 'rb') as fp:
                                        st.download_button(
                                            label="Download",
                                            data=fp.read(),
                                            file_name=file_record.file_name,
                                            mime=file_record.file_type,
                                            key=f"download_file_{file_record.id}"
                                        )
                                except Exception as e:
                                    st.warning(f"Could not read file {file_record.file_name}: {e}")
                            else:
                                st.warning(f"File not found: {file_record.file_name}")
                        with file_col3:
                             # Add a delete button for the individual file
                             if st.button("❌", key=f"delete_file_{file_record.id}", help="Delete this file"):
                                 # Call the actual delete function
                                 delete_success = delete_result_file(file_record.id)
                                 if delete_success:
                                     st.session_state.experiment_updated = True
                                     st.rerun()
                                 # Error message handled by delete_result_file
                else:
                    st.caption("No files associated with this time point.")
                
                st.markdown("---") # Separator

                # Edit/Delete buttons for the entire time point entry
                col1, col2, col3 = st.columns([1, 1, 5]) 
                with col1:
                    if st.button("Edit Scalars/Add Files", key=f"edit_result_{result.id}"):
                        st.session_state.show_results_form = True
                        st.session_state.editing_result_id = result.id 
                        st.session_state.current_experiment_id_results = experiment['id']
                        st.rerun()
                with col2:
                    if st.button("Delete Time Point", key=f"delete_result_{result.id}"):
                        try:
                            delete_experimental_results(result.id)
                            st.session_state.experiment_updated = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting result time point: {e}")


    else:
         if not showing_form_for_this_experiment:
             st.info("No results recorded for this experiment yet.")

    # --- Add Results Button ---
    # Show button only if not currently showing the form for this experiment
    if not showing_form_for_this_experiment:
        if st.button("Add Results", key=f"add_results_btn_{experiment['id']}"):
            st.session_state.show_results_form = True
            st.session_state.editing_result_id = None # Ensure we are adding, not editing
            st.session_state.current_experiment_id_results = experiment['id']
            st.rerun()

    # --- Add/Edit Results Form ---
    if showing_form_for_this_experiment:
        form_title = "Add New Results"
        current_data = {}
        editing_time = None
        # Generate base key parts
        base_key_part = f"results_{experiment['id']}_{st.session_state.editing_result_id or 'new'}"
        # Use distinct keys 
        form_key = f"{base_key_part}_form"
        buffer_key = f"{base_key_part}_buffer" 
        file_uploader_key = f"{base_key_part}_uploader"

        # --- Initialize Session State for file buffer ---
        if buffer_key not in st.session_state:
            st.session_state[buffer_key] = {'uploaded_files': [], 'descriptions': {}}
        file_buffer = st.session_state[buffer_key]

        if st.session_state.editing_result_id:
            # Fetch the specific result being edited to pre-populate form
            db = SessionLocal()
            try:
                result_to_edit = db.query(ExperimentalResults).filter(
                    ExperimentalResults.id == st.session_state.editing_result_id
                ).first()
                if result_to_edit:
                    form_title = f"Edit Results at {result_to_edit.time_post_reaction:.1f} hours"
                    editing_time = result_to_edit.time_post_reaction
                    for field_name in RESULTS_CONFIG.keys():
                        current_data[field_name] = getattr(result_to_edit, field_name, RESULTS_CONFIG[field_name]['default'])
                else:
                    st.error("Could not find the result entry to edit.")
                    st.session_state.show_results_form = False
                    st.session_state.editing_result_id = None
                    st.session_state.current_experiment_id_results = None
                    st.rerun()
            finally:
                db.close()
        else:
            # If adding, use defaults for scalars
            for field_name, config in RESULTS_CONFIG.items():
                current_data[field_name] = config['default']
            # The buffer persistence logic is handled by session state itself
            # No explicit pass needed here

        st.markdown(f"#### {form_title}")
        
        # --- File Upload Section (Outside Form) ---
        st.markdown("**Upload New Files**")
        uploaded_files_widget = st.file_uploader(
            "Select files to associate with this time point",
            accept_multiple_files=True,
            key=file_uploader_key, # Use the dedicated uploader key
            help="Upload data files, images, etc. related to these results."
        )

        # --- Update Session State based on File Uploader --- 
        # (Logic remains the same, uses file_buffer alias pointing to buffer_key)
        # ... (sync logic) ...
        current_widget_files = uploaded_files_widget if uploaded_files_widget else []
        current_widget_file_names = {f.name for f in current_widget_files}
        buffer_file_names = {f.name for f in file_buffer['uploaded_files']}
        for file in current_widget_files:
             if file.name not in buffer_file_names:
                 file_buffer['uploaded_files'].append(file)
                 if file.name not in file_buffer['descriptions']:
                     file_buffer['descriptions'][file.name] = ""
        new_buffer_files = []
        for file in file_buffer['uploaded_files']:
             if file.name in current_widget_file_names:
                 new_buffer_files.append(file)
             else:
                 if file.name in file_buffer['descriptions']:
                     del file_buffer['descriptions'][file.name]
        file_buffer['uploaded_files'] = new_buffer_files


        # --- Display Description Inputs (Outside Form) ---
        if file_buffer['uploaded_files']:
            st.write("Add optional descriptions for uploaded files:")
            for i, uploaded_file in enumerate(file_buffer['uploaded_files']):
                # Use buffer_key in description key
                desc_key = f"file_desc_{i}_{uploaded_file.name}_{buffer_key}" 
                file_buffer['descriptions'][uploaded_file.name] = st.text_input(
                    f"Description for {uploaded_file.name}",
                    value=file_buffer['descriptions'].get(uploaded_file.name, ""),
                    key=desc_key
                )

        # --- Form for Scalar Values and Submit --- 
        # Use the dedicated form_key
        with st.form(form_key):
            # --- Display Scalar Fields (Inside Form) --- 
            form_values = {}
            field_keys_config = {}
            for field_name, config in RESULTS_CONFIG.items():
                # Use form_key in scalar keys
                field_key = f"results_{field_name}_{form_key}_scalar"
                field_keys_config[field_name] = field_key
                field_label = config['label']
                field_type = config['type']
                field_help = config.get('help', None)
                current_value = current_data.get(field_name)
                if field_name == 'time_post_reaction' and st.session_state.editing_result_id is not None:
                     st.text_input(label=f"{field_label} (Cannot be changed)", value=f"{current_value:.1f}" if current_value is not None else "N/A", key=field_key, disabled=True, help=config.get('help', '') + " Time cannot be changed during edit.")
                     form_values[field_name] = current_value 
                elif field_type == 'number':
                    form_values[field_name] = st.number_input(label=field_label, min_value=config.get('min_value'), max_value=config.get('max_value'), value=float(current_value) if current_value is not None else config.get('default'), step=config.get('step'), format=config.get('format', "%.2f"), key=field_key, help=field_help)
                else:
                     st.warning(f"Unsupported field type '{field_type}' for '{field_name}' in results form.")

            # --- Save/Cancel Buttons (Inside Form) --- 
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Save Results")
                if submitted:
                    # Get form values
                    time_val = form_values.get('time_post_reaction')
                    ph_val = form_values.get('final_ph')
                    nitrate_val = form_values.get('final_nitrate_concentration')
                    ferrous_iron_yield_val = form_values.get('ferrous_iron_yield')
                    grams_per_ton_yield_val = form_values.get('grams_per_ton_yield')
                    final_dissolved_oxygen_val = form_values.get('final_dissolved_oxygen')
                    final_conductivity_val = form_values.get('final_conductivity')
                    final_alkalinity_val = form_values.get('final_alkalinity')
                    sampling_volume_val = form_values.get('sampling_volume')

                    # File data comes from the buffer (accessed via file_buffer alias -> buffer_key)
                    files_to_save = []
                    if file_buffer['uploaded_files']:
                        for uploaded_file in file_buffer['uploaded_files']:
                            files_to_save.append({
                                'file': uploaded_file,
                                'description': file_buffer['descriptions'].get(uploaded_file.name, '') 
                            })

                    # Validation logic
                    if time_val is None and st.session_state.editing_result_id is None:
                         st.error("Time Post-Reaction is required.")
                    else:
                        # Save logic
                        if st.session_state.editing_result_id is not None:
                            pass 
                        save_success = save_results(
                            experiment_id=experiment['id'],
                            time_post_reaction=time_val,
                            final_ph=ph_val,
                            final_nitrate=nitrate_val,
                            ferrous_iron_yield=ferrous_iron_yield_val,
                            grams_per_ton_yield=grams_per_ton_yield_val,
                            final_dissolved_oxygen=final_dissolved_oxygen_val,
                            final_conductivity=final_conductivity_val,
                            final_alkalinity=final_alkalinity_val,
                            sampling_volume=sampling_volume_val,
                            uploaded_files_data=files_to_save
                        )
                        if save_success:
                            # Clear the buffer using buffer_key
                            if buffer_key in st.session_state:
                                del st.session_state[buffer_key]
                            # (Reset general form display state)
                            # ...
                            st.session_state.show_results_form = False
                            st.session_state.editing_result_id = None
                            st.session_state.current_experiment_id_results = None
                            st.session_state.experiment_updated = True
                            st.rerun()
            with col2:
                # --- Cancel Button (Inside Form) --- 
                if st.form_submit_button("Cancel"):
                     # Clear the buffer using buffer_key
                    if buffer_key in st.session_state:
                        del st.session_state[buffer_key]
                    # (Reset general form display state)
                    # ...
                    st.session_state.show_results_form = False
                    st.session_state.editing_result_id = None
                    st.session_state.current_experiment_id_results = None
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
                        # Check if file exists before creating download button
                        if os.path.exists(analysis['report_file_path']):
                            try:
                                with open(analysis['report_file_path'], 'rb') as fp:
                                    st.download_button(
                                        f"Download {analysis['report_file_name']}",
                                        fp.read(),
                                        file_name=analysis['report_file_name'],
                                        mime=analysis['report_file_type']
                                    )
                            except Exception as e:
                                st.warning(f"Could not read analysis report file {analysis['report_file_name']}: {e}")
                        else:
                            st.warning(f"Analysis report file not found: {analysis['report_file_name']}")
                    
                    if analysis['analysis_metadata']:
                        st.write("Additional Data:")
                        st.json(analysis['analysis_metadata'])
                    
                    # Delete button
                    if st.button("Delete Analysis", key=f"delete_analysis_{analysis['id']}"):
                        delete_external_analysis(analysis['id'])
                        st.session_state.experiment_updated = True # Flag sample update
                        st.rerun()
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
    if st.button("Add Note", key=f"add_note_{experiment['id']}"):
        st.session_state.note_form_state['adding_note'] = True
        st.session_state.note_form_state['editing_note_id'] = None # Ensure not editing
        st.rerun()
    
    # Note Form
    if st.session_state.note_form_state['adding_note']:
        with st.form("note_form", clear_on_submit=True):
            st.markdown("#### Add New Note")
            note_text = st.text_area(
                "Note Text",
                height=150,
                key=f"new_note_text_{experiment['id']}",
                help="Enter your lab note here."
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save Note"):
                    if note_text:
                        save_note(experiment['id'], note_text)
                        st.session_state.note_form_state['adding_note'] = False
                        st.session_state.experiment_updated = True
                        st.rerun()
                    else:
                        st.warning("Note text cannot be empty.")
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.note_form_state['adding_note'] = False
                    st.rerun()
    
    # Display existing notes
    if 'notes' in experiment and experiment['notes']:
        # Sort notes by creation date, newest first
        sorted_notes = sorted(experiment['notes'], key=lambda x: x['created_at'], reverse=True)
        for note in sorted_notes:
            with st.expander(f"Note from {note['created_at'].strftime('%Y-%m-%d %H:%M')}"):
                # Check if editing this specific note
                is_editing_this_note = st.session_state.note_form_state.get('editing_note_id') == note['id']

                if is_editing_this_note:
                    # Edit mode for this note
                    with st.form(f"edit_note_{note['id']}"):
                        edited_text = st.text_area(
                            "Edit Note",
                            value=note['note_text'],
                            height=150,
                            key=f"edit_text_{note['id']}",
                            help="Edit your lab note here."
                        )
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Save Changes"):
                                submit_note_edit(note['id'], edited_text)
                                st.session_state.experiment_updated = True
                                st.rerun() # Rerun after saving changes
                        with col2:
                            if st.form_submit_button("Cancel Edit"):
                                st.session_state.note_form_state['editing_note_id'] = None
                                st.rerun() # Rerun to exit edit mode
                else:
                    # View mode for this note
                    st.markdown(note['note_text'])
                    if note.get('updated_at') and note['updated_at'] > note['created_at']:
                        st.caption(f"Last updated: {note['updated_at'].strftime('%Y-%m-%d %H:%M')}")
                    
                    # Edit and Delete buttons (only show if not adding a new note)
                    if not st.session_state.note_form_state.get('adding_note', False):
                        col1, col2 = st.columns([1, 1]) # Adjust columns as needed
                        with col1:
                            if st.button("Edit", key=f"edit_{note['id']}"):
                                st.session_state.note_form_state['editing_note_id'] = note['id']
                                st.session_state.note_form_state['adding_note'] = False # Ensure not adding
                                st.rerun() # Rerun to show edit form
                        # Consider adding delete functionality here if needed
                        # with col2:
                        #    if st.button("Delete", key=f"delete_{note['id']}"):
                        #        # Add deletion logic (potentially with confirmation)
                        #        st.session_state.note_form_state['note_to_delete'] = note['id']
                        #        st.rerun()
    else:
        # Only show if not adding or editing a note
        if not st.session_state.note_form_state.get('adding_note', False) and not st.session_state.note_form_state.get('editing_note_id'):
             st.info("No lab notes recorded for this experiment.")