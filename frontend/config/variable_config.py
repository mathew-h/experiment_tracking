"""
Configuration file containing all experiment-related constants and defaults.
"""

# Available experiment types
EXPERIMENT_TYPES = ['Serum', 'Autoclave', 'HPHT', 'Core Flood']

# Available experiment statuses
EXPERIMENT_STATUSES = ['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED']

# Available external analysis types
ANALYSIS_TYPES = ['XRD', 'SEM', 'Elemental', 'Other']

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
        'step': 0.000001,
        'format': "%.6f",
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