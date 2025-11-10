from __future__ import annotations

import io
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from database import Experiment
from database.models.enums import ExperimentStatus


@dataclass
class StatusChangePreview:
    """Preview of status changes to be applied"""
    to_ongoing: List[Dict[str, Any]]  # List of {experiment_id, current_status}
    to_completed: List[Dict[str, Any]]  # List of {experiment_id, current_status}
    missing_ids: List[str]  # Experiment IDs not found in database
    errors: List[str]  # Validation errors


class ExperimentStatusService:
    """Service for bulk updating experiment statuses"""
    
    @staticmethod
    def preview_status_changes_from_excel(
        db: Session, 
        file_bytes: bytes
    ) -> StatusChangePreview:
        """
        Preview status changes from an Excel file.
        
        Args:
            db: Database session
            file_bytes: Excel file bytes with 'experiment_id' column
            
        Returns:
            StatusChangePreview with lists of changes to be made
        """
        errors: List[str] = []
        missing_ids: List[str] = []
        
        # Read Excel file
        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
        except Exception as e:
            return StatusChangePreview(
                to_ongoing=[],
                to_completed=[],
                missing_ids=[],
                errors=[f"Failed to read Excel: {e}"]
            )
        
        # Normalize column names (case-insensitive)
        col_map = {str(c).lower().strip(): str(c) for c in df.columns}
        
        # Check for required column
        if "experiment_id" not in col_map:
            return StatusChangePreview(
                to_ongoing=[],
                to_completed=[],
                missing_ids=[],
                errors=["Missing required column: 'experiment_id'"]
            )
        
        # Rename to standard column name
        df = df.rename(columns={col_map["experiment_id"]: "experiment_id"})
        
        # Extract experiment IDs (remove blanks and duplicates)
        listed_exp_ids = []
        for idx, row in df.iterrows():
            exp_id = str(row.get("experiment_id") or "").strip()
            if exp_id and exp_id not in listed_exp_ids:
                listed_exp_ids.append(exp_id)
        
        if not listed_exp_ids:
            return StatusChangePreview(
                to_ongoing=[],
                to_completed=[],
                missing_ids=[],
                errors=["No valid experiment IDs found in file"]
            )
        
        # Find experiments to set ONGOING (must exist in DB)
        to_ongoing_exps = db.query(Experiment).filter(
            Experiment.experiment_id.in_(listed_exp_ids)
        ).all()
        
        # Track which IDs were found
        found_ids = {exp.experiment_id for exp in to_ongoing_exps}
        missing_ids = [exp_id for exp_id in listed_exp_ids if exp_id not in found_ids]
        
        # Find experiments to set COMPLETED (currently ONGOING, not in list)
        to_completed_exps = db.query(Experiment).filter(
            Experiment.status == ExperimentStatus.ONGOING,
            ~Experiment.experiment_id.in_(listed_exp_ids)
        ).all()
        
        # Build preview data
        to_ongoing = [
            {
                "experiment_id": exp.experiment_id,
                "current_status": exp.status.value if exp.status else "None"
            }
            for exp in to_ongoing_exps
        ]
        
        to_completed = [
            {
                "experiment_id": exp.experiment_id,
                "current_status": exp.status.value
            }
            for exp in to_completed_exps
        ]
        
        return StatusChangePreview(
            to_ongoing=to_ongoing,
            to_completed=to_completed,
            missing_ids=missing_ids,
            errors=errors
        )
    
    @staticmethod
    def apply_status_changes(
        db: Session,
        experiment_ids_to_ongoing: List[str]
    ) -> Tuple[int, int, List[str]]:
        """
        Apply status changes: set listed experiments to ONGOING, others to COMPLETED.
        
        Args:
            db: Database session
            experiment_ids_to_ongoing: List of experiment IDs to mark as ONGOING
            
        Returns:
            Tuple of (marked_ongoing_count, marked_completed_count, errors)
        """
        errors: List[str] = []
        marked_ongoing = 0
        marked_completed = 0
        
        try:
            # Update experiments to ONGOING
            if experiment_ids_to_ongoing:
                to_ongoing_exps = db.query(Experiment).filter(
                    Experiment.experiment_id.in_(experiment_ids_to_ongoing)
                ).all()
                
                for exp in to_ongoing_exps:
                    exp.status = ExperimentStatus.ONGOING
                    marked_ongoing += 1
            
            # Update other ONGOING experiments to COMPLETED
            to_completed_exps = db.query(Experiment).filter(
                Experiment.status == ExperimentStatus.ONGOING,
                ~Experiment.experiment_id.in_(experiment_ids_to_ongoing) if experiment_ids_to_ongoing else True
            ).all()
            
            for exp in to_completed_exps:
                exp.status = ExperimentStatus.COMPLETED
                marked_completed += 1
            
        except Exception as e:
            errors.append(f"Error applying status changes: {e}")
        
        return marked_ongoing, marked_completed, errors

