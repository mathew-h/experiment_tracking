from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey, Enum as SQLEnum, Text, UniqueConstraint, and_
from sqlalchemy.orm import relationship, foreign
from sqlalchemy.sql import func
import enum
from .database import Base

class ExperimentStatus(enum.Enum):
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String, unique=True, nullable=False, index=True)  # User-defined experiment identifier
    experiment_number = Column(Integer, unique=True, nullable=False)  # Auto-incrementing number
    sample_id = Column(String, ForeignKey("sample_info.sample_id", ondelete="SET NULL"), nullable=True) # Foreign key to SampleInfo, SET NULL on delete
    researcher = Column(String)
    date = Column(DateTime(timezone=True))
    status = Column(SQLEnum(ExperimentStatus))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    conditions = relationship("ExperimentalConditions", back_populates="experiment", uselist=False, cascade="all, delete-orphan")
    notes = relationship("ExperimentNotes", back_populates="experiment", cascade="all, delete-orphan")
    modifications = relationship("ModificationsLog", back_populates="experiment", cascade="all, delete-orphan")
    results = relationship("ExperimentalResults", back_populates="experiment", foreign_keys="[ExperimentalResults.experiment_fk]", cascade="all, delete-orphan")
    sample_info = relationship("SampleInfo", back_populates="experiments", foreign_keys=[sample_id])

