from frontend.config.variable_config import (
    REQUIRED_DEFAULTS,
    OPTIONAL_FIELDS,
    VALUE_LABELS,
)

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