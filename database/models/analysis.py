from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from typing import Dict
from ..database import Base

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
    # Add one-to-one relationships for specific analysis types
    pxrf_reading = relationship("PXRFReading", back_populates="external_analyses")
    xrd_analysis = relationship("XRDAnalysis", back_populates="external_analysis", uselist=False, cascade="all, delete-orphan")
    elemental_analysis = relationship("ElementalAnalysis", back_populates="external_analysis", uselist=False, cascade="all, delete-orphan")

class XRDAnalysis(Base):
    __tablename__ = "xrd_analysis"

    id = Column(Integer, primary_key=True, index=True)
    external_analysis_id = Column(Integer, ForeignKey("external_analyses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    mineral_phases = Column(JSON)  # e.g., {"quartz": 45.2, "feldspar": 23.8}
    peak_positions = Column(JSON)  # e.g., {"2-theta": [20.8, 26.6, ...]}
    intensities = Column(JSON)     # e.g., {"counts": [1500, 8000, ...]}
    d_spacings = Column(JSON)      # e.g., {"angstrom": [4.26, 3.34, ...]}
    analysis_parameters = Column(JSON) # e.g., {"xray_source": "CuKa", "scan_range": "5-90"}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    external_analysis = relationship("ExternalAnalysis", back_populates="xrd_analysis")

    @validates('mineral_phases', 'peak_positions', 'intensities', 'd_spacings', 'analysis_parameters')
    def validate_json(self, key, value):
        if value is not None and not isinstance(value, (dict, list)):
             raise ValueError(f"{key} must be a valid JSON object or array.")
        return value

    def get_mineral_percentage(self, mineral_name):
        """Returns the percentage of a given mineral, or 0 if not found."""
        if self.mineral_phases and isinstance(self.mineral_phases, dict):
            return self.mineral_phases.get(mineral_name.lower(), 0)
        return 0

    def validate_mineral_percentages(self, tolerance=5):
        """Validates if the mineral percentages sum to 100 ± tolerance."""
        if not self.mineral_phases or not isinstance(self.mineral_phases, dict):
            return True # No data to validate
        
        total_percentage = sum(self.mineral_phases.values())
        return (100 - tolerance) <= total_percentage <= (100 + tolerance)

class ElementalAnalysis(Base):
    __tablename__ = "elemental_analysis"

    id = Column(Integer, primary_key=True, index=True)
    external_analysis_id = Column(Integer, ForeignKey("external_analyses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    major_elements = Column(JSON) # e.g., {"SiO2": 65.5, "Al2O3": 15.2}
    minor_elements = Column(JSON) # e.g., {"TiO2": 0.8, "Fe2O3": 4.5}
    trace_elements = Column(JSON) # e.g., {"Sr": 400, "Ba": 850} (in ppm)
    detection_method = Column(String) # e.g., "XRF", "ICP-MS"
    detection_limits = Column(JSON) # e.g., {"Sr": 0.5, "Ba": 1} (in ppm)
    analytical_conditions = Column(JSON) # e.g., {"instrument": "Thermo Fisher iCAP Q", "digestion_method": "HF-HNO3"}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    external_analysis = relationship("ExternalAnalysis", back_populates="elemental_analysis")

    @validates('major_elements', 'minor_elements', 'trace_elements', 'detection_limits', 'analytical_conditions')
    def validate_json(self, key, value):
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"{key} must be a valid JSON object.")
        return value

    def get_element_concentration(self, element_type, element_name):
        """
        Returns the concentration of a given element from the specified type.
        Element types can be 'major', 'minor', or 'trace'.
        """
        target_dict = getattr(self, f"{element_type}_elements", None)
        if target_dict and isinstance(target_dict, dict):
            # Case-insensitive lookup for element name
            for key, val in target_dict.items():
                if key.lower() == element_name.lower():
                    return val
        return 0

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
