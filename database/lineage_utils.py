"""
Utility functions for managing experiment lineage.

This module provides functions to parse experiment IDs, identify derivations,
and establish parent-child relationships between experiments.

Supports hybrid delimiter system:
- Hyphen-NUMBER for sequential lineage (e.g., -2, -3)
- Underscore-TEXT for treatment variants (e.g., _Desorption)
"""
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func


def parse_experiment_id(experiment_id: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Parse an experiment ID to extract the base ID, derivation number, and treatment variant.
    
    Uses hybrid delimiter system:
    - Hyphen-NUMBER for sequential lineage (e.g., -2, -3)
    - Underscore-TEXT for treatment variants (e.g., _Desorption)
    
    Args:
        experiment_id: The experiment ID to parse (e.g., "HPHT_MH_001-2_Desorption")
        
    Returns:
        A tuple of (base_experiment_id, derivation_number, treatment_variant)
        - For "HPHT_MH_001-2": returns ("HPHT_MH_001", 2, None)
        - For "HPHT_MH_001": returns ("HPHT_MH_001", None, None)
        - For "HPHT_MH_001_Desorption": returns ("HPHT_MH_001", None, "Desorption")
        - For "HPHT_MH_001-2_Desorption": returns ("HPHT_MH_001", 2, "Desorption")
        
    Examples:
        >>> parse_experiment_id("HPHT_MH_001-2")
        ("HPHT_MH_001", 2, None)
        >>> parse_experiment_id("HPHT_MH_001")
        ("HPHT_MH_001", None, None)
        >>> parse_experiment_id("HPHT_MH_001_Desorption")
        ("HPHT_MH_001", None, "Desorption")
        >>> parse_experiment_id("HPHT_MH_001-2_Desorption")
        ("HPHT_MH_001", 2, "Desorption")
    """
    if not experiment_id or not isinstance(experiment_id, str):
        return None, None, None
    
    experiment_id = experiment_id.strip()
    if not experiment_id:
        return None, None, None
    
    treatment_variant = None
    derivation_num = None
    base_id = experiment_id
    
    # First, extract treatment suffix (last underscore followed by non-numeric text)
    # We need to be careful not to treat underscore in base name as treatment delimiter
    # Strategy: Look for last underscore followed by text that's NOT part of standard format
    parts = experiment_id.split('_')
    if len(parts) > 3:  # More than TYPE_INITIALS_INDEX format
        # Check if last part looks like a treatment (not all numeric, not part of base format)
        potential_treatment = parts[-1]
        # If it contains a hyphen with number, split and check
        if '-' in potential_treatment:
            treatment_parts = potential_treatment.rsplit('-', 1)
            # Check if last part after hyphen is numeric (sequential)
            if treatment_parts[-1].isdigit():
                # Pattern: Treatment-Number, unusual but handle it
                # Treat the whole thing as treatment for now
                treatment_variant = potential_treatment
                base_id = '_'.join(parts[:-1])
            else:
                # Last part is not numeric, might be treatment without sequential
                treatment_variant = potential_treatment
                base_id = '_'.join(parts[:-1])
        elif not potential_treatment.isdigit():
            # Last part is not numeric and has no hyphen, likely a treatment
            treatment_variant = potential_treatment
            base_id = '_'.join(parts[:-1])
    
    # Now extract sequential number from base_id (or remaining ID)
    # Look for last hyphen followed by digits
    if '-' in base_id:
        hyphen_parts = base_id.rsplit('-', 1)
        if len(hyphen_parts) == 2 and hyphen_parts[-1].isdigit():
            derivation_num = int(hyphen_parts[-1])
            base_id = hyphen_parts[0]
    
    return base_id, derivation_num, treatment_variant


def get_or_find_parent_experiment(db: Session, experiment_id: str):
    """
    Find the parent (base) experiment for a given experiment ID.
    
    Args:
        db: Database session
        experiment_id: The experiment ID to find the parent for
        
    Returns:
        The parent Experiment object if found, None otherwise
        
    Note:
        This function will import Experiment model inside to avoid circular imports.
    """
    from .models import Experiment
    
    base_id, derivation_num, treatment_variant = parse_experiment_id(experiment_id)
    
    # If this is not a derivation, there's no parent
    if derivation_num is None:
        return None
    
    # Find the base experiment
    # Use case-insensitive search, ignoring hyphens, underscores, and spaces
    base_id_norm = ''.join(ch for ch in base_id.lower() if ch not in ['-', '_', ' '])
    parent = db.query(Experiment).filter(
        func.lower(
            func.replace(
                func.replace(
                    func.replace(Experiment.experiment_id, '-', ''),
                    '_', ''
                ),
                ' ', ''
            )
        ) == base_id_norm
    ).first()
    
    return parent


def update_experiment_lineage(db: Session, experiment):
    """
    Update the lineage fields (base_experiment_id, parent_experiment_fk) for an experiment.
    
    Args:
        db: Database session
        experiment: The Experiment object to update
        
    Returns:
        True if lineage was updated, False if no update was needed
        
    Note:
        This function modifies the experiment object but does not commit the session.
        Treatment variants are tracked in the experiment_id but do not affect parent relationships.
    """
    if not experiment or not experiment.experiment_id:
        return False
    
    base_id, derivation_num, treatment_variant = parse_experiment_id(experiment.experiment_id)
    
    # If this is not a derivation, clear any lineage fields
    if derivation_num is None:
        if experiment.base_experiment_id or experiment.parent_experiment_fk:
            experiment.base_experiment_id = None
            experiment.parent_experiment_fk = None
            return True
        return False
    
    # This is a derivation, set base_experiment_id
    experiment.base_experiment_id = base_id
    
    # Try to find and set the parent
    parent = get_or_find_parent_experiment(db, experiment.experiment_id)
    if parent:
        experiment.parent_experiment_fk = parent.id
    else:
        # Parent doesn't exist yet, leave parent_experiment_fk as None
        experiment.parent_experiment_fk = None
    
    return True


def update_orphaned_derivations(db: Session, base_experiment_id: str):
    """
    Update any derivations that reference this base experiment but don't have parent_experiment_fk set.
    
    This is called after a base experiment is inserted to link any pre-existing derivations.
    
    Args:
        db: Database session
        base_experiment_id: The experiment_id of the newly created base experiment
        
    Returns:
        The number of derivations updated
    """
    from .models import Experiment
    
    if not base_experiment_id:
        return 0
    
    # Find the base experiment
    base_id_norm = ''.join(ch for ch in base_experiment_id.lower() if ch not in ['-', '_', ' '])
    base_experiment = db.query(Experiment).filter(
        func.lower(
            func.replace(
                func.replace(
                    func.replace(Experiment.experiment_id, '-', ''),
                    '_', ''
                ),
                ' ', ''
            )
        ) == base_id_norm
    ).first()
    
    if not base_experiment:
        return 0
    
    # Find orphaned derivations (those with base_experiment_id matching but parent_experiment_fk is NULL)
    orphaned = db.query(Experiment).filter(
        Experiment.base_experiment_id == base_experiment_id,
        Experiment.parent_experiment_fk.is_(None)
    ).all()
    
    count = 0
    for derivation in orphaned:
        derivation.parent_experiment_fk = base_experiment.id
        count += 1
    
    return count

