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
    experiment_number = Column(Integer, unique=True, nullable=False)
    experiment_id = Column(String, unique=True)
    sample_id = Column(String)
    researcher = Column(String)
    date = Column(DateTime)
    status = Column(Enum(ExperimentStatus))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    conditions = relationship("ExperimentalConditions", back_populates="experiment", uselist=False)
    notes = relationship("ExperimentNotes", back_populates="experiment", cascade="all, delete-orphan")
    modifications = relationship("ModificationsLog", back_populates="experiment", cascade="all, delete-orphan")
    results = relationship("ExperimentalResults", back_populates="experiment", cascade="all, delete-orphan")

class ExperimentalConditions(Base):
    __tablename__ = "experimental_conditions"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    particle_size = Column(String)
    water_to_rock_ratio = Column(Float, nullable=True)
    initial_ph = Column(Float)
    catalyst = Column(String)
    catalyst_mass = Column(Float)
    rock_mass = Column(Float)
    water_volume = Column(Float)
    catalyst_percentage = Column(Float)
    temperature = Column(Float)
    buffer_system = Column(String, nullable=True)
    buffer_concentration = Column(Float)  # in mM
    pressure = Column(Float)  # in psi instead of bar
    flow_rate = Column(Float, nullable=True)
    experiment_type = Column(String)  # Serum, Autoclave, HPHT, Core Flood
    initial_nitrate_concentration = Column(Float)  # in mM, optional
    dissolved_oxygen = Column(Float)  # in ppm, optional
    surfactant_type = Column(String)  # optional
    surfactant_concentration = Column(Float)  # optional
    co2_partial_pressure = Column(Float)  # in psi, optional
    confining_pressure = Column(Float)  # optional
    pore_pressure = Column(Float)  # optional
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    experiment = relationship("Experiment", back_populates="conditions")

class ExperimentalResults(Base):
    __tablename__ = "experimental_results"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    
    # Results data
    yield_value = Column(Float)  # in percentage
    final_ph = Column(Float)  # Optional result field
    final_nitrate_concentration = Column(Float)  # in mM, optional result field
    
    # File and data storage
    data_type = Column(String)  # e.g., 'NMR', 'GC', 'AMMONIA_YIELD'
    file_path = Column(String)  # Path to stored file
    file_name = Column(String)  # Original file name
    file_type = Column(String)  # File extension
    
    # Raw data storage
    nmr_data = Column(JSON)  # Store NMR data as JSON
    gc_data = Column(JSON)   # Store GC data as JSON
    data_values = Column(JSON)  # For numerical data like ammonia yield
    
    # Metadata
    description = Column(Text)  # Optional description of the data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # when results were collected
    # calculate theoretical yield based on rock analysis

    # Relationship
    experiment = relationship("Experiment", back_populates="results")

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
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    note_text = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    experiment = relationship("Experiment", back_populates="notes")

class ModificationsLog(Base):
    __tablename__ = "modifications_log"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    modified_by = Column(String)  # Username or identifier of who made the change
    modification_type = Column(String)  # e.g., 'create', 'update', 'delete'
    modified_table = Column(String)  # Which table was modified
    old_values = Column(JSON)  # Previous values
    new_values = Column(JSON)  # New values
    created_at = Column(DateTime, server_default=func.now())

    experiment = relationship("Experiment", back_populates="modifications")

class SampleInfo(Base):
    __tablename__ = "sample_info"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(String, unique=True, nullable=False)
    rock_classification = Column(String)
    state = Column(String)
    country = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    description = Column(Text)
    photo_path = Column(String)  # Path to stored photo
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    external_analyses = relationship("ExternalAnalysis", back_populates="sample_info", cascade="all, delete-orphan")

class ExternalAnalysis(Base):
    __tablename__ = "external_analyses"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(String, ForeignKey("sample_info.sample_id"), nullable=False)
    analysis_type = Column(String)  # e.g., 'XRD', 'SEM', 'Elemental'
    report_file_path = Column(String)
    report_file_name = Column(String)
    report_file_type = Column(String)
    analysis_date = Column(DateTime)
    laboratory = Column(String)
    analyst = Column(String)
    description = Column(Text)
    analysis_metadata = Column(JSON)  # For storing additional analysis-specific data
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    sample_info = relationship("SampleInfo", back_populates="external_analyses") 