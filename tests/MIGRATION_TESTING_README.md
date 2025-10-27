# Data Migration Testing Guide

This guide explains how to safely test and run data migrations using the snapshot utilities.

## Overview

The migration testing system provides:

1. **Snapshot creation** - Capture database state before migrations
2. **Test runs** - Run migrations on temporary copies
3. **Verification** - Compare before/after states
4. **Safe rollback** - Restore from snapshots if needed

## Files

- `snapshot.py` - Core snapshot utility and helper functions
- `test_lineage_migration.py` - Unit tests for experiment lineage migration
- `run_migration_with_snapshot.py` - Interactive migration runner with snapshots
- `restore_snapshot.py` - Restore database from a snapshot

## Quick Start

### Testing a Migration (Recommended Workflow)

1. **Test on a temporary copy first:**
   ```bash
   python tests/run_migration_with_snapshot.py establish_experiment_lineage_006
   ```

   This will:
   - Create a snapshot of your current database
   - Create a temporary test copy
   - Run the migration on the test copy
   - Show you the before/after comparison
   - Clean up the test copy

2. **If the test looks good, apply to production:**
   ```bash
   python tests/run_migration_with_snapshot.py establish_experiment_lineage_006 --apply
   ```

   This will:
   - Create a snapshot for rollback
   - Run the migration on your production database
   - Show verification results

3. **If something goes wrong, rollback:**
   ```bash
   python tests/restore_snapshot.py tests/snapshots/pre_establish_experiment_lineage_006.db
   ```

## Running Unit Tests

Run the comprehensive test suite:

```bash
# Run all migration tests
pytest tests/test_lineage_migration.py -v

# Run a specific test
pytest tests/test_lineage_migration.py::TestExperimentLineageMigration::test_migration_on_sample_data -v

# Run with output
pytest tests/test_lineage_migration.py -v -s
```

## Using the Snapshot Utility Programmatically

### Basic Usage

```python
from tests.snapshot import DatabaseSnapshot

# Create snapshot utility
snapshot = DatabaseSnapshot("experiments.db")

# Create a snapshot
snapshot_path = snapshot.create_snapshot("before_my_changes")

# Create a temporary test copy
temp_db_path, temp_url = snapshot.create_temp_copy()

# ... run migration on temp database ...

# Compare databases
comparison = snapshot.compare_databases("experiments.db", temp_db_path)
print(comparison)

# Cleanup
snapshot.cleanup()
```

### Extracting Lineage Information

```python
from tests.snapshot import get_experiment_lineage_info, print_lineage_report
from database import SessionLocal

# Get lineage info
session = SessionLocal()
lineage_info = get_experiment_lineage_info(session)

# Print a formatted report
print_lineage_report(lineage_info)

# Access specific data
print(f"Total derivations: {lineage_info['derivations']}")
print(f"Orphaned: {lineage_info['orphaned_experiment_ids']}")
```

## Test Coverage

The test suite covers:

1. **ID Parsing** - Correctly identifies base experiments vs derivations
2. **Parent Finding** - Locates parent experiments for derivations
3. **Orphan Handling** - Handles derivations with missing parents
4. **Edge Cases** - Non-derivations with hyphens, empty IDs, etc.
5. **Dry Run** - Verifies dry-run mode doesn't commit changes
6. **Idempotency** - Ensures running migration multiple times is safe
7. **Full Migration** - End-to-end migration process with verification

## Migration Workflow Best Practices

### Development (Personal PC)

1. Create a test migration script in `database/data_migrations/`
2. Write unit tests in `tests/test_lineage_migration.py` (or similar)
3. Run unit tests: `pytest tests/test_lineage_migration.py -v`
4. Test with snapshot tool: `python tests/run_migration_with_snapshot.py <migration_name>`
5. Commit and push to GitHub

### Production (Lab PC)

1. Pull latest changes from GitHub
2. Test migration first (without --apply):
   ```bash
   python tests/run_migration_with_snapshot.py <migration_name>
   ```
3. Review the test results carefully
4. Apply to production (if tests pass):
   ```bash
   python tests/run_migration_with_snapshot.py <migration_name> --apply
   ```
5. Verify the results in the Streamlit app
6. Keep the snapshot for at least 48 hours in case rollback is needed

