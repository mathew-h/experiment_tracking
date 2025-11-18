# Example Usage: Testing the Experiment Lineage Migration

This document provides a quick walkthrough of testing the `establish_experiment_lineage_006` migration.

## Quick Test Run

You can now run the tests I've created! Here's what you should try:

### 1. Run the Unit Tests

```bash
# Run all lineage migration tests
python -m pytest tests/test_lineage_migration.py -v -s

# Or run a specific test
python -m pytest tests/test_lineage_migration.py::TestExperimentLineageMigration::test_parse_experiment_id -v
```

This will test the parsing logic and migration behavior on synthetic data.

### 2. Test on Your Actual Database (Safe Mode)

```bash
# This creates a temp copy and tests the migration without touching your real database
python tests/run_migration_with_snapshot.py establish_experiment_lineage_006
```

**What this does:**
- ✓ Creates a snapshot: `tests/snapshots/pre_establish_experiment_lineage_006.db`
- ✓ Copies your database to a temporary location
- ✓ Runs the migration on the copy
- ✓ Shows you before/after comparison
- ✓ Cleans up the temporary copy
- ✓ **Your production database is NOT modified**

**Example Output:**

```
======================================================================
DATA MIGRATION WITH SNAPSHOT
======================================================================
Migration: establish_experiment_lineage_006
Mode: TEST
======================================================================

📊 Source database: experiments.db

──────────────────────────────────────────────────────────────────────
STEP 1: Creating snapshot of current database
──────────────────────────────────────────────────────────────────────
✓ Snapshot created: tests/snapshots/pre_establish_experiment_lineage_006.db

──────────────────────────────────────────────────────────────────────
STEP 2: Analyzing current database state
──────────────────────────────────────────────────────────────────────

Table row counts:
  experiments                    52 rows
  experimental_conditions        50 rows
  ...

──────────────────────────────────────────────────────────────────────
Current experiment lineage state:
============================================================
EXPERIMENT LINEAGE REPORT
============================================================
Total experiments:        52
Base experiments:         52
Derivations:              0
  - Linked to parent:     0
  - Orphaned:             0
============================================================

──────────────────────────────────────────────────────────────────────
STEP 3: Creating temporary test database
──────────────────────────────────────────────────────────────────────
✓ Temporary test database created: C:\...\test_migration.db

──────────────────────────────────────────────────────────────────────
STEP 4: Running migration on test copy
──────────────────────────────────────────────────────────────────────
Scanning 52 experiments...
  Found derivation: HPHT_MH_001-2 -> base: HPHT_MH_001
  Found derivation: HPHT_MH_001-3 -> base: HPHT_MH_001
  ...

Resolving parent relationships...
  Linked HPHT_MH_001-2 to parent HPHT_MH_001
  Linked HPHT_MH_001-3 to parent HPHT_MH_001
  ...

=== Changes committed ===

✓ Migration completed
  Experiments scanned:     52
  Derivations found:       8
  Parents linked:          7
  Orphaned derivations:    1
  Errors:                  0

──────────────────────────────────────────────────────────────────────
STEP 5: Verifying migration results
──────────────────────────────────────────────────────────────────────

Table row count changes:
  No row count changes (migration updated existing rows)

──────────────────────────────────────────────────────────────────────
Experiment lineage state after migration:
============================================================
EXPERIMENT LINEAGE REPORT
============================================================
Total experiments:        52
Base experiments:         44
Derivations:              8
  - Linked to parent:     7
  - Orphaned:             1
============================================================

Orphaned derivations:
  - SOME_EXP-2

Linked derivations:
  - HPHT_MH_001-2
  - HPHT_MH_001-3
  ...

======================================================================
MIGRATION SUMMARY
======================================================================
✓ Migration tested successfully on temporary copy
✓ Snapshot saved at: tests/snapshots/pre_establish_experiment_lineage_006.db

To apply to production, run:
  python tests/run_migration_with_snapshot.py establish_experiment_lineage_006 --apply
======================================================================
```

