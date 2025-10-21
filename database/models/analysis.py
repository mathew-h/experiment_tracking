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


class Analyte(Base):
    __tablename__ = "analytes"

    id = Column(Integer, primary_key=True, index=True)  # analyte_id
    analyte_symbol = Column(String, unique=True, nullable=False, index=True)  # e.g., FeO, SiO2
    unit = Column(String, nullable=False)  # e.g., ppm, %
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    elemental_results = relationship("ElementalAnalysis", back_populates="analyte")


class ElementalAnalysis(Base):
    __tablename__ = "elemental_analysis"

    id = Column(Integer, primary_key=True, index=True)
    # Link to SampleInfo via its string primary key sample_id
    sample_id = Column(String, ForeignKey("sample_info.sample_id", ondelete="CASCADE"), nullable=False, index=True)
    analyte_id = Column(Integer, ForeignKey("analytes.id", ondelete="CASCADE"), nullable=False, index=True)
    analyte_composition = Column(Float, nullable=True)  # numeric value in the unit defined by Analyte.unit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Uniqueness: one row per (sample_id, analyte_id)
    __table_args__ = (
        UniqueConstraint('sample_id', 'analyte_id', name='uq_elemental_analysis_sample_analyte'),
    )

    # Relationships
    analyte = relationship("Analyte", back_populates="elemental_results")
