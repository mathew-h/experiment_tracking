from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from ..database import Base


class XRDAnalysis(Base):
    __tablename__ = "xrd_analysis"

    id = Column(Integer, primary_key=True, index=True)
    external_analysis_id = Column(
        Integer,
        ForeignKey("external_analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Store primary mineralogy as JSON for engines that support JSON operators.
    # In SQLite this will be stored as TEXT via SQLAlchemy and treated as opaque JSON.
    mineral_phases = Column(JSON)       # e.g., {"quartz": 45.2, "feldspar": 23.8}
    peak_positions = Column(JSON)       # e.g., {"2-theta": [20.8, 26.6, ...]}
    intensities = Column(JSON)          # e.g., {"counts": [1500, 8000, ...]}
    d_spacings = Column(JSON)           # e.g., {"angstrom": [4.26, 3.34, ...]}
    analysis_parameters = Column(JSON)  # e.g., {"xray_source": "CuKa", "scan_range": "5-90"}

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    external_analysis = relationship("ExternalAnalysis", back_populates="xrd_analysis")

    @validates("mineral_phases", "peak_positions", "intensities", "d_spacings", "analysis_parameters")
    def validate_json(self, key, value):
        if value is not None and not isinstance(value, (dict, list)):
            raise ValueError(f"{key} must be a valid JSON object or array.")
        return value

    def get_mineral_percentage(self, mineral_name: str) -> float:
        """Returns the percentage of a given mineral, or 0 if not found."""
        if self.mineral_phases and isinstance(self.mineral_phases, dict):
            return self.mineral_phases.get(mineral_name.lower(), 0)
        return 0

    def validate_mineral_percentages(self, tolerance: float = 5) -> bool:
        """Validates if the mineral percentages sum to 100 ± tolerance."""
        if not self.mineral_phases or not isinstance(self.mineral_phases, dict):
            return True
        total_percentage = sum(self.mineral_phases.values())
        return (100 - tolerance) <= total_percentage <= (100 + tolerance)


class XRDPhase(Base):
    __tablename__ = "xrd_phases"

    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(
        String,
        ForeignKey("sample_info.sample_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional link to the parent ExternalAnalysis; allows associating normalized rows to a specific analysis
    external_analysis_id = Column(
        Integer,
        ForeignKey("external_analyses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    mineral_name = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("sample_id", "mineral_name", name="uq_xrd_phase_sample_mineral"),
    )

    # Relationships (one-way; no back_populates added to avoid widening changes)
    external_analysis = relationship("ExternalAnalysis")