class ExperimentalConditions(Base):
    __tablename__ = "experimental_conditions"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String, nullable=False, index=True) # Human-readable ID
    experiment_fk = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False) # FK to Experiment PK
    particle_size = Column(Float)
    initial_ph = Column(Float)
    catalyst = Column(String)
    catalyst_mass = Column(Float)
    rock_mass = Column(Float)
    water_volume = Column(Float)
    temperature = Column(Float)
    buffer_system = Column(String, nullable=True)
    water_to_rock_ratio = Column(Float, nullable=True)
    catalyst_percentage = Column(Float, nullable=True)
    catalyst_ppm = Column(Float, nullable=True)
    buffer_concentration = Column(Float, nullable=True)  # in mM
    room_temp_pressure = Column(Float, nullable=True)  # in psi instead of bar
    flow_rate = Column(Float, nullable=True)
    experiment_type = Column(String)  # Serum, Autoclave, HPHT, Core Flood
    initial_nitrate_concentration = Column(Float, nullable=True)  # in mM, optional
    initial_dissolved_oxygen = Column(Float, nullable=True)  # in ppm, optional
    surfactant_type = Column(String, nullable=True)  # optional
    surfactant_concentration = Column(Float, nullable=True)  # optional
    co2_partial_pressure = Column(Float, nullable=True)  # in psi, optional
    confining_pressure = Column(Float, nullable=True)  # optional
    pore_pressure = Column(Float, nullable=True)  # optional
    ammonium_chloride_concentration = Column(Float, nullable=True)  # optional
    rxn_temp_pressure = Column(Float, nullable=True)
    core_height = Column(Float, nullable=True)
    core_width = Column(Float, nullable=True)
    core_volume = Column(Float, nullable=True)
    stir_speed = Column(Float, nullable=True)
    initial_conductivity = Column(Float, nullable=True)
    initial_alkalinity = Column(Float, nullable=True)
    feedstock = Column(String, nullable=True)  # Valid values: "Nitrogen", "Nitrate", "Blank"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    experiment = relationship("Experiment", back_populates="conditions", foreign_keys=[experiment_fk])

    def calculate_derived_conditions(self):
        """
        Calculate water_to_rock_ratio and catalyst_percentage if they are not
        already set and the required input fields are available.
        """
        # Calculate water_to_rock_ratio
        if self.water_to_rock_ratio is None and \
           self.water_volume is not None and \
           self.rock_mass is not None and self.rock_mass > 0:
            self.water_to_rock_ratio = self.water_volume / self.rock_mass

        # Calculate catalyst_percentage
        if self.catalyst_percentage is None and \
           self.catalyst is not None and \
           self.catalyst_mass is not None and \
           self.rock_mass is not None and self.rock_mass > 0:
            
            elemental_metal_mass = None
            catalyst_name = self.catalyst.lower()

            # Nickel calculation (assuming NiCl2·6H2O)
            if 'nickel' in catalyst_name or 'ni' in catalyst_name:
                # Molar masses: Ni = 58.69, NiCl2·6H2O = 237.69
                elemental_metal_mass = self.catalyst_mass * (58.69 / 237.69)
            
            # Copper calculation (assuming CuCl2·2H2O)
            elif 'copper' in catalyst_name or 'cu' in catalyst_name:
                # Molar masses: Cu = 63.55, CuCl2·2H2O = 170.48
                elemental_metal_mass = self.catalyst_mass * (63.55 / 170.48)
            
            # Add other catalyst types here if needed
            # elif 'iron' in catalyst_name or 'fe' in catalyst_name:
            #     # Example: FeCl3·6H2O (Molar mass Fe=55.845, FeCl3·6H2O=270.30)
            #     elemental_metal_mass = self.catalyst_mass * (55.845 / 270.30)

            if elemental_metal_mass is not None:
                # Calculate percentage (mass/mass)
                self.catalyst_percentage = (elemental_metal_mass / self.rock_mass) * 100 # Convert ratio to percentage

                # Calculate catalyst_ppm (parts per million by mass)
                if self.water_volume is not None and self.water_volume > 0:
                    # ppm = (mass_of_solute [g] / mass_of_solvent [g]) * 1,000,000
                    # Assuming water density is 1 g/mL, water_volume in mL is equivalent to water_mass in g.
                    self.catalyst_ppm = (elemental_metal_mass / self.water_volume) * 1_000_000

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
    grams_per_ton_yield = Column(Float, nullable=True)  # yield in g/ton
    final_ph = Column(Float, nullable=True)
    final_nitrate_concentration = Column(Float, nullable=True)  # in mM
    final_dissolved_oxygen = Column(Float, nullable=True) # in ppm
    co2_partial_pressure = Column(Float, nullable=True) # in psi
    final_conductivity = Column(Float, nullable=True) # in uS/cm
    final_alkalinity = Column(Float, nullable=True) # in mg/L CaCO3
    sampling_volume = Column(Float, nullable=True) # in mL

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

        # TODO: Calculate ferrous_iron_yield when the calculation method is determined
        # Example: Check if specific inputs for Fe yield are present
        # if required_input_for_fe_yield is not None:
        #    self.ferrous_iron_yield = ... calculation ...
        # else:
        #    self.ferrous_iron_yield = None # Or leave as is if manually entered

# --- Add classes for GCResults, PXRFResults, etc. later ---

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

"""
Injection flow rate
Confining pressure
Temperature
Pore Pressure
Outlet Flow Rate
GC Analysis Data for each injection
"""

class ExperimentNotes(Base):
    __tablename__ = "experiment_notes"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String, nullable=False, index=True) # Human-readable ID
    experiment_fk = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False) # FK to Experiment PK
    note_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    experiment = relationship("Experiment", back_populates="notes", foreign_keys=[experiment_fk])

class ModificationsLog(Base):
    __tablename__ = "modifications_log"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String, nullable=True, index=True) # Human-readable ID, nullable as it might log other things? Or should be non-null? Let's keep nullable for now.
    experiment_fk = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=True) # FK to Experiment PK, nullable to match experiment_id
    modified_by = Column(String)  # Username or identifier of who made the change
    modification_type = Column(String)  # e.g., 'create', 'update', 'delete'
    modified_table = Column(String)  # Which table was modified
    old_values = Column(JSON)  # Previous values
    new_values = Column(JSON)  # New values
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    experiment = relationship("Experiment", back_populates="modifications", foreign_keys=[experiment_fk])

