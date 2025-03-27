def build_conditions(REQUIRED_DEFAULTS, OPTIONAL_FIELDS, data, experiment_id):
    # Merge defaults
    merged = {**REQUIRED_DEFAULTS, **OPTIONAL_FIELDS}
    # Override with values provided in 'data'
    merged.update({key: data.get(key, default) for key, default in merged.items()})
    # Add experiment_id for the relationship
    merged['experiment_id'] = experiment_id
    return merged