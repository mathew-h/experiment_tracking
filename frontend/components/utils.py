from frontend.config.variable_config import (
    FIELD_CONFIG,
)
import os
import streamlit as st
from database.models import ModificationsLog
import json # Added for JSON serialization in logging
import datetime # Added for timestamp in logging and date input
from database.database import SessionLocal
import pandas as pd
from pathlib import Path
import logging
# Import the centralized storage functions
from utils.storage import save_file, get_file, delete_file
from sqlalchemy.orm import Session, joinedload
from database.models import ExperimentalResults, NMRResults, ScalarResults, ExperimentalConditions, Experiment

logger = logging.getLogger(__name__)

def get_condition_display_dict(conditions):
    """
    Build a display dictionary for experimental conditions.
    
    It leverages FIELD_CONFIG to determine:
      - Which fields to display,
      - The expected type of the field (numeric if the default is a float, string otherwise),
      - And a friendly label with units.
    """
    display_dict = {}
    
    for field_name, config in FIELD_CONFIG.items():
        # Get the friendly label from the config
        label = config['label']
        value = conditions.get(field_name)
        
        # If value is None or an empty string, display as "N/A"
        if value is None or (isinstance(value, str) and not value.strip()):
            display_value = "N/A"
        else:
            # If the field type is number and has a format, use it
            if config['type'] == 'number' and config.get('format') and isinstance(value, (int, float)):
                try:
                    display_value = config['format'] % float(value)
                except (ValueError, TypeError):
                    display_value = str(value)
            else:
                display_value = str(value)
        
        display_dict[label] = display_value
    return display_dict

def split_conditions_for_display(conditions):
    """
    Splits conditions into required and optional fields for display purposes.
    
    It uses get_condition_display_dict to build the full display dict, and then
    separates the required fields (based on FIELD_CONFIG) from the rest.
    """
    display_dict = get_condition_display_dict(conditions)
    
    # Build a set of display labels for required fields using FIELD_CONFIG
    required_labels = {config['label'] for field_name, config in FIELD_CONFIG.items() if config.get('required', False)}
    
    required_fields = {label: value for label, value in display_dict.items() if label in required_labels}
    optional_fields = {label: value for label, value in display_dict.items() if label not in required_labels}
    
    return required_fields, optional_fields

def build_conditions(data, experiment_id):
    """
    Builds a complete conditions dictionary for an experiment.
    
    This function creates a conditions dictionary using FIELD_CONFIG defaults
    and provided data, then adds the experiment_id.
    
    Args:
        data (dict): Dictionary containing actual values to use
        experiment_id (int): ID of the experiment these conditions belong to
        
    Returns:
        dict: Complete conditions dictionary ready for database storage
    """
    # Start with default values from FIELD_CONFIG
    conditions = {name: config['default'] for name, config in FIELD_CONFIG.items()}
    
    # Override with values provided in 'data'
    conditions.update({key: data.get(key, default) for key, default in conditions.items()})
    
    # Add experiment_id for the relationship
    conditions['experiment_id'] = experiment_id
    
    return conditions

# --- File Storage Helpers (Using utils.storage) ---

# Removed the FileStorage class and get_upload_dir function

def save_uploaded_file(file, storage_folder, filename_prefix):
    """
    Saves an uploaded file using the centralized utils.storage.save_file.

    Args:
        file (UploadedFile): The file object from st.file_uploader.
        storage_folder (str): The target folder/prefix in the storage backend (e.g., "photos/sample_123").
        filename_prefix (str): A prefix to potentially add to the original filename (often not needed when using folders).

    Returns:
        str or None: The storage path/URL of the saved file, or None if error.
    """
    if not file:
        return None

    try:
        file_bytes = file.getvalue()
        original_filename = file.name
        # Note: filename_prefix might be redundant if storage_folder provides uniqueness
        # Construct the final file name (e.g., keep original name within the folder)
        final_file_name = os.path.basename(original_filename).replace(" ", "_") 

        # Use the centralized save_file function
        file_path_url = save_file(
            file_data=file_bytes,
            file_name=final_file_name, # Use the cleaned original filename
            folder=storage_folder
        )
        return file_path_url
    except Exception as e:
        st.error(f"Error saving file {file.name}: {str(e)}")
        logger.error(f"Error in save_uploaded_file: {e}", exc_info=True)
        return None