### 3. Apply to Production (If Test Looks Good)

```bash
python tests/run_migration_with_snapshot.py establish_experiment_lineage_006 --apply
```

**Important:** This will ask for confirmation:

```
⚠️  WARNING: You are about to apply this migration to the PRODUCTION database!
This operation will modify your data.
A snapshot will be created for rollback, but proceed with caution.

Type 'YES' to confirm:
```

Type `YES` and press Enter to proceed.

### 4. Rollback (If Needed)

If something goes wrong, you can restore from the snapshot:

```bash
# List available snapshots
python tests/restore_snapshot.py

# Restore from a specific snapshot
python tests/restore_snapshot.py tests/snapshots/pre_establish_experiment_lineage_006.db
```

## Understanding the Results

### What Gets Updated

The migration identifies experiments with IDs like:
- `HPHT_MH_001-2` → Derivation of `HPHT_MH_001`
- `HPHT_MH_001-3` → Derivation of `HPHT_MH_001`
- `LEACH_TEST_005-1` → Derivation of `LEACH_TEST_005`

And sets:
- `base_experiment_id`: The base experiment ID (e.g., "HPHT_MH_001")
- `parent_experiment_fk`: Foreign key to the parent experiment's ID

### Orphaned Derivations

If you have an experiment like `HPHT_MH_001-2` but no `HPHT_MH_001` in the database:
- `base_experiment_id` is set to "HPHT_MH_001"
- `parent_experiment_fk` remains NULL
- When you create `HPHT_MH_001` later, the relationship will be established automatically

### Non-Derivations

Experiments with hyphens that DON'T end in numbers are left alone:
- `HPHT-HIGH-TEMP` → Not a derivation
- `TEST-SAMPLE-ABC` → Not a derivation
- `LEACH-001` → IS a derivation (001 = numeric)

## Python API Usage

You can also use the snapshot utilities in your own scripts:

```python
from tests.snapshot import DatabaseSnapshot, get_experiment_lineage_info, print_lineage_report
from database import SessionLocal

# Create snapshot
snapshot = DatabaseSnapshot("experiments.db")
snapshot.create_snapshot("my_custom_backup")

# Get lineage info
session = SessionLocal()
lineage_info = get_experiment_lineage_info(session)
print_lineage_report(lineage_info)

# Access specific data
print(f"Total derivations: {lineage_info['derivations']}")
print(f"Orphaned IDs: {lineage_info['orphaned_experiment_ids']}")

session.close()
```

## For Lab PC Deployment

When you're ready to run this on the Lab PC:

1. **Pull changes from GitHub** (in Git Bash):
   ```bash
   cd /c/path/to/experiment_tracking
   git pull origin main
   ```

2. **Stop the Streamlit app** (if running)

3. **Test the migration** (in PowerShell or Command Prompt):
   ```bash
   python tests/run_migration_with_snapshot.py establish_experiment_lineage_006
   ```

4. **Review the output carefully**

5. **Apply if satisfied**:
   ```bash
   python tests/run_migration_with_snapshot.py establish_experiment_lineage_006 --apply
   ```

6. **Restart the Streamlit app**

7. **Verify in the UI** that experiment relationships look correct

## Troubleshooting

### "Database is locked"
- Stop Streamlit app
- Close any DB browser tools
- Try again

### "Module not found" errors
Make sure you're in the project root and your virtual environment is activated:
```bash
cd /c/path/to/experiment_tracking
.venv/Scripts/activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

### Tests fail
The tests use in-memory databases with synthetic data. If they fail:
1. Check the error message
2. The parsing logic might need adjustment for your specific ID format
3. Open an issue or ask for help

## What's Next?

After running the migration successfully:
- Existing experiments have lineage set
- New experiments will automatically have lineage set (via event listeners)
- You can query derivations: `experiment.derived_experiments`
- You can query parents: `experiment.parent`

Enjoy your new experiment lineage tracking! 🎉