### Rollback Procedure

If you need to rollback a migration:

1. Stop the Streamlit app
2. List available snapshots:
   ```bash
   python tests/restore_snapshot.py
   ```
3. Restore from snapshot:
   ```bash
   python tests/restore_snapshot.py tests/snapshots/<snapshot_name>.db
   ```
4. Restart the Streamlit app
5. Verify the rollback was successful

## Example: Testing Experiment Lineage Migration

```bash
# Step 1: Run unit tests
pytest tests/test_lineage_migration.py -v -s

# Step 2: Test on a temporary copy
python tests/run_migration_with_snapshot.py establish_experiment_lineage_006

# Example output:
# ======================================================================
# DATA MIGRATION WITH SNAPSHOT
# ======================================================================
# Migration: establish_experiment_lineage_006
# Mode: TEST
# ======================================================================
# 
# 📊 Source database: experiments.db
# 
# ──────────────────────────────────────────────────────────────────────
# STEP 1: Creating snapshot of current database
# ──────────────────────────────────────────────────────────────────────
# ✓ Snapshot created: tests/snapshots/pre_establish_experiment_lineage_006.db
# 
# ──────────────────────────────────────────────────────────────────────
# STEP 2: Analyzing current database state
# ──────────────────────────────────────────────────────────────────────
# 
# Table row counts:
#   experiments                    150 rows
#   experimental_conditions         148 rows
#   ...
# 
# ──────────────────────────────────────────────────────────────────────
# Current experiment lineage state:
# ============================================================
# EXPERIMENT LINEAGE REPORT
# ============================================================
# Total experiments:        150
# Base experiments:         150
# Derivations:              0
# ...

# Step 3: Review output and apply if satisfied
python tests/run_migration_with_snapshot.py establish_experiment_lineage_006 --apply
```

## Snapshot Management

### Listing Snapshots

```bash
ls -lh tests/snapshots/
```

### Cleaning Old Snapshots

```bash
# Remove snapshots older than 7 days
find tests/snapshots/ -name "*.db" -mtime +7 -delete
```

### Manual Snapshot Creation

```python
from tests.snapshot import DatabaseSnapshot

snapshot = DatabaseSnapshot("experiments.db")
snapshot.create_snapshot("manual_backup_before_experiment_001")
```

## Troubleshooting

### "Database is locked" error

If you see this error:
1. Make sure the Streamlit app is stopped
2. Close any DB browser tools
3. Try again

### Migration fails partway through

The migration includes rollback on error, but if something goes wrong:
1. Restore from the most recent snapshot
2. Review the error message
3. Fix the migration script
4. Test again

### Snapshot directory fills up

Snapshots are stored in `tests/snapshots/`. Clean up old snapshots periodically:
```bash
# Keep only snapshots from the last 7 days
find tests/snapshots/ -name "*.db" -mtime +7 -delete
```

## Advanced Usage

### Testing Multiple Migrations in Sequence

```python
from tests.snapshot import DatabaseSnapshot

snapshot = DatabaseSnapshot("experiments.db")

# Create base snapshot
base_snapshot = snapshot.create_snapshot("before_migrations")

# Test migrations in sequence
migrations = [
    "migration_001",
    "migration_002", 
    "migration_003"
]

for migration_name in migrations:
    print(f"\nTesting {migration_name}...")
    # Run migration (pseudo-code)
    # Verify results
    
# Restore to base state between tests
snapshot.restore_snapshot()
```

### Custom Verification Queries

```python
from database import SessionLocal
from database.models import Experiment

session = SessionLocal()

# Custom verification
derivations = session.query(Experiment).filter(
    Experiment.base_experiment_id.isnot(None)
).all()

for deriv in derivations:
    parent = session.query(Experiment).filter_by(
        id=deriv.parent_experiment_fk
    ).first()
    
    print(f"{deriv.experiment_id} -> {parent.experiment_id if parent else 'ORPHANED'}")
```

## Integration with CI/CD

You can add migration tests to your CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Test data migrations
  run: |
    pytest tests/test_lineage_migration.py -v
```

## Questions?

See also:
- `database/data_migrations/README.md` - Migration documentation
- `scripts/run_data_migration.py` - Simple migration runner
- Individual migration scripts for inline documentation

