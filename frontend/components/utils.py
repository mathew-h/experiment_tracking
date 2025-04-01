from frontend.config.variable_config import (
    REQUIRED_DEFAULTS,
    OPTIONAL_FIELDS,
    VALUE_LABELS,
)
import os
import streamlit as st
from database.models import ModificationsLog
import json # Added for JSON serialization in logging
import datetime # Added for timestamp in logging

def get_condition_display_dict(conditions):
    """
    Build a display dictionary for experimental conditions.
    
    This function takes a dictionary of experimental conditions and formats them for display.
    It uses REQUIRED_DEFAULTS and OPTIONAL_FIELDS to determine which fields to include
    and how to format them.
    
    Args:
        conditions (dict): Dictionary containing experimental conditions
        
    Returns:
        dict: Formatted display dictionary with friendly labels and formatted values
    """
    display_dict = {}
    # Combine both required and optional defaults to get all possible fields
    combined_defaults = {**REQUIRED_DEFAULTS, **OPTIONAL_FIELDS}
    
    for field, default in combined_defaults.items():
        # Get the friendly label from VALUE_LABELS, fallback to field name if not found
        label = VALUE_LABELS.get(field, field)
        value = conditions.get(field)
        
        # Handle empty or None values
        if value is None or (isinstance(value, str) and not value.strip()):
            display_value = "N/A"
        else:
            # Format numeric values with 2 decimal places if default is float
            if isinstance(default, float) and isinstance(value, (int, float)):
                display_value = f"{float(value):.2f}"
            else:
                display_value = str(value)
        
        display_dict[label] = display_value
    return display_dict

def split_conditions_for_display(conditions):
    """
    Splits conditions into required and optional fields for display purposes.
    
    This function uses get_condition_display_dict to format all conditions,
    then separates them into required and optional fields based on REQUIRED_DEFAULTS.
    
    Args:
        conditions (dict): Dictionary containing experimental conditions
        
    Returns:
        tuple: (required_fields, optional_fields) - Two dictionaries containing formatted values
    """
    # Get formatted display dictionary for all conditions
    display_dict = get_condition_display_dict(conditions)
    
    # Create set of required field labels using REQUIRED_DEFAULTS keys
    required_labels = {VALUE_LABELS.get(field, field) for field in REQUIRED_DEFAULTS.keys()}
    
    # Split display dictionary into required and optional fields
    required_fields = {label: value for label, value in display_dict.items() if label in required_labels}
    optional_fields = {label: value for label, value in display_dict.items() if label not in required_labels}
    
    return required_fields, optional_fields

def build_conditions(REQUIRED_DEFAULTS, OPTIONAL_FIELDS, data, experiment_id):
    """
    Builds a complete conditions dictionary for an experiment.
    
    This function merges default values with provided data and adds the experiment_id.
    It's used when creating or updating experimental conditions.
    
    Args:
        REQUIRED_DEFAULTS (dict): Dictionary of required default values
        OPTIONAL_FIELDS (dict): Dictionary of optional default values
        data (dict): Dictionary containing actual values to use
        experiment_id (int): ID of the experiment these conditions belong to
        
    Returns:
        dict: Complete conditions dictionary ready for database storage
    """
    # Merge defaults
    merged = {**REQUIRED_DEFAULTS, **OPTIONAL_FIELDS}
    # Override with values provided in 'data'
    merged.update({key: data.get(key, default) for key, default in merged.items()})
    # Add experiment_id for the relationship
    merged['experiment_id'] = experiment_id
    return merged

# --- File Handling Utilities ---

def get_upload_dir(base_dir_name):
    """
    Constructs the path to an upload directory and ensures it exists.
    
    Args:
        base_dir_name (str): The name of the subdirectory within 'uploads' (e.g., 'sample_photos').
        
    Returns:
        str: The absolute path to the upload directory.
    """
    # Assumes utils.py is in frontend/components
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    upload_dir = os.path.join(project_root, 'uploads', base_dir_name)
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir

