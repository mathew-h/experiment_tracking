"""
Configuration file containing all experiment-related constants and defaults.
"""

import os # Add os import if not present
import datetime # Make sure datetime is imported if needed for date default

# Path configuration
DATA_DIR = 'data'
PXRF_DATA_FILENAME = 'pXRF_data.xlsx'
PXRF_DATA_PATH = os.path.join(DATA_DIR, PXRF_DATA_FILENAME)

# Available experiment types
EXPERIMENT_TYPES = ['Serum', 'Autoclave', 'HPHT', 'Core Flood', 'Other']

# Available experiment statuses
EXPERIMENT_STATUSES = ['ONGOING', 'COMPLETED', 'CANCELLED']

# Available external analysis types
ANALYSIS_TYPES = ['pXRF', 'XRD', 'SEM', 'Elemental', 'Other', 'Magnetic Susceptibility']

# Feedstock types
FEEDSTOCK_TYPES = ['Nitrogen', 'Nitrate', 'Blank']

# Expected columns in the pXRF data file
PXRF_REQUIRED_COLUMNS = {'Reading No', 'Fe', 'Mg', 'Ni', 'Cu', 'Si', 'Co', 'Mo', 'Al'}
PXRF_ELEMENT_COLUMNS = PXRF_REQUIRED_COLUMNS - {'Reading No'}