class SamplePhotos(Base):
    __tablename__ = "sample_photos"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(String, ForeignKey("sample_info.sample_id"), nullable=False) # Added FK to SampleInfo.sample_id
    file_path = Column(String, nullable=False)
    file_name = Column(String)
    file_type = Column(String)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sample_info = relationship("SampleInfo", back_populates="photos", foreign_keys=[sample_id])

class SampleInfo(Base):
    __tablename__ = "sample_info"

    # Use sample_id as the primary key
    sample_id = Column(String, primary_key=True, index=True)
    rock_classification = Column(String)
    state = Column(String)
    country = Column(String)
    locality = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    experiments = relationship("Experiment", back_populates="sample_info", foreign_keys="[Experiment.sample_id]")
    external_analyses = relationship(
        "ExternalAnalysis",
        back_populates="sample_info",
        cascade="all, delete-orphan",
        foreign_keys="[ExternalAnalysis.sample_id]" # Join on sample_id
    )
    photos = relationship("SamplePhotos", back_populates="sample_info", cascade="all, delete-orphan", foreign_keys="[SamplePhotos.sample_id]")

class AnalysisFiles(Base):
    __tablename__ = "analysis_files"

    id = Column(Integer, primary_key=True, index=True)
    external_analysis_id = Column(Integer, ForeignKey("external_analyses.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String, nullable=False)
    file_name = Column(String)
    file_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    external_analysis = relationship("ExternalAnalysis", back_populates="analysis_files")

class ExternalAnalysis(Base):
    __tablename__ = "external_analyses"

    id = Column(Integer, primary_key=True, index=True)
    # Add ondelete="CASCADE"
    sample_id = Column(String, ForeignKey("sample_info.sample_id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_type = Column(String)  # General type/category (e.g., 'Elemental Scan', 'Mineralogy')
    analysis_date = Column(DateTime(timezone=True))
    laboratory = Column(String)
    analyst = Column(String)
    # Link to PXRFReading table via this field, with SET NULL on delete
    pxrf_reading_no = Column(String, ForeignKey("pxrf_readings.reading_no", ondelete="SET NULL"), nullable=True, index=True)
    description = Column(Text)
    analysis_metadata = Column(JSON)  # For storing additional analysis-specific data
    # Add magnetic susceptibility field
    magnetic_susceptibility = Column(String, nullable=True)  # Store as string to maintain flexibility
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    # Updated sample_info relationship
    sample_info = relationship(
        "SampleInfo",
        back_populates="external_analyses",
        foreign_keys=[sample_id] # Join on sample_id
    )
    analysis_files = relationship("AnalysisFiles", back_populates="external_analysis", cascade="all, delete-orphan")
    # Add relationship to PXRFReading
    pxrf_reading = relationship("PXRFReading", back_populates="external_analyses")

class PXRFReading(Base):
    __tablename__ = "pxrf_readings"

    # Using Reading No as the primary key - ensure it's treated as string consistently
    reading_no = Column(String, primary_key=True, index=True)

    # Elemental data columns - nullable allows for missing data in source
    fe = Column(Float, name="Fe", nullable=True)
    mg = Column(Float, name="Mg", nullable=True)
    ni = Column(Float, name="Ni", nullable=True)
    cu = Column(Float, name="Cu", nullable=True)
    si = Column(Float, name="Si", nullable=True)
    co = Column(Float, name="Co", nullable=True)
    mo = Column(Float, name="Mo", nullable=True)
    al = Column(Float, name="Al", nullable=True)
    # Add other elements as needed, matching REQUIRED_COLUMNS in ingestion script

    # Timestamps for tracking ingestion
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Add relationship back to ExternalAnalysis
    external_analyses = relationship("ExternalAnalysis", back_populates="pxrf_reading")

    def __repr__(self):
        return f"<PXRFReading(reading_no='{self.reading_no}')>" 