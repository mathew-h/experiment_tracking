"""
Experiment ID validation and parsing service.

This module provides validation and parsing for experiment IDs following the format:
ExperimentType_ResearcherInitials_Index with optional sequential (-NUMBER) and 
treatment (_TEXT) suffixes.

Format Examples:
- Base: Serum_MH_101
- Sequential: Serum_MH_101-2 (2nd run)
- Treatment: Serum_MH_101_Desorption (treatment variant)
- Combined: Serum_MH_101-2_Desorption (treatment on 2nd run)
"""

from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
from database.models.enums import ExperimentType
import re


# Mapping of common abbreviations to ExperimentType enum values
EXPERIMENT_TYPE_ABBREVIATIONS: Dict[str, ExperimentType] = {
    # Full names (case-insensitive)
    "serum": ExperimentType.SERUM,
    "autoclave": ExperimentType.AUTOCLAVE,
    "hpht": ExperimentType.HPHT,
    "coreflood": ExperimentType.CF,
    "core flood": ExperimentType.CF,
    "cf": ExperimentType.CF,
    "other": ExperimentType.OTHER,
    # Common abbreviations
    "ac": ExperimentType.AUTOCLAVE,
}


@dataclass
class ParsedExperimentID:
    """Result of parsing an experiment ID."""
    experiment_type: Optional[ExperimentType]
    researcher_initials: Optional[str]
    index: Optional[str]
    sequential_number: Optional[int]
    treatment_variant: Optional[str]
    base_id: str  # The ID without sequential/treatment suffixes
    original_id: str
    is_valid: bool
    warnings: List[str]


def get_experiment_type_from_id(type_text: str) -> Optional[ExperimentType]:
    """
    Map experiment type text (abbreviation or full name) to ExperimentType enum.
    
    Args:
        type_text: The type portion from experiment ID (case-insensitive)
        
    Returns:
        ExperimentType enum value if found, None otherwise
        
    Examples:
        >>> get_experiment_type_from_id("Serum")
        ExperimentType.SERUM
        >>> get_experiment_type_from_id("CF")
        ExperimentType.CF
        >>> get_experiment_type_from_id("ac")
        ExperimentType.AUTOCLAVE
    """
    if not type_text:
        return None
    
    normalized = type_text.strip().lower()
    return EXPERIMENT_TYPE_ABBREVIATIONS.get(normalized)


def extract_lineage_info(experiment_id: str) -> Tuple[str, Optional[int], Optional[str]]:
    """
    Extract base ID, sequential number, and treatment variant from experiment ID.
    
    Uses hybrid delimiter system:
    - Hyphen-NUMBER for sequential lineage (e.g., -2, -3)
    - Underscore-TEXT for treatment variants (e.g., _Desorption)
    
    Args:
        experiment_id: The full experiment ID
        
    Returns:
        Tuple of (base_id, sequential_number, treatment_variant)
        
    Examples:
        >>> extract_lineage_info("Serum_MH_101")
        ("Serum_MH_101", None, None)
        >>> extract_lineage_info("Serum_MH_101-2")
        ("Serum_MH_101", 2, None)
        >>> extract_lineage_info("Serum_MH_101_Desorption")
        ("Serum_MH_101", None, "Desorption")
        >>> extract_lineage_info("Serum_MH_101-2_Desorption")
        ("Serum_MH_101", 2, "Desorption")
    """
    if not experiment_id:
        return "", None, None
    
    treatment_variant = None
    sequential_number = None
    base_id = experiment_id
    
    # First, extract treatment suffix (last underscore followed by non-numeric text)
    # We need to be careful not to treat underscore in base name as treatment delimiter
    # Strategy: Look for last underscore followed by text that's NOT part of standard format
    parts = experiment_id.split('_')
    if len(parts) > 3:  # More than TYPE_INITIALS_INDEX format
        # Check if last part looks like a treatment (not all numeric, not part of base format)
        potential_treatment = parts[-1]
        # If it contains a hyphen with number, extract treatment first
        if '-' in potential_treatment:
            treatment_parts = potential_treatment.split('-')
            # Check if last part after hyphen is numeric (sequential)
            if treatment_parts[-1].isdigit():
                # This is like "Desorption-2" which is unusual, treat whole thing as treatment
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
    
    # Now extract sequential number from base_id (or modified experiment_id)
    # Look for last hyphen followed by digits
    if treatment_variant:
        # Work with base_id
        if '-' in base_id:
            hyphen_parts = base_id.rsplit('-', 1)
            if len(hyphen_parts) == 2 and hyphen_parts[-1].isdigit():
                sequential_number = int(hyphen_parts[-1])
                base_id = hyphen_parts[0]
    else:
        # No treatment found, check full experiment_id for sequential
        if '-' in experiment_id:
            hyphen_parts = experiment_id.rsplit('-', 1)
            if len(hyphen_parts) == 2 and hyphen_parts[-1].isdigit():
                sequential_number = int(hyphen_parts[-1])
                base_id = hyphen_parts[0]
    
    return base_id, sequential_number, treatment_variant


