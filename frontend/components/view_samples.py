import streamlit as st
import pandas as pd
from database.database import SessionLocal
from database.models import SampleInfo, ExternalAnalysis, ModificationsLog, SamplePhotos, AnalysisFiles, PXRFReading
import os
import datetime
import json
# Import utilities and config
from frontend.components.utils import (
    log_modification, 
    save_uploaded_file, 
    delete_file_if_exists,
    generate_form_fields
)
from frontend.config.variable_config import (
    ANALYSIS_TYPES,
    EXTERNAL_ANALYSIS_CONFIG,
    ROCK_SAMPLE_CONFIG,
    PXRF_ELEMENT_COLUMNS
)

# Import for eager loading
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import func # For potential averaging in DB
# Import functions moved to edit_sample.py
from frontend.components.edit_sample import (
    delete_external_analysis, 
    add_external_analysis, 
    add_sample_photo,        
    delete_sample_photo,     
    delete_analysis_file,    
    update_sample_info
)

def render_sample_inventory():
    """
    Render the main sample inventory view with search, filtering, and pXRF averages from DB.
    """
    st.header("Rock Sample Inventory")
    
    # Initialize session state for viewing sample details if not exists
    if 'view_sample_id' not in st.session_state:
        st.session_state.view_sample_id = None
    
    # Initialize pagination state
    if 'samples_page' not in st.session_state:
        st.session_state.samples_page = 1
    if 'samples_per_page' not in st.session_state:
        st.session_state.samples_per_page = 10

    # Get total count for pagination
    total_samples = get_total_samples_count()
    total_pages = (total_samples + st.session_state.samples_per_page - 1) // st.session_state.samples_per_page
    
    # Add search and filter options
    col1, col2 = st.columns(2)
    with col1:
        search_term = st.text_input("Search by Sample ID or Classification:")
        
    with col2:
        location_filter = st.text_input("Filter by Location (State/Country):")
    
    # Get sample data including calculated pXRF averages with pagination
    samples_with_pxrf_avg = get_all_samples_with_pxrf_averages(
        page=st.session_state.samples_page,
        per_page=st.session_state.samples_per_page
    )

    # Apply filters to the enriched data
    filtered_samples = samples_with_pxrf_avg
    if search_term:
        filtered_samples = [s for s in filtered_samples if (
            search_term.lower() in s['sample_id'].lower() or
            (s['rock_classification'] and search_term.lower() in s['rock_classification'].lower()) # Handle potential None
        )]

    if location_filter:
        filtered_samples = [s for s in filtered_samples if (
            (s['state'] and location_filter.lower() in s['state'].lower()) or
            (s['country'] and location_filter.lower() in s['country'].lower()) # Handle potential None
        )]

    # Display samples in a table
    if filtered_samples:
        st.markdown("### Sample List")

        # --- Modify Column Layout --- 
        base_headers = ["Sample ID", "Classification", "Location", "Coordinates"]
        # Format element headers with proper capitalization (Fe, Ni, etc.)
        pxrf_headers = [f"{el.title()} Avg" for el in PXRF_ELEMENT_COLUMNS]
        action_header = ["Actions"]

        # Define column widths
        base_widths = [1, 2, 1, 1.5]
        pxrf_widths = [1] * len(pxrf_headers)
        action_width = [1]

        all_headers = base_headers + pxrf_headers + action_header
        all_widths = base_widths + pxrf_widths + action_width

        # Create columns
        cols = st.columns(all_widths)

        # Write headers
        for col, header in zip(cols, all_headers):
            with col:
                st.markdown(f"**{header}**")

        st.markdown("<hr style='margin: 2px 0px; background-color: #f0f0f0; height: 1px; border: none;'>", unsafe_allow_html=True)

        for sample in filtered_samples:
            with st.container():
                cols = st.columns(all_widths)

                # Display base data
                with cols[0]:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{sample['sample_id']}</div>", unsafe_allow_html=True)
                with cols[1]:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{sample.get('rock_classification', 'N/A')}</div>", unsafe_allow_html=True)
                with cols[2]:
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{sample.get('state', 'N/A')}, {sample.get('country', 'N/A')}</div>", unsafe_allow_html=True)
                with cols[3]:
                    lat = sample.get('latitude')
                    lon = sample.get('longitude')
                    coord_str = f"({lat:.4f}, {lon:.4f})" if lat is not None and lon is not None else "N/A"
                    st.write(f"<div style='margin: 0px; padding: 2px;'>{coord_str}</div>", unsafe_allow_html=True)

                # Display pXRF average data with proper element capitalization
                for i, element in enumerate(PXRF_ELEMENT_COLUMNS):
                    with cols[len(base_headers) + i]:
                        avg_key = f"{element.lower()}_avg"
                        value = sample.get(avg_key)
                        display_val = f"{value:.2f}" if value is not None else "N/A"
                        st.write(f"<div style='margin: 0px; padding: 2px;'>{display_val}</div>", unsafe_allow_html=True)

                # Display action button
                with cols[-1]:
                    if st.button("Details", key=f"view_sample_{sample['sample_id']}"):
                        st.session_state.view_sample_id = sample['sample_id']
                        st.rerun()

                st.markdown("<hr style='margin: 2px 0px; background-color: #f0f0f0; height: 1px; border: none;'>", unsafe_allow_html=True)
                
        # Pagination controls
        st.markdown("---")
        pagination_cols = st.columns([1, 2, 1])
        
        with pagination_cols[0]:
            if st.session_state.samples_page > 1:
                if st.button("← Previous"):
                    st.session_state.samples_page -= 1
                    st.rerun()
                    
        with pagination_cols[1]:
            st.markdown(f"<div style='text-align: center'>Page {st.session_state.samples_page} of {total_pages}</div>", unsafe_allow_html=True)
            
        with pagination_cols[2]:
            if st.session_state.samples_page < total_pages:
                if st.button("Next →"):
                    st.session_state.samples_page += 1
                    st.rerun()
                    
        # Items per page selector
        st.selectbox(
            "Items per page",
            options=[10, 25, 50],
            key="samples_per_page",
            on_change=lambda: setattr(st.session_state, 'samples_page', 1)
        )
    else:
        st.info("No samples found matching the selected criteria.")
    
    # Display sample details if a sample is selected
    if st.session_state.view_sample_id:
        display_sample_details(st.session_state.view_sample_id)

