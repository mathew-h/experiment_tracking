import streamlit as st
import pandas as pd
import os
import json
from sqlalchemy import orm
from database.database import SessionLocal
from database.models import (
    ExperimentalResults,
    ResultType,
    ScalarResults, # Import ScalarResults
    NMRResults,    # Import NMRResults
    ResultFiles
)
from frontend.config.variable_config import (
    SCALAR_RESULTS_CONFIG,
    NMR_RESULTS_CONFIG,
    RESULT_TYPE_FIELDS # Import this mapping
)
from frontend.components.utils import (
    generate_form_fields,
    format_value # Assuming format_value is moved or duplicated here/in utils
)
from frontend.components.experimental_results import (
    save_results,
    delete_experimental_results,
    delete_result_file,
    save_uploaded_file
)

# --- Main Rendering Function ---
def render_results_section(experiment):
    """
    Renders the entire 'Results' section for an experiment, including display and add/edit forms.
    """
    st.markdown("### Results")

    db = SessionLocal()
    try:
        # Fetch all results for the experiment, preloading related data
        # Sort by time_post_reaction
        all_results = db.query(ExperimentalResults).options(
            # Eager load specific result data and files
            orm.selectinload(ExperimentalResults.scalar_data),
            orm.selectinload(ExperimentalResults.nmr_data),
            orm.selectinload(ExperimentalResults.files)
        ).filter(
            ExperimentalResults.experiment_id == experiment['experiment_id'] # Use experiment_id string
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
        st.session_state.current_experiment_id_results == experiment['id'] # Use DB id for state tracking
    )

    # --- Display Existing Results ---
    if all_results:
        st.write("Recorded Results:")
        for result in all_results:
            display_single_result(result, experiment['id']) # Pass experiment DB id
    elif not showing_form_for_this_experiment:
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
        render_results_form(experiment['id']) # Pass experiment DB id

# --- Helper to Display a Single Result Entry ---
def display_single_result(result, experiment_db_id):
    """Displays a single result entry (time point) in an expander."""
    # Create title based on primary result type
    expander_title = f"{result.result_type.name} Results at {result.time_post_reaction:.1f} hours"
    
    with st.expander(expander_title):
        # --- Directly access scalar_data via relationship ---
        scalar_data = result.scalar_data 

        # --- Display Scalar Results First ---
        if scalar_data:
            st.markdown("##### Scalar Measurements") # Changed header slightly
            scalar_data_dict = {}
            
            # First show key calculated fields
            key_fields = ['grams_per_ton_yield', 'ferrous_iron_yield']
            for field in key_fields:
                value = getattr(scalar_data, field, None)
                if value is not None:  # Only add non-null values
                    # Ensure the field exists in SCALAR_RESULTS_CONFIG before accessing
                    if field in SCALAR_RESULTS_CONFIG: 
                        config = SCALAR_RESULTS_CONFIG[field]
                        scalar_data_dict[config['label']] = format_value(value, config)
                    else:
                         scalar_data_dict[field.replace('_', ' ').title()] = value # Fallback display
            
            # Then show other scalar fields
            skip_fields = ['time_post_reaction'] + key_fields
            for field_name, config in SCALAR_RESULTS_CONFIG.items():
                if field_name not in skip_fields:
                    value = getattr(scalar_data, field_name, None)
                    if value is not None:  # Only add non-null values
                        scalar_data_dict[config['label']] = format_value(value, config)
            
            if scalar_data_dict:
                scalar_df = pd.DataFrame([scalar_data_dict]).T.rename(columns={0: "Value"})
                scalar_df["Value"] = scalar_df["Value"].astype(str) # Ensure string type
                st.table(scalar_df)
            # Display message only if no scalar_data object exists at all
        else:
             st.info("No associated scalar measurements recorded for this time point.")

        # --- Display Primary Result Data (e.g., NMR) Second ---
        primary_data_displayed = False
        if result.result_type == ResultType.NMR and result.nmr_data:
            st.markdown("##### NMR Data")
            nmr_data_dict = {}
            nmr_config = RESULT_TYPE_FIELDS['NMR']['config']
            
            # Calculated NMR fields first
            calc_fields = ['ammonium_concentration_mm', 'total_nh4_peak_area']
            for field in calc_fields:
                if field in nmr_config:
                    value = getattr(result.nmr_data, field, None)
                    if value is not None:
                        nmr_data_dict[nmr_config[field]['label']] = format_value(value, nmr_config[field])
            
            # Other NMR fields
            for field_name, config in nmr_config.items():
                if field_name not in calc_fields:
                    value = getattr(result.nmr_data, field_name, None)
                    if value is not None:
                        nmr_data_dict[config['label']] = format_value(value, config)
            
            if nmr_data_dict:
                nmr_df = pd.DataFrame([nmr_data_dict]).T.rename(columns={0: "Value"})
                nmr_df["Value"] = nmr_df["Value"].astype(str) # Ensure string type
                st.table(nmr_df)
                primary_data_displayed = True
            else:
                 st.info("NMR record exists, but contains no values.")
        # --- Add elif blocks for other primary result types (GC, PXRF, etc.) ---
        # elif result.result_type == ResultType.GC and result.gc_data:
             # ... Display GC data ...
             # primary_data_displayed = True
        
        # If no specific data was found/displayed for the primary type
        if not primary_data_displayed:
             st.info(f"No specific {result.result_type.name} data recorded for this time point.")

        # --- Display Associated Files ---
        if result.files:
            st.markdown("##### Associated Files")
            for file_record in result.files:
                file_col1, file_col2, file_col3 = st.columns([3, 4, 1])
                with file_col1:
                    st.write(f"- {file_record.file_name}")
                with file_col2:
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
                     if st.button("❌", key=f"delete_file_{file_record.id}", help="Delete this file"):
                         delete_success = delete_result_file(file_record.id)
                         if delete_success:
                             st.session_state.experiment_updated = True
                             st.rerun()

        st.markdown("---") # Separator

        # --- Edit/Delete Buttons ---
        col1, col2, col3 = st.columns([1, 1, 5])
        with col1:
            # Button text reflects what can be edited
            edit_button_label = f"Edit Data / Add Files"
            if st.button(edit_button_label, key=f"edit_result_{result.id}"):
                st.session_state.show_results_form = True
                st.session_state.editing_result_id = result.id
                st.session_state.current_experiment_id_results = experiment_db_id
                st.rerun()
        with col2:
            if st.button("Delete Time Point", key=f"delete_result_{result.id}"):
                try:
                    delete_experimental_results(result.id)
                    st.session_state.experiment_updated = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting result time point: {e}")

