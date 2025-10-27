"""
Data migration to establish experiment lineage for existing experiments.

This migration:
1. Parses all experiment IDs to identify derivations (e.g., "HPHT_MH_001-2")
2. Sets the base_experiment_id field for all derivations
3. Establishes parent_experiment_fk relationships where base experiments exist
4. Handles orphaned derivations (where base doesn't exist yet)

Run with:
    python scripts/run_data_migration.py establish_experiment_lineage_006
or:
    python database/data_migrations/establish_experiment_lineage_006.py
"""
from database import SessionLocal
from database.models import Experiment
from database.lineage_utils import parse_experiment_id, get_or_find_parent_experiment


def establish_experiment_lineage(dry_run: bool = False) -> dict:
    """
    Establish lineage relationships for all existing experiments.
    
    Args:
        dry_run: If True, rollback changes instead of committing
        
    Returns:
        A dictionary with migration statistics
    """
    db = SessionLocal()
    summary = {
        "experiments_scanned": 0,
        "derivations_found": 0,
        "parents_linked": 0,
        "orphaned_derivations": 0,
        "errors": 0,
    }
    
    try:
        # Get all experiments
        experiments = db.query(Experiment).all()
        summary["experiments_scanned"] = len(experiments)
        
        print(f"Scanning {summary['experiments_scanned']} experiments...")
        
        # First pass: Parse IDs and set base_experiment_id
        for exp in experiments:
            try:
                if not exp.experiment_id:
                    continue
                
                base_id, derivation_num = parse_experiment_id(exp.experiment_id)
                
                if derivation_num is not None:
                    # This is a derivation
                    summary["derivations_found"] += 1
                    exp.base_experiment_id = base_id
                    print(f"  Found derivation: {exp.experiment_id} -> base: {base_id}")
                else:
                    # This is a base experiment, ensure lineage fields are clear
                    exp.base_experiment_id = None
                    exp.parent_experiment_fk = None
            
            except Exception as e:
                summary["errors"] += 1
                print(f"  Error processing {exp.experiment_id}: {e}")
        
        # Commit first pass
        if not dry_run:
            db.commit()
        else:
            db.flush()
        
        # Second pass: Resolve parent relationships
        print("\nResolving parent relationships...")
        derivations = db.query(Experiment).filter(
            Experiment.base_experiment_id.isnot(None)
        ).all()
        
        for deriv in derivations:
            try:
                parent = get_or_find_parent_experiment(db, deriv.experiment_id)
                
                if parent:
                    deriv.parent_experiment_fk = parent.id
                    summary["parents_linked"] += 1
                    print(f"  Linked {deriv.experiment_id} to parent {parent.experiment_id}")
                else:
                    summary["orphaned_derivations"] += 1
                    print(f"  Warning: Orphaned derivation {deriv.experiment_id} (base '{deriv.base_experiment_id}' not found)")
            
            except Exception as e:
                summary["errors"] += 1
                print(f"  Error linking parent for {deriv.experiment_id}: {e}")
        
        # Final commit or rollback
        if dry_run:
            print("\n=== DRY RUN: Rolling back changes ===")
            db.rollback()
        else:
            db.commit()
            print("\n=== Changes committed ===")
        
        return summary
    
    except Exception as e:
        print(f"\nCritical error during migration: {e}")
        db.rollback()
        raise
    
    finally:
        db.close()


def run_migration():
    """
    Entry point for scripts/run_data_migration.py runner.
    """
    print("=" * 60)
    print("ESTABLISHING EXPERIMENT LINEAGE")
    print("=" * 60)
    
    # Run the migration
    summary = establish_experiment_lineage(dry_run=False)
    
    # Print summary
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Experiments scanned:     {summary['experiments_scanned']}")
    print(f"Derivations found:       {summary['derivations_found']}")
    print(f"Parents linked:          {summary['parents_linked']}")
    print(f"Orphaned derivations:    {summary['orphaned_derivations']}")
    print(f"Errors:                  {summary['errors']}")
    print("=" * 60)
    
    if summary["orphaned_derivations"] > 0:
        print("\nNote: Orphaned derivations have their base_experiment_id set")
        print("but parent_experiment_fk is NULL because the base experiment")
        print("doesn't exist. When the base experiment is created, the relationship")
        print("will be automatically established by the event listeners.")
    
    return True


if __name__ == "__main__":
    # Simple manual runner for local use
    import sys
    
    dry_run = "--dry-run" in sys.argv
    
    if dry_run:
        print("Running in DRY RUN mode (no changes will be saved)\n")
    
    summary = establish_experiment_lineage(dry_run=dry_run)
    
    print("\nSummary:")
    print(summary)

