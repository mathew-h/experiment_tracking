from sqlalchemy import event
from sqlalchemy.orm import Session, attributes
from .models import ExternalAnalysis, SampleInfo, ChemicalAdditive

def update_sample_characterized_status(session: Session, sample_id: str):
    """
    Updates the 'characterized' status of a SampleInfo record based on
    the existence of 'XRD' or 'Elemental' analyses. This should be called
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

    # Determine if any of the final instances are of the characterizing types
    is_characterized = any(
        instance.analysis_type in ['XRD', 'Elemental'] for instance in final_instances
    )

    sample_info = session.query(SampleInfo).filter(SampleInfo.sample_id == sample_id).first()

    if sample_info and sample_info.characterized != is_characterized:
        sample_info.characterized = is_characterized

@event.listens_for(Session, 'before_flush')
def before_flush_handler(session, flush_context, instances):
    """
    Listen for changes before a flush and update characterized status.
    """
    samples_to_update = set()

    # Collect sample_ids from new, modified, and deleted ExternalAnalysis objects
    for obj in session.new.union(session.dirty):
        if isinstance(obj, ExternalAnalysis):
            samples_to_update.add(obj.sample_id)
            # If sample_id was changed, also update the old sample
            history = attributes.get_history(obj, 'sample_id')
            if history.has_changes() and history.deleted:
                samples_to_update.add(history.deleted[0])

    for obj in session.deleted:
        if isinstance(obj, ExternalAnalysis):
            samples_to_update.add(obj.sample_id)

    # Process all collected sample_ids
    for sample_id in samples_to_update:
        if sample_id:
            update_sample_characterized_status(session, sample_id)

@event.listens_for(ChemicalAdditive, 'before_insert')
@event.listens_for(ChemicalAdditive, 'before_update')
def calculate_additive_derived_values(mapper, connection, target):
    """
    Automatically calculate derived values for ChemicalAdditive before insert or update.
    This includes mass conversions, molar calculations, concentrations, and catalyst-specific
    values (elemental_metal_mass, catalyst_percentage, catalyst_ppm).
    """
    target.calculate_derived_values() 