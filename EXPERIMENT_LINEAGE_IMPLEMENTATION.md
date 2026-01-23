# Experiment Lineage System - Implementation Summary

## Overview
Successfully implemented a single-level experiment lineage tracking system that automatically identifies and links experiment derivations (e.g., "HPHT_MH_001-2" derives from "HPHT_MH_001").

## What Was Implemented

### 1. Database Schema Changes (`database/models/experiments.py`)
Added two new columns to the `Experiment` model:
- `base_experiment_id` (String): Stores the base experiment ID for derivations
- `parent_experiment_fk` (Integer, FK): Foreign key linking to the parent experiment
- Added `parent` and `derived_experiments` relationships for easy navigation

### 2. Lineage Utilities (`database/lineage_utils.py`)
Created utility functions for lineage management:
- `parse_experiment_id()`: Parses experiment IDs to extract base ID and derivation number
- `get_or_find_parent_experiment()`: Finds the parent experiment in the database
- `update_experiment_lineage()`: Updates lineage fields for an experiment
- `update_orphaned_derivations()`: Links derivations when their base experiment is created

### 3. Event Listeners (`database/event_listeners.py`)
Added automatic lineage tracking:
- `update_experiment_lineage_on_flush()`: Automatically sets lineage fields when experiments are created
- Handles orphaned derivations (created before their base experiment exists)
- Event listeners trigger on every experiment insert, ensuring lineage is always maintained

### 4. Data Migration (`database/data_migrations/establish_experiment_lineage_006.py`)
Created migration script to establish lineage for existing experiments:
- Two-pass approach: first sets base_experiment_id, then resolves parent_experiment_fk
- Handles orphaned derivations gracefully
- Includes dry-run mode for testing

### 5. Documentation (`database/data_migrations/README.md`)
Updated README with migration documentation and usage examples.

## How It Works

### Parsing Logic
The system identifies derivations by looking for experiment IDs ending with "-N" where N is a number:
- `"HPHT_MH_001-2"` → Base: `"HPHT_MH_001"`, Derivation: 2
- `"HPHT_MH_001"` → Base experiment (no derivation)
- `"HPHT-MH-001"` → Base experiment (hyphens are part of the ID, not a derivation)

### Automatic Lineage Establishment
When a new experiment is created:
1. Event listener parses the experiment_id
2. If it's a derivation, sets `base_experiment_id`
3. Attempts to find and link to the parent experiment
4. If the parent doesn't exist yet, leaves `parent_experiment_fk` as NULL
5. When the base experiment is later created, orphaned derivations are automatically linked

### Case-Insensitive Matching
The system uses case-insensitive matching and ignores hyphens, underscores, and spaces when finding parent experiments, ensuring flexible ID matching.

## Deployment Instructions

### Step 1: Generate Database Migration
On your **personal work computer**, generate the Alembic migration for the schema changes:

```bash
# In the project root directory
alembic revision --autogenerate -m "Add experiment lineage tracking"
```

This will create a new migration file in `database/migrations/versions/`.

### Step 2: Review the Migration
Review the generated migration file to ensure it includes:
- Adding `base_experiment_id` column (String, nullable, indexed)
- Adding `parent_experiment_fk` column (Integer, FK to experiments.id, nullable)

### Step 3: Commit and Push Changes
```bash
git add .
git commit -m "Implement experiment lineage tracking system"
git push origin main
```

### Step 4: Deploy to Lab PC
On the **Lab PC**, run these commands in Git Bash:

```bash
# Navigate to the project directory
cd /c/path/to/experiment_tracking

# Pull the latest changes
git pull origin main

# Apply the database schema migration
alembic upgrade head

# Run the data migration to establish lineage for existing experiments
python scripts/run_data_migration.py establish_experiment_lineage_006

# Restart the Streamlit app
# (Stop the current app if running, then restart)
```

## Usage Examples

### Creating Derivation Experiments
Simply create an experiment with an ID ending in "-N":

```python
# In the UI or via code:
experiment = Experiment(
    experiment_number=next_number,
    experiment_id="HPHT_MH_001-2",  # Derivation format
    researcher="John Doe",
    # ... other fields
)
db.add(experiment)
db.commit()

# The lineage fields will be automatically set by event listeners:
# - base_experiment_id = "HPHT_MH_001"
# - parent_experiment_fk = (id of "HPHT_MH_001" experiment, if it exists)
```

### Querying Lineage
```python
# Get parent experiment
experiment = db.query(Experiment).filter_by(experiment_id="HPHT_MH_001-2").first()
if experiment.parent:
    print(f"Parent: {experiment.parent.experiment_id}")

# Get all derivations of a base experiment
base_exp = db.query(Experiment).filter_by(experiment_id="HPHT_MH_001").first()
for derivation in base_exp.derived_experiments:
    print(f"Derivation: {derivation.experiment_id}")

# Query all derivations with a specific base
derivations = db.query(Experiment).filter_by(base_experiment_id="HPHT_MH_001").all()
```

### Orphaned Derivations
If you create "HPHT_MH_001-2" before "HPHT_MH_001" exists:
1. `base_experiment_id` is set to "HPHT_MH_001"
2. `parent_experiment_fk` is NULL (orphaned)
3. When "HPHT_MH_001" is later created, the relationship is automatically established

## Benefits

1. **Automatic**: No manual effort required - lineage is established automatically
2. **Flexible**: Handles cases where derivations are created before base experiments
3. **Consistent**: All new and existing experiments follow the same lineage structure
4. **Traceable**: Easy to track treatment chains and experiment families
5. **Queryable**: Simple to find all derivations of a base experiment or navigate to parent

## Testing

After deployment, verify the system is working:

1. Create a base experiment (e.g., "TEST_BASE_001")
2. Create a derivation (e.g., "TEST_BASE_001-2")
3. Query the database to verify:
   - Derivation has `base_experiment_id = "TEST_BASE_001"`
   - Derivation has `parent_experiment_fk` linking to the base experiment
4. Check that the parent-child relationships work in both directions

## Notes

- The first note on a derivation experiment should describe the treatment/reason for the derivation
- Lineage system supports single-level derivations only (e.g., "-2", "-3" all derive from base)
- Multi-level chains (e.g., "-2-3") are not supported in the current implementation
- The system is fully backward compatible - existing experiments without derivations are unaffected

