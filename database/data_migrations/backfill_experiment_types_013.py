"""
Data migration to backfill experiment_type on all ExperimentalConditions rows.

For each conditions row the experiment_type is inferred from the leading prefix
of experiment_id (e.g. "HPHT" → "HPHT", "CF" → "Core Flood", etc.).

Rows that already have a non-null experiment_type are left unchanged unless
--force is supplied, which overwrites every row with the inferred value.

Run modes
---------
Dry run (preview only, no changes saved):
    python database/data_migrations/backfill_experiment_types_013.py

Apply changes:
    python database/data_migrations/backfill_experiment_types_013.py --apply

Force overwrite all rows (even those already set):
    python database/data_migrations/backfill_experiment_types_013.py --apply --force
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from database import SessionLocal
from database.models import ExperimentalConditions
from backend.services.experiment_type_service import infer_experiment_type_value


def backfill_experiment_types(dry_run: bool = True, force: bool = False) -> dict:
    """
    Backfill ExperimentalConditions.experiment_type from the experiment_id prefix.

    Args:
        dry_run: When True, rolls back all changes instead of committing.
        force:   When True, overwrites rows that already have an experiment_type.

    Returns:
        Summary dict with counts of rows inspected, updated, skipped, and errored.
    """
    db = SessionLocal()
    summary = {
        "rows_inspected": 0,
        "rows_updated": 0,
        "rows_skipped": 0,
        "rows_errored": 0,
    }

    try:
        conditions = db.query(ExperimentalConditions).all()
        summary["rows_inspected"] = len(conditions)

        print(f"Inspecting {summary['rows_inspected']} ExperimentalConditions rows...\n")

        for cond in conditions:
            try:
                if not cond.experiment_id:
                    summary["rows_skipped"] += 1
                    print(f"  SKIP  (no experiment_id) conditions.id={cond.id}")
                    continue

                inferred = infer_experiment_type_value(cond.experiment_id)
                current = cond.experiment_type

                if current is not None and not force:
                    summary["rows_skipped"] += 1
                    print(
                        f"  SKIP  {cond.experiment_id:<30} already has type='{current}'"
                    )
                    continue

                if current == inferred and not force:
                    summary["rows_skipped"] += 1
                    continue

                print(
                    f"  {'SET ' if current is None else 'OVERWRITE'}"
                    f"  {cond.experiment_id:<30}"
                    f"  '{current}' → '{inferred}'"
                )
                cond.experiment_type = inferred
                summary["rows_updated"] += 1

            except Exception as exc:
                summary["rows_errored"] += 1
                print(f"  ERROR processing conditions.id={cond.id} "
                      f"({cond.experiment_id}): {exc}")

        if dry_run:
            print("\n=== DRY RUN: Rolling back — no changes saved ===")
            db.rollback()
        else:
            db.commit()
            print("\n=== Changes committed ===")

        return summary

    except Exception as exc:
        print(f"\nCritical error during migration: {exc}")
        db.rollback()
        raise

    finally:
        db.close()


def run_migration():
    """Entry point called by scripts/run_data_migration.py."""
    print("=" * 60)
    print("BACKFILL EXPERIMENT TYPES (migration 013)")
    print("=" * 60)

    summary = backfill_experiment_types(dry_run=False, force=False)

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Rows inspected:  {summary['rows_inspected']}")
    print(f"Rows updated:    {summary['rows_updated']}")
    print(f"Rows skipped:    {summary['rows_skipped']}")
    print(f"Rows errored:    {summary['rows_errored']}")
    print("=" * 60)

    return True


if __name__ == "__main__":
    dry_run = "--apply" not in sys.argv
    force = "--force" in sys.argv

    if dry_run:
        print("Running in DRY RUN mode (pass --apply to save changes)\n")
    if force:
        print("FORCE mode: all rows will be overwritten with inferred type\n")

    summary = backfill_experiment_types(dry_run=dry_run, force=force)

    print("\nSummary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
