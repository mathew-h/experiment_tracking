"""
Utility functions for managing experiment lineage.

This module provides functions to parse experiment IDs, identify derivations,
and establish parent-child relationships between experiments.
"""
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func


def parse_experiment_id(experiment_id: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Parse an experiment ID to extract the base ID and derivation number.
    
    Args:
        experiment_id: The experiment ID to parse (e.g., "HPHT_MH_001-2")
        
    Returns:
        A tuple of (base_experiment_id, derivation_number)
        - For "HPHT_MH_001-2": returns ("HPHT_MH_001", 2)
        - For "HPHT_MH_001": returns ("HPHT_MH_001", None)
        - For "HPHT-MH-001": returns ("HPHT-MH-001", None)
        
    Examples:
        >>> parse_experiment_id("HPHT_MH_001-2")
        ("HPHT_MH_001", 2)
        >>> parse_experiment_id("HPHT_MH_001")
        ("HPHT_MH_001", None)
        >>> parse_experiment_id("HPHT-MH-001")
        ("HPHT-MH-001", None)
    """
    if not experiment_id or not isinstance(experiment_id, str):
        return None, None
    
    experiment_id = experiment_id.strip()
    if not experiment_id:
        return None, None
    
    parts = experiment_id.split('-')
    if len(parts) < 2:
        # No hyphen, so it's a base experiment
        return experiment_id, None
    
    # Check if last part is numeric
    try:
        derivation_num = int(parts[-1])
        base_id = '-'.join(parts[:-1])
        return base_id, derivation_num
    except ValueError:
        # Last part is not numeric, so this is not a derivation
        # (e.g., "HPHT-MH-001" where "001" is not meant to be a derivation)
        return experiment_id, None


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
    
    base_id, derivation_num = parse_experiment_id(experiment_id)
    
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
    """
    if not experiment or not experiment.experiment_id:
        return False
    
    base_id, derivation_num = parse_experiment_id(experiment.experiment_id)
    
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