def save_uploaded_file(file, base_dir_name, filename_prefix):
    """
    Saves an uploaded file to the specified directory.
    
    Args:
        file (UploadedFile): The Streamlit uploaded file object.
        base_dir_name (str): The name of the subdirectory within 'uploads'.
        filename_prefix (str): A prefix to add to the filename (e.g., sample_id or experiment_id).
        
    Returns:
        str: The absolute path where the file was saved, or None if save failed.
    """
    if not file:
        return None
        
    try:
        upload_dir = get_upload_dir(base_dir_name)
        # Sanitize file name if needed (basic example)
        safe_filename = os.path.basename(file.name).replace(" ", "_") 
        file_path = os.path.join(upload_dir, f"{filename_prefix}_{safe_filename}")
        
        with open(file_path, 'wb') as f:
            f.write(file.getvalue())
        return file_path
    except Exception as e:
        st.error(f"Error saving file {file.name}: {str(e)}")
        return None

def delete_file_if_exists(file_path):
    """
    Deletes a file if it exists.
    
    Args:
        file_path (str): The absolute path to the file to delete.
        
    Returns:
        bool: True if the file was deleted or didn't exist, False if deletion failed.
    """
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            return True
        except OSError as e:
            st.warning(f"Could not delete file {file_path}: {e}")
            return False
    return True # File doesn't exist, so considered successful deletion

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
        current_value = current_data.get(field_name, config['default'])
        key = f"{key_prefix}_{field_name}"
        help_text = config.get('help')

        # Ensure numeric defaults are floats if step/format implies it
        # This helps prevent type errors with st.number_input
        if field_type == 'number' and isinstance(current_value, (int, float)):
             try:
                 # Attempt conversion based on format hint if available
                 if 'format' in config and '%' in config['format']:
                    # Basic check for float format
                    if any(f_char in config['format'] for f_char in ['f', 'e', 'g', 'E', 'G']):
                        current_value = float(current_value)
                 elif 'step' in config and isinstance(config['step'], float):
                    current_value = float(current_value)
             except (ValueError, TypeError):
                 # Fallback if conversion fails
                 current_value = float(config['default'])
        elif field_type == 'number' and current_value is None:
            current_value = float(config['default']) # Use float default if current is None


        if field_type == 'text':
            form_values[field_name] = st.text_input(
                label=label,
                value=str(current_value) if current_value is not None else '',
                key=key,
                help=help_text
            )
        elif field_type == 'number':
            # Ensure value is float for number input if step/min/max are floats
            try:
                # Handle None case specifically for number inputs
                display_value = float(current_value) if current_value is not None else float(config['default'])
            except (ValueError, TypeError):
                display_value = float(config['default'])
                
            form_values[field_name] = st.number_input(
                label=label,
                min_value=config.get('min_value'),
                max_value=config.get('max_value'),
                value=display_value,
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
        # Add more types (e.g., date, file_uploader) as needed
        else:
            st.warning(f"Unsupported field type '{field_type}' for field '{field_name}'. Skipping.")

    return form_values

# --- Modification Logging Utility ---

def log_modification(db, experiment_id, modified_table, modification_type, old_values=None, new_values=None):
    """
    Creates and adds a modification log entry to the database session.
    
    Args:
        db (Session): The SQLAlchemy database session.
        experiment_id (int or None): The ID of the related experiment (None for sample-level changes).
        modified_table (str): The name of the table that was modified.
        modification_type (str): Type of modification ('create', 'update', 'delete', 'add').
        old_values (dict, optional): Dictionary of values before the change (for update/delete).
        new_values (dict, optional): Dictionary of values after the change (for create/update/add).
    """
    try:
        # Get user identifier from session state
        user = st.session_state.get('user', {})
        user_identifier = user.get('email', 'Unknown User') if isinstance(user, dict) else 'Unknown User'
        
        # Serialize dicts to JSON strings if they exist
        old_values_json = json.dumps(old_values) if old_values else None
        new_values_json = json.dumps(new_values, default=str) if new_values else None # Use default=str for non-serializable types like datetime
            
        modification = ModificationsLog(
            experiment_id=experiment_id,
            modified_by=user_identifier,
            modification_type=modification_type,
            modified_table=modified_table,
            old_values=old_values_json,
            new_values=new_values_json,
            timestamp=datetime.datetime.now() # Add timestamp explicitly if needed
        )
        db.add(modification)
    except Exception as e:
        # Log the error but don't crash the main operation
        st.error(f"Error creating modification log: {str(e)}")