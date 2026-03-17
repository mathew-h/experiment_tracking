"""
Service for inferring experiment type from experiment ID prefix.

Experiment IDs encode the type in the leading prefix segment:
  - HPHT_MH_001  → ExperimentType.HPHT  ("HPHT")
  - SERUM_JW_051 → ExperimentType.SERUM  ("Serum")
  - CF_MH_010    → ExperimentType.CF     ("Core Flood")
  - AUTOCLAVE_xx → ExperimentType.AUTOCLAVE ("Autoclave")
  - anything else → ExperimentType.OTHER ("Other")
"""

from database.models.enums import ExperimentType

# Map uppercase ID prefixes to ExperimentType enum members.
# Extend this dict if new prefixes/types are added.
_PREFIX_TO_TYPE: dict[str, ExperimentType] = {
    "HPHT": ExperimentType.HPHT,
    "SERUM": ExperimentType.SERUM,
    "CF": ExperimentType.CF,
    "AUTOCLAVE": ExperimentType.AUTOCLAVE,
}


def infer_experiment_type_from_id(experiment_id: str) -> ExperimentType:
    """
    Infer the ExperimentType from the leading prefix of an experiment ID.

    The prefix is the segment before the first underscore, compared
    case-insensitively against the known prefix map. Returns
    ExperimentType.OTHER for unrecognised prefixes.

    Args:
        experiment_id: A string such as "HPHT_MH_001" or "CF_001-2_Desorption".

    Returns:
        The matching ExperimentType enum member, or ExperimentType.OTHER.
    """
    if not experiment_id:
        return ExperimentType.OTHER

    prefix = experiment_id.split("_")[0].upper()
    return _PREFIX_TO_TYPE.get(prefix, ExperimentType.OTHER)


def infer_experiment_type_value(experiment_id: str) -> str:
    """
    Convenience wrapper that returns the string value stored in the database
    (e.g. "Core Flood", "HPHT", "Serum") rather than the enum member.

    Args:
        experiment_id: A string such as "HPHT_MH_001".

    Returns:
        The .value of the inferred ExperimentType.
    """
    return infer_experiment_type_from_id(experiment_id).value