def delete_file_if_exists(file_path):
    """
    Deletes a file using the centralized utils.storage.delete_file.

    Args:
        file_path (str): The storage path/URL of the file to delete.

    Returns:
        bool: True if deletion was successful or file didn't exist, False otherwise.
    """
    if not file_path:
        return True # Nothing to delete
    try:
        delete_file(file_path)
        return True
    except FileNotFoundError:
        logger.warning(f"File not found for deletion (already deleted?): {file_path}")
        return True # Consider file not found as success in deletion context
    except Exception as e:
        st.warning(f"Could not delete file {file_path}: {e}")
        logger.error(f"Error in delete_file_if_exists: {e}", exc_info=True)
        return False

# --- Formatting Utility ---

def format_value(value, config):
    """Formats a value based on its config (type, format string)."""
    if value is None:
        return "N/A"
    if config['type'] == 'number' and config.get('format') and isinstance(value, (int, float)):
        try:
           return config['format'] % float(value)
        except (ValueError, TypeError):
           # Fallback if format string fails
           return str(value)
    else:
        # Handle non-numeric types or numbers without specific format
        return str(value)

# --- New Form Generation Utility ---
def generate_form_fields(field_config, current_data, field_names, key_prefix):
    """
    Generates Streamlit form input elements based on configuration.

    Args:
        field_config (dict): The FIELD_CONFIG dictionary from variable_config.py.
        current_data (dict): Dictionary containing the current values for the fields 
                             (e.g., from session_state or an existing experiment record).
        field_names (list): A list of field names (keys from field_config) to generate inputs for.
        key_prefix (str): A unique prefix for Streamlit widget keys to avoid conflicts.

    Returns:
        dict: A dictionary where keys are field names and values are the 
              current values entered/selected by the user in the generated widgets.
    """
    form_values = {}
    for field_name in field_names:
        if field_name not in field_config:
            st.warning(f"Configuration for field '{field_name}' not found. Skipping.")
            continue

        config = field_config[field_name]
        label = config['label']
        field_type = config['type']
        # Get current value, falling back to default if not present in current_data
        current_value = current_data.get(field_name, config.get('default')) # Use .get for default
        key = f"{key_prefix}_{field_name}"
        help_text = config.get('help')

        # Handle numeric fields with None values and ensure type consistency
        if field_type == 'number':
            step = config.get('step') # Get the step value
            is_int_step = isinstance(step, int) # Check if step is integer

            try:
                # Set default based on step type if current_value is None
                if current_value is None:
                    current_value = 0 if is_int_step else 0.0

                # Convert to the appropriate type (int or float)
                if is_int_step:
                    # Allow float input but convert final value to int if step is int
                    # st.number_input handles intermediate float values during input
                    # We just need to ensure the initial value matches step type if possible
                    current_value = int(float(current_value))
                else:
                    # Ensure it's a float if step is float
                    current_value = float(current_value)

            except (ValueError, TypeError):
                # Fallback to 0 or 0.0 based on step type
                current_value = 0 if is_int_step else 0.0

        if field_type == 'text':
            form_values[field_name] = st.text_input(
                label=label,
                value=str(current_value) if current_value is not None else '',
                key=key,
                help=help_text
            )
        elif field_type == 'number':
            form_values[field_name] = st.number_input(
                label=label,
                min_value=config.get('min_value'),
                max_value=config.get('max_value'),
                value=current_value,
                step=config.get('step'),
                format=config.get('format'),
                key=key,
                help=help_text
            )
        elif field_type == 'select':
             # Find index for selectbox, default to 0 if not found or invalid
            try:
                index = config['options'].index(current_value) if current_value in config['options'] else 0
            except ValueError:
                index = 0 # Default to first option if value not in list
            form_values[field_name] = st.selectbox(
                label=label,
                options=config['options'],
                index=index, 
                key=key,
                help=help_text
            )
        elif field_type == 'text_area': # Added for notes or descriptions
             form_values[field_name] = st.text_area(
                 label=label,
                 value=str(current_value) if current_value is not None else '',
                 height=config.get('height', 100), # Optional height
                 key=key,
                 help=help_text
             )
        elif field_type == 'date':
             # st.date_input handles None value correctly (shows current date by default)
             # Ensure value passed is either None or a datetime.date/datetime.datetime
             date_value = current_value if isinstance(current_value, (datetime.date, datetime.datetime)) else None
             form_values[field_name] = st.date_input(
                 label=label,
                 value=date_value, 
                 key=key,
                 help=help_text
             )
        # Add more types (e.g., date, file_uploader) as needed
        else:
            st.warning(f"Unsupported field type '{field_type}' for field '{field_name}'. Skipping.")

    return form_values

