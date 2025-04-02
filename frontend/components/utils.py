from frontend.config.variable_config import (
    FIELD_CONFIG,
)
import os
import streamlit as st
from database.models import ModificationsLog
import json # Added for JSON serialization in logging
import datetime # Added for timestamp in logging and date input

def get_condition_display_dict(conditions):
    """
    Build a display dictionary for experimental conditions.
    
    This function takes a dictionary of experimental conditions and formats 
    them for display using the FIELD_CONFIG.
    
    Args:
        conditions (dict): Dictionary containing experimental conditions
        
    Returns:
        dict: Formatted display dictionary with friendly labels and formatted values
    """
    display_dict = {}
    for field_name, config in FIELD_CONFIG.items():
        label = config['label']
        value = conditions.get(field_name)
        
        # Handle empty or None values
        if value is None or (isinstance(value, str) and not value.strip()):
            display_value = "N/A"
        else:
            # Use format string from config if available for numbers
            if config['type'] == 'number' and config.get('format') and isinstance(value, (int, float)):
                try:
                    display_value = config['format'] % float(value)
                except (ValueError, TypeError):
                    display_value = str(value) # Fallback to string if format fails
            else:
                display_value = str(value)
        
        display_dict[label] = display_value
    return display_dict

def split_conditions_for_display(conditions):
    """
    Splits conditions into required and optional fields for display purposes.
    
    Uses get_condition_display_dict to format conditions based on FIELD_CONFIG,
    then separates them using the 'required' flag in the config.
    
    Args:
        conditions (dict): Dictionary containing experimental conditions
        
    Returns:
        tuple: (required_fields, optional_fields) - Two dictionaries containing formatted values
    """
    required_fields = {}
    optional_fields = {}

    for field_name, config in FIELD_CONFIG.items():
        label = config['label']
        value = conditions.get(field_name)

        # Format the value for display (similar logic as get_condition_display_dict)
        if value is None or (isinstance(value, str) and not value.strip()):
            display_value = "N/A"
        else:
            if config['type'] == 'number' and config.get('format') and isinstance(value, (int, float)):
                try:
                    display_value = config['format'] % float(value)
                except (ValueError, TypeError):
                    display_value = str(value)
            else:
                display_value = str(value)

        # Assign to the correct dictionary based on the 'required' flag
        if config.get('required', False):
            required_fields[label] = display_value
        else:
            optional_fields[label] = display_value

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

# --- Cloud Storage Abstraction ---
class FileStorage:
    """
    Abstract file storage interface that supports both local and cloud storage.
    """
    def __init__(self, storage_type='local', **kwargs):
        """
        Initialize the storage backend.
        
        Args:
            storage_type (str): Type of storage ('local', 's3', 'gcs', 'azure')
            **kwargs: Additional configuration for the specific storage type
        """
        self.storage_type = storage_type
        self.config = kwargs
        
    def get_upload_path(self, base_dir_name):
        """
        Get the appropriate upload path for the storage type.
        """
        if self.storage_type == 'local':
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            upload_dir = os.path.join(project_root, 'uploads', base_dir_name)
            os.makedirs(upload_dir, exist_ok=True)
            return upload_dir
        else:
            # For cloud storage, return the virtual path
            return f"{base_dir_name}/"
            
    def save_file(self, file, base_dir_name, filename_prefix):
        """
        Save a file using the appropriate storage backend.
        """
        if self.storage_type == 'local':
            return self._save_local(file, base_dir_name, filename_prefix)
        elif self.storage_type == 's3':
            return self._save_s3(file, base_dir_name, filename_prefix)
        elif self.storage_type == 'gcs':
            return self._save_gcs(file, base_dir_name, filename_prefix)
        elif self.storage_type == 'azure':
            return self._save_azure(file, base_dir_name, filename_prefix)
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
            
    def delete_file(self, file_path):
        """
        Delete a file using the appropriate storage backend.
        """
        if self.storage_type == 'local':
            return self._delete_local(file_path)
        elif self.storage_type == 's3':
            return self._delete_s3(file_path)
        elif self.storage_type == 'gcs':
            return self._delete_gcs(file_path)
        elif self.storage_type == 'azure':
            return self._delete_azure(file_path)
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")
            
    def _save_local(self, file, base_dir_name, filename_prefix):
        """Local filesystem implementation"""
        if not file:
            return None
            
        try:
            upload_dir = self.get_upload_path(base_dir_name)
            safe_filename = os.path.basename(file.name).replace(" ", "_")
            file_path = os.path.join(upload_dir, f"{filename_prefix}_{safe_filename}")
            
            with open(file_path, 'wb') as f:
                f.write(file.getvalue())
            return file_path
        except Exception as e:
            st.error(f"Error saving file {file.name}: {str(e)}")
            return None
            
    def _delete_local(self, file_path):
        """Local filesystem implementation"""
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                return True
            except OSError as e:
                st.warning(f"Could not delete file {file_path}: {e}")
                return False
        return True
        
    def _save_s3(self, file, base_dir_name, filename_prefix):
        """AWS S3 implementation"""
        # TODO: Implement S3 storage
        raise NotImplementedError("S3 storage not yet implemented")
        
    def _delete_s3(self, file_path):
        """AWS S3 implementation"""
        # TODO: Implement S3 deletion
        raise NotImplementedError("S3 deletion not yet implemented")
        
    def _save_gcs(self, file, base_dir_name, filename_prefix):
        """Google Cloud Storage implementation"""
        # TODO: Implement GCS storage
        raise NotImplementedError("GCS storage not yet implemented")
        
    def _delete_gcs(self, file_path):
        """Google Cloud Storage implementation"""
        # TODO: Implement GCS deletion
        raise NotImplementedError("GCS deletion not yet implemented")
        
    def _save_azure(self, file, base_dir_name, filename_prefix):
        """Azure Blob Storage implementation"""
        # TODO: Implement Azure storage
        raise NotImplementedError("Azure storage not yet implemented")
        
    def _delete_azure(self, file_path):
        """Azure Blob Storage implementation"""
        # TODO: Implement Azure deletion
        raise NotImplementedError("Azure deletion not yet implemented")

# Initialize the file storage with default local storage
file_storage = FileStorage()

# Update the existing functions to use the FileStorage class
def get_upload_dir(base_dir_name):
    """
    Constructs the path to an upload directory and ensures it exists.
    """
    return file_storage.get_upload_path(base_dir_name)

def save_uploaded_file(file, base_dir_name, filename_prefix):
    """
    Saves an uploaded file using the configured storage backend.
    """
    return file_storage.save_file(file, base_dir_name, filename_prefix)

def delete_file_if_exists(file_path):
    """
    Deletes a file using the configured storage backend.
    """
    return file_storage.delete_file(file_path)

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

        # Handle numeric fields with None values
        if field_type == 'number':
            try:
                # If current_value is None, use 0.0 as default
                if current_value is None:
                    current_value = 0.0
                # Convert to float if it's a string or number
                current_value = float(current_value)
            except (ValueError, TypeError):
                # If conversion fails, use 0.0 as fallback
                current_value = 0.0

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
            new_values=new_values_json
        )
        db.add(modification)
    except Exception as e:
        # Log the error but don't crash the main operation
        st.error(f"Error creating modification log: {str(e)}")