def display_sample_details(sample_id):
    """
    Display detailed information about a specific rock sample, fetching pXRF from DB.
    """
    try:
        sample = get_sample_by_id(sample_id)
        
        if sample is None:
            st.error(f"Sample with ID {sample_id} not found.")
            if st.button("Back to Sample List"):
                st.session_state.view_sample_id = None
                st.rerun()
            return
        
        if st.button("← Back to Sample List"):
            st.session_state.view_sample_id = None
            st.rerun()
        
        st.subheader(f"Sample Details: {sample.sample_id}")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### Basic Information")
            
            if 'editing_sample' not in st.session_state:
                st.session_state.editing_sample = False
            
            info_data = {
                ROCK_SAMPLE_CONFIG[field]['label']: getattr(sample, field) or "Not specified"
                for field in ROCK_SAMPLE_CONFIG.keys()
            }
            st.table(pd.DataFrame([info_data]).T.rename(columns={0: "Value"}))
            
            if not st.session_state.editing_sample:
                if st.button("Edit Sample Information"):
                    st.session_state.editing_sample = True
                    st.rerun()
            
            if st.session_state.editing_sample:
                with st.form("edit_sample_form"):
                    st.markdown("#### Edit Sample Information")
                    
                    current_values = {
                        field: getattr(sample, field)
                        for field in ROCK_SAMPLE_CONFIG.keys()
                    }
                    
                    form_values = generate_form_fields(
                        ROCK_SAMPLE_CONFIG,
                        current_values,
                        list(ROCK_SAMPLE_CONFIG.keys()),
                        'edit_sample'
                    )
                    
                    edit_col1, edit_col2 = st.columns(2)
                    with edit_col1:
                        if st.form_submit_button("Save Changes"):
                            if update_sample_info(sample_id, form_values):
                                st.session_state.editing_sample = False
                                st.rerun()
                    
                    with edit_col2:
                        if st.form_submit_button("Cancel"):
                            st.session_state.editing_sample = False
                            st.rerun()
            
            st.markdown("### External Analyses")
            analyses = sample.external_analyses
            
            if analyses:
                db_session_for_pxrf = SessionLocal()
                try:
                    for analysis in analyses:
                        date_str = analysis.analysis_date.strftime('%Y-%m-%d') if analysis.analysis_date else 'Date not specified'
                        
                        with st.expander(f"{analysis.analysis_type} Analysis - {date_str}"):
                            if analysis.laboratory:
                                st.write(f"**Laboratory:** {analysis.laboratory}")
                            if analysis.analyst:
                                st.write(f"**Analyst:** {analysis.analyst}")
                            if analysis.analysis_date:
                                st.write(f"**Date:** {analysis.analysis_date.strftime('%Y-%m-%d')}")

                            if analysis.pxrf_reading_no:
                                st.write(f"**pXRF Reading No(s):** {analysis.pxrf_reading_no}")
                            if analysis.description:
                                st.write("**Description:**")
                                st.markdown(f"> {analysis.description}")
                            if analysis.analysis_metadata:
                                st.write("**Additional Metadata:**")
                                try:
                                    metadata = json.loads(analysis.analysis_metadata) if isinstance(analysis.analysis_metadata, str) else analysis.analysis_metadata
                                    st.json(metadata)
                                except:
                                    st.text(analysis.analysis_metadata)

                            if analysis.analysis_type == 'pXRF' and analysis.pxrf_reading_no:
                                st.markdown("--- ")
                                st.markdown("#### pXRF Analysis Results")
                                reading_numbers_list = [num.strip() for num in analysis.pxrf_reading_no.split(',') if num.strip()]
                                
                                if reading_numbers_list:
                                    pxrf_data_query = db_session_for_pxrf.query(PXRFReading).filter(
                                        PXRFReading.reading_no.in_(reading_numbers_list)
                                    ).all()
                                    
                                    if pxrf_data_query:
                                        pxrf_readings_list = []
                                        for reading in pxrf_data_query:
                                            reading_dict = {
                                                'Reading No': reading.reading_no,
                                                **{el.title(): getattr(reading, el.lower(), None) for el in PXRF_ELEMENT_COLUMNS}
                                            }
                                            pxrf_readings_list.append(reading_dict)
                                        
                                        readings_df = pd.DataFrame(pxrf_readings_list)
                                        element_cols = [el.title() for el in PXRF_ELEMENT_COLUMNS]
                                        display_cols = ['Reading No'] + element_cols
                                        
                                        for col in element_cols:
                                            if col in readings_df.columns:
                                                readings_df[col] = pd.to_numeric(readings_df[col], errors='coerce')
                                        
                                        formatters = {
                                            col: "{:.2f}".format
                                            for col in element_cols
                                            if col in readings_df.columns and pd.api.types.is_numeric_dtype(readings_df[col])
                                        }
                                        
                                        st.markdown("##### Individual Readings")
                                        st.dataframe(
                                            readings_df[display_cols].style.format(formatters, na_rep='N/A'),
                                            use_container_width=True,
                                            hide_index=True
                                        )

                                        numeric_cols = [
                                            col for col in element_cols 
                                            if col in readings_df.columns and pd.api.types.is_numeric_dtype(readings_df[col])
                                        ]
                                        
                                        if numeric_cols:
                                            averages = readings_df[numeric_cols].mean().to_dict()
                                            st.markdown("##### Average Values")
                                            avg_df = pd.DataFrame([averages])
                                            st.dataframe(
                                                avg_df[numeric_cols].style.format("{:.2f}"),
                                                use_container_width=True,
                                                hide_index=True
                                            )
                                    else:
                                        st.info(f"No pXRF data found for Reading No(s): {analysis.pxrf_reading_no}")
                                else:
                                    st.warning("pXRF Reading Number(s) field is empty.")

                            st.markdown("--- ")
                            st.markdown("**Analysis Files:**")
                            if analysis.analysis_files:
                                for analysis_file in analysis.analysis_files:
                                    file_key = f"analysis_file_{analysis_file.id}"
                                    file_col1, file_col2 = st.columns([4, 1])
                                    with file_col1:
                                        if analysis_file.file_path and os.path.exists(analysis_file.file_path):
                                            try:
                                                with open(analysis_file.file_path, 'rb') as fp:
                                                    st.download_button(
                                                        f"Download {analysis_file.file_name}",
                                                        fp.read(),
                                                        file_name=analysis_file.file_name,
                                                        mime=analysis_file.file_type,
                                                        key=f"download_{file_key}"
                                                    )
                                            except Exception as e:
                                                st.warning(f"Could not read file {analysis_file.file_name}: {e}")
                                        elif analysis_file.file_path:
                                            st.warning(f"File not found: {analysis_file.file_name}")
                                        else:
                                            st.info("No file path recorded.")
                                    with file_col2:
                                        if st.button("Del", key=f"delete_{file_key}", help="Delete this specific file"):
                                            delete_analysis_file(analysis_file.id)
                                            st.rerun()
                                st.markdown("<hr style='margin: 1px 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)
                            else:
                                st.info("No specific files uploaded for this analysis entry.")

                            st.markdown("--- ")
                            if st.button("Delete Entire Analysis Entry", key=f"delete_analysis_{analysis.id}"):
                                delete_external_analysis(analysis.id)
                                st.rerun()
                finally:
                    db_session_for_pxrf.close()
            else:
                st.info("No external analyses recorded for this sample.")
        
        with col2:
            # Sample Photos Section (Modified)
            st.markdown("### Sample Photos")
            photos = sample.photos
            if photos:
                for photo in photos:
                    photo_key = f"photo_{photo.id}"
                    with st.expander(f"Photo {photo.id} ({photo.file_name or 'details'}) - Added: {photo.created_at.strftime('%Y-%m-%d')}"):
                        if photo.file_path and os.path.exists(photo.file_path):
                            try:
                                st.image(photo.file_path, caption=f"ID: {photo.id} - {photo.file_name}")
                            except Exception as e:
                                st.warning(f"Could not load image {photo.file_name}: {e}")
                        else:
                            st.warning(f"Photo file not found: {photo.file_name}")
                        if photo.description:
                            st.write("Description:")
                            st.write(photo.description)
                        
                        # Delete button for each photo
                        if st.button("Delete Photo", key=f"delete_{photo_key}"):
                            delete_sample_photo(photo.id) # Use imported function
                            st.rerun() # Rerun to refresh view after delete
            else:
                st.info("No photos available for this sample.")
            
            # Add Photo Button
            if st.button("Add Photo", key=f"add_photo_{sample_id}"):
                # Initialize session state flags for the form
                st.session_state.adding_photo = True
                st.session_state.adding_analysis = False # Ensure analysis form is closed
                st.session_state.current_sample_id = sample_id 
                st.session_state.current_sample_db_id = sample.id
                st.rerun() # Rerun to show the form immediately

            # Photo Upload Form 
            if st.session_state.get('adding_photo') and st.session_state.get('current_sample_id') == sample_id:
                 with st.form(f"photo_upload_form_{sample_id}", clear_on_submit=True):
                    st.markdown("#### Upload New Photo")
                    photo_file = st.file_uploader(
                        "Select Photo",
                        type=['jpg', 'jpeg', 'png'],
                        help="Select a photo file to upload.",
                        key=f"photo_upload_{sample_id}"
                    )
                    photo_desc = st.text_area("Photo Description (Optional)", key=f"photo_desc_{sample_id}")
                    
                    submitted = st.form_submit_button("Save Photo")
                    if submitted:
                        if photo_file:
                            # Calls the imported add_sample_photo function
                            add_sample_photo(st.session_state.current_sample_db_id, photo_file, photo_desc)
                            st.session_state.adding_photo = False
                            st.session_state.experiment_updated = True # Flag update for potential refresh
                            st.rerun()
                        else:
                             st.warning("Please select a photo file.")
                    
                    # Add a cancel button
                    if st.form_submit_button("Cancel"):
                         st.session_state.adding_photo = False
                         st.rerun()

            # Add External Analysis Button
            if st.button("Add External Analysis Entry", key=f"add_ext_analysis_{sample_id}"):
                st.session_state.adding_analysis = True
                st.session_state.adding_photo = False # Ensure photo form is closed
                st.session_state.current_sample_id = sample_id
                st.session_state.current_sample_db_id = sample.id 
                st.rerun() # Rerun to show the form immediately
            
            # External Analysis Form
            if st.session_state.get('adding_analysis', False) and st.session_state.get('current_sample_id') == sample_id:
                with st.form(f"external_analysis_form_{sample_id}", clear_on_submit=True):
                    st.markdown("#### Add New Analysis Entry")
                    # Keep fields for the overall analysis entry (using generate_form_fields)
                    form_values = generate_form_fields(
                        EXTERNAL_ANALYSIS_CONFIG,
                        {},  # Empty dict for new analysis
                        list(EXTERNAL_ANALYSIS_CONFIG.keys()),
                        f'analysis_{sample_id}'
                    )
                    
                    # Keep multi-file uploader
                    uploaded_files = st.file_uploader(
                        "Upload Analysis File(s)",
                        accept_multiple_files=True,
                        key=f"report_files_{sample_id}"
                    )
                    
                    submitted = st.form_submit_button("Save Analysis Entry")
                    if submitted:
                            # Base required fields from config
                            required_fields = [field for field, config in EXTERNAL_ANALYSIS_CONFIG.items() if config.get('required', False)]
                            missing_fields = [EXTERNAL_ANALYSIS_CONFIG[field]['label'] for field in required_fields if not form_values.get(field)]
                            
                            # Conditional requirement for pXRF Reading No
                            if form_values.get('analysis_type') == 'pXRF' and not form_values.get('pxrf_reading_no'):
                                missing_fields.append(EXTERNAL_ANALYSIS_CONFIG['pxrf_reading_no']['label'])

                            if missing_fields:
                                st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
                            else:
                                # Prepare the analysis_data dict from form_values
                                analysis_data_to_save = {
                                    'analysis_type': form_values['analysis_type'],
                                    'laboratory': form_values['laboratory'],
                                    'analyst': form_values['analyst'],
                                    'analysis_date': form_values['analysis_date'], # Already a date object
                                    'pxrf_reading_no': form_values.get('pxrf_reading_no'), # Add new field
                                    'description': form_values.get('description', ''),
                                    'analysis_metadata': None # Add logic here if metadata is captured in form
                                }
                                
                                # Calls the imported add_external_analysis function
                                success = add_external_analysis(
                                    user_sample_id=sample.sample_id, # Pass the string sample ID
                                    analysis_data=analysis_data_to_save, # Pass the prepared data dict
                                    uploaded_files=uploaded_files # Pass the list of files
                                )
                                if success:
                                    st.session_state.adding_analysis = False
                                    st.session_state.experiment_updated = True # Flag update
                                    st.rerun()

                    # Add a cancel button
                    if st.form_submit_button("Cancel"):
                         st.session_state.adding_analysis = False
                         st.rerun()

    except Exception as e:
        st.error(f"Error displaying sample details: {str(e)}")
        # Ensure db session is closed in case of error within the try block
        if 'db_session_for_pxrf' in locals() and db_session_for_pxrf.is_active:
            db_session_for_pxrf.close()

def get_sample_by_id(sample_id_str):
    """
    Retrieves a specific sample by its string ID with related photos and analyses.
    Args:
        sample_id_str (str): The string ID of the sample.
    Returns:
        SampleInfo: SQLAlchemy ORM object or None if not found.
    """
    db = None
    try:
        db = SessionLocal()
        sample = db.query(SampleInfo).options(
            selectinload(SampleInfo.photos),
            # Load external analyses AND their associated files
            selectinload(SampleInfo.external_analyses).selectinload(ExternalAnalysis.analysis_files)
        ).filter(SampleInfo.sample_id == sample_id_str).first()
        return sample
    except Exception as e:
        st.error(f"Error retrieving sample {sample_id_str}: {str(e)}")
        return None
    finally:
        if db and db.is_active:
            db.close()

def get_total_samples_count(db=None):
    """
    Get total count of samples for pagination.
    """
    try:
        if db is None:
            db = SessionLocal()
        return db.query(SampleInfo).count()
    except Exception as e:
        st.error(f"Error getting sample count: {str(e)}")
        return 0
    finally:
        if db:
            db.close()

def get_all_samples_with_pxrf_averages(page=1, per_page=10):
    """
    Retrieve paginated samples and calculate average pXRF values from linked readings in the DB.

    Args:
        page (int): Current page number (1-based)
        per_page (int): Number of items per page

    Returns:
        list: A list of dictionaries, each representing a sample with added 
              '<element>_avg' keys for calculated pXRF averages.
    """
    db = None
    try:
        db = SessionLocal()
        offset = (page - 1) * per_page
        samples = db.query(SampleInfo).options(
            selectinload(SampleInfo.external_analyses)
        ).offset(offset).limit(per_page).all()

        results = []
        all_reading_nos_needed = set()
        sample_reading_map = {}

        # First pass: Collect all reading numbers and initialize sample data
        for sample in samples:
            sample_data = {
                field: getattr(sample, field)
                for field in ROCK_SAMPLE_CONFIG.keys()
            }
            sample_data['id'] = sample.id
            
            sample_reading_nos = set()
            for analysis in sample.external_analyses:
                if analysis.analysis_type == 'pXRF' and analysis.pxrf_reading_no:
                    nums = {num.strip() for num in analysis.pxrf_reading_no.split(',') if num.strip()}
                    sample_reading_nos.update(nums)
                    all_reading_nos_needed.update(nums)
            
            # Initialize average fields with None
            for element in PXRF_ELEMENT_COLUMNS:
                sample_data[f"{element.lower()}_avg"] = None
                
            results.append(sample_data)
            sample_reading_map[sample.sample_id] = sample_reading_nos

        # Second pass: Query all required PXRFReading data
        if all_reading_nos_needed:
            pxrf_readings_db = db.query(PXRFReading).filter(
                PXRFReading.reading_no.in_(list(all_reading_nos_needed))
            ).all()

            # Convert readings to a dictionary for lookup
            pxrf_data_dict = {}
            for reading in pxrf_readings_db:
                reading_dict = {
                    el.title(): getattr(reading, el.lower(), None)
                    for el in PXRF_ELEMENT_COLUMNS
                }
                pxrf_data_dict[reading.reading_no] = reading_dict

        # Third pass: Calculate averages for each sample
        for sample_data in results:
            sample_id = sample_data['sample_id']
            relevant_reading_nos = sample_reading_map.get(sample_id, set())
            
            if not relevant_reading_nos:
                continue
                
            # Collect values for each element
            element_values = {el.title(): [] for el in PXRF_ELEMENT_COLUMNS}
            
            for reading_no in relevant_reading_nos:
                reading_data = pxrf_data_dict.get(reading_no)
                if reading_data:
                    for element in PXRF_ELEMENT_COLUMNS:
                        element_title = element.title()
                        value = reading_data.get(element_title)
                        if value is not None and pd.api.types.is_number(value):
                            element_values[element_title].append(value)
            
            # Calculate averages
            for element in PXRF_ELEMENT_COLUMNS:
                element_title = element.title()
                values = element_values[element_title]
                if values:
                    avg = sum(values) / len(values)
                    sample_data[f"{element.lower()}_avg"] = avg
                    
        return results

    except Exception as e:
        st.error(f"Error retrieving samples with pXRF averages: {str(e)}")
        return []
    finally:
        if db and db.is_active:
            db.close()