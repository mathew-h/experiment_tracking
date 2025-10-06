import streamlit as st
import pandas as pd
import io
from database import SessionLocal, Experiment, ExperimentalResults, ScalarResults, SampleInfo, PXRFReading, ExperimentalConditions, Compound, ChemicalAdditive, AmountUnit
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
        (
            "Select data type",
            "Scalar Results (NMR/pH/Conductivity/Alkalinity)",
            "ICP Elemental Analysis",
            "Rock Samples (Sample Info)",
            "pXRF Readings",
            "Chemical Inventory (Compounds)",
            "Experiment Additives (Compounds per Experiment)"
        )
    )

    if upload_option == "Scalar Results (NMR/pH/Conductivity/Alkalinity)":
        handle_solution_chemistry_upload()
    elif upload_option == "ICP Elemental Analysis":
        handle_icp_upload()
    elif upload_option == "Rock Samples (Sample Info)":
        st.info("Bulk upload for Rock Samples is not yet implemented.")
    elif upload_option == "pXRF Readings":
        st.info("Bulk upload for pXRF Readings is not yet implemented.")
    elif upload_option == "Chemical Inventory (Compounds)":
        upload_chemical_inventory()
    elif upload_option == "Experiment Additives (Compounds per Experiment)":
        experiments_additives()