# Configuration for rock sample form fields
ROCK_SAMPLE_CONFIG = {
    'sample_id': {
        'label': "Sample ID",
        'type': 'text',
        'required': True,
        'default': '',
        'help': "Enter a unique identifier for this rock sample (e.g., 20UM21)"
    },
    'description': {
        'label': "Sample Description (optional)",
        'type': 'text',
        'required': False,
        'default': '',
        'help': "Add any relevant details about the rock sample"
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
    'locality': {
        'label': "Locality (optional)",
        'type': 'text',
        'required': False,
        'default': '',
        'help': "Enter the specific locality where the sample was collected"
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
        'help': "Enter the latitude coordinate of the collection site (0.0 for unknown/unspecified location)"
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
        'help': "Enter the longitude coordinate of the collection site (0.0 for unknown/unspecified location)"
    },
    'rock_classification': {
        'label': "Rock Classification (optional)",
        'type': 'text',
        'required': False,
        'default': '',
        'help': "Enter the rock type/classification"
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
    'pxrf_reading_no': {
        'label': "pXRF Reading No(s)",
        'type': 'text',
        'default': '',
        'required': False, # Required conditionally in the UI, not always
        'help': "Enter the pXRF reading number(s). Can be integers separated by commas (e.g., 1, 2, 5)."
    },
    'magnetic_susceptibility': {
        'label': "Mag. Susc (1x10^-3)",
        'type': 'text',
        'default': '',
        'required': False,
        'help': "Enter the magnetic susceptibility value or range (e.g., 0.5-1). Units: 1x10^-3. Leave blank if not measured."
    },
    'description': {
        'label': "Description",
        'type': 'text_area',
        'default': '',
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
    'rock_mass': {
        'label': "Rock Mass (g)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.001,
        'format': "%.3f",
        'required': True,
        'help': "Enter the mass of the rock sample in grams."
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
        'step': 0.0001,
        'format': "%.4f",
        'required': True,
        'help': "Enter the mass of catalyst used in grams."
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

    # --- Optional Fields ---
    'particle_size': {
        'label': "Particle Size (μm)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the particle size in micrometers. Leave blank for control experiments with no rock added."
    },
    'water_to_rock_ratio': {
        'label': "Water to Rock Ratio",
        'default': 0.0,  # Simple default value instead of lambda
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "This is automatically calculated based on rock mass and water volume.",
        'readonly': True # Make this field read-only
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
        'help': "Enter the catalyst percentage relative to rock mass (optional).",
        'readonly': True
    },
    'catalyst_ppm': {
        'label': "Catalyst Concentration (ppm)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Calculated concentration of catalyst in the water (mg/L).",
        'readonly': True
    },
    'feedstock': {
        'label': "Feedstock Type",
        'type': 'select',
        'options': FEEDSTOCK_TYPES,
        'default': 'Nitrate',
        'required': True,
        'help': "Feedstock type. Valid values: Nitrogen, Nitrate, or Blank."
    },
    'buffer_system': {
        'label': "Buffer System",
        'default': '',
        'type': 'text',
        'required': False,
        'help': "Specify the buffer system used, if any (e.g., 'Phosphate', 'Tris')."
    },
    'buffer_concentration': {
        'label': "Buffer Concentration (M)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the buffer concentration in molar (M)."
    },
    'ammonium_chloride_concentration': {
        'label': "Ammonium Chloride Concentration (mM)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the ammonium chloride concentration in millimolar (mM)."
    },
    'initial_nitrate_concentration': {
        'label': "Initial Nitrate Concentration (mM)",
        'default': 50.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the initial nitrate concentration in millimolar (mM). Should be 50 for 'Nitrate' feedstock and 0 for 'Nitrogen' or 'Blank'."
    },
    'initial_dissolved_oxygen': {  # Renamed from 'dissolved_oxygen'
        'label': "Initial Dissolved Oxygen (ppm)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'max_value': 100.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the initial dissolved oxygen concentration in parts per million (ppm)."
    },
    'surfactant_type': {
        'label': "Surfactant Type",
        'default': '',
        'type': 'text',
        'required': False,
        'help': "Enter the type of surfactant used, if any."
    },
    'surfactant_concentration': {
        'label': "Surfactant Concentration (mM)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Enter the surfactant concentration in millimolar (mM)."
    },
    'stir_speed': {
        'label': "Stir Speed (RPM)",
        'type': 'number',
        'default': None,
        'min_value': 0.0,
        'step': 1.0,
        'format': "%.0f",
        'required': False,
        'help': "Stir speed in rotations per minute (RPM)."
    },
    'initial_conductivity': {
        'label': "Initial Conductivity (μS/cm)",
        'type': 'number',
        'default': None,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Initial conductivity measurement (microsiemens per centimeter)."
    },
    'initial_alkalinity': {
        'label': "Initial Alkalinity (mg/L CaCO₃)",
        'type': 'number',
        'default': None,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Initial alkalinity measurement (mg/L as CaCO₃)."
    },
    'room_temp_pressure': {  
        'label': "Pressure at Room Temperature (psi)",
        'default': 14.6959, # Standard atmospheric pressure
        'type': 'number',
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Specify the room temperature pressure in pounds per square inch (psi)."
    },
    'rxn_temp_pressure': {
        'label': "Pressure at Reaction Temperature (psi)",
        'type': 'number',
        'default': None,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Reaction temperature pressure (psi)."
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
    },
    'core_height': {
        'label': "Core Height (cm)",
        'type': 'number',
        'default': None,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Core height (in centimeters)."
    },
    'core_width': {
        'label': "Core Width (cm)",
        'type': 'number',
        'default': None,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Core width (in centimeters)."
    },
    'core_volume': {
        'label': "Core Volume (cm³)",
        'type': 'number',
        'default': None,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.2f",
        'required': False,
        'help': "Core volume (in cubic centimeters)."
    },
    'flow_rate': {
        'label': "Flow Rate (mL/min)",
        'default': 0.0,
        'type': 'number',
        'min_value': 0.0,
        'step': 0.001,
        'format': "%.3f",
        'required': False,
        'help': "Specify the flow rate in mL/min (for flow-through experiments)."
    },
}

# Configuration for experiment scalar results (formerly RESULTS_CONFIG)
SCALAR_RESULTS_CONFIG = {
    'solution_ammonium_concentration': {
        'label': "Solution Ammonium Concentration (mM)",
        'type': 'number',
        'default': 0.0,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the ammonium concentration in the solution in millimolar (mM)."
    },
    'final_ph': {
        'label': "Final pH",
        'type': 'number',
        'default': 0.0,
        'min_value': 0.0,
        'max_value': 14.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the final pH of the solution (if measured)."
    },
    'sampling_volume': {
        'label': "Sampling Volume (mL)",
        'type': 'number',
        'default': 0.0,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Sampling volume in milliliters."
    },
    'grams_per_ton_yield': {
        'label': "Yield (g NH3/ton rock)",
        'type': 'number',
        'default': 0.0,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the yield in grams per ton (if measured)."
    },
    'ferrous_iron_yield': {  
        'label': "Ferrous Iron Yield (%)",
        'type': 'number',
        'default': 0.0,
        'min_value': 0.0,
        'max_value': 100.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the ferrous iron yield as a percentage (if measured)."
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

    'final_nitrate_concentration': {
        'label': "Final Nitrate Concentration (mM)",
        'type': 'number',
        'default': 0.0,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Enter the final nitrate concentration in mM (if measured)."
    },
    'final_dissolved_oxygen': {
        'label': "Final Dissolved Oxygen (ppm)",
        'type': 'number',
        'default': 0.0,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Final dissolved oxygen concentration (ppm)."
    },
    'final_conductivity': {
        'label': "Final Conductivity (μS/cm)",
        'type': 'number',
        'default': 0.0,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Final conductivity measurement (microsiemens per centimeter)."
    },
    'final_alkalinity': {
        'label': "Final Alkalinity (mg/L CaCO₃)",
        'type': 'number',
        'default': 0.0,
        'min_value': 0.0,
        'step': 0.1,
        'format': "%.1f",
        'required': False,
        'help': "Final alkalinity measurement (mg/L as CaCO₃)."
    },
    'time_post_reaction': {
        'label': "Time Post-Reaction (hours)",
        'type': 'number',
        'required': True,
        'default': 0.0,
        'min_value': 0.0,
        'step': 0.5,
        'format': "%.1f",
        'help': "Enter the time elapsed in hours since the reaction started when these results were measured."
    }
} 