def parse_experiment_id(experiment_id: str) -> ParsedExperimentID:
    """
    Parse and validate an experiment ID.
    
    Expected format: ExperimentType_ResearcherInitials_Index[-Sequential][_Treatment]
    
    Args:
        experiment_id: The experiment ID to parse
        
    Returns:
        ParsedExperimentID object with parsed components and validation warnings
        
    Examples:
        >>> result = parse_experiment_id("Serum_MH_101")
        >>> result.experiment_type
        ExperimentType.SERUM
        >>> result.researcher_initials
        'MH'
        >>> result.index
        '101'
    """
    warnings = []
    
    if not experiment_id or not isinstance(experiment_id, str):
        return ParsedExperimentID(
            experiment_type=None,
            researcher_initials=None,
            index=None,
            sequential_number=None,
            treatment_variant=None,
            base_id="",
            original_id=experiment_id or "",
            is_valid=False,
            warnings=["Experiment ID is empty or invalid"]
        )
    
    original_id = experiment_id.strip()
    
    # Extract lineage info first
    base_id, sequential_number, treatment_variant = extract_lineage_info(original_id)
    
    # Parse base_id as TYPE_INITIALS_INDEX
    parts = base_id.split('_')
    
    experiment_type = None
    researcher_initials = None
    index = None
    
    if len(parts) < 3:
        warnings.append(
            f"Expected format: ExperimentType_ResearcherInitials_Index (e.g., Serum_MH_101). "
            f"Got: {original_id}"
        )
        is_valid = False
    else:
        # Extract components
        type_text = parts[0]
        researcher_initials = parts[1]
        index = parts[2]
        
        # Validate experiment type
        experiment_type = get_experiment_type_from_id(type_text)
        if not experiment_type:
            warnings.append(
                f"Unknown experiment type '{type_text}'. Expected one of: "
                f"{', '.join(sorted(set(EXPERIMENT_TYPE_ABBREVIATIONS.keys())))}"
            )
        
        # Validate researcher initials (basic check)
        if not researcher_initials or not researcher_initials.isalnum():
            warnings.append(
                f"Researcher initials '{researcher_initials}' should be alphanumeric (e.g., MH, JD)"
            )
        
        # Validate index (should be numeric or alphanumeric)
        if not index:
            warnings.append("Index portion is missing (e.g., 101, 001)")
        
        is_valid = len(warnings) == 0
    
    return ParsedExperimentID(
        experiment_type=experiment_type,
        researcher_initials=researcher_initials,
        index=index,
        sequential_number=sequential_number,
        treatment_variant=treatment_variant,
        base_id=base_id,
        original_id=original_id,
        is_valid=is_valid,
        warnings=warnings
    )


def validate_experiment_id(experiment_id: str) -> Tuple[bool, List[str]]:
    """
    Validate an experiment ID and return warnings.
    
    This is a convenience function that returns just the validation status and warnings.
    
    Args:
        experiment_id: The experiment ID to validate
        
    Returns:
        Tuple of (is_valid, warnings_list)
        
    Example:
        >>> is_valid, warnings = validate_experiment_id("Serum_MH_101")
        >>> is_valid
        True
        >>> warnings
        []
    """
    parsed = parse_experiment_id(experiment_id)
    return parsed.is_valid, parsed.warnings


def format_validation_warning(warnings: List[str]) -> str:
    """
    Format validation warnings into a user-friendly message.
    
    Args:
        warnings: List of warning messages
        
    Returns:
        Formatted warning string
    """
    if not warnings:
        return ""
    
    if len(warnings) == 1:
        return f"⚠️ {warnings[0]}"
    
    return "⚠️ Validation warnings:\n" + "\n".join(f"  • {w}" for w in warnings)