def upload_chemical_inventory():
    """
    Upload a template-driven Excel to create or update chemical compounds in the database.
    - Provides a downloadable template with supported fields
    - Accepts an uploaded Excel and upserts rows into the `compounds` table
    """
    st.header("Bulk Upload Chemical Inventory (Compounds)")

    # Template definition (column order preserved)
    template_columns = [
        "name",                 # required, unique
        "formula",
        "cas_number",          # optional, unique if provided
        "molecular_weight",    # g/mol
        "density",             # g/cm³ (solids) or g/mL (liquids)
        "melting_point",       # °C
        "boiling_point",       # °C
        "solubility",
        "hazard_class",
        "supplier",
        "catalog_number",
        "notes",
    ]

    example_row = {
        "name": "Sodium Chloride",
        "formula": "NaCl",
        "cas_number": "7647-14-5",
        "molecular_weight": 58.44,
        "density": 2.165,
        "melting_point": 801.0,
        "boiling_point": 1413.0,
        "solubility": "Soluble in water",
        "hazard_class": "Non-hazardous",
        "supplier": "Sigma-Aldrich",
        "catalog_number": "S7653",
        "notes": "Food grade"
    }

    template_df = pd.DataFrame([example_row], columns=template_columns)

    # Download template
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False, sheet_name='compounds')
    buf.seek(0)
    st.download_button(
        label="Download Compound Template",
        data=buf,
        file_name="compound_inventory_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("---")
    uploaded_file = st.file_uploader("Upload filled compound template (xlsx)", type=["xlsx"])

    if not uploaded_file:
        return

    try:
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Failed to read Excel: {e}")
        return

    # Normalize column names (case-insensitive match to template)
    col_map = {c.lower().strip(): c for c in df.columns}
    missing_required = []
    if "name" not in col_map:
        missing_required.append("name")
    if missing_required:
        st.error(f"Missing required column(s): {', '.join(missing_required)}")
        return

    # Reindex to expected columns (optional ones may be absent)
    normalized_cols = [c for c in template_columns if c in col_map]
    df = df.rename(columns={col_map[c]: c for c in normalized_cols if c in col_map})

    created, updated, skipped, errors = 0, 0, 0, []
    db = SessionLocal()
    try:
        for idx, row in df.iterrows():
            try:
                name = str(row.get("name") or "").strip()
                if not name:
                    skipped += 1
                    continue

                formula = str(row.get("formula")) if not pd.isna(row.get("formula")) else None
                cas_number = str(row.get("cas_number")) if not pd.isna(row.get("cas_number")) else None

                # Numeric fields safe parse
                def num(val):
                    try:
                        return float(val)
                    except Exception:
                        return None

                molecular_weight = num(row.get("molecular_weight"))
                density = num(row.get("density"))
                melting_point = num(row.get("melting_point"))
                boiling_point = num(row.get("boiling_point"))
                solubility = str(row.get("solubility")) if not pd.isna(row.get("solubility")) else None
                hazard_class = str(row.get("hazard_class")) if not pd.isna(row.get("hazard_class")) else None
                supplier = str(row.get("supplier")) if not pd.isna(row.get("supplier")) else None
                catalog_number = str(row.get("catalog_number")) if not pd.isna(row.get("catalog_number")) else None
                notes = str(row.get("notes")) if not pd.isna(row.get("notes")) else None

                # Duplicate checks: by name (case-insensitive), and CAS if provided
                existing = db.query(Compound).filter(Compound.name.ilike(name)).first()
                if not existing and cas_number:
                    existing = db.query(Compound).filter(Compound.cas_number == cas_number).first()

                if existing:
                    # Update existing compound
                    existing.formula = formula or existing.formula
                    existing.cas_number = cas_number or existing.cas_number
                    existing.molecular_weight = molecular_weight if molecular_weight is not None else existing.molecular_weight
                    existing.density = density if density is not None else existing.density
                    existing.melting_point = melting_point if melting_point is not None else existing.melting_point
                    existing.boiling_point = boiling_point if boiling_point is not None else existing.boiling_point
                    existing.solubility = solubility or existing.solubility
                    existing.hazard_class = hazard_class or existing.hazard_class
                    existing.supplier = supplier or existing.supplier
                    existing.catalog_number = catalog_number or existing.catalog_number
                    existing.notes = notes or existing.notes
                    updated += 1
                else:
                    comp = Compound(
                        name=name,
                        formula=formula,
                        cas_number=cas_number,
                        molecular_weight=molecular_weight,
                        density=density,
                        melting_point=melting_point,
                        boiling_point=boiling_point,
                        solubility=solubility,
                        hazard_class=hazard_class,
                        supplier=supplier,
                        catalog_number=catalog_number,
                        notes=notes,
                    )
                    db.add(comp)
                    created += 1
            except Exception as e:
                errors.append(f"Row {idx+2}: {e}")  # +2 for header and 1-based index

        if errors:
            # If errors exist, rollback to avoid partial writes and report
            db.rollback()
            st.error("Upload failed; no changes were applied.")
            for msg in errors[:50]:
                st.error(msg)
            if len(errors) > 50:
                st.info(f"...and {len(errors)-50} more errors")
        else:
            db.commit()
            st.success(f"Compounds created: {created}, updated: {updated}, skipped: {skipped}")

    except Exception as e:
        db.rollback()
        st.error(f"Unexpected error during compound upload: {e}")
    finally:
        db.close()

def experiments_additives():
    """
    Bulk upload chemical additives for specific experiments.

    Template columns (sheet name 'experiment_additives'):
      - experiment_id* (string)
      - compound* (existing compound name)
      - amount* (numeric > 0)
      - unit* (one of AmountUnit values, e.g., g, mg, μg, kg, μL, mL, L, μmol, mmol, mol, ppm, mM, M)
      - order (optional integer)
      - method (optional text)
    """
    st.header("Bulk Upload Experiment Additives")

    # Build template
    unit_options = [u.value for u in AmountUnit]
    example = {
        'experiment_id': 'Serum_MH_001',
        'compound': 'Sodium Chloride',
        'amount': 100.0,
        'unit': unit_options[0] if unit_options else 'mg',
        'order': 1,
        'method': 'solution'
    }
    template_df = pd.DataFrame([example], columns=['experiment_id', 'compound', 'amount', 'unit', 'order', 'method'])

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False, sheet_name='experiment_additives')
    buf.seek(0)
    st.download_button(
        label="Download Additives Template",
        data=buf,
        file_name="experiment_additives_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.markdown("---")
    replace_mode = st.checkbox("Replace existing additives for each experiment before applying", value=False)
    uploaded = st.file_uploader("Upload filled additives template (xlsx)", type=["xlsx"])

    if not uploaded:
        return

    try:
        df = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Failed to read Excel: {e}")
        return

    # Normalize columns
    required_cols = {'experiment_id', 'compound', 'amount', 'unit'}
    df.columns = [str(c).strip().lower() for c in df.columns]
    if not required_cols.issubset(set(df.columns)):
        missing = ', '.join(sorted(required_cols - set(df.columns)))
        st.error(f"Missing required columns: {missing}")
        return

    # Start processing
    db = SessionLocal()
    created, updated, deleted, errors, skipped = 0, 0, 0, [], 0

    # Group by experiment for optional replace
    try:
        # Build fast compound lookup (case-insensitive by name)
        all_compounds = db.query(Compound).all()
        name_to_compound = {c.name.lower(): c for c in all_compounds}

        # Build fast experiment lookup by experiment_id string
        # We'll fetch on demand to avoid loading everything

        # Track which experiments we already cleared when replace_mode is on
        cleared_conditions_ids = set()

        for idx, row in df.iterrows():
            try:
                exp_id = str(row.get('experiment_id') or '').strip()
                comp_name = str(row.get('compound') or '').strip()
                unit_val = str(row.get('unit') or '').strip()
                amount_val = row.get('amount')
                order_val = row.get('order') if 'order' in df.columns else None
                method_val = row.get('method') if 'method' in df.columns else None

                if not exp_id or not comp_name or not unit_val:
                    skipped += 1
                    continue

                try:
                    amount_float = float(amount_val)
                except Exception:
                    errors.append(f"Row {idx+2}: invalid amount '{amount_val}'")
                    continue
                if amount_float <= 0:
                    errors.append(f"Row {idx+2}: amount must be > 0")
                    continue

                # Validate unit
                unit_enum = None
                for u in AmountUnit:
                    if u.value == unit_val:
                        unit_enum = u
                        break
                if unit_enum is None:
                    errors.append(f"Row {idx+2}: invalid unit '{unit_val}'")
                    continue

                # Resolve experiment
                experiment = db.query(Experiment).filter(Experiment.experiment_id == exp_id).first()
                if not experiment:
                    errors.append(f"Row {idx+2}: experiment_id '{exp_id}' not found")
                    continue

                # Resolve or create ExperimentalConditions for this experiment
                conditions = db.query(ExperimentalConditions).filter(ExperimentalConditions.experiment_fk == experiment.id).first()
                if not conditions:
                    conditions = ExperimentalConditions(
                        experiment_id=experiment.experiment_id,
                        experiment_fk=experiment.id,
                    )
                    db.add(conditions)
                    db.flush()

                # Replace existing additives once per conditions if requested
                if replace_mode and conditions.id not in cleared_conditions_ids:
                    existing = db.query(ChemicalAdditive).filter(ChemicalAdditive.experiment_id == conditions.id).all()
                    for a in existing:
                        db.delete(a)
                        deleted += 1
                    db.flush()
                    cleared_conditions_ids.add(conditions.id)

                # Resolve compound
                comp = name_to_compound.get(comp_name.lower())
                if not comp:
                    errors.append(f"Row {idx+2}: compound '{comp_name}' not found; upload inventory first")
                    continue

                # Upsert additive
                existing_add = db.query(ChemicalAdditive).filter(
                    ChemicalAdditive.experiment_id == conditions.id,
                    ChemicalAdditive.compound_id == comp.id,
                ).first()

                # Parse order int
                try:
                    order_int = int(order_val) if order_val is not None and str(order_val).strip() != '' else None
                except Exception:
                    order_int = None

                method_text = str(method_val).strip() if method_val is not None and str(method_val).strip() != '' else None

                if existing_add:
                    existing_add.amount = amount_float
                    existing_add.unit = unit_enum
                    existing_add.addition_order = order_int
                    existing_add.addition_method = method_text
                    existing_add.calculate_derived_values()
                    updated += 1
                else:
                    new_add = ChemicalAdditive(
                        experiment_id=conditions.id,
                        compound_id=comp.id,
                        amount=amount_float,
                        unit=unit_enum,
                        addition_order=order_int,
                        addition_method=method_text,
                    )
                    new_add.calculate_derived_values()
                    db.add(new_add)
                    created += 1

            except Exception as e:
                errors.append(f"Row {idx+2}: {e}")

        if errors:
            db.rollback()
            st.error("Upload failed; no changes were applied.")
            for msg in errors[:50]:
                st.error(msg)
            if len(errors) > 50:
                st.info(f"...and {len(errors)-50} more errors")
        else:
            db.commit()
            st.success(f"Additives created: {created}, updated: {updated}, deleted: {deleted}, skipped: {skipped}")

    except Exception as e:
        db.rollback()
        st.error(f"Unexpected error during additives upload: {e}")
    finally:
        db.close()

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
            
            # Separate errors from overwrite notifications
            actual_errors = [msg for msg in upload_errors if not msg.startswith("Sample") or "Updated existing ICP data" not in msg]
            overwrite_notifications = [msg for msg in upload_errors if "Updated existing ICP data" in msg]
            
            # Handle upload feedback
            if actual_errors:
                st.subheader("❌ Upload Errors")
                for error in actual_errors:
                    st.error(error)
            
            if overwrite_notifications:
                st.subheader("🔄 Data Updates")
                for notification in overwrite_notifications:
                    st.info(notification.replace("Sample ", "Entry "))
            
            if results and not actual_errors:
                db.commit()
                st.success(f"✅ Successfully processed {len(results)} ICP results.")
                
                # Show success summary
                experiments = list(set([data['experiment_id'] for data in processed_data if data['experiment_id']]))
                new_count = len(results) - len(overwrite_notifications)
                update_count = len(overwrite_notifications)
                
                summary_parts = []
                if new_count > 0:
                    summary_parts.append(f"{new_count} new")
                if update_count > 0:
                    summary_parts.append(f"{update_count} updated")
                
                summary = " and ".join(summary_parts)
                st.info(f"**Summary:** {summary} ICP results for {len(experiments)} experiments")
                
            elif not results and not actual_errors:
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