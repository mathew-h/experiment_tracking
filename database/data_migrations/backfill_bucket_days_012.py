"""
Data Migration 012: Backfill time_post_reaction_bucket_days

Populates NULL time_post_reaction_bucket_days values on experimental_results rows
that were created via the UI form path before the bucket normalization fix.
Also re-evaluates primary result designations for affected experiments.

Why needed:
  The save_results() UI form path did not set time_post_reaction_bucket_days,
  leaving it NULL. This prevented scalar data (ammonia, hydrogen) from being
  plotted against the bucket-aligned time axis in the v_primary_experiment_results
  view, while ICP data (whose ingestion path always set the bucket) plotted fine.

Usage:
  python database/data_migrations/backfill_bucket_days_012.py          # Dry run
  python database/data_migrations/backfill_bucket_days_012.py --apply  # Apply
"""

import sys
import os
import argparse

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy.orm import Session
from database import SessionLocal, ExperimentalResults
from backend.services.result_merge_utils import (
    normalize_timepoint,
    ensure_primary_result_for_timepoint,
)


def run_migration(apply: bool = False):
    db: Session = SessionLocal()
    try:
        # Find rows that have a time value but no bucket value
        rows_missing_bucket = (
            db.query(ExperimentalResults)
            .filter(
                ExperimentalResults.time_post_reaction_days.isnot(None),
                ExperimentalResults.time_post_reaction_bucket_days.is_(None),
            )
            .all()
        )

        print(f"Found {len(rows_missing_bucket)} result row(s) with NULL time_post_reaction_bucket_days.")

        if not rows_missing_bucket:
            print("Nothing to do.")
            return

        # Preview affected rows
        for row in rows_missing_bucket:
            normalized = normalize_timepoint(row.time_post_reaction_days)
            print(
                f"  Result ID {row.id}  experiment_fk={row.experiment_fk}  "
                f"time_days={row.time_post_reaction_days}  -> bucket={normalized}  "
                f"primary={row.is_primary_timepoint_result}"
            )

        if not apply:
            print("\nDry run complete. Re-run with --apply to persist changes.")
            return

        # Apply bucket values
        for row in rows_missing_bucket:
            row.time_post_reaction_bucket_days = normalize_timepoint(row.time_post_reaction_days)
        db.flush()

        # Re-evaluate primary designations for each affected experiment/timepoint
        affected_experiments = {row.experiment_fk for row in rows_missing_bucket}
        print(f"\nRe-evaluating primary designations for {len(affected_experiments)} experiment(s)...")

        for exp_fk in affected_experiments:
            exp_results = (
                db.query(ExperimentalResults)
                .filter(ExperimentalResults.experiment_fk == exp_fk)
                .all()
            )
            seen_buckets: set = set()
            for r in exp_results:
                bucket_key = (r.experiment_fk, r.time_post_reaction_bucket_days)
                if bucket_key not in seen_buckets:
                    seen_buckets.add(bucket_key)
                    ensure_primary_result_for_timepoint(
                        db=db,
                        experiment_fk=r.experiment_fk,
                        time_post_reaction=r.time_post_reaction_days,
                    )

        db.commit()
        print(f"\nBackfilled {len(rows_missing_bucket)} row(s) and re-evaluated primary designations. Done.")

    except Exception as e:
        print(f"Error during migration: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    args = parser.parse_args()
    run_migration(apply=args.apply)
