import streamlit as st
import pandas as pd
import io
from database.database import SessionLocal
from database.models import Experiment, ExperimentalResults, ScalarResults, SampleInfo, PXRFReading, ExperimentalConditions
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

EXPERIMENTAL_RESULTS_REQUIRED_COLS = {
    "experiment_id", "time_post_reaction", "description",
    "solution_ammonium_concentration"
}

def render_bulk_uploads_page():
    """
    Renders the bulk uploads page in the Streamlit app.
    Allows users to select a data type and upload data in bulk.
    """
    st.title("Bulk Uploads")

    upload_option = st.selectbox(
        "Select data type to upload:",
        ("Select data type", "NMR Results", "Rock Samples (Sample Info)", "pXRF Readings")
    )

    if upload_option == "NMR Results":
        handle_nmr_results_upload()
    elif upload_option == "Rock Samples (Sample Info)":
        st.info("Bulk upload for Rock Samples is not yet implemented.")
    elif upload_option == "pXRF Readings":
        st.info("Bulk upload for pXRF Readings is not yet implemented.")

def handle_nmr_results_upload():
    """
    Handles the UI and logic for bulk uploading NMR results.
    """
    st.header("Bulk Upload NMR Results")
    st.markdown("""
    Upload an Excel file for NMR results. The file should have the
    following columns. Please ensure `Experiment ID` is in the database.

    **Columns marked with an asterisk (*) are required.**
    """)

    # --- Template Generation ---
    template_data = {
        "experiment_id": ["EXP-001"],
        "time_post_reaction": [1.0],
        "description": ["Sampled after acid addition"],
        "ammonium_quant_method": ["NMR"],
        "solution_ammonium_concentration": [10.5],
        "sampling_volume": [5.0],
        "final_ph": [7.2],
        "ferrous_iron_yield": [0.0],
        "final_nitrate_concentration": [0.1],
        "final_dissolved_oxygen": [2.5],
        "co2_partial_pressure": [14.7],
        "final_conductivity": [1500.0],
        "final_alkalinity": [120.0],

    }

    template_cols_ordered = {}
    for col, val in template_data.items():
        if col in EXPERIMENTAL_RESULTS_REQUIRED_COLS:
            template_cols_ordered[f"{col}*"] = val
        else:
            template_cols_ordered[col] = val
    
    template_df = pd.DataFrame(template_cols_ordered)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False, sheet_name='Experimental Results')
    output.seek(0)

    st.download_button(
        label="Download Template",
        data=output,
        file_name="experimental_results_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            _process_nmr_results_df(df)
        except Exception as e:
            st.error(f"An error occurred: {e}")

def _process_nmr_results_df(df):
    """
    Processes the DataFrame from the uploaded Excel file for NMR results.
    Validates data and inserts it into the database.
    """
    # Clean column names by removing the asterisk
    df.columns = df.columns.str.replace('*', '', regex=False)

    if not EXPERIMENTAL_RESULTS_REQUIRED_COLS.issubset(df.columns):
        st.error(f"File is missing required columns. Required: {', '.join(EXPERIMENTAL_RESULTS_REQUIRED_COLS)}")
        return

    db = SessionLocal()
    try:
        results_to_add = []
        errors = []
        for index, row in df.iterrows():
            exp_id_raw = row['experiment_id']
            # Normalize experiment_id: lower case and remove hyphens and underscores
            exp_id_normalized = exp_id_raw.lower().replace('-', '').replace('_', '')

            # Query by normalized experiment_id
            experiment = db.query(Experiment).filter(
                func.lower(func.replace(func.replace(Experiment.experiment_id, '-', ''), '_', '')) == exp_id_normalized
            ).options(joinedload(Experiment.conditions)).first()

            if not experiment:
                errors.append(f"Row {index+2}: Experiment with ID '{exp_id_raw}' not found.")
                continue

            # Check for existing result to prevent duplicates
            existing_result = db.query(ExperimentalResults).filter_by(
                experiment_fk=experiment.id,
                time_post_reaction=row['time_post_reaction']
            ).first()

            if existing_result:
                errors.append(f"Row {index+2}: Result for experiment '{exp_id_raw}' at time {row['time_post_reaction']} already exists.")
                continue

            new_result = ExperimentalResults(
                experiment_id=experiment.experiment_id,  # Use the ID from the database
                experiment_fk=experiment.id,
                time_post_reaction=row['time_post_reaction'],
                description=row['description']
            )

            scalar_data = ScalarResults(
                ferrous_iron_yield=row.get('ferrous_iron_yield'),
                solution_ammonium_concentration=row.get('solution_ammonium_concentration'),
                ammonium_quant_method=row.get('ammonium_quant_method'),
                final_ph=row.get('final_ph'),
                final_nitrate_concentration=row.get('final_nitrate_concentration'),
                final_dissolved_oxygen=row.get('final_dissolved_oxygen'),
                co2_partial_pressure=row.get('co2_partial_pressure'),
                final_conductivity=row.get('final_conductivity'),
                final_alkalinity=row.get('final_alkalinity'),
                sampling_volume=row.get('sampling_volume'),
                result_entry=new_result
            )
            scalar_data.calculate_yields()
            results_to_add.append(new_result)

        if errors:
            for error in errors:
                st.warning(error)
        
        if results_to_add and not errors:
            db.add_all(results_to_add)
            db.commit()
            st.success(f"Successfully uploaded {len(results_to_add)} new NMR results.")
        elif not results_to_add and not errors:
            st.info("No new data to upload.")
        else:
            st.error("Upload failed due to errors. Please correct the file and try again.")
            db.rollback()

    except IntegrityError as e:
        db.rollback()
        st.error(f"Database error: {e.orig}")
    except Exception as e:
        db.rollback()
        st.error(f"An unexpected error occurred: {e}")
    finally:
        db.close() 