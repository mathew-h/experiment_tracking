import streamlit as st
import pandas as pd
import io
from database.database import SessionLocal
from database.models import Experiment, ExperimentalResults, ScalarResults, SampleInfo, PXRFReading, ExperimentalConditions
from backend.services.scalar_results_service import ScalarResultsService
from backend.services.icp_service import ICPService
from sqlalchemy.exc import IntegrityError

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
        ("Select data type", "Scalar Results (NMR/pH/Conductivity/Alkalinity)", "ICP Elemental Analysis", "Rock Samples (Sample Info)", "pXRF Readings")
    )

    if upload_option == "Scalar Results (NMR/pH/Conductivity/Alkalinity)":
        handle_solution_chemistry_upload()
    elif upload_option == "ICP Elemental Analysis":
        handle_icp_upload()
    elif upload_option == "Rock Samples (Sample Info)":
        st.info("Bulk upload for Rock Samples is not yet implemented.")
    elif upload_option == "pXRF Readings":
        st.info("Bulk upload for pXRF Readings is not yet implemented.")

def handle_solution_chemistry_upload():
    """
    Handles the UI and logic for bulk uploading solution chemistry results (NMR-quantified).
    """
    st.header("Bulk Upload Solution Chemistry Results")
    st.markdown("""
    Upload an Excel file for solution chemistry results quantified by NMR. 
    The file should have the following columns. Please ensure `Experiment ID` is in the database.

    **Columns marked with an asterisk (*) are required.**
    """)

    # --- Template Generation ---
    template_data = {
        "experiment_id": ["Serum_MH_025"],
        "time_post_reaction": [1],
        "description": ["Sampled after acid addition"],
        "ammonium_quant_method": ["NMR"],
        "solution_ammonium_concentration": [10.5],
        "sampling_volume": [5.0],
        "final_ph": [7.2],
        "ferrous_iron_yield": [0.0],
        "final_nitrate_concentration": [0],
        "final_dissolved_oxygen": [0],
        "co2_partial_pressure": [0],
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
        template_df.to_excel(writer, index=False, sheet_name='Solution Chemistry')
    output.seek(0)

    st.download_button(
        label="Download Template",
        data=output,
        file_name="solution_chemistry_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx"])

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            _process_solution_chemistry_df(df)
        except Exception as e:
            st.error(f"An error occurred: {e}")

def _process_solution_chemistry_df(df):
    """
    Processes the DataFrame from the uploaded Excel file for solution chemistry results.
    Uses ScalarResultsService for all backend logic.
    """
    # Clean column names by removing the asterisk
    df.columns = df.columns.str.replace('*', '', regex=False)

    if not EXPERIMENTAL_RESULTS_REQUIRED_COLS.issubset(df.columns):
        st.error(f"File is missing required columns. Required: {', '.join(EXPERIMENTAL_RESULTS_REQUIRED_COLS)}")
        return

    # Convert DataFrame to list of dictionaries for service
    results_data = df.to_dict('records')
    
    db = SessionLocal()
    try:
        # Use service for all business logic
        results, errors = ScalarResultsService.bulk_create_scalar_results(db, results_data)
        
        # Handle UI feedback
        if errors:
            for error in errors:
                st.warning(error)
        
        if results and not errors:
            db.commit()
            st.success(f"Successfully uploaded {len(results)} solution chemistry results.")
        elif not results and not errors:
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

def handle_icp_upload():
    """
    Handles the UI and logic for bulk uploading ICP elemental analysis results.
    Processes CSV files directly from ICP instrument output.
    """
    st.header("Bulk Upload ICP Elemental Analysis")
    st.markdown("""
    Upload a CSV file containing ICP elemental analysis data. 
    This should be the direct output from the ICP instrument containing:
    
    - **Experiment ID**, **Time Point**, and **Dilution** in 'Label' Column (e.g. 'Serum_MH_011_Day5_5x)
    - **Elemental concentrations** in ppm (Fe, Mg, Ni, Cu, Si, Co, Mo, Al, etc.)
    - Please ensure all referenced Experiment IDs exist in the database
    
    **Note:** No template is provided as this processes direct instrument output files.
    """)

    uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

    if uploaded_file:
        try:
            # Read file content as bytes for ICPService
            file_content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset file pointer for potential re-reading
            
            _process_icp_csv(file_content)
            
        except Exception as e:
            st.error(f"An error occurred processing the CSV file: {e}")

def _process_icp_csv(file_content: bytes):
    """
    Processes the ICP CSV file using ICPService for all backend logic.
    """
    db = SessionLocal()
    try:
        # Step 1: Parse and process the ICP file
        st.info("Processing ICP data file...")
        processed_data, processing_errors = ICPService.parse_and_process_icp_file(file_content)
        
        if processing_errors:
            st.subheader("⚠️ Processing Issues Found")
            for error in processing_errors:
                st.warning(error)
        
        if not processed_data:
            st.error("No valid ICP data found to upload.")
            return
        
        # Step 2: Show preview of processed data
        st.subheader("📊 Processed ICP Data Preview")
        
        # Convert processed data to DataFrame for display
        preview_df = pd.DataFrame(processed_data)
        
        # Show summary info
        st.info(f"Found {len(processed_data)} samples with ICP data")
        
        # Show first few samples
        if len(preview_df) > 0:
            st.write("**Sample Overview:**")
            display_cols = ['experiment_id', 'time_post_reaction', 'dilution_factor']
            element_cols = [col for col in preview_df.columns if col not in ['experiment_id', 'time_post_reaction', 'dilution_factor', 'raw_label']]
            display_cols.extend(element_cols[:5])  # Show first 5 elements
            
            if len(element_cols) > 5:
                st.write(f"*Showing first 5 elements. Total elements detected: {len(element_cols)}*")
            
            st.dataframe(preview_df[display_cols].head(10))
        
        # Step 3: Upload to database if no critical errors
        if not processing_errors or st.button("Upload Despite Warnings"):
            st.info("Uploading ICP data to database...")
            
            results, upload_errors = ICPService.bulk_create_icp_results(db, processed_data)
            
            # Handle upload feedback
            if upload_errors:
                st.subheader("❌ Upload Errors")
                for error in upload_errors:
                    st.error(error)
            
            if results and not upload_errors:
                db.commit()
                st.success(f"✅ Successfully uploaded {len(results)} ICP results.")
                
                # Show success summary
                experiments = list(set([data['experiment_id'] for data in processed_data if data['experiment_id']]))
                st.info(f"**Summary:** Uploaded ICP data for {len(experiments)} experiments")
                
            elif not results and not upload_errors:
                st.info("ℹ️ No new ICP data to upload.")
            else:
                st.error("❌ Upload failed due to errors. Please correct the issues and try again.")
                db.rollback()
        
    except IntegrityError as e:
        db.rollback()
        st.error(f"Database integrity error: {e.orig}")
    except Exception as e:
        db.rollback()
        st.error(f"An unexpected error occurred during ICP processing: {e}")
    finally:
        db.close()