# --- Modification Logging Utility ---

def log_modification(db, experiment_id, modified_table, modification_type, old_values=None, new_values=None, related_id=None):
    """
    Creates and adds a modification log entry to the database session.
    
    Args:
        db (Session): The SQLAlchemy database session.
        experiment_id (int or None): The ID of the related experiment (None for sample-level changes).
        modified_table (str): The name of the table that was modified.
        modification_type (str): Type of modification ('create', 'update', 'delete', 'add').
        old_values (dict, optional): Dictionary of values before the change (for update/delete).
        new_values (dict, optional): Dictionary of values after the change (for create/update/add).
        related_id (int, optional): ID of a related record (e.g., result_id for files) for additional context.
    """
    try:
        # Get user identifier from session state
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Serialize dicts to JSON strings if they exist
        old_values_json = json.dumps(old_values) if old_values else None
        new_values_json = json.dumps(new_values, default=str) if new_values else None # Use default=str for non-serializable types like datetime
            
        # If related_id is provided, include it in the values
        if related_id is not None:
            if old_values_json:
                old_values_dict = json.loads(old_values_json)
                old_values_dict['related_id'] = related_id
                old_values_json = json.dumps(old_values_dict)
            if new_values_json:
                new_values_dict = json.loads(new_values_json)
                new_values_dict['related_id'] = related_id
                new_values_json = json.dumps(new_values_dict)
            
        modification = ModificationsLog(
            experiment_id=experiment_id,
            modified_by=user_identifier,
            modification_type=modification_type,
            modified_table=modified_table,
            old_values=old_values_json,
            new_values=new_values_json
        )
        db.add(modification)
    except Exception as e:
        # Log the error but don't crash the main operation
        st.error(f"Error creating modification log: {str(e)}")

# --- Moved from view_experiments.py ---
def extract_conditions(conditions_obj):
    """
    Extracts experimental conditions from an ORM object.
    
    This function uses FIELD_CONFIG to provide default values
    for any missing conditions.
    
    Args:
        conditions_obj: SQLAlchemy ORM object containing experimental conditions
        
    Returns:
        dict: Dictionary of conditions with default values for missing fields
    """
    extracted = {}
    for field_name, config in FIELD_CONFIG.items():
        # Try to get the attribute from the conditions object;
        # if it's None or missing, use the default
        value = getattr(conditions_obj, field_name, None)
        extracted[field_name] = value if value is not None else config['default']
    return extracted