# --- Form Rendering Function ---
def render_results_form(experiment_db_id):
    """Renders the Add/Edit form for experiment results."""

    form_title = "Add New Results"
    current_data = {} # Combined dict for pre-populating
    editing_time = None
    primary_result_type = None # Track the primary type being added/edited

    # Generate base key parts using DB id
    base_key_part = f"results_{experiment_db_id}_{st.session_state.editing_result_id or 'new'}"
    form_key = f"{base_key_part}_form"
    buffer_key = f"{base_key_part}_buffer"
    file_uploader_key = f"{base_key_part}_uploader"

    # --- Initialize Session State for file buffer ---
    if buffer_key not in st.session_state:
        st.session_state[buffer_key] = {'uploaded_files': []}
    file_buffer = st.session_state[buffer_key]

    if st.session_state.editing_result_id:
        # Fetch the specific result being edited to pre-populate form
        db = SessionLocal()
        try:
            result_to_edit = db.query(ExperimentalResults).options(
                orm.selectinload(ExperimentalResults.scalar_data), # Always load scalar
                orm.selectinload(ExperimentalResults.nmr_data)     # Load primary types as needed
                # Add selectinload for GC, PXRF etc. if models exist
            ).filter(
                ExperimentalResults.id == st.session_state.editing_result_id
            ).first()

            if result_to_edit:
                primary_result_type = result_to_edit.result_type # Get the primary type being edited
                form_title = f"Edit {primary_result_type.name} Results at {result_to_edit.time_post_reaction:.1f} hours"
                editing_time = result_to_edit.time_post_reaction
                current_data['time_post_reaction'] = editing_time # Pre-populate time
                current_data['description'] = result_to_edit.description # Pre-populate description

                # Pre-populate from ScalarResults first
                if result_to_edit.scalar_data:
                    scalar_config = SCALAR_RESULTS_CONFIG
                    for field_name in scalar_config.keys():
                        default_val = scalar_config[field_name].get('default')
                        current_data[field_name] = getattr(result_to_edit.scalar_data, field_name, default_val)
                else: # Populate with scalar defaults if no scalar record exists yet
                    for field_name, config in SCALAR_RESULTS_CONFIG.items():
                        current_data[field_name] = config['default']

                # Pre-populate from the primary result type's data
                primary_data_source = None
                primary_config = {}
                if primary_result_type.name in RESULT_TYPE_FIELDS:
                     primary_config = RESULT_TYPE_FIELDS[primary_result_type.name].get('config', {})
                     # Get the actual data attribute based on type (e.g., result_to_edit.nmr_data)
                     data_attr_name = f"{primary_result_type.name.lower()}_data"
                     if hasattr(result_to_edit, data_attr_name):
                          primary_data_source = getattr(result_to_edit, data_attr_name)

                if primary_data_source:
                    for field_name in primary_config.keys():
                        default_val = primary_config[field_name].get('default')
                        current_data[field_name] = getattr(primary_data_source, field_name, default_val)
                # If primary data source doesn't exist (shouldn't happen for edit?), populate with defaults
                elif primary_config:
                     for field_name, config in primary_config.items():
                          if field_name not in current_data: # Avoid overwriting (e.g., from scalar)
                               current_data[field_name] = config['default']

            else:
                st.error("Could not find the result entry to edit.")
                # Reset state and rerun
                st.session_state.show_results_form = False
                st.session_state.editing_result_id = None
                st.session_state.current_experiment_id_results = None
                st.rerun()
        finally:
            db.close()
    else:
        # Adding new: Determine default primary type
        available_types = list(RESULT_TYPE_FIELDS.keys()) # NMR, GC, etc.
        default_primary_type_name = available_types[0] if available_types else None
        if default_primary_type_name:
             try:
                 primary_result_type = ResultType[default_primary_type_name]
             except KeyError:
                 st.warning(f"Default result type {default_primary_type_name} not in ResultType enum.")
                 primary_result_type = None # Handle error state

        # Use defaults from SCALAR config
        for field_name, config in SCALAR_RESULTS_CONFIG.items():
            current_data[field_name] = config['default']
        current_data['description'] = "" # Default to empty for new results
        # Use defaults from the default primary type's config
        if primary_result_type and primary_result_type.name in RESULT_TYPE_FIELDS:
            primary_config = RESULT_TYPE_FIELDS[primary_result_type.name].get('config', {})
            for field_name, config in primary_config.items():
                if field_name not in current_data: # Avoid overwriting scalar defaults
                    current_data[field_name] = config['default']

    st.markdown(f"#### {form_title}")

    # --- File Upload Section (Outside Form) ---
    st.markdown("**Upload New Files** (Associated with this time point)")
    uploaded_files_widget = st.file_uploader(
        "Select files",
        accept_multiple_files=True,
        key=file_uploader_key,
        help="Upload data files, images, etc. related to these results."
    )

    # --- Update file buffer based on File Uploader ---
    current_widget_files = uploaded_files_widget if uploaded_files_widget else []
    current_widget_file_names = {f.name for f in current_widget_files}
    buffer_file_names = {f.name for f in file_buffer['uploaded_files']}

    # Add new files from widget to buffer
    for file in current_widget_files:
         if file.name not in buffer_file_names:
             file_buffer['uploaded_files'].append(file)

    # Remove files from buffer that are no longer in the widget
    new_buffer_files = []
    for file in file_buffer['uploaded_files']:
         if file.name in current_widget_file_names:
             new_buffer_files.append(file)

    file_buffer['uploaded_files'] = new_buffer_files

    with st.form(key=form_key, clear_on_submit=True):
        form_values = {} # Will store scalar values
        primary_specific_data_values = {} # Will store primary type values

        # Determine which fields to show based on the primary result type
        # For "Add New", let user choose. For "Edit", it's fixed.
        if st.session_state.editing_result_id is None:
            # Get available types from RESULT_TYPE_FIELDS
            available_primary_types = list(RESULT_TYPE_FIELDS.keys())

            if available_primary_types:
                # Let user choose which type of result they are adding
                selected_primary_type_name = st.selectbox(
                    "Primary Result Type",
                    options=available_primary_types,
                    index=0,  # Default to first available type
                    key=f"{base_key_part}_primary_type_select"
                )
                try:
                    primary_result_type = ResultType[selected_primary_type_name]
                except KeyError:
                    st.error(f"Invalid primary result type: {selected_primary_type_name}")
                    primary_result_type = None  # Handle error
            else:
                st.warning("No primary result types (e.g., NMR, GC) are configured. Please check `variable_config.py`.")
                primary_result_type = None
        # In edit mode, primary_result_type is already set from the database record loaded earlier.

        # --- Render form fields ---
        st.markdown("**Result Metadata**")
        col1_meta, col2_meta = st.columns(2)
        with col1_meta:
            form_values['time_post_reaction'] = st.number_input(
                label=SCALAR_RESULTS_CONFIG['time_post_reaction']['label'],
                value=current_data.get('time_post_reaction', 0.0),
                min_value=0.0,
                step=0.5,
                format="%.1f",
                help=SCALAR_RESULTS_CONFIG['time_post_reaction']['help'],
                disabled=(editing_time is not None) # Disable if editing
            )

        with col2_meta:
            form_values['description'] = st.text_input(
                "Add a general description for this result entry",
                value=current_data.get('description', ''),
                key=f"{base_key_part}_desc"
            )

        st.markdown("---")
        
        col1, col2 = st.columns(2)

        with col1:
            # --- Render Scalar Fields ---
            st.markdown("**Scalar Measurements**")
            scalar_field_names = [f for f in SCALAR_RESULTS_CONFIG.keys() if f not in ['time_post_reaction', 'description']]
            
            for field_name in scalar_field_names:
                config = SCALAR_RESULTS_CONFIG[field_name]
                default_val = current_data.get(field_name, config.get('default'))
                field_key = f"{base_key_part}_{field_name}"

                if config['type'] == 'number':
                    form_values[field_name] = st.number_input(
                        label=config['label'],
                        value=default_val,
                        min_value=config.get('min_value'),
                        max_value=config.get('max_value'),
                        step=config.get('step'),
                        format=config.get('format'),
                        help=config.get('help'),
                        key=field_key,
                        disabled=config.get('readonly', False)
                    )

        with col2:
            # --- Render Primary-Specific Fields (e.g., NMR) ---
            if primary_result_type and primary_result_type.name in RESULT_TYPE_FIELDS:
                st.markdown(f"**{primary_result_type.name} Data**")
                primary_config = RESULT_TYPE_FIELDS[primary_result_type.name]['config']
                primary_field_names = list(primary_config.keys())
                
                for field_name in primary_field_names:
                    with st.container(): # Use container to group fields
                        config = primary_config[field_name]
                        default_val = current_data.get(field_name, config.get('default'))
                        field_key = f"{base_key_part}_{field_name}"

                        if config['type'] == 'number':
                            primary_specific_data_values[field_name] = st.number_input(
                                label=config['label'],
                                value=default_val,
                                min_value=config.get('min_value'),
                                max_value=config.get('max_value'),
                                step=config.get('step'),
                                format=config.get('format'),
                                help=config.get('help'),
                                key=field_key,
                                disabled=config.get('readonly', False)
                            )
        
        # --- Submit Button ---
        st.markdown("---")
        submitted = st.form_submit_button(
            "Save Results",
            type="primary",
            use_container_width=True
        )

    # --- Post-form processing ---
    if submitted:
        # Re-determine primary type for saving
        if st.session_state.editing_result_id is None:
            # On new submission, get the type that was selected in the form
            selected_type_name = st.session_state.get(f"{base_key_part}_primary_type_select")
            if selected_type_name:
                primary_result_type = ResultType[selected_type_name]
        
        # Get description from form_values
        result_description = form_values.get('description', "")

        # Prepare list of files to be saved
        files_to_save = []
        if file_buffer.get('uploaded_files'):
             for uploaded_file in file_buffer['uploaded_files']:
                 # No description needed anymore
                 files_to_save.append({'file': uploaded_file})

        # Save all data
        save_results(
            experiment_id=experiment_db_id,
            time_post_reaction=form_values['time_post_reaction'],
            result_description=result_description,
            result_type=primary_result_type, # Pass the ResultType enum member
            scalar_data=form_values,
            primary_data=primary_specific_data_values,
            files_to_save=files_to_save,
            result_id_to_edit=st.session_state.editing_result_id
        )

        # Clear buffer and reset state
        st.session_state[buffer_key] = {'uploaded_files': []}
        st.session_state.show_results_form = False
        st.session_state.editing_result_id = None
        st.session_state.current_experiment_id_results = None
        st.rerun()
