"""
Backfill cumulative_time_post_reaction_days for all experimental result rows.

Background
----------
``cumulative_time_post_reaction_days`` is meant to represent the true elapsed
time across a parent → child experiment chain.  For example, in the chain:

    SERUM_JW_051 (max 14 d)
        └─ SERUM_JW_051-2 (max 10 d, offset = 14)
            ├─ SERUM_JW_051-3 (offset should be 24 = 14+10)
            └─ SERUM_JW_051-4 (offset should be 24 = 14+10)

Two bugs left some experiments with wrong values:

1. ``parent_experiment_fk`` NULL on derivations whose parent existed at
   migration time but was not linked (e.g. SERUM_JW_051-3).  Because
   ``get_ancestor_time_offset`` stops walking when it hits a NULL parent,
   those experiments end up with offset 0 and cumulative == raw time.

2. Root experiments with ``base_experiment_id = NULL`` were silently
   excluded from the chain query inside
   ``update_cumulative_times_for_chain``, so their own rows were never
   written.

This script fixes both:

  Pass 1 – re-verify lineage
    Re-runs ``update_experiment_lineage`` for every experiment to ensure
    ``base_experiment_id`` and ``parent_experiment_fk`` are correct.

  Pass 2 – recalculate cumulative times
    Iterates every experiment, calls ``get_ancestor_time_offset`` (which
    now has correct parent links), and stamps the result on every
    ``ExperimentalResults`` row belonging to that experiment.

Usage
-----
    # Preview (no changes saved):
    python database/data_migrations/backfill_cumulative_times_012.py

    # Apply:
    python database/data_migrations/backfill_cumulative_times_012.py --apply
"""

import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy.orm import Session

from database import SessionLocal
from database.models import Experiment, ExperimentalResults
from database.lineage_utils import update_experiment_lineage
from backend.services.result_merge_utils import get_ancestor_time_offset


# ---------------------------------------------------------------------------
# Pass 1 – repair lineage
# ---------------------------------------------------------------------------

def repair_lineage(db: Session, dry_run: bool) -> dict:
    """Ensure every experiment has correct base_experiment_id / parent_experiment_fk."""
    stats = {
        "scanned": 0,
        "base_id_fixed": 0,
        "parent_fk_fixed": 0,
        "orphaned": 0,
    }

    experiments = db.query(Experiment).order_by(Experiment.experiment_id).all()
    stats["scanned"] = len(experiments)

    for exp in experiments:
        old_base = exp.base_experiment_id
        old_parent_fk = exp.parent_experiment_fk

        changed = update_experiment_lineage(db, exp)

        if not changed:
            continue

        if exp.base_experiment_id != old_base:
            stats["base_id_fixed"] += 1
            print(
                f"  [lineage] {exp.experiment_id}: "
                f"base_experiment_id  {old_base!r} -> {exp.base_experiment_id!r}"
            )

        if exp.parent_experiment_fk != old_parent_fk:
            if exp.parent_experiment_fk is None:
                stats["orphaned"] += 1
                print(
                    f"  [lineage] {exp.experiment_id}: "
                    f"parent_experiment_fk {old_parent_fk} -> NULL  (orphaned - parent not found)"
                )
            else:
                stats["parent_fk_fixed"] += 1
                # Resolve parent experiment_id for a readable log line
                parent_exp = db.query(Experiment).filter(
                    Experiment.id == exp.parent_experiment_fk
                ).first()
                parent_label = parent_exp.experiment_id if parent_exp else exp.parent_experiment_fk
                print(
                    f"  [lineage] {exp.experiment_id}: "
                    f"parent_experiment_fk {old_parent_fk} -> {exp.parent_experiment_fk} "
                    f"({parent_label})"
                )

    if dry_run:
        db.flush()
    else:
        db.commit()

    return stats


# ---------------------------------------------------------------------------
# Pass 2 – recalculate cumulative times
# ---------------------------------------------------------------------------

def recalculate_cumulative_times(db: Session, dry_run: bool) -> dict:
    """
    For every experiment, compute the correct ancestor offset and stamp
    cumulative_time_post_reaction_days on all its result rows.
    """
    stats = {
        "experiments_processed": 0,
        "rows_checked": 0,
        "rows_changed": 0,
        "rows_cleared": 0,
    }

    experiments = db.query(Experiment).order_by(Experiment.experiment_id).all()

    for exp in experiments:
        offset = get_ancestor_time_offset(db, exp)

        results = (
            db.query(ExperimentalResults)
            .filter(ExperimentalResults.experiment_fk == exp.id)
            .all()
        )

        stats["experiments_processed"] += 1

        for row in results:
            stats["rows_checked"] += 1
            old_val = row.cumulative_time_post_reaction_days

            if row.time_post_reaction_days is not None:
                new_val = round(offset + row.time_post_reaction_days, 6)
            else:
                new_val = None

            # Treat both-None as unchanged; compare floats with a tiny epsilon
            changed = False
            if new_val is None and old_val is not None:
                changed = True
                stats["rows_cleared"] += 1
            elif new_val is not None and old_val is None:
                changed = True
                stats["rows_changed"] += 1
            elif new_val is not None and old_val is not None:
                if abs(new_val - old_val) > 1e-6:
                    changed = True
                    stats["rows_changed"] += 1

            if changed:
                print(
                    f"  [cumtime] {exp.experiment_id}  "
                    f"t={row.time_post_reaction_days}d  "
                    f"offset={offset}  "
                    f"cumulative: {old_val} -> {new_val}"
                )
                row.cumulative_time_post_reaction_days = new_val

    if dry_run:
        db.flush()
    else:
        db.commit()

    return stats


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def run_migration(dry_run: bool = True) -> bool:
    db: Session = SessionLocal()
    try:
        mode_label = "DRY RUN (no changes saved)" if dry_run else "APPLY MODE"
        print("=" * 65)
        print(f"BACKFILL CUMULATIVE TIMES  --  {mode_label}")
        print("=" * 65)

        # ------------------------------------------------------------------
        print("\n--- Pass 1: Verify / repair experiment lineage ---")
        lineage_stats = repair_lineage(db, dry_run)
        print(f"\n  Experiments scanned : {lineage_stats['scanned']}")
        print(f"  base_experiment_id  fixes : {lineage_stats['base_id_fixed']}")
        print(f"  parent_experiment_fk fixes : {lineage_stats['parent_fk_fixed']}")
        print(f"  Orphaned derivations (parent not found) : {lineage_stats['orphaned']}")

        # ------------------------------------------------------------------
        print("\n--- Pass 2: Recalculate cumulative_time_post_reaction_days ---")
        time_stats = recalculate_cumulative_times(db, dry_run)
        print(f"\n  Experiments processed : {time_stats['experiments_processed']}")
        print(f"  Result rows checked   : {time_stats['rows_checked']}")
        print(f"  Rows updated          : {time_stats['rows_changed']}")
        print(f"  Rows cleared (NULL)   : {time_stats['rows_cleared']}")

        print("\n" + "=" * 65)
        if dry_run:
            print("DRY RUN complete -- re-run with --apply to save changes.")
        else:
            print("Migration complete — changes committed.")
        print("=" * 65)

        return True

    except Exception as exc:
        print(f"\nCritical error: {exc}")
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    if not apply:
        print("Running in DRY RUN mode (pass --apply to save changes)\n")
    run_migration(dry_run=not apply)
