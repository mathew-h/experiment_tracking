from sqlalchemy import event, text
from sqlalchemy.orm import Session, attributes
from .models import ExternalAnalysis, SampleInfo, ChemicalAdditive, ElementalAnalysis, Experiment
from .database import engine
from .lineage_utils import update_experiment_lineage, update_orphaned_derivations

def update_sample_characterized_status(session: Session, sample_id: str):
    """
    Updates the 'characterized' status of a SampleInfo record based on
    the existence of XRD analyses or titration (elemental) data. This should be called
    within a 'before_flush' event.
    """
    if not sample_id:
        return

    # Combine all known instances in the session for this sample_id
    all_instances = (
        session.query(ExternalAnalysis)
        .filter(ExternalAnalysis.sample_id == sample_id)
        .all()
    )

    # Add newly created instances that are not yet in the query result
    for obj in session.new:
        if isinstance(obj, ExternalAnalysis) and obj.sample_id == sample_id:
            if obj not in all_instances:
                all_instances.append(obj)

    # Filter out instances marked for deletion
    final_instances = [
        instance for instance in all_instances if instance not in session.deleted
    ]

    # XRD via ExternalAnalysis entries
    has_xrd = any(instance.analysis_type == 'XRD' for instance in final_instances)

    # Titration/elemental data via ElementalAnalysis normalized table
    # Start with DB state
    titration_instances = (
        session.query(ElementalAnalysis)
        .filter(ElementalAnalysis.sample_id == sample_id)
        .all()
    )
    # Remove any that are being deleted this flush
    titration_final = [ea for ea in titration_instances if ea not in session.deleted]
    # Include any new ones not yet persisted
    for obj in session.new:
        if isinstance(obj, ElementalAnalysis) and obj.sample_id == sample_id:
            if obj not in titration_final:
                titration_final.append(obj)

    has_titration = len(titration_final) > 0

    is_characterized = has_xrd or has_titration

    sample_info = session.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()

    if sample_info and sample_info.characterized != is_characterized:
        sample_info.characterized = is_characterized

@event.listens_for(Session, 'before_flush')
def before_flush_handler(session, flush_context, instances):
    """
    Listen for changes before a flush and update characterized status.
    """
    samples_to_update = set()

    # Collect sample_ids from new, modified, and deleted ExternalAnalysis and ElementalAnalysis objects
    for obj in session.new.union(session.dirty):
        if isinstance(obj, ExternalAnalysis):
            samples_to_update.add(obj.sample_id)
            # If sample_id was changed, also update the old sample
            history = attributes.get_history(obj, 'sample_id')
            if history.has_changes() and history.deleted:
                samples_to_update.add(history.deleted[0])
        if isinstance(obj, ElementalAnalysis):
            samples_to_update.add(obj.sample_id)
            history = attributes.get_history(obj, 'sample_id')
            if history.has_changes() and history.deleted:
                samples_to_update.add(history.deleted[0])

    for obj in session.deleted:
        if isinstance(obj, ExternalAnalysis):
            samples_to_update.add(obj.sample_id)
        if isinstance(obj, ElementalAnalysis):
            samples_to_update.add(obj.sample_id)

    # Process all collected sample_ids
    for sample_id in samples_to_update:
        if sample_id:
            update_sample_characterized_status(session, sample_id)

# Ensure additives summary view exists (SQLite) at import time
try:
    with engine.connect() as conn:
        conn.execute(text(
            """
            CREATE VIEW IF NOT EXISTS v_experiment_additives_summary AS
            SELECT e.experiment_id AS experiment_id,
                   GROUP_CONCAT(c.name || ' ' || CAST(a.amount AS TEXT) || ' ' || a.unit, '; ') AS additives_summary
            FROM chemical_additives a
            JOIN experimental_conditions ec ON ec.id = a.experiment_id
            JOIN experiments e ON e.id = ec.experiment_fk
            JOIN compounds c ON c.id = a.compound_id
            GROUP BY e.experiment_id;
            """
        ))
        conn.commit()
except Exception:
    # Safe to ignore at import; view creation isn't critical at this moment
    pass

@event.listens_for(ChemicalAdditive, 'before_insert')
@event.listens_for(ChemicalAdditive, 'before_update')
def calculate_additive_derived_values(mapper, connection, target):
    """
    Automatically calculate derived values for ChemicalAdditive before insert or update.
    This includes mass conversions, molar calculations, concentrations, and catalyst-specific
    values (elemental_metal_mass, catalyst_percentage, catalyst_ppm).
    """
    target.calculate_derived_values()

@event.listens_for(Session, 'before_flush')
def update_experiment_lineage_on_flush(session, flush_context, instances):
    """
    Automatically update experiment lineage fields before flushing.
    
    This listener:
    1. Parses experiment IDs for new experiments
    2. Sets base_experiment_id and parent_experiment_fk
    3. Updates orphaned derivations when a base experiment is created
    """
    from .models import Experiment
    
    # Track base experiments being inserted to update their derivations
    new_base_experiments = []
    
    # Process new experiments
    for obj in session.new:
        if isinstance(obj, Experiment) and obj.experiment_id:
            # Update lineage for this experiment
            update_experiment_lineage(session, obj)
            
            # Track if this is a potential base experiment (no derivation number)
            from .lineage_utils import parse_experiment_id
            _, derivation_num, _ = parse_experiment_id(obj.experiment_id)
            if derivation_num is None:
                new_base_experiments.append(obj.experiment_id)
    
    # After processing new experiments, update any orphaned derivations
    # This handles the case where a derivation was created before its base
    for base_exp_id in new_base_experiments:
        update_orphaned_derivations(session, base_exp_id) 