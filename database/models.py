from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base

class ExperimentStatus(enum.Enum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String, unique=True, nullable=False, index=True)  # User-defined experiment identifier
    experiment_number = Column(Integer, unique=True, nullable=False)  # Auto-incrementing number
    sample_id = Column(String)
    researcher = Column(String)
    date = Column(DateTime)
    status = Column(Enum(ExperimentStatus))
    sample_info_id = Column(Integer, ForeignKey("sample_info.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    conditions = relationship("ExperimentalConditions", back_populates="experiment", uselist=False)
    notes = relationship("ExperimentNotes", back_populates="experiment", cascade="all, delete-orphan")
    modifications = relationship("ModificationsLog", back_populates="experiment", cascade="all, delete-orphan")
    results = relationship("ExperimentalResults", back_populates="experiment", cascade="all, delete-orphan")
    sample_info = relationship("SampleInfo", backref="experiments")

class ExperimentalConditions(Base):
    __tablename__ = "experimental_conditions"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String, ForeignKey("experiments.experiment_id"), nullable=False)
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
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    experiment = relationship("Experiment", back_populates="conditions")

class ExperimentalResults(Base):
    __tablename__ = "experimental_results"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String, ForeignKey("experiments.experiment_id"), nullable=False)
    
    # Results data
    ferrous_iron_yield = Column(Float, nullable=True)  # in percentage
    grams_per_ton_yield = Column(Float, nullable=True)  # yield in g/ton
    final_ph = Column(Float, nullable=True)  # Optional result field
    final_nitrate_concentration = Column(Float, nullable=True)  # in mM, optional result field
    
    # New optional result fields
    final_dissolved_oxygen = Column(Float, nullable=True)
    co2_partial_pressure = Column(Float, nullable=True)
    final_conductivity = Column(Float, nullable=True)
    final_alkalinity = Column(Float, nullable=True)
    sampling_volume = Column(Float, nullable=True)
    
    # Time-series data
    time_post_reaction = Column(Float, nullable=True) # Time in hours post-reaction start
    
    # File and data storage
    data_type = Column(String)  # e.g., 'NMR', 'GC', 'AMMONIA_YIELD', 'SCALAR'
    file_path = Column(String)  # Path to stored file
    file_name = Column(String)  # Original file name
    file_type = Column(String)  # File extension
    
    # Raw data storage
    nmr_data = Column(JSON, nullable=True)  # Store NMR data as JSON
    gc_data = Column(JSON, nullable=True)   # Store GC data as JSON
    data_values = Column(JSON, nullable=True)  # For numerical data like ammonia yield
    
    # Metadata
    description = Column(Text)  # Optional description of the data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # when results were collected
    # calculate theoretical yield based on rock analysis

    # Relationship
    experiment = relationship("Experiment", back_populates="results")
    # Add relationship to ResultFiles
    files = relationship("ResultFiles", back_populates="result_entry", cascade="all, delete-orphan")

class ResultFiles(Base):
    __tablename__ = "result_files"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("experimental_results.id"), nullable=False)
    file_path = Column(String, nullable=False)
    file_name = Column(String)
    file_type = Column(String)
    description = Column(Text)
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
    experiment_id = Column(String, ForeignKey("experiments.experiment_id"), nullable=False)
    note_text = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    experiment = relationship("Experiment", back_populates="notes")

class ModificationsLog(Base):
    __tablename__ = "modifications_log"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(String, ForeignKey("experiments.experiment_id"), nullable=False)
    modified_by = Column(String)  # Username or identifier of who made the change
    modification_type = Column(String)  # e.g., 'create', 'update', 'delete'
    modified_table = Column(String)  # Which table was modified
    old_values = Column(JSON)  # Previous values
    new_values = Column(JSON)  # New values
    created_at = Column(DateTime, server_default=func.now())

    experiment = relationship("Experiment", back_populates="modifications")

class SamplePhotos(Base):
    __tablename__ = "sample_photos"

    id = Column(Integer, primary_key=True, index=True)
    sample_info_id = Column(Integer, ForeignKey("sample_info.id"), nullable=False)
    file_path = Column(String, nullable=False)
    file_name = Column(String)
    file_type = Column(String)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sample_info = relationship("SampleInfo", back_populates="photos")

class SampleInfo(Base):
    __tablename__ = "sample_info"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(String, unique=True, nullable=False)
    rock_classification = Column(String)
    state = Column(String)
    country = Column(String)
    locality = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    external_analyses = relationship(
        "ExternalAnalysis", 
        back_populates="sample_info", 
        cascade="all, delete-orphan",
        foreign_keys="[ExternalAnalysis.sample_info_id]" # Specify the correct FK column
    )
    photos = relationship("SamplePhotos", back_populates="sample_info", cascade="all, delete-orphan")

class AnalysisFiles(Base):
    __tablename__ = "analysis_files"

    id = Column(Integer, primary_key=True, index=True)
    external_analysis_id = Column(Integer, ForeignKey("external_analyses.id"), nullable=False)
    file_path = Column(String, nullable=False)
    file_name = Column(String)
    file_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    external_analysis = relationship("ExternalAnalysis", back_populates="analysis_files")

class ExternalAnalysis(Base):
    __tablename__ = "external_analyses"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(String, ForeignKey("sample_info.sample_id"), nullable=False)
    sample_info_id = Column(Integer, ForeignKey("sample_info.id"), nullable=False)
    analysis_type = Column(String)  # General type/category (e.g., 'Elemental Scan', 'Mineralogy')
    analysis_date = Column(DateTime)
    laboratory = Column(String)
    analyst = Column(String)
    pxrf_reading_no = Column(String, nullable=True) # Link to PXRFReading table via this field
    description = Column(Text)
    analysis_metadata = Column(JSON)  # For storing additional analysis-specific data
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    sample_info = relationship(
        "SampleInfo",
        back_populates="external_analyses",
        foreign_keys=[sample_info_id] # Specify the correct FK column
    )
    analysis_files = relationship("AnalysisFiles", back_populates="external_analysis", cascade="all, delete-orphan")

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
    ingested_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    def __repr__(self):
        return f"<PXRFReading(reading_no='{self.reading_no}')>" 