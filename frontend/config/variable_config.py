"""
Configuration file containing all experiment-related constants and defaults.
"""

import datetime # Make sure datetime is imported if needed for date default

# Available experiment types
EXPERIMENT_TYPES = ['Serum', 'Autoclave', 'HPHT', 'Core Flood']

# Available experiment statuses
EXPERIMENT_STATUSES = ['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED']

# Available external analysis types
ANALYSIS_TYPES = ['XRD', 'SEM', 'Elemental', 'Other']

# Configuration for rock sample form fields
ROCK_SAMPLE_CONFIG = {
    'sample_id': {
        'label': "Sample ID",
        'type': 'text',
        'required': True,
        'default': '',
        'help': "Enter a unique identifier for this rock sample (e.g., 20UM21)"
    },
    'rock_classification': {
        'label': "Rock Classification",
        'type': 'text',
        'required': True,
        'default': '',
        'help': "Enter the rock type/classification"
    },
    'state': {
        'label': "State/Province",
        'type': 'text',
        'required': True,
        'default': '',
        'help': "Enter the state or province where the sample was collected"
    },
    'country': {
        'label': "Country",
        'type': 'text',
        'required': True,
        'default': '',
        'help': "Enter the country where the sample was collected"
    },
    'latitude': {
        'label': "Latitude",
        'type': 'number',
        'required': True,
        'default': 0.0,
        'min_value': -90.0,
        'max_value': 90.0,
        'step': 0.000001,
        'format': "%.6f",
        'help': "Enter the latitude coordinate of the collection site"
    },
    'longitude': {
        'label': "Longitude",
        'type': 'number',
        'required': True,
        'default': 0.0,
        'min_value': -180.0,
        'max_value': 180.0,
        'step': 0.000001,
        'format': "%.6f",
        'help': "Enter the longitude coordinate of the collection site"
    },
    'description': {
        'label': "Sample Description",
        'type': 'text_area',
        'required': False,
        'default': '',
        'height': 100,
        'help': "Add any relevant details about the rock sample"
    }
}

# Configuration for external analysis form fields
EXTERNAL_ANALYSIS_CONFIG = {
    'analysis_type': {
        'label': "Analysis Type",
        'type': 'select',
        'options': ANALYSIS_TYPES,
        'default': ANALYSIS_TYPES[0] if ANALYSIS_TYPES else None, # Default to first option or None
        'required': True,
        'help': "Select the type of analysis performed"
    },
    'laboratory': {
        'label': "Laboratory",
        'type': 'text',
        'default': '', # Default to empty string
        'required': True,
        'help': "Enter the name of the laboratory performing the analysis"
    },
    'analyst': {
        'label': "Analyst",
        'type': 'text',
        'default': '', # Default to empty string
        'required': True,
        'help': "Enter the name of the analyst"
    },
    'analysis_date': {
        'label': "Analysis Date",
        'type': 'date',
        'default': None, # Default to None for date input
        'required': True,
        'help': "Select the date when the analysis was performed"
    },
    'description': {
        'label': "Description",
        'type': 'text_area',
        'default': '', # Default to empty string
        'required': False,
        'height': 100,
        'help': "Add a description of the analysis"
    }
}

