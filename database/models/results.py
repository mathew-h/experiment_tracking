from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from typing import Dict
from ..database import Base

class ExperimentalResults(Base):
    __tablename__ = "experimental_results"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String, nullable=False, index=True)
    experiment_fk = Column(Integer,
                           ForeignKey("experiments.id", ondelete="CASCADE"),
                           nullable=False)
    time_post_reaction = Column(Float, nullable=False, index=True) # Time in days post-reaction start
    description = Column(Text, nullable=False) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    experiment = relationship("Experiment", back_populates="results", foreign_keys=[experiment_fk])
    # Relationship to ResultFiles (one-to-many)
    files = relationship("ResultFiles", back_populates="result_entry", cascade="all, delete-orphan")

    # Relationships to specific data tables (one-to-one)
    scalar_data = relationship(
        "ScalarResults",
        back_populates="result_entry",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    icp_data = relationship(
        "ICPResults",
        back_populates="result_entry",
        uselist=False,
        cascade="all, delete-orphan"
    )

    # Add a unique constraint on experiment_fk and time_post_reaction
    __table_args__ = (
        UniqueConstraint('experiment_fk', 'time_post_reaction', name='uix_experiment_time'),
    )

class ScalarResults(Base):
    __tablename__ = "scalar_results"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("experimental_results.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Scalar fields
    ferrous_iron_yield = Column(Float, nullable=True)  # in percentage
    solution_ammonium_concentration = Column(Float, nullable=True)  # in mM
    ammonium_quant_method = Column(String, nullable=True) # e.g., 'NMR', 'Colorimetric Assay'
    grams_per_ton_yield = Column(Float, nullable=True)  # yield in g/ton
    final_ph = Column(Float, nullable=True)
    final_nitrate_concentration = Column(Float, nullable=True)  # in mM
    final_dissolved_oxygen = Column(Float, nullable=True) # in ppm
    co2_partial_pressure = Column(Float, nullable=True) # in psi
    final_conductivity = Column(Float, nullable=True) # in uS/cm
    final_alkalinity = Column(Float, nullable=True) # in mg/L CaCO3
    sampling_volume = Column(Float, nullable=True) # in mL

    # Hydrogen tracking inputs
    h2_concentration = Column(Float, nullable=True)  # % (vol) or ppm
    h2_concentration_unit = Column(String, nullable=True)  # '%' or 'ppm'
    gas_sampling_volume_ml = Column(Float, nullable=True)  # mL at sampling conditions
    gas_sampling_pressure = Column(Float, nullable=True)  # psi at sampling conditions

    # Hydrogen derived outputs (stored as microunits per requirements)
    h2_moles = Column(Float, nullable=True)  # micromoles (μmol)
    h2_mass_g = Column(Float, nullable=True)  # micrograms (μg)

    # Relationship back to the main entry using result_id
    result_entry = relationship(
        "ExperimentalResults",
        back_populates="scalar_data",
    )

    def calculate_yields(self):
        """Calculate and update the yield values based on solution concentration and experimental conditions."""
        # Ensure necessary parent relationships exist
        if not self.result_entry or not self.result_entry.experiment or not self.result_entry.experiment.conditions:
            self.grams_per_ton_yield = None
            # Still try hydrogen calc which uses only scalar inputs and user-provided pressure
            self.calculate_hydrogen()
            return

        rock_mass = self.result_entry.experiment.conditions.rock_mass
        water_volume_ml = self.result_entry.experiment.conditions.water_volume
        
        ammonia_mass_g = None
        if self.solution_ammonium_concentration is not None and water_volume_ml is not None and water_volume_ml > 0:
            # Molar mass of NH4+ is ~18.04 g/mol
            ammonia_mass_g = (
                (self.solution_ammonium_concentration / 1000) *  # Convert mM to M (mol/L)
                (water_volume_ml / 1000) *  # Convert mL to L
                18.04  # Molar mass of NH4+ (g/mol)
            )

        # Calculate grams_per_ton_yield
        if (ammonia_mass_g is not None and
            rock_mass is not None and
            rock_mass > 0):

            # Convert to g/ton using rock mass in grams
            # 1 ton = 1,000,000 grams
            self.grams_per_ton_yield = 1_000_000 * (ammonia_mass_g / rock_mass)
        else:
            # Set to None if required data is missing or invalid
            self.grams_per_ton_yield = None

        # Hydrogen calculations (PV = nRT at 25°C, pressure required)
        self.calculate_hydrogen()

        # TODO: Calculate ferrous_iron_yield when the calculation method is determined
        # Example: Check if specific inputs for Fe yield are present
        # if required_input_for_fe_yield is not None:
        #    self.ferrous_iron_yield = ... calculation ...
        # else:
        #    self.ferrous_iron_yield = None # Or leave as is if manually entered

    @validates('h2_concentration', 'gas_sampling_volume_ml', 'gas_sampling_pressure')
    def validate_non_negative(self, key, value):
        if value is not None and value < 0:
            raise ValueError(f"{key} must be non-negative.")
        return value

    @validates('h2_concentration_unit')
    def validate_h2_unit(self, key, value):
        if value is None:
            return value
        allowed = ['%', 'ppm']
        if value not in allowed:
            raise ValueError(f"h2_concentration_unit must be one of {allowed}")
        return value

    def calculate_hydrogen(self):
        """
        Calculate hydrogen amount from gas concentration and sample volume using PV = nRT.
        Assumptions:
        - Temperature fixed at 25°C (298.15 K)
        - Pressure must be provided by user in psi; converted to atm
        - Volume provided in mL; converted to L
        Stores:
        - h2_moles as micromoles (μmol)
        - h2_mass_g as micrograms (μg)
        """
        # Validate required inputs
        if (
            self.h2_concentration is None or
            self.h2_concentration_unit is None or
            self.gas_sampling_volume_ml is None or self.gas_sampling_volume_ml <= 0 or
            self.gas_sampling_pressure is None or self.gas_sampling_pressure <= 0
        ):
            self.h2_moles = None
            self.h2_mass_g = None
            return

        # Constants
        R = 0.082057  # L·atm/(mol·K)
        T_K = 298.15  # 25°C fixed
        P_atm = self.gas_sampling_pressure / 14.6959  # psi -> atm

        if P_atm <= 0:
            self.h2_moles = None
            self.h2_mass_g = None
            return

        V_L = self.gas_sampling_volume_ml / 1000.0

        # Total moles of gas in the sample
        try:
            total_moles = (P_atm * V_L) / (R * T_K)
        except ZeroDivisionError:
            self.h2_moles = None
            self.h2_mass_g = None
            return

        # Convert concentration to fraction
        unit = (self.h2_concentration_unit or '').lower()
        if unit == '%':
            fraction = self.h2_concentration / 100.0
        elif unit == 'ppm':
            fraction = self.h2_concentration / 1_000_000.0
        else:
            self.h2_moles = None
            self.h2_mass_g = None
            return

        if fraction is None or fraction < 0:
            self.h2_moles = None
            self.h2_mass_g = None
            return

        h2_moles = total_moles * fraction

        # Store in microunits per requirements
        h2_micromoles = h2_moles * 1_000_000.0
        h2_micrograms = h2_moles * 2.01588 * 1_000_000.0  # g/mol * mol -> g, then g to μg

        self.h2_moles = h2_micromoles
        self.h2_mass_g = h2_micrograms

class ICPResults(Base):
    __tablename__ = "icp_results"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("experimental_results.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Fixed columns for common elements (all concentrations in ppm)
    fe = Column(Float, nullable=True)   # Iron
    si = Column(Float, nullable=True)   # Silicon
    ni = Column(Float, nullable=True)   # Nickel
    cu = Column(Float, nullable=True)   # Copper
    mo = Column(Float, nullable=True)   # Molybdenum
    zn = Column(Float, nullable=True)   # Zinc
    mn = Column(Float, nullable=True)   # Manganese
    cr = Column(Float, nullable=True)   # Chromium
    co = Column(Float, nullable=True)   # Cobalt
    mg = Column(Float, nullable=True)   # Magnesium
    al = Column(Float, nullable=True)   # Aluminum

    # JSON storage for all elements (including the fixed ones above for completeness)
    all_elements = Column(JSON, nullable=True)  # e.g., {"fe": 125.0, "mg": 45.8, "ca": 12.3, "k": 8.9}
    
    # ICP-specific metadata
    dilution_factor = Column(Float, nullable=True)
    analysis_date = Column(DateTime(timezone=True), nullable=True)
    instrument_used = Column(String, nullable=True)
    detection_limits = Column(JSON, nullable=True)  # Store per-element detection limits
    raw_label = Column(String, nullable=True)  # Original sample label from ICP file
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship back to the main entry using result_id
    result_entry = relationship(
        "ExperimentalResults",
        back_populates="icp_data",
    )

    @validates('all_elements', 'detection_limits')
    def validate_json(self, key, value):
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"{key} must be a valid JSON object.")
        return value

    def get_element_concentration(self, element_symbol: str) -> float:
        """
        Get concentration for any element, checking fixed columns first, then JSON.
        
        Args:
            element_symbol: Element symbol (e.g., 'Fe', 'Mg', 'Ca')
            
        Returns:
            Concentration in ppm, or 0 if not found
        """
        element_lower = element_symbol.lower()
        
        # Check fixed columns first (faster)
        if hasattr(self, element_lower):
            value = getattr(self, element_lower)
            if value is not None:
                return value
        
        # Check JSON storage
        if self.all_elements and isinstance(self.all_elements, dict):
            return self.all_elements.get(element_lower, 0)
        
        return 0

    def get_all_detected_elements(self) -> Dict[str, float]:
        """
        Get all detected elements with their concentrations.
        
        Returns:
            Dictionary of {element: concentration_ppm}
        """
        elements = {}
        
        # Add fixed columns
        fixed_elements = ['fe', 'si', 'ni', 'cu', 'mo', 'zn', 'mn', 'cr', 'co', 'mg', 'al']
        for element in fixed_elements:
            value = getattr(self, element)
            if value is not None:
                elements[element] = value
        
        # Add JSON elements (may override fixed columns with same values)
        if self.all_elements and isinstance(self.all_elements, dict):
            elements.update(self.all_elements)
        
        return elements

class ResultFiles(Base):
    __tablename__ = "result_files"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("experimental_results.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String, nullable=False)
    file_name = Column(String)
    file_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to the specific result entry
    result_entry = relationship("ExperimentalResults", back_populates="files")