def remove_duplicate_samples(excel_path: str = "data/20250404_Master Data Migration Sheet.xlsx") -> None:
    """
    Reads the sample_info sheet from the Excel file, identifies and removes rows with duplicate sample_ids.
    Keeps the first occurrence of each sample_id and removes subsequent duplicates.
    Saves the modified Excel file with '_cleaned' suffix.
    
    Args:
        excel_path (str): Path to the Excel file
    """
    try:
        # Read the Excel file
        excel_file = pd.ExcelFile(excel_path)
        
        # Check if sample_info sheet exists
        if 'sample_info' not in excel_file.sheet_names:
            logger.error("No 'sample_info' sheet found in the Excel file")
            return
        
        # Read all sheets into a dictionary
        all_sheets = {}
        for sheet_name in excel_file.sheet_names:
            all_sheets[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
        
        # Get the sample_info sheet
        sample_df = all_sheets['sample_info']
        
        # Check if sample_id column exists
        if 'sample_id' not in sample_df.columns:
            logger.error("No 'sample_id' column found in sample_info sheet")
            return
        
        # Find duplicates
        duplicates = sample_df[sample_df['sample_id'].duplicated()]['sample_id'].unique()
        
        if len(duplicates) == 0:
            logger.info("No duplicate sample_ids found")
            return
        
        # Log the duplicates found
        logger.info(f"Found {len(duplicates)} duplicate sample_ids: {', '.join(str(d) for d in duplicates)}")
        
        # Keep first occurrence of each sample_id
        original_count = len(sample_df)
        sample_df = sample_df.drop_duplicates(subset=['sample_id'], keep='first')
        removed_count = original_count - len(sample_df)
        
        # Update the dictionary with cleaned sample_info
        all_sheets['sample_info'] = sample_df
        
        # Create new filename with '_cleaned' suffix
        file_path = Path(excel_path)
        new_path = file_path.parent / f"{file_path.stem}_cleaned{file_path.suffix}"
        
        # Save all sheets to new Excel file
        with pd.ExcelWriter(new_path) as writer:
            for sheet_name, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        logger.info(f"Removed {removed_count} duplicate rows")
        logger.info(f"Saved cleaned file to: {new_path}")
        
    except Exception as e:
        logger.error(f"Error processing Excel file: {str(e)}")
        raise

def check_experiment_duplicates(excel_path: str = "data/20250404_Master Data Migration Sheet.xlsx") -> None:
    """
    Checks for duplicate experiment_numbers and experiment_ids in the experiments sheet.
    
    Args:
        excel_path (str): Path to the Excel file
    """
    try:
        # Read the Excel file
        excel_file = pd.ExcelFile(excel_path)
        
        # Check if experiments sheet exists
        if 'experiments' not in excel_file.sheet_names:
            logger.error("No 'experiments' sheet found in the Excel file")
            return
        
        # Read experiments sheet
        df = pd.read_excel(excel_file, sheet_name='experiments', engine='openpyxl')
        
        # Check for experiment_number duplicates
        if 'experiment_number' in df.columns:
            num_duplicates = df[df['experiment_number'].duplicated()]
            if not num_duplicates.empty:
                logger.error("\nDuplicate experiment_numbers found:")
                for _, row in num_duplicates.iterrows():
                    logger.error(f"experiment_number {row['experiment_number']} is duplicated (experiment_id: {row['experiment_id']})")
        else:
            logger.error("No 'experiment_number' column found")
            
        # Check for experiment_id duplicates
        if 'experiment_id' in df.columns:
            id_duplicates = df[df['experiment_id'].duplicated()]
            if not id_duplicates.empty:
                logger.error("\nDuplicate experiment_ids found:")
                for _, row in id_duplicates.iterrows():
                    logger.error(f"experiment_id {row['experiment_id']} is duplicated (experiment_number: {row['experiment_number']})")
        else:
            logger.error("No 'experiment_id' column found")
            
        # Show all experiment records for verification
        logger.info("\nAll experiments in sheet:")
        for _, row in df.iterrows():
            logger.info(f"experiment_number: {row['experiment_number']}, experiment_id: {row['experiment_id']}")
            
    except Exception as e:
        logger.error(f"Error checking experiment duplicates: {str(e)}")
        raise

def clean_external_analyses(excel_path: str = "data/20250404_Master Data Migration Sheet.xlsx") -> None:
    """
    Reads the external_analyses sheet from the Excel file, removes rows where pxrf_reading_no is blank,
    and ensures proper sample_info_id relationships are maintained.
    Saves the modified Excel file with '_cleaned' suffix.
    
    Args:
        excel_path (str): Path to the Excel file
    """
    try:
        # Read the Excel file
        excel_file = pd.ExcelFile(excel_path)
        
        # Check if required sheets exist
        required_sheets = {'external_analyses', 'sample_info'}
        missing_sheets = required_sheets - set(excel_file.sheet_names)
        if missing_sheets:
            logger.error(f"Missing required sheets: {', '.join(missing_sheets)}")
            return
        
        # Read all sheets into a dictionary
        all_sheets = {}
        for sheet_name in excel_file.sheet_names:
            all_sheets[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name, engine='openpyxl')
        
        # Get the relevant sheets
        analyses_df = all_sheets['external_analyses']
        sample_info_df = all_sheets['sample_info']
        
        # Check if required columns exist
        if 'pxrf_reading_no' not in analyses_df.columns:
            logger.error("No 'pxrf_reading_no' column found in external_analyses sheet")
            return
        if 'sample_id' not in analyses_df.columns or 'sample_id' not in sample_info_df.columns:
            logger.error("'sample_id' column missing in one or both sheets")
            return
            
        # Count rows before cleaning
        original_count = len(analyses_df)
        
        # Remove rows where pxrf_reading_no is blank (NaN, None, or empty string)
        analyses_df = analyses_df.dropna(subset=['pxrf_reading_no'])
        analyses_df = analyses_df[analyses_df['pxrf_reading_no'].astype(str).str.strip() != '']
        
        # Create a mapping of sample_id to auto-incrementing sample_info_id
        sample_id_mapping = {row['sample_id']: idx + 1 
                           for idx, row in sample_info_df.iterrows()}
        
        # Add/update sample_info_id based on sample_id
        analyses_df['sample_info_id'] = analyses_df['sample_id'].map(sample_id_mapping)
        
        # Remove rows where we couldn't find a matching sample_info_id
        invalid_samples = analyses_df[analyses_df['sample_info_id'].isna()]['sample_id'].unique()
        if len(invalid_samples) > 0:
            logger.warning(f"Found {len(invalid_samples)} samples in external_analyses with no matching sample_info: {invalid_samples}")
            
        analyses_df = analyses_df.dropna(subset=['sample_info_id'])
        
        # Convert sample_info_id to integer
        analyses_df['sample_info_id'] = analyses_df['sample_info_id'].astype(int)
        
        # Count removed rows
        removed_count = original_count - len(analyses_df)
        
        # Update the dictionary with cleaned external_analyses
        all_sheets['external_analyses'] = analyses_df
        
        # Create new filename with '_cleaned' suffix
        file_path = Path(excel_path)
        new_path = file_path.parent / f"{file_path.stem}_cleaned{file_path.suffix}"
        
        # Save all sheets to new Excel file
        with pd.ExcelWriter(new_path) as writer:
            for sheet_name, df in all_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        logger.info(f"Removed {removed_count} rows with blank pxrf_reading_no values or invalid sample_ids")
        logger.info(f"Successfully mapped sample_info_ids for {len(analyses_df)} rows")
        logger.info(f"Saved cleaned file to: {new_path}")
        
    except Exception as e:
        logger.error(f"Error cleaning external_analyses sheet: {str(e)}")
        raise

def backfill_calculated_fields(db: Session):
    """
    Iterates through results and conditions, recalculating derived fields.
    Commits changes to the database if any updates were made.
    """
    print("Starting backfill of calculated fields...")
    updated_count = 0 # Track total updates across all types

    # 1. Backfill ExperimentalConditions derived fields
    # Fetch conditions where calculation inputs are present but outputs might be null
    conditions_to_update = db.query(ExperimentalConditions).filter(
        (
            (ExperimentalConditions.water_to_rock_ratio == None) &
            (ExperimentalConditions.water_volume != None) &
            (ExperimentalConditions.rock_mass != None) &
            (ExperimentalConditions.rock_mass > 0)
        ) |
        (
            (ExperimentalConditions.catalyst_percentage == None) &
            (ExperimentalConditions.catalyst != None) &
            (ExperimentalConditions.catalyst_mass != None) &
            (ExperimentalConditions.rock_mass != None) &
            (ExperimentalConditions.rock_mass > 0)
        )
        # Add other conditions if more derived fields are added
    ).all()
    
    updated_conditions_count = 0
    if conditions_to_update:
        print(f"Checking {len(conditions_to_update)} ExperimentalConditions entries for potential updates...")
        for condition in conditions_to_update:
            # Store original values to check if anything changed
            original_wtr = condition.water_to_rock_ratio
            original_cat_perc = condition.catalyst_percentage
            condition.calculate_derived_conditions() # Attempt calculation
            if (condition.water_to_rock_ratio != original_wtr or
                condition.catalyst_percentage != original_cat_perc):
                updated_conditions_count += 1
                # No need to explicitly add, SQLAlchemy tracks changes within the session
        if updated_conditions_count > 0:
            print(f"Updated derived fields for {updated_conditions_count} ExperimentalConditions entries.")
            updated_count += updated_conditions_count

    # 2. Backfill NMRResults calculated fields
    # It's often simplest to recalculate all, assuming inputs might have changed
    # Load related experiment and conditions data needed for ammonia_mass_g calculation
    nmr_results_to_update = db.query(NMRResults).options(
        joinedload(NMRResults.result_entry)
            .joinedload(ExperimentalResults.experiment)
            .joinedload(Experiment.conditions)
    ).all()
    
    updated_nmr_count = 0
    if nmr_results_to_update:
        print(f"Checking {len(nmr_results_to_update)} NMRResults entries for potential updates...")
        for nmr_result in nmr_results_to_update:
            # Store original values
            original_total_area = nmr_result.total_nh4_peak_area
            original_conc_mm = nmr_result.ammonium_concentration_mm
            original_mass_g = nmr_result.ammonia_mass_g
            nmr_result.calculate_values() # Recalculate
            if (nmr_result.total_nh4_peak_area != original_total_area or
                nmr_result.ammonium_concentration_mm != original_conc_mm or
                nmr_result.ammonia_mass_g != original_mass_g):
                 updated_nmr_count += 1
                 # No need to explicitly add
        if updated_nmr_count > 0:
             print(f"Recalculated values for {updated_nmr_count} NMRResults entries.")
             updated_count += updated_nmr_count

    # 3. Backfill ScalarResults calculated fields (yields)
    # Fetch Scalar results, ensuring related NMR data and conditions are loaded for yield calculation
    scalar_results_to_update = db.query(ScalarResults).options(
        joinedload(ScalarResults.result_entry).joinedload(ExperimentalResults.nmr_data),
        joinedload(ScalarResults.result_entry).joinedload(ExperimentalResults.experiment).joinedload(Experiment.conditions)
    ).all()
    
    updated_scalar_count = 0
    if scalar_results_to_update:
        print(f"Checking {len(scalar_results_to_update)} ScalarResults entries for potential updates...")
        for scalar_result in scalar_results_to_update:
            # Store original values
            original_g_per_ton = scalar_result.grams_per_ton_yield
            # original_fe_yield = scalar_result.ferrous_iron_yield # If/when calculated
            scalar_result.calculate_yields() # Recalculate
            # Check if g_per_ton changed (and potentially fe_yield later)
            if scalar_result.grams_per_ton_yield != original_g_per_ton: # or scalar_result.ferrous_iron_yield != original_fe_yield:
                updated_scalar_count += 1
                # No need to explicitly add
        if updated_scalar_count > 0:
            print(f"Recalculated yields for {updated_scalar_count} ScalarResults entries.")
            updated_count += updated_scalar_count

    # Commit changes if any updates were made
    if updated_count > 0:
        print(f"Committing {updated_count} total updates...")
        db.commit()
        print("Backfill commit successful.")
    else:
        print("No calculated fields needed updating.")

    print("Backfill process finished.")

# --- How to run this --- #
# This function needs to be called from a script or an admin interface.
# Example (in a separate script like scripts/run_backfill.py):
#
# from sqlalchemy.orm import Session
# from database.database import SessionLocal
# from frontend.components.utils import backfill_calculated_fields
#
# if __name__ == "__main__":
#     db: Session = SessionLocal()
#     try:
#         print("Running database calculation backfill...")
#         backfill_calculated_fields(db)
#         print("Backfill complete.")
#     except Exception as e:
#         print(f"An error occurred during backfill: {e}")
#         db.rollback() # Rollback in case of error during commit
#     finally:
#         print("Closing database session.")
#         db.close()

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Run the duplicate checks
    # check_experiment_duplicates()
    # Run the sample duplicate removal if needed
    # remove_duplicate_samples()
    # Clean external analyses if needed
    clean_external_analyses()