# Configuration for experiment form fields
FIELD_CONFIG = {
    # --- Required Fields ---
    'experiment_type': {
        'label': "Experiment Type",
        'default': 'Serum',
        'type': 'select',
        'options': EXPERIMENT_TYPES, # Reference the list above
        'required': True,
        'help': "Select the type of experiment setup."
    },
    'particle_size': {
        'label': "Particle Size (μm)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': True,
        'help': "Enter the particle size in micrometers."
    },
    'initial_ph': {
        'label': "Initial pH",
        'default': 7.0,
        'type': 'number',
        'min_value': 0.0,
        'max_value': 14.0,
        'step': 0.1,
        'format': "%.1f",
        'required': True,
        'help': "Specify the starting pH of the solution."
    },
    'catalyst': {
        'label': "Catalyst",
        'default': '',
        'type': 'text',
        'required': True,
        'help': "Enter the catalyst used (e.g., 'Fe', 'Ni/Al2O3'). Leave blank if none."
    },
    'catalyst_mass': {
        'label': "Catalyst Mass (g)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.00001,
        'format': "%.5f",
        'required': True,
        'help': "Enter the mass of catalyst used in grams."
    },
     'rock_mass': {
        'label': "Rock Mass (g)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.000001,
        'format': "%.6f",
        'required': True,
        'help': "Enter the mass of the rock sample in grams."
    },
    'water_volume': {
        'label': "Water Volume (mL)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': True,
        'help': "Enter the volume of water used in milliliters."
    },
    'temperature': {
        'label': "Temperature (°C)",
        'default': 25.0,
        'type': 'number',
        'min_value': -273.15, # Absolute zero
        'step': 1.0,
        'format': "%.1f",
        'required': True,
        'help': "Specify the experiment temperature in Celsius."
    },
    'pressure': {
        'label': "Pressure (psi)",
        'default': 14.6959, # Standard atmospheric pressure
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': True,
        'help': "Specify the experiment pressure in pounds per square inch (psi)."
    },

    # --- Optional Fields ---
    'water_to_rock_ratio': {
        'label': "Water to Rock Ratio",
        'default': 0.0, # Consider if a different default makes sense, or calculate based on rock_mass/water_volume?
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Enter the mass ratio of water to rock (optional)."
    },
    'catalyst_percentage': {
        'label': "Catalyst Percentage (%)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'max_value': 100.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the catalyst percentage relative to rock mass (optional)."
    },
    'buffer_system': {
        'label': "Buffer System",
        'default': '',
        'type': 'text',
        'required': False,
        'help': "Specify the buffer system used, if any (e.g., 'Phosphate', 'Tris')."
    },
    'buffer_concentration': {
        'label': "Buffer Concentration (mM)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the buffer concentration in millimolar (mM)."
    },
    'flow_rate': {
        'label': "Flow Rate (mL/min)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Specify the flow rate in mL/min (for flow-through experiments)."
    },
    'initial_nitrate_concentration': {
        'label': "Initial Nitrate Concentration (mM)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the initial nitrate concentration in millimolar (mM)."
    },
    'dissolved_oxygen': {
        'label': "Dissolved Oxygen (ppm)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Specify the dissolved oxygen level in parts per million (ppm)."
    },
     'surfactant_type': {
        'label': "Surfactant Type",
        'default': '',
        'type': 'text',
        'required': False,
        'help': "Enter the type of surfactant used, if any."
    },
    'surfactant_concentration': {
        'label': "Surfactant Concentration",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f", # Assuming potentially smaller concentrations
        'required': False,
        'help': "Enter the surfactant concentration (units depend on type)."
    },
    'dissolved_oxygen': {
        'label': "Dissolved Oxygen (ppm)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'max_value': 100.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the dissolved oxygen concentration in parts per million (ppm)."
    },
    'co2_partial_pressure': {
        'label': "CO2 Partial Pressure (psi)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Specify the partial pressure of CO2 in psi (for relevant experiments)."
    },
    'confining_pressure': {
        'label': "Confining Pressure (psi)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Specify the confining pressure in psi (for core flood/HPHT)."
    },
    'pore_pressure': {
        'label': "Pore Pressure (psi)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Specify the pore pressure in psi (for core flood/HPHT)."
    }
}

# Configuration for basic experiment results fields
RESULTS_CONFIG = {
    'final_ph': {
        'label': "Final pH",
        'type': 'number',
        'required': False, # Assuming results might not always be complete
        'default': None, # Use None as default, handle in form logic
        'min_value': 0.0,
        'max_value': 14.0,
        'step': 0.1,
        'format': "%.1f",
        'help': "Enter the final pH of the solution (if measured)."
    },
    'final_nitrate_concentration': {
        'label': "Final Nitrate Concentration (mM)",
        'type': 'number',
        'required': False,
        'default': None,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'help': "Enter the final nitrate concentration in mM (if measured)."
    },
    'yield_value': {
        'label': "Yield Value (%)", # Assuming this is Ammonia Yield, adjust label if needed
        'type': 'number',
        'required': False,
        'default': None,
        'min_value': 0.0,
        'max_value': 100.0, # Or remove max_value if yield can exceed 100
        'step': 0.1,
        'format': "%.1f",
        'help': "Enter the yield value as a percentage (if measured)."
    },
    'time_post_reaction': {
        'label': "Time Post-Reaction (hours)",
        'type': 'number',
        'required': True, # Make this required for new entries
        'default': 0.0,
        'min_value': 0.0,
        'step': 0.5,
        'format': "%.1f",
        'help': "Enter the time elapsed in hours since the reaction started when these results were measured."
    }
} 