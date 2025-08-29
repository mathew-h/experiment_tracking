from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
from .enums import ExperimentStatus

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
