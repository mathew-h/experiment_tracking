"""
Configuration file containing all experiment-related constants and defaults.
"""

# Default values for required experiment fields
REQUIRED_DEFAULTS = {
    'particle_size': 0.0,
    'initial_ph': 7.0,
    'catalyst': '',
    'catalyst_mass': 0.0,
    'rock_mass': 0.0,
    'water_volume': 0.0,
    'temperature': 25.0,
    'pressure': 14.6959,
    'experiment_type': 'Serum',
}

# Default values for optional experiment fields
OPTIONAL_FIELDS = {
    'water_to_rock_ratio': 0.0,
    'surfactant_type': '',
    'catalyst_percentage': 0.0,
    'flow_rate': 0.0,
    'initial_nitrate_concentration': 0.0,
    'dissolved_oxygen': 0.0,
    'surfactant_concentration': 0.0,
    'buffer_concentration': 0.0,
    'co2_partial_pressure': 0.0,
    'confining_pressure': 0.0,
    'pore_pressure': 0.0,
    'buffer_system': '' 
}

# Human-readable labels for all experiment fields
VALUE_LABELS = {
    'experiment_type': "Experiment Type",
    'particle_size': "Particle Size (μm)",
    'initial_ph': "Initial pH",
    'catalyst': "Catalyst",
    'catalyst_mass': "Catalyst Mass (g)",
    'rock_mass': "Rock Mass (g)",
    'water_volume': "Water Volume (mL)",
    'temperature': "Temperature (°C)",
    'pressure': "Pressure (psi)",
    'water_to_rock_ratio': "Water to Rock Ratio",
    'catalyst_percentage': "Catalyst Percentage (%)",
    'buffer_system': "Buffer System",
    'buffer_concentration': "Buffer Concentration (mM)",
    'flow_rate': "Flow Rate (mL/min)",
    'initial_nitrate_concentration': "Initial Nitrate Concentration (mM)",
    'dissolved_oxygen': "Dissolved Oxygen (ppm)",
    'surfactant_type': "Surfactant Type",
    'surfactant_concentration': "Surfactant Concentration",
    'co2_partial_pressure': "CO2 Partial Pressure (psi)",
    'confining_pressure': "Confining Pressure (psi)",
    'pore_pressure': "Pore Pressure (psi)"
}

# Available experiment types
EXPERIMENT_TYPES = ['Serum', 'Autoclave', 'HPHT', 'Core Flood']

# Available experiment statuses
EXPERIMENT_STATUSES = ['PLANNED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